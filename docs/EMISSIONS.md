# Per-query inference energy ledger

Riprap surfaces the energy and token cost of every inference call it
makes during a briefing. The numbers are **measured**, not data-sheet
estimates: off the L4 GPU via NVML when a remote inference proxy is
reachable, or off Apple Silicon via `powermetrics` on a Mac Mini /
local-dev deployment.

```
5 Stones · 21 fired · 11 evidence cards · 14.0s wall-clock · ✓ 1.4 Wh / 6.9K tok inference
```

The chip on the Findings status row reports total energy (Wh) plus
total tokens. The leading icon discloses how the number was derived:

| Icon | Meaning |
|---|---|
| `✓` | All recorded calls came back with a real NVML reading from the L4 GPU |
| `◐` | Some calls measured, others fell back to the data-sheet estimate |
| `~` | All calls used the data-sheet estimate (proxy unreachable, NVML disabled, or local-only run) |

Hover the chip for the full breakdown — call count, hardware, prompt
vs completion split, and the method.

---

## What's measured vs. what's estimated

| Field | Source |
|---|---|
| `duration_s` | Real wallclock on the client side (`time.monotonic` around each call) |
| `prompt_tokens`, `completion_tokens` | Reported by the model server (LiteLLM `usage` block) for non-stream LLM calls |
| `completion_tokens` (streaming) | Estimated as `len(response_text) / 4` when the backend doesn't surface a final usage block (Ollama path) |
| `power_w` | **Measured** — `nvmlDeviceGetPowerUsage` on the L4 inference Space, sampled every 100 ms, mean of samples bracketing each call |
| `wh`, `joules` | `power_w × duration_s` (when `measured: true`) or `data-sheet_W × duration_s` (when `measured: false`) |

Each call record on the ledger carries a `measured: bool` flag plus
the exact `power_w` value used so a reviewer can audit any row.

---

## How the measurement works

A remote L4 GPU backend (e.g. the Modal deployment, companion repo
`msradam/riprap-triton`) runs a FastAPI proxy in front of vLLM and the
ML specialist service. The proxy initialises NVML at startup and runs
a background sampler that reads `nvmlDeviceGetPowerUsage` every
100 ms into a 60-second ring buffer.

```
riprap_proxy.py::_power_sampler   (in msradam/riprap-triton)
  ├── NVML init at startup, single L4 device handle
  ├── 100 ms ring buffer (600 samples = 60 s of history)
  └── degrades to no-op if NVML init fails
```

When the proxy forwards a POST to vLLM or riprap-models, it stamps
the upstream call window `(t0, t1)` and computes the mean power
across the samples that fall inside that window. The result lands
on the response as headers:

```
X-GPU-Power-W      mean draw in watts
X-GPU-Energy-J     energy in joules over the window
X-GPU-Duration-S   forwarded-call duration in seconds
X-GPU-Device       "NVIDIA L4"
```

`app/inference.py::_post()` reads those headers off the proxy
response and forwards them into `emissions.Tracker.record_ml`. The
tracker stamps `measured=True` and uses the exact joule value.

For the LLM client path (`app/llm.py::chat()`) we route through
LiteLLM, which doesn't surface response headers. So instead the
client brackets the call with two GETs to `/v1/power`:

```python
p0 = _sample_gpu_power_w()                # ~50 ms, returns 1 s avg
t0 = time.monotonic()
resp = _router.completion(...)            # the actual LLM call
duration_s = time.monotonic() - t0
p1 = _sample_gpu_power_w()                # ~50 ms, returns 1 s avg
avg = (p0 + p1) / 2
```

`avg` is the average power during the call; `avg × duration_s`
gives joules. The tracker records `power_w_real=avg`,
`joules_real=avg×duration_s`, and `measured=True`.

### Apple Silicon (Mac Mini / local dev)

There's no NVML equivalent on macOS, and the tool that reads real
package power — `powermetrics` — needs root, so the app process
can't shell out to it per call. Instead an operator starts it once,
continuously, as its own root process:

```bash
scripts/mac_powermetrics_start.sh   # sudo powermetrics -i 200 \
                                     #   --samplers cpu_power,gpu_power,ane_power \
                                     #   -o /tmp/riprap-powermetrics.log
export RIPRAP_POWERMETRICS_LOG=/tmp/riprap-powermetrics.log
```

`app/power_mac.py` tails that log from an unprivileged background
thread, parsing each sample's `Combined Power (CPU + GPU + ANE)`
line, and exposes `read_instant_w()` — the latest reading, or `None`
if the log has gone stale (sampler died — treated as "no
measurement," never a frozen number). Both `app/llm.py` (LLM calls)
and `app/inference.py` (ML specialist calls) bracket their call the
same before/after way the L4 path does, via the shared
`power_mac.avg_w(p0, p1)` helper, and fall back to the `apple_m`
data-sheet estimate only when the sampler isn't running.

Verified end-to-end on a Mac Mini (M-series, 2026-07-11): a full
briefing — planner + reconciler LLM calls plus every specialist ML
call — came back `measured: true` on 4/4 calls, 3–7 W range,
11.58 mWh total for the query.

---

## Hardware profiles (`app/emissions.HARDWARE`)

The fallback path uses a sustained-power figure from the hardware
data sheet when no real measurement is available:

| Key | Label | Sustained W | Source |
|---|---|---|---|
| `nvidia_l4` | NVIDIA L4 | 60 | L4 data sheet (72 W TGP, Ada Lovelace) |
| `amd_mi300x` | AMD MI300X | 600 | MI300X data sheet (750 W TDP); used when `RIPRAP_HARDWARE_LABEL=AMD MI300X` |
| `nvidia_t4` | NVIDIA T4 | 50 | T4 data sheet (70 W max) |
| `apple_m` | Apple M-series | 20 | ml.energy / community measurements — used only when `RIPRAP_POWERMETRICS_LOG` isn't set or has gone stale; see the Apple Silicon section above for the real-measurement path |
| `cpu_server` | x86 CPU | 30 | Typical sustained server-core load |

The fallback only fires when neither a real GPU proxy nor a fresh
`powermetrics` sample is available (unreachable proxy, NVML init
failed, sampler not running, or the call streamed — we currently
don't measure streamed LLM calls precisely; they bracket-sample as
best-effort).

---

## End-to-end shape

```
Riprap app (FastAPI + SvelteKit) — any deployment target
   │
   │  Tracker installed per-query in web/main.py:
   │  install(Tracker())
   │
   ├── planner       — app/llm.py::chat
   │                   ├─ GET /v1/power  (bracket-start)
   │                   ├─ POST /v1/chat/completions
   │                   └─ GET /v1/power  (bracket-end)
   │
   ├── FSM specialists — app/inference.py::_post
   │                     POST /v1/{prithvi-pluvial, terramind, ...}
   │                     ← X-GPU-Power-W, X-GPU-Energy-J headers
   │
   └── reconciler    — app/llm.py::chat (Mellea-validated)
                       same bracket pattern as planner
                  │
                  ▼
       Tracker.summarize() → emissions block on /api/agent/stream final
                  │
                  ▼
       SvelteKit RunHealthStrip — chip rendered with measured-icon
```

---

## Verifying

`scripts/probe_addresses.py` runs an end-to-end address query
against a running deployment (local, Docker, Modal, or Mac Mini) and
asserts all five Stones fire, no specialist returns a dep-regression
string, and the final `emissions` block carries non-zero tokens with
the hardware key you expect for that deployment.

```bash
PYTHONPATH=. uv run python scripts/probe_addresses.py --base http://localhost:7860
```

The first call after a cold start (Modal container boot, or a
freshly-restarted local server warming Ollama + RAG) pays a
one-time compile/load penalty; warm queries land far lower — see
`docs/BENCHMARKS.md` for measured numbers per deployment.

---

## Why this matters

Inference cost is usually invisible. AI tools that publish a
"green" or "low-energy" claim mostly cite a vendor data sheet or a
research mean. Riprap reports the actual joules drawn off the
device under the load of a single user query — auditable down to
the row.

The raw ledger is shipped on the SSE `final` event under
`emissions.calls`, so any consumer (dashboard, billing model,
reproducibility check) can reuse the data without round-tripping
back through Riprap.
