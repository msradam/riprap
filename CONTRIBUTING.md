# Contributing

Riprap is an open-source civic-tech framework that began as the
AMD × lablab.ai Developer Hackathon submission and now ships under
Apache 2.0. NYC is the reference deployment; six cities run on the
same code (NYC, Chicago, Seattle, San Francisco, Boston, Albany). The
architecture is hazard-, city-, and platform-agnostic — the easiest
contribution is to add your jurisdiction.

PRs welcome. Three high-leverage paths in:

- **Port your city** — fork the closest existing `deployments/<city>/`
  and replace the data sources. Most US cities are a manifest directory
  away because they expose a Socrata or CKAN open-data portal. See
  [`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md) for the
  step-by-step using Boston as the worked example.
- **Bring your own data** — drop a YAML manifest into `${CWD}/.riprap/`
  or point `RIPRAP_EXTRA_MANIFESTS` at it. No fork needed. See
  [`docs/byod.md`](docs/byod.md).
- **Write a new adapter** — if your data source isn't covered by
  `socrata_records`, `ckan_records`, `csv_points`, `baked_vector`,
  `rest_json`, or `python_call`, drop a new adapter into
  `riprap/core/pebbles/adapters/` and register it in `__init__.py`.

## Quickstart

Requires [Git LFS](https://git-lfs.com) — `data/` (flood layers, ~150 MB
of GeoJSON/raster) and `corpus/` (policy PDFs) are LFS-tracked. Without
it, `git clone` silently checks out small text pointer files instead of
the real data, and the app crashes on startup trying to parse one as
GeoJSON (`DataSourceError: not recognized as being in a supported file
format`). Install it once, then clone normally:

```bash
brew install git-lfs   # or apt/your package manager
git lfs install        # one-time, per machine

git clone https://github.com/msradam/riprap
cd riprap
uv venv && uv pip install -r requirements.txt
```

If you already cloned before installing Git LFS, `git lfs pull` inside
the repo fetches the real files retroactively.

The PDF route (`/api/print`) uses WeasyPrint, which needs pango / cairo
system libraries:

```bash
# macOS
brew install pango

# Debian / Ubuntu
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
```

If you skip this, the rest of Riprap still works — `/api/print` will
return 503 with a clear message until the deps are installed.

SvelteKit (the build is committed; only rebuild when sources
change under `web/sveltekit/src`):

```bash
cd web/sveltekit && npm ci && npm run build && cd ../..
```

Run the dev server pointing at a deployed Modal backend (real Granite +
EO models, real NVML energy readings — see `docs/DEPLOY.md`):

```bash
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=<your Modal deployment's riprap-proxy URL> \
RIPRAP_LLM_API_KEY=<token> \
RIPRAP_ML_BACKEND=remote \
RIPRAP_ML_BASE_URL=<same URL> \
RIPRAP_ML_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

Or run pure-local with Ollama. On Apple Silicon, add
`scripts/mac_powermetrics_start.sh` + `RIPRAP_POWERMETRICS_LOG` for
real measured power instead of the data-sheet estimate — see
`docs/DEPLOY.md`'s Mac Mini section:

```bash
ollama pull granite4.1:3b granite4.1:8b
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860
```

## Verifying changes

Three probe scripts exercise the framework at three different scales —
run all three before opening a PR that touches anything load-bearing.

```bash
# 1. Six-deployment sweep against a locally running server (no LLM,
#    real upstream APIs). Each deployment's compliance must report
#    13/13 PASS.
.venv/bin/python scripts/probe_cities_smoke.py http://127.0.0.1:7860

# 2. Unit + integration tests (skip live-server tests by default).
.venv/bin/python -m pytest tests/ -q \
    --ignore=tests/integration --ignore=tests/test_integration.py

# 3. NYC end-to-end suite with full LLM specialist stack, against a
#    locally running server.
.venv/bin/python scripts/probe_addresses.py --base http://127.0.0.1:7860
```

Point `--base` at a Modal deployment or Mac Mini instead of localhost
to verify against one of those. See
[`docs/VERIFICATION.md`](docs/VERIFICATION.md) for the current
snapshot of what's verified deterministically.

## Structure

```
app/                       Python package — the FSM and its specialists
├── fsm.py                 Burr FSM, one @action per probe
├── llm.py                 LiteLLM Router shim (Ollama / vLLM)
├── inference.py           HTTP client for the riprap-models service
├── emissions.py           Per-query energy + token tracker
├── power_mac.py           Real Apple Silicon power via `powermetrics`
├── stones/                Stone taxonomy (NAME / TAGLINE / collect())
├── flood_layers/          Cornerstone probes (sandy, dep, microtopo, …)
├── context/               Keystone + Touchstone register + EO probes
├── live/                  Lodestone forecast probes
├── intents/               single_address / neighborhood / compare / live_now
├── reconcile.py           Capstone — Granite-native document reconcile
└── mellea_validator.py    Mellea four-check rejection sampling

web/                       FastAPI + SvelteKit
├── main.py                FastAPI app, SSE streaming, layer endpoints
├── sveltekit/             Primary UI (adapter-static; build committed)
└── static/                Legacy custom-element pages (still mounted)

inference/                 Ollama-backed inference sidecar (Dockerfile)
services/riprap-models/    The EO/forecast specialist HTTP service
                            (self-hostable via docker-compose --profile with-models)

scripts/
├── probe_addresses.py     Canonical 5-address end-to-end suite
├── probe_cities_smoke.py  Cross-city smoke probe (all six deployments)
├── probe_narrative_contracts.py  Card/narrative contract checks
├── mac_powermetrics_start.sh     Start the Mac Mini power sampler
└── …                       Register builders, raster bakers, etc.

experiments/               Reproduction recipes for the three NYC fine-tunes
docs/                      Architecture, methodology, deploy, emissions, runbooks
tests/                     pytest suite (envelope + compare-shape tests)
```

## Style

- Python 3.12; `uv` for package management.
- LLM calls go through `app/llm.py` — never import `litellm` /
  `ollama` directly from a specialist. The `chat()` shim wraps both
  backends and the energy ledger reads off it.
- Remote ML calls go through `app/inference.py::_post`. Specialists
  may try local fallback only when `inference.remote_enabled()` is
  False; once a remote call has been attempted, return a clean
  `{ok: False, skipped: ...}` on failure rather than crashing
  through to local code paths that may not be installed.
- Every specialist emits one trace record per call with `step` /
  `ok` / `elapsed_s` / `result` / `err` so the SSE stream and the
  emissions tracker can reason about it.

## Reporting issues

GitHub issues at <https://github.com/msradam/riprap/issues>.
Templates:

- **[Port your city](https://github.com/msradam/riprap/issues/new?template=port_to_new_city.yml)** —
  scope an add-a-deployment effort.
- **[Bug report](https://github.com/msradam/riprap/issues/new?template=bug_report.yml)**.
- **[Feature request](https://github.com/msradam/riprap/issues/new?template=feature_request.yml)**.
