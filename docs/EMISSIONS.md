# Per-call inference energy ledger

`app/emissions.py` records every LLM call a briefing makes: model,
endpoint, prompt and completion tokens, duration, and an energy figure
with a label that says how it was obtained. No-LLM briefings make no LLM
calls, so their ledger is empty.

## Energy status

| Status | When | How the figure is obtained |
|---|---|---|
| `measured` | Local endpoint on Apple Silicon, with the `energy` extra installed (`uv sync --extra energy`) | zeus-apple-silicon reads the SoC energy counters (CPU, GPU, DRAM, ANE) for the call's window. No sudo. It is whole-chip energy, so it includes other processes. |
| `estimated` | Local endpoint with `RIPRAP_ENERGY_WATTS` set | Declared watts times the call's duration. |
| `unknown` | Everything else | No figure. |

A local endpoint is one whose host is `localhost`, `127.0.0.1`, `::1`,
`0.0.0.0` or `ollama`. Hosted endpoints are always `unknown`: they report
no energy, and power times duration on shared hardware would be invented.
Riprap reports no per-query figure for them.

zeus-apple-silicon 1.1.0 reads 0 mJ of CPU energy on an Apple M5. A call
longer than half a second with a zero CPU reading is treated as a broken
counter, and the call falls back to `estimated` (if `RIPRAP_ENERGY_WATTS`
is set) or `unknown`.

## Where it appears

Every result carries an `emissions` block (`riprap/core/burr/app.py`,
`energy_summary`), also sent on the SSE `final` event:

| Field | Meaning |
|---|---|
| `n_calls`, `n_measured` | LLM calls in the briefing, and how many were measured |
| `energy_status` | One status if all calls share it, otherwise `mixed`; `none` when there were no calls |
| `total_wh` | Sum of the calls' Wh, only when every call has a measured or estimated figure; otherwise `null` |
| `tokens` | Prompt, completion and total tokens |
| `calls` | The per-call records, each with `energy_status`, `wh` and an `energy_note` |

In-process CPU models (TTM, Granite Embedding, Flair NER, the GLiClass
entailment check on guarded answers and the GLiClass 311 filter) are not
in the ledger. On the retired GPU stack the TTM, embedding and NER models
were about 0.3% of a briefing's inference energy; the GLiClass models were
not measured.

## Measured on this laptop (2026-09-30)

`scripts/measure_energy.py` reads the SMC's `PowerTelemetryData` accumulator through
`ioreg` (no sudo): whole-machine power sampled once a second and published in one-minute
batches. It records an idle window, then runs a list of briefings against a local server,
aligning both windows to the batches, and takes the idle draw off for the net figure.

| | Value |
|---|---|
| Machine | Apple M5 laptop, 32 GB, on mains power, otherwise idle |
| Model | Granite 4.1 8B (Q4_K_M) over Ollama, two LLM calls per briefing, about 2,600 tokens |
| Idle | 8.4 W over 300 s |
| 16 question briefings | 24.0 W mean over 240 s, 150 s of it running, 9.4 s per briefing |
| Per briefing, gross | 0.10 Wh (whole machine, including idle) |
| Per briefing, net of idle | 0.065 Wh, about 25 W above idle while running |
| A no-LLM briefing | no model call; the run itself is below the accumulator's resolution |

The figure is whole-machine, not per process, and the one-minute batches make a single
call unmeasurable in the app. So per-call figures in the ledger stay `estimated` on this
machine: `RIPRAP_ENERGY_WATTS=25` declares the measured draw above idle, and the ledger
labels each call's Wh as declared watts times duration. The gallery entries were regenerated
that way and say so.

## Historical numbers

[`history/BENCHMARKS.md`](history/BENCHMARKS.md) reports 1.3 to 1.6 Wh per briefing. Those
figures came from the retired Modal/L4 stack on 2026-05-09 (Granite 4.1
8B on vLLM, NVML sampling through a proxy) and are historical. The NVML
proxy headers, the `/v1/power` bracket sampling and the
`sudo powermetrics` log reader that earlier versions of this page
described are removed.

## Verifying

Run a briefing against a local Ollama endpoint with the `energy` extra
installed, or with `RIPRAP_ENERGY_WATTS` set, and read the `emissions`
block:

```bash
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 \
RIPRAP_LLM_MODEL=hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M \
  uv run python -c "from riprap.core.burr.app import run; import json; \
print(json.dumps(run('189 Atlantic Avenue, Brooklyn, NY')['emissions'], indent=2, default=str))"
```
