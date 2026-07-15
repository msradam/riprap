# Deployment

Three ways to run Riprap end to end, in order of how much you want to
manage yourself. All three run the same app and the same manifest-driven
deployments (`deployments/{nyc,chicago,seattle,sf,boston,albany}`) — the
only thing that changes is where the LLM and specialist ML calls execute.

## 1. Modal (scale-to-zero cloud GPU)

The lowest-effort way to get a real GPU-backed deployment without
paying for idle time. Two components, both scale-to-zero:

**Specialists** — `msradam/riprap-inference`'s `modal_app.py` deploys
the same LitServe backend that also runs natively on a Mac Mini (see
§2). One codebase, either target:

```bash
# in msradam/riprap-inference
modal secret create riprap-inference-secret \
    RIPRAP_INFERENCE_API_KEY=$(openssl rand -hex 24) --env riprap
modal deploy modal_app.py --env riprap
```

**LLM** — `msradam/riprap-inference`'s `modal_vllm_app.py` deploys
Granite 4.1 via vLLM as its own scale-to-zero Modal app, separate from
the specialists (different GPU profile — an 8B LLM at 8192 context
wants more VRAM than the five specialists — and a different image,
since vLLM pins its own torch):

```bash
# in msradam/riprap-inference
modal secret create riprap-vllm-secret \
    RIPRAP_VLLM_API_KEY=$(openssl rand -hex 24) --env riprap
modal deploy modal_vllm_app.py --env riprap
```

Or point `RIPRAP_LLM_BASE_URL` at any other OpenAI-compatible vLLM
endpoint you already run.

Point this repo's app at whichever you deployed:

```bash
export RIPRAP_LLM_PRIMARY=vllm
export RIPRAP_LLM_BASE_URL=<your riprap-vllm Modal URL>/v1
export RIPRAP_LLM_API_KEY=<the RIPRAP_VLLM_API_KEY value above>
export RIPRAP_ML_BACKEND=remote
export RIPRAP_ML_BASE_URL=<your riprap-inference Modal URL>
export RIPRAP_ML_API_KEY=<the RIPRAP_INFERENCE_API_KEY value above>
```

Cold start is roughly a minute or two on a warm Modal Volume (cached
weights); every container scales to zero — and to $0 — when idle.

## 2. Mac Mini / Apple Silicon (fully local, no cloud)

The whole stack — FastAPI + SvelteKit app, Ollama-served Granite 4.1,
and the ML specialists — runs on one Apple Silicon box, with **real
measured power draw**, not a data-sheet estimate. This is the
reference "clone it and it just works, no GPU rental" deployment.

```bash
# 1. Ollama, for the planner + reconciler LLM
brew services start ollama
ollama pull granite4.1:3b
ollama pull granite4.1:8b       # skip this pull on a <=16 GB box — see
                                 # "Memory-constrained boxes" below instead

# 2. ML specialists — a separate process so the app/model split stays
#    clean even on a single box. Same codebase as the Modal path in
#    §1, just run natively for real MPS access.
git clone https://github.com/msradam/riprap-inference
cd riprap-inference && python server.py &

# 3. The app itself
cd riprap
uv venv && uv pip install -r requirements.txt
export RIPRAP_ML_BACKEND=remote
export RIPRAP_ML_BASE_URL=http://localhost:8000
uv run uvicorn web.main:app --host 0.0.0.0 --port 7860

# 4. Real power measurement (optional but recommended — this is the
#    whole point of running on Apple Silicon instead of a GPU rental)
./scripts/mac_powermetrics_start.sh &     # needs sudo, one time
export RIPRAP_POWERMETRICS_LOG=/tmp/riprap-powermetrics.log
```

Every LLM call and every specialist ML call now reports `measured:
true` in the `emissions` block of each briefing, with power read off
`powermetrics`' `Combined Power (CPU + GPU + ANE)` sample — see
`docs/EMISSIONS.md` for how the measurement pipeline works and a real
end-to-end number from this exact setup. `RIPRAP_HARDWARE_LABEL` and
`RIPRAP_LLM_BASE_URL` should stay unset for this path (an empty or
`localhost` base URL is what tells `emissions.hardware_for()` this is
Apple Silicon, not a remote GPU — see `.env.example`).

### Memory-constrained boxes (e.g. a 16 GB Mac Mini)

`granite4.1:3b` + `granite4.1:8b` loaded simultaneously (the default —
the planner stays on 3b for low TTFB even when the reconciler runs 8b)
is ~8 GB of resident Ollama model weight alone, on top of the RAG
embedder, geopandas/rasterio, and the app process. On a 16 GB box this
is tight enough that a burst of back-to-back queries can push the
kernel into swap-thrash and, in the worst case, a watchdog panic —
observed in practice on a 16 GB Mac Mini running back-to-back live
queries.

`app/llm.py` already has the knob for this: `RIPRAP_OLLAMA_3B_TAG` /
`RIPRAP_OLLAMA_8B_TAG` remap the two logical model slots ("granite-3b",
used by the planner and by `live_now`'s reconciler; "granite-8b", used
by the single_address / neighborhood / development_check reconciler) to
whatever physical Ollama tag you actually want — the same knob already
used to collapse both slots onto one pulled tag on disk-constrained
deployments. Point them at a real 1B + 3B pair instead of 3B + 8B:

```bash
ollama pull ibm/granite4:1b-q4_K_M
# (granite4.1:3b already pulled above)
export RIPRAP_OLLAMA_3B_TAG=ibm/granite4:1b-q4_K_M   # routing (planner + live_now)
export RIPRAP_OLLAMA_8B_TAG=granite4.1:3b            # summarizer (the other 3 intents)
```

~3.5 GB resident instead of ~8 GB. The 1B model shares the same Granite
chat template (`document <id>`-role grounding included), so citation
grounding still works — verified live: `live_now` and `neighborhood`
both still hit 12-13/13 on the briefing-standards compliance predicates
after the swap, with `neighborhood`'s one non-13/13 case being a
pre-existing, unrelated gap (`projection_has_horizon`, TCFD 3.2) it has
regardless of model tier.

## 3. Docker / docker-compose (self-host, any Linux box)

`Dockerfile.app` builds a lightweight self-host image (FastAPI +
SvelteKit) that does **not** bundle Ollama or GPU weights — it
dispatches LLM and ML calls over HTTP to whatever backend you point it
at (Modal, your own vLLM, or a self-hosted `riprap-inference`).

```bash
cp .env.example .env    # point RIPRAP_LLM_BASE_URL / RIPRAP_ML_BASE_URL
                         # at your backend of choice
docker compose up
```

`docker-compose.yml` has two optional profiles: `local-llm` (bundles
an Ollama container so the whole stack is self-contained without an
external endpoint — the right shape for an NGO deployment without a
GPU) and `with-models` (adds a GPU specialist container for operators
with their own CUDA/ROCm box).

## Which one should I pick?

- **Just want to see it work, no ops:** Modal.
- **Want a fully local, no-cloud, real-power-numbers story** (the one
  this project uses to prove its own energy claims): Mac Mini.
- **Already run your own infra / want a container to drop into
  existing orchestration:** docker-compose.

Every deployment shares the same env-var contract (`RIPRAP_LLM_*`,
`RIPRAP_ML_*`, `RIPRAP_DEPLOYMENT`) — see `.env.example` for the full
list and `README.md`'s Quickstart for the fastest path to a first
briefing.
