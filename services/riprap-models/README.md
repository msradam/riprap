# Riprap Models: self-hosted GPU inference microservice

GPU inference microservice for operators self-hosting on their own
AMD ROCm GPU box (see `docker-compose.yml`'s `with-models` profile,
and `docs/DEPLOY.md`). Exposes one HTTP endpoint per model class
consumed by the Riprap FastAPI app's probes, so all GPU-accelerable
forward passes (Prithvi-NYC-Pluvial, TerraMind LULC + Buildings,
Granite TTM r2, Granite Embedding 278M, GLiNER) run on the GPU
regardless of which surface hosts the FastAPI process.

Built and verified against an AMD Instinct MI300X during the project's
original hackathon phase; the Dockerfile targets AMD's public ROCm
base image generically, so it should build against any ROCm-capable
AMD GPU. For a non-AMD or fully local setup, see `docs/DEPLOY.md`'s
Modal and Mac Mini paths instead — this service is the AMD-GPU
self-host option specifically.

## Service contract

| Method | Path | Purpose |
|---|---|---|
| GET   | `/healthz`            | reachability probe + which models are warm |
| POST  | `/v1/prithvi-pluvial` | Prithvi-NYC-Pluvial v2 segmentation |
| POST  | `/v1/terramind`       | TerraMind LULC / Buildings / Synthesis (adapter-dispatched) |
| POST  | `/v1/ttm-forecast`    | Granite TTM r2 (zero-shot Battery, fine-tune Battery, weekly 311, FloodNet recurrence) |
| POST  | `/v1/granite-embed`   | Granite Embedding 278M batch encode |
| POST  | `/v1/gliner-extract`  | GLiNER typed-entity extraction |

Auth: bearer token on every `/v1/*` route via `RIPRAP_MODELS_API_KEY`.
Same shape as vLLM. `/healthz` is open so liveness probes don't need
auth.

## Deploy: docker-compose (recommended)

From the repo root, on a box with Docker + an AMD GPU (`/dev/kfd`,
`/dev/dri` device files):

```bash
docker compose --profile with-models up -d
```

This builds `services/riprap-models/Dockerfile` and starts the
container on host port 7861 (see `docker-compose.yml`). Set
`RIPRAP_ML_API_KEY` in your `.env` before starting — the container
reads it as `RIPRAP_MODELS_API_KEY`.

## Deploy: manual docker build

Equivalent without compose, useful if you're wiring this into your
own orchestration:

```bash
docker build -t riprap-models:latest -f services/riprap-models/Dockerfile .
docker run -d --name riprap-models \
  --device=/dev/kfd --device=/dev/dri \
  -p 7860:7860 \
  -e RIPRAP_MODELS_API_KEY=<bearer-token> \
  riprap-models:latest
```

First build takes ~10-20 min (ROCm + PyTorch base image + weights on
first request); rebuilds with the same base layers are fast.

Then point the main app at it — set `RIPRAP_ML_BACKEND=remote` and
`RIPRAP_ML_BASE_URL` to wherever this container is reachable, and run
`scripts/probe_addresses.py` to verify end-to-end.

## Redeploying

The container is stateless aside from the HF cache — weights
(Prithvi v2 ~1.3 GB, TerraMind adapters ~600 MB, Granite Embedding
~600 MB, GLiNER ~400 MB, Granite TTM r2 ~6 MB) re-download on first
request after a fresh container start unless the HF cache directory
is volume-mounted. `docker compose --profile with-models up -d --build`
rebuilds and restarts in place; generate a fresh `RIPRAP_ML_API_KEY`
if you're rotating it.

## Local app config

Set in your `.env` (see `.env.example`):

```
RIPRAP_ML_BACKEND   = remote
RIPRAP_ML_BASE_URL  = http://localhost:7861
RIPRAP_ML_API_KEY   = <bearer>
```

`app/inference.py` posts to those endpoints; specialists fall back
to local in-process model loads when the service is unreachable.
