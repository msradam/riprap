# Contributing

Riprap is an open-source civic-tech framework that began as the
AMD × lablab.ai Developer Hackathon submission and now ships under
Apache 2.0. NYC is the reference deployment; six cities run on the
same code (NYC, Chicago, Seattle, San Francisco, Boston, Albany; all but
NYC are experimental). The architecture is hazard-, city- and
platform-agnostic, so the easiest contribution is to add your
jurisdiction.

PRs welcome. Three high-leverage paths in:

- **Port your city.** Fork the closest existing `deployments/<city>/`
  and replace the data sources. Most US cities are a manifest directory
  away because they expose a Socrata or CKAN open-data portal. See
  [`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md) for the
  step-by-step using Boston as the worked example.
- **Bring your own data.** Drop a YAML manifest into `${CWD}/.riprap/`
  or point `RIPRAP_EXTRA_MANIFESTS` at it. No fork needed. See
  [`docs/byod.md`](docs/byod.md).
- **Write a new adapter.** If your data source isn't covered by
  `socrata_records`, `ckan_records`, `csv_points`, `baked_vector`,
  `rest_json`, or `python_call`, drop a new adapter into
  `riprap/core/pebbles/adapters/` and register it in `__init__.py`.

## Quickstart

Requires [Git LFS](https://git-lfs.com): `data/` (flood layers, about
150 MB of GeoJSON/raster) and `corpus/` (policy PDFs) are LFS-tracked. Without
it, `git clone` silently checks out small text pointer files instead of
the real data, and the app crashes on startup trying to parse one as
GeoJSON (`DataSourceError: not recognized as being in a supported file
format`). Install it once, then clone normally:

```bash
brew install git-lfs   # or apt/your package manager
git lfs install        # one-time, per machine

git clone https://github.com/msradam/riprap
cd riprap
uv sync                # light core: no torch, about 290 MB
uv sync --extra ml     # add TTM, Granite Embedding and Flair NER (CPU)
```

If you already cloned before installing Git LFS, `git lfs pull` inside
the repo fetches the real files retroactively.

Other extras: `eo` (terratorch and STAC libraries for the batch
earth-observation script, never per request), `pdf` (WeasyPrint for
`/api/print`) and `energy` (zeus-apple-silicon, measured energy on Apple
Silicon). WeasyPrint needs pango and cairo system libraries:

```bash
# macOS
brew install pango

# Debian / Ubuntu
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
```

Without them the rest of Riprap still works; `/api/print` returns 503
with a clear message.

SvelteKit (the build is committed; only rebuild when sources change
under `web/sveltekit/src`):

```bash
cd web/sveltekit && pnpm install --frozen-lockfile && pnpm run build && cd ../..
```

Run the server. With no LLM endpoint every briefing is the no-LLM
evidence briefing:

```bash
uv run uvicorn web.main:app --host 127.0.0.1 --port 7860
```

To work on LLM mode, point it at any OpenAI-compatible endpoint, such as
local Ollama (see [`docs/DEPLOY.md`](docs/DEPLOY.md) and
[`docs/GROUNDING.md`](docs/GROUNDING.md)):

```bash
ollama pull granite4:micro
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 RIPRAP_LLM_MODEL=granite4:micro \
  uv run uvicorn web.main:app --host 127.0.0.1 --port 7860
```

## Verifying changes

```bash
# 1. Lint and tests (CI runs the same; live-server tests are skipped
#    unless a server is up).
uvx ruff check riprap/ web/main.py app/geocode.py app/planner.py app/areas/ tests/
uv run pytest -q

# 2. Six-deployment sweep against a locally running server (no LLM, real
#    upstream APIs). Every deployment must pass the 13 disclosure checks.
uv run python scripts/probe_cities_smoke.py http://127.0.0.1:7860

# 3. NYC end-to-end addresses against a locally running server.
uv run python scripts/probe_addresses.py --base http://127.0.0.1:7860

# 4. If you touched claim verification or prompts: LLM-mode grounding
#    probe over the gallery addresses (needs RIPRAP_LLM_* set).
uv run python scripts/probe_grounding.py

# 5. If you edited a manifest's provenance: request every source link once
#    and list the status codes (needs the network; CI does not run it).
#    Exits 1 on any 4xx, 5xx or unreachable link. Wiley answers 403 to
#    scripted requests for the NPCC4 paper, which opens in a browser.
uv run python scripts/check_links.py            # all deployments
uv run python scripts/check_links.py nyc boston # some of them

# 6. If you touched place resolution: no-LLM accuracy on
#    tests/place_resolution_cases.yaml (needs the network for geocoding).
uv run python scripts/place_eval.py run
```

## Structure

```
riprap/core/
├── burr/                  The one Burr app: intake, stones fan-out,
│                          evidence.py, synthesis.py (claim verification)
├── pebbles/               Manifest schema, registry, adapters, shapers
├── compliance/            Disclosure checks (caveat-phrase substring tests)
├── http.py                Shared httpx client: hishel cache, stamina retries
└── llm.py                 OpenAI-compatible client, tier selection

riprap/mcp/server.py       MCP server (stdio or --http)

app/
├── context/, flood_layers/, live/, assets/, areas/
│                          Functions that python_call manifests point at
├── planner.py             LLM planner (LLM mode)
├── geocode.py             NYC Geosearch, then Nominatim
├── emissions.py           Per-call energy and token ledger
├── rag.py                 Policy-corpus retrieval (query embedding)
└── score.py               Register tier rubric (offline builders only)

deployments/<city>/        Manifests, stones.yaml, data
web/main.py                FastAPI: JSON, SSE, district, 311, layers, PDF
web/sveltekit/             UI and static gallery (build committed)

scripts/
├── build_gallery.py       Precompute the static gallery (no LLM)
├── build_rag_index.py     Build data/rag_index.npz offline
├── run_eo_batch.py        Batch Prithvi surface-water run (eo extra)
├── probe_addresses.py     NYC end-to-end addresses
├── probe_cities_smoke.py  Cross-city smoke probe (all six deployments)
├── probe_grounding.py     LLM-mode claim verification probe
└── …                      Register builders, raster bakers, etc.

experiments/               Reproduction recipes for the NYC fine-tunes
docs/                      See docs/INDEX.md
tests/                     pytest suite
```

## Style

- Python 3.12+; `uv` for Python packages, `pnpm` for JavaScript.
- Fetch public data through `riprap/core/http.py`, not a new client, so
  every source gets the same cache and retries.
- Citations, source URLs and vintages come from the manifest
  `provenance` block and nowhere else. Mark uncertain outputs
  `maturity: experimental`.
- LLM calls go through `riprap/core/llm.py` (the `openai` client against
  `RIPRAP_LLM_BASE_URL`), so the energy ledger sees them.
- Every pebble and pipeline step emits one trace record with `step`,
  `ok`, `elapsed_s`, `result` and `err`, so the SSE stream can report it.

## Reporting issues

GitHub issues at <https://github.com/msradam/riprap/issues>.
Templates:

- [Port your city](https://github.com/msradam/riprap/issues/new?template=port_to_new_city.yml),
  to scope an add-a-deployment effort.
- [Bug report](https://github.com/msradam/riprap/issues/new?template=bug_report.yml).
- [Feature request](https://github.com/msradam/riprap/issues/new?template=feature_request.yml).
