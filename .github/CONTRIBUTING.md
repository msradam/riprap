# Contributing

Riprap is an open-source civic-tech framework that began as the
AMD × lablab.ai Developer Hackathon submission and now ships under
Apache 2.0. NYC is the reference deployment; four cities run on the
same code (NYC, Chicago, Seattle, Albany; all but NYC are experimental).
The easiest contribution is to add your jurisdiction.

PRs welcome. Three high-leverage paths in:

- **Port your city.** Fork the closest existing `deployments/<city>/`
  and replace the data sources. A city with a Socrata open-data portal
  needs only manifests. See
  [`docs/PORT-YOUR-CITY.md`](../docs/PORT-YOUR-CITY.md) for the
  step-by-step using Chicago as the worked example.
- **Bring your own data.** Drop a YAML manifest into `${CWD}/.riprap/`
  or point `RIPRAP_EXTRA_MANIFESTS` at it. No fork needed. See
  [`docs/byod.md`](../docs/byod.md).
- **Write a new adapter.** If your data source isn't covered by
  `socrata_records`, `csv_points`, `baked_vector`, `rest_json`, or
  `python_call`, drop a new adapter into
  `riprap/core/pebbles/adapters/` and register it in `__init__.py`.

## Quickstart

Requires [Git LFS](https://git-lfs.com): `data/` (flood layers, GeoJSON
and rasters) is LFS-tracked. Without
it, `git clone` silently checks out small text pointer files instead of
the real data, and the app crashes on startup trying to parse one as
GeoJSON (`DataSourceError: not recognized as being in a supported file
format`). Install it once, then clone normally:

```bash
brew install git-lfs   # or apt/your package manager
git lfs install        # one-time, per machine

git clone https://github.com/msradam/riprap
cd riprap
uv sync                # everything the app needs; no torch
```

If you already cloned before installing Git LFS, `git lfs pull` inside
the repo fetches the real files retroactively.

The one extra is `energy` (zeus-apple-silicon, measured energy on Apple
Silicon): `uv sync --extra energy`.

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
local Ollama (see [`docs/DEPLOY.md`](../docs/DEPLOY.md) and
[`docs/GROUNDING.md`](../docs/GROUNDING.md)):

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

# 2. Four-city sweep against a locally running server (no LLM, real
#    upstream APIs). Every city line must PASS.
uv run python scripts/probe_cities_smoke.py http://127.0.0.1:7860

# 3. If you touched claim verification or prompts: LLM-mode grounding
#    probe over the gallery addresses (needs RIPRAP_LLM_* set).
uv run python scripts/probe_grounding.py

# 4. If you edited a manifest's provenance: request every source link once
#    and list the status codes (needs the network; CI does not run it).
#    Exits 1 on any 4xx, 5xx or unreachable link. Wiley answers 403 to
#    scripted requests for the NPCC4 paper, which opens in a browser.
uv run python scripts/check_links.py             # all deployments
uv run python scripts/check_links.py nyc chicago # some of them
uv run python scripts/check_links.py --local     # relative links in README, docs/ and .github/; no network

# 5. If you touched place resolution: no-LLM accuracy on
#    tests/place_resolution_cases.yaml (needs the network for geocoding).
uv run python scripts/place_eval.py run

# 6. If you touched the frontend: the browser journeys (with axe checks)
#    against the running server. It serves the prerendered gallery pages
#    from the committed build, so the gallery specs need no second server;
#    RIPRAP_STATIC_URL points them at another build of those pages.
cd web/sveltekit && pnpm build && pnpm test:e2e
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
riprap/cli/register.py     riprap-register: flood flags per asset, as CSV

app/
├── context/, flood_layers/, assets/, registers/, areas/
│                          Functions that python_call manifests point at
├── planner.py             LLM planner (LLM mode)
├── geocode.py             NYC Geosearch, then Nominatim
├── emissions.py           Per-call energy and token ledger
├── models_info.py         Which LLM endpoint took part in a briefing
└── register_builder.py    Bakes data/registers/<class>.json

deployments/<city>/        Manifests and stones.yaml
data/                      NYC flood layers, rasters and baked registers
deploy/                    Dockerfile and the optional Modal host (modal_app.py)
web/main.py                FastAPI: JSON, SSE, district, 311, registers, layers
web/sveltekit/             UI and static gallery (build committed)

scripts/
├── build_gallery.py       Precompute the static gallery
├── probe_cities_smoke.py  Cross-city smoke probe (the four city deployments)
├── probe_grounding.py     LLM-mode claim verification probe
└── …                      Register builders, raster bakers, etc.

docs/                      See docs/INDEX.md
tests/                     pytest suite; tests/load/ has k6 load scripts
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
