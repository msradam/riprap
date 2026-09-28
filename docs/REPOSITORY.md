# Code map

The pipeline at a glance, the source-of-truth paths and the repository tree. Moved from the README in refactor 7; the long form is [ARCHITECTURE.md](ARCHITECTURE.md).

## Architecture

```
query ──► plan (LLM planner: intent, question, pebbles needed; regex heuristic in no-LLM mode)
             │
             ▼
   geocode_target (point intents) │ resolve_area (NTA or community district)
             │
             ▼
   select_deployment (bounding box → deployments/<city>/)
             │
             ▼
   select_sources (planner's pebbles + a floor; all of them for a bare address)
             │
             ▼
   stones: one parallel MapActions fan-out over the selected pebbles
   (Cornerstone, Keystone, Touchstone, Lodestone)
             │
             ▼
   assemble_legacy_state ──► policy_corpus ──► reconcile
             │
             ▼
   evidence from manifest templates ──► no-LLM briefing, or JSON claims checked in code for citations and numbers
             │
             ▼
   cited briefing + disclosure checks + energy ledger ──► JSON, SSE, MCP
```

`riprap/core/burr/app.py` is the only orchestrator. It handles every
intent (`single_address`, `neighborhood`, `development_check`, `live_now`,
`compare`, `not_implemented`, `out_of_scope`); `out_of_scope` returns a
fixed refusal, and `compare` is two `single_address` runs
merged. Point intents run pebbles with `spatial.scope: point`,
`neighborhood` and `development_check` run the polygon pebbles, and
`live_now` runs only the live point pebbles. Burr tracking is off unless
`RIPRAP_BURR_TRACKING=1`.

Every public source goes through one HTTP client (`riprap/core/http.py`:
httpx with hishel caching and stamina retries). NYC Geosearch is tried
first for NYC addresses and Nominatim (rate limited to 1 request per
second) for everything else.

Source-of-truth pointers:

| Path | What it is |
|---|---|
| `riprap/core/pebbles/` | Manifest schema, registry, adapters and shapers |
| `riprap/core/burr/` | The Burr app, evidence rendering (`evidence.py`) and claim verification (`synthesis.py`) |
| `riprap/core/http.py` | Shared cached HTTP client with retries |
| `riprap/core/compliance/` | Disclosure checks: substring tests for required caveat phrases. They do not measure quality. |
| `deployments/<city>/` | Manifests, `stones.yaml`, data and corpus for one deployment |
| `app/` | Pebble implementations (`context/`, `flood_layers/`, `live/`, `assets/`, `areas/`), planner, geocoder, energy ledger |
| `web/main.py` | FastAPI: `/api/agent`, `/api/agent/stream` (SSE), `/api/district/{code}`, `/api/nyc311/flood_requests`, layer endpoints |
| `riprap/mcp/server.py` | MCP server (stdio or `--http`) |
| `web/sveltekit/` | UI and static gallery (adapter-static, build committed) |

Long form in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Grounding in
[`docs/GROUNDING.md`](GROUNDING.md). Methodology and civil-engineering
framing in [`docs/METHODOLOGY.md`](METHODOLOGY.md). Literature review
in [`docs/history/RESEARCH.md`](history/RESEARCH.md). Deployment in
[`docs/DEPLOY.md`](DEPLOY.md).


## Repository structure

```
riprap/core/               The framework
├── pebbles/               Pebble schema, registry, adapters, shapers
├── burr/                  Burr app, evidence, claim verification
├── compliance/            Disclosure checks (caveat-phrase substring tests)
└── http.py                Shared cached HTTP client

riprap/mcp/                MCP server

deployments/               One directory per deployment
├── nyc/                   Reference: manifests, stones.yaml, data, corpus
├── federal/               Pebbles every US deployment shares
└── chicago, seattle, sf, boston, albany, heat, air

app/                       Pebble implementations, planner, geocoder,
                           energy ledger, PDF export, register builder

web/                       FastAPI + SvelteKit
├── main.py                FastAPI app, SSE stream, layer endpoints
└── sveltekit/             UI and static gallery (build committed)

deploy/                    Dockerfile and the optional Modal host (modal_app.py)
scripts/                   Gallery, RAG index, EO batch, probes, register builders
experiments/               Reproduction recipes for the NYC fine-tunes
docs/                      See docs/INDEX.md
tests/                     pytest + vitest
```

[`CONTRIBUTING.md`](../.github/CONTRIBUTING.md) covers dev setup and house style.
[`CHANGELOG.md`](../CHANGELOG.md) tracks changes since the v0.5.0 hackathon
submission.

