# Deployment

Three ways to run Riprap end to end, in order of how much you want to
manage yourself. All three run the same app and the same manifest-driven
deployments (`deployments/{nyc,chicago,seattle,sf,boston,albany}`) — the
only thing that changes is where the LLM and specialist ML calls execute.

## 1. Modal (scale-to-zero cloud GPU)

The lowest-effort way to get a real GPU-backed deployment without
paying for idle time. `msradam/riprap-triton`'s `modal/riprap_modal.py`
packages all five Triton-era specialists (Prithvi, TerraMind, TTM,
Granite Embedding, GLiNER) plus a vLLM-served Granite 4.1 8B in one
container, and `modal/riprap_frontend.py` in this repo serves the app
itself.

```bash
# in msradam/riprap-triton
modal deploy modal/riprap_modal.py
```

Cold start is a couple of minutes on a warm Modal Volume (cached
weights); the container scales to zero — and to $0 — when idle. Point
this repo's app at the deployed URL:

```bash
export RIPRAP_LLM_PRIMARY=vllm
export RIPRAP_LLM_BASE_URL=<your Modal deployment's riprap-proxy URL>
export RIPRAP_ML_BASE_URL=<same URL>
export RIPRAP_LLM_API_KEY=<the proxy bearer token — `modal secret list`>
```

or deploy the frontend itself to Modal with `modal/riprap_frontend.py`.
See `msradam/riprap-triton/modal/README.md` for the full walkthrough.

## 2. Mac Mini / Apple Silicon (fully local, no cloud)

The whole stack — FastAPI + SvelteKit app, Ollama-served Granite 4.1,
and the ML specialists — runs on one Apple Silicon box, with **real
measured power draw**, not a data-sheet estimate. This is the
reference "clone it and it just works, no GPU rental" deployment.

```bash
# 1. Ollama, for the planner + reconciler LLM
brew services start ollama
ollama pull granite4.1:3b
ollama pull granite4.1:8b       # or a smaller/quantized tag for a
                                 # lower-memory box — see README

# 2. ML specialists — a separate process so the app/model split stays
#    clean even on a single box; see msradam/riprap-inference
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
