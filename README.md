<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/msradam/riprap/actions/workflows/check.yml/badge.svg)](https://github.com/msradam/riprap/actions/workflows/check.yml)
[![Deployments](https://img.shields.io/badge/deployments-NYC%20·%20Chicago%20·%20Seattle%20·%20SF%20·%20Boston%20·%20Albany-005EA2)](docs/multi-city.md)
[![Civic Hydrology](https://img.shields.io/badge/palette-civic%20hydrology-005EA2)](web/sveltekit/src/lib/tokens.css)
[![Apache-2.0 foundation models](https://img.shields.io/badge/models-Apache--2.0%20end--to--end-1A4480)](#nyc-specialised-foundation-models-apache-20)

## Citation-grounded climate-exposure briefings, city by city.

Riprap gathers public flood evidence for an address and cites every
sentence to its source. An optional LLM rewrites that evidence as claims;
code checks each claim's citations and numbers and drops the ones that
fail. See [`docs/GROUNDING.md`](docs/GROUNDING.md).

![Riprap flood-exposure briefing for DUMBO, Brooklyn](assets/screenshots/hero.png)

Run it locally with one command (see the Quickstart). The original
hackathon demo is frozen at its May 2026 build with inference disabled:
<https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>.

> **Now an open-source civic-tech framework.** NYC is the reference
> deployment. Five more deployments (Chicago, Seattle, San Francisco,
> Boston, Albany) share the same code and are experimental: they have only
> the federal pebbles plus a 311 feed and/or a water-level gauge, and the
> Chicago, SF and Boston 311 feeds are not flood-filtered (a reported "200"
> is the query limit). Adding your city is a directory of YAML, not a fork.
>
> - **[`docs/multi-city.md`](docs/multi-city.md)** — six cities, three
>   311-platform paths (Socrata, CKAN, SeeClickFix), one codebase.
> - **[`docs/byod.md`](docs/byod.md)** — drop your own data in via
>   `.riprap/` auto-discovery or the `RIPRAP_EXTRA_MANIFESTS` env var.
> - **[`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md)** — walkthrough
>   for adding a new city, using the Boston port as the worked example.
> - **[`docs/multi-hazard.md`](docs/multi-hazard.md)** — the same Five
>   Stones produce a heat-exposure or air-quality briefing from a
>   `deployments/heat/` or `deployments/air/` directory. Flood/NYC is
>   the production-grade deployment (23 pebbles); heat and air are
>   working scaffolds (3-4 pebbles) proving the architecture
>   generalizes past flood.

---

## The problem Riprap solves

Cities publish the hazard-exposure inputs an engineer needs. NYC alone has
decades of it: Sandy 2012 inundation, NYC DEP stormwater scenarios,
FloodNet sensors, NOAA tide gauges, USGS 3DEP LiDAR, 311 complaints, MTA,
NYCHA, schools, hospitals — and Chicago, Seattle, San Francisco, Boston,
and Albany each publish their own equivalents. The data is public. None of
it composes itself.

Every engineer doing a drainage review, every resilience office siting a
capital project, every climate-adaptation team prioritising blocks
reassembles the same evidence by hand, per address, from a dozen agencies. A
briefing that should be a tool call ends up as a half-day of manual joins.
Existing tools either return opaque vendor risk scores or skip the audit
trail a stamped engineering memo actually requires.

Riprap composes it. Type an address in any deployed city, get a
four-section, citation-grounded briefing in about two minutes, with every
claim pointing back to a `[doc_id]` in public-record data.

---

## What this is. What this isn't.

Riprap is a **reference dossier generator** for analysts who already
work with public-record climate data. It is **not** a stamped
engineering memo, a risk score, a real-estate disclosure, or a
substitute for a licensed professional.

**Use Riprap if you are:**

- A climate-adaptation or resilience consultant who currently opens
  six tabs (NFHL, NOAA SLR, NPCC4 PDF, 311 portal, FloodNet, NWS),
  screenshots them into a Word memo, and cites manually. Riprap
  collapses that into one URL with a citation trail you can hand to
  a client.
- A Phase I ESA preparer adding a **Business Environmental Risk
  addendum** under ASTM E1527-21. The disclosure checks look for the
  caveat phrases that scope expects.
- An investigative journalist or civic researcher who needs
  *defensible*, primary-source-linked numbers about flood-zone
  exposure, asset proximity, or 311 patterns.
- A resilience-office analyst (NYC MOCEJ, Chicago CDOT, etc.) who
  needs to turn agency data into something a deputy commissioner
  reads in five minutes.

**Don't use Riprap for:**

- **Drainage / hydraulic design.** Use HEC-RAS, SWMM, or a licensed
  civil engineer's full hydraulic model. Riprap is triage, not design.
- **Resident-facing flood guidance.** For NYC, defer to
  [FloodHelpNY](https://www.floodhelpny.org) (Center for NYC
  Neighborhoods, HUD CDBG-DR funded) and
  [FloodNet NYC](https://www.floodnet.nyc) for sensor data.
- **Mortgage / insurance underwriting.** Closed-model risk scores
  have regulatory acceptance Riprap doesn't claim and doesn't seek.
- **Personal property decisions or real-estate transactions.** The
  briefing format is engineering-shaped, not consumer-shaped. Using a
  Riprap citation as evidence in a transaction is outside the design
  scope of this tool and outside the support scope of its
  contributors.

**On FEMA determinations specifically:** when FEMA proposes a change to
a flood hazard determination — a Base Flood Elevation, an SFHA
boundary, a floodway — federal regulation gives the affected community
a 90-day appeal window, and an appeal must rest solely on scientific or
technical evidence, not policy or economic argument (44 CFR Part 67).
Riprap does not issue, contest, or substitute for a determination made
through that process. If a decision turns on the official flood zone
at a parcel, use FEMA's [Flood Map Service Center](https://msc.fema.gov)
or the community's Flood Zone Determination process, not a Riprap
citation.

---

## Quickstart

You need [uv](https://docs.astral.sh/uv/) and [Git LFS](https://git-lfs.com)
(`data/` and `corpus/` are LFS files; without it the clone has pointer files
and the app cannot load its layers). No GPU and no API keys.

```bash
git clone https://github.com/msradam/riprap && cd riprap
git lfs install && git lfs pull
uv sync --extra ml
uv run uvicorn web.main:app --port 7860
```

Open <http://localhost:7860> and type an NYC address. You get the no-LLM
evidence briefing: one cited sentence per data source, grouped by Stone.
`uv sync` without `--extra ml` is the light core (no torch, about 290 MB);
the in-process forecasts and policy retrieval then skip themselves.

The same briefing from the command line:

```bash
uv run python -c "from riprap.core.burr.app import run; print(run('189 Atlantic Avenue, Brooklyn, NY')['paragraph'])"
```

### LLM synthesis (optional)

Point Riprap at any OpenAI-compatible endpoint. With local
[Ollama](https://ollama.com):

```bash
ollama pull granite4:micro
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 RIPRAP_LLM_MODEL=granite4:micro \
  uv run uvicorn web.main:app --port 7860
```

The model rewrites the evidence as JSON claims. Code checks every claim's
citations and numbers against the documents it cites, retries once, and
drops what still fails; dropped claims are listed, never shown as part of
the briefing ([`docs/GROUNDING.md`](docs/GROUNDING.md)). Other deployment
shapes (Docker, a GPU endpoint on Modal) are in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

### MCP server

```bash
uv run python -m riprap.mcp.server            # stdio
uv run python -m riprap.mcp.server --http     # streamable HTTP on :8765
```

Tools: `list_sources`, `get_evidence`, `get_citation`, `nyc311_flood_requests`
and `get_briefing`. All but `get_briefing` work without an LLM.

### Static gallery

`scripts/build_gallery.py` precomputes briefings for ten NYC addresses into
`web/sveltekit/src/lib/gallery/`; the SvelteKit build prerenders them at
`/gallery` with no backend, so the gallery can be served from GitHub Pages.

### Other cities and your own data

Deployments are directories of YAML manifests (`deployments/<city>/`). A
query routes to the deployment whose bounding box contains it. Layer your own
data on top with [`docs/byod.md`](docs/byod.md) and add a city with
[`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md).

---

## How Riprap works: the Five Stones

Behind every briefing, a couple dozen atomic data probes (**pebbles**)
fan out across public datasets, sensors and forecasts. Each pebble is one
YAML manifest plus a small adapter; the framework loads them from a
deployment directory and groups them into five roles, the **Five Stones**:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | NYC pebbles |
|---|---|---|
| **Cornerstone** | What the ground remembers | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, FEMA NFHL zone, 2021 Ida USGS high-water marks, satellite-detected surface water after Ida (experimental), USGS 3DEP DEM with HAND and TWI |
| **Keystone** | What is exposed | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals |
| **Touchstone** | Current state of the city | FloodNet depth sensors, NYC 311 flood complaints, NWS hourly observations, NOAA tide-gauge water levels, USGS stream gauges |
| **Lodestone** | What is coming | NWS flood alerts, NPCC4 sea-level projections, 311 weekly forecast (experimental), FloodNet recurrence forecast (experimental), Battery surge forecast (experimental) |
| **Capstone** | The briefing | The evidence sentences as written (no-LLM mode), or JSON claims from any OpenAI-compatible model with citations and numbers checked in code |

One Burr application runs every intent. All pebbles for the intent fan out
in one parallel `MapActions` group; the Capstone then turns their evidence
into one cited briefing. Adding a data source is a new manifest in the
deployment directory, not a code change.

---

## The Five Stones beyond NYC

The Five Stones are a city-agnostic template. The five roles stay the
same; only the pebbles plugged into each Stone change.

| Stone | Role | What you replace |
|---|---|---|
| **Cornerstone** | Hazard memory | Local historical inundation extents, regional DEM, regulatory floodplain maps |
| **Keystone** | Asset registers | The transit, housing, education and healthcare layers your jurisdiction publishes |
| **Touchstone** | Live observation | Whatever live sensors and complaint streams the city or region exposes (FloodNet has analogues in Houston, Boston, Miami) |
| **Lodestone** | Forecasts | Local NWS forecast office output, regional surge or hydrologic models |
| **Capstone** | Citation-grounded synthesis | Same |

What transfers unchanged: one Burr graph that fans pebble manifests out in
parallel, evidence rendered from manifest templates, verified structured
claims when an LLM is configured, and every sentence cited to its source.
To port Riprap to a new city you write a deployment directory of manifests
against local data. See [`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md).

---

## Models

Every model is optional. Without the `ml` extra the model pebbles skip
themselves and the briefing is built from the data pebbles alone. The
table lists what the app runs today and what each evaluation supports.

| Model | Where it runs | Maturity | What the evidence supports |
|---|---|---|---|
| [`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge) | `ttm_battery_surge` pebble, in process on CPU | Experimental | Test MAE 0.1091 m on held-out Battery gauge data, 41% better than persistence and 25% better than zero-shot TTM. It forecasts the surge residual only, has no wind or pressure input, and its briefing sentence points readers to NOAA ETSS or the Stevens Flood Advisory System for storm decisions. |
| Granite TimeSeries TTM r2 (base) | `ttm_311_forecast` and `floodnet_forecast` pebbles, in process on CPU | Experimental | Indicative forecasts of 311 complaint volume and FloodNet event recurrence. No held-out evaluation is published. |
| Granite Embedding 278M | `policy_corpus` pebble, query embedding only (the corpus index is built offline by `scripts/build_rag_index.py`) | Experimental | Retrieves passages from five NYC agency PDFs. Retrieval quality is not scored. |
| Flair NER (`flair/ner-english-ontonotes-fast`) | `policy_corpus` pebble, in process on CPU | Experimental | Coarse entity tags (agency, date, amount, place) on the retrieved passages. |
| Prithvi-EO 2.0 | Offline only: the baked Ida layer behind `prithvi_water`, and `scripts/run_eo_batch.py` | Experimental | Satellite-detected surface water after Ida. It mostly shows marsh, shoreline and park water, gives no inside or outside verdict for an address, and says nothing about street or basement flooding. |
| [`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial) | Default checkpoint for `scripts/run_eo_batch.py`; not used by the app at runtime | Experimental | Test IoU 0.598, but the labels are the base model's own Ida polygons (self-distillation) and the random split shares parent scenes, so this measures agreement with pseudo-labels, not flood detection. |
| [`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters) | Not used by the app | Research artifact | LoRA family on TerraMind 1.0. Reported mIoU: LULC 0.5866, TiM 0.6023, Buildings 0.5511. |
| Any OpenAI-compatible LLM | Optional, external endpoint | Production path, with claims checked in code | On ten gallery addresses, `granite4:micro` kept 122 claims and dropped 0; `llama3.1:8b` kept 191 and dropped 0 (`tests/probe_grounding_results*.json`). Only citations and numbers are checked ([`docs/GROUNDING.md`](docs/GROUNDING.md)). |

The three `msradam/*` fine-tunes were trained on AMD Instinct MI300X via
AMD Developer Cloud and are published under Apache 2.0. Reproduction
recipes live under `experiments/`.

---

## Architecture

```
query ──► plan (LLM planner, or regex heuristic in no-LLM mode)
             │
             ▼
   geocode_target (point intents) │ resolve_area (NTA or community district)
             │
             ▼
   select_deployment (bounding box → deployments/<city>/)
             │
             ▼
   stones: one parallel MapActions fan-out over every pebble for the intent
   (Cornerstone, Keystone, Touchstone, Lodestone)
             │
             ▼
   assemble_legacy_state ──► policy_corpus ──► reconcile
             │
             ▼
   evidence from manifest templates ──► no-LLM briefing, or verified JSON claims
             │
             ▼
   cited briefing + disclosure checks + energy ledger ──► JSON, SSE, MCP
```

`riprap/core/burr/app.py` is the only orchestrator. It handles every
intent (`single_address`, `neighborhood`, `development_check`, `live_now`,
`compare`, `not_implemented`); `compare` is two `single_address` runs
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

Long form in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Grounding in
[`docs/GROUNDING.md`](docs/GROUNDING.md). Methodology and civil-engineering
framing in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md). Literature review
in [`docs/RESEARCH.md`](docs/RESEARCH.md). Deployment in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

---

## Inference energy

`app/emissions.py` records every LLM call in a briefing with its tokens,
duration and an energy status:

| Status | When |
|---|---|
| measured | Local endpoint on Apple Silicon with the `energy` extra (zeus-apple-silicon). Whole-chip energy during the call, so it includes other processes. |
| estimated | Local endpoint with `RIPRAP_ENERGY_WATTS` set: declared watts times duration. |
| unknown | Everything else. Hosted endpoints are always unknown and no per-query figure is reported for them. |

zeus-apple-silicon 1.1.0 reads 0 mJ of CPU energy on an Apple M5; those
readings are rejected and the call is marked unknown. The ledger is the
`emissions` block of every result. In-process CPU models are not in it.
The numbers in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) come from the
retired GPU stack and are historical. Details in
[`docs/EMISSIONS.md`](docs/EMISSIONS.md).

---

## Data sources

Riprap contacts only public-record federal, state and city sources at
runtime. No commercial APIs, no proprietary scores. Source URLs, licences,
`date_modified` and `retrieved_at` for each come from the pebble's manifest
`provenance` block; `list_sources` on the MCP server prints them.

| Source | Hosting agency | Used for |
|---|---|---|
| Hurricane Sandy 2012 inundation zone | NYC OTI / NOAA Office for Coastal Management | Hazard memory |
| NYC DEP Stormwater Flood Maps | NYC Department of Environmental Protection | Modeled scenarios |
| FEMA National Flood Hazard Layer | FEMA | Regulatory flood zone |
| Hurricane Ida 2021 USGS high-water marks | USGS Short-Term Network | Empirical points |
| FloodNet ultrasonic sensor network | NYU CUSP / FloodNet | Flood-event log |
| NYC 311 flood complaints | NYC Open Data | Complaint history |
| NOAA tide gauge, The Battery | NOAA CO-OPS | Tide and surge level |
| USGS stream gauges | USGS Water Data (OGC API) | Live stage |
| NWS observations and alerts | National Weather Service | Precipitation, active warnings |
| MTA subway entrances | MTA / NYC Open Data | Transit assets |
| NYCHA developments | NYC Housing Authority (`phvi-damg`) | Public housing |
| NYC DOE schools | NYC Department of Education | Schools |
| NYS DOH hospitals | New York State Department of Health (`vn5v-hh5r`) | Hospitals |
| USGS 3DEP 1 m DEM | USGS National Map | HAND and TWI |
| NYC DOB permits | NYC Department of Buildings | `development_check` intent |
| NPCC4 sea-level projections and agency PDFs | NYC Panel on Climate Change, NYC agencies | Policy context |
| Sentinel-2 MSI imagery | ESA / Copernicus | Offline Prithvi layers |

---

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

modal/                     Optional Modal host for the app (CPU)
scripts/                   Gallery, RAG index, EO batch, probes, register builders
experiments/               Reproduction recipes for the NYC fine-tunes
docs/                      See docs/INDEX.md
tests/                     pytest + vitest
```

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers dev setup and house style.
[`CHANGELOG.md`](CHANGELOG.md) tracks changes since the v0.5.0 hackathon
submission.

---

## Citation

If you reference Riprap in academic or professional work:

```bibtex
@software{riprap_2026,
  author       = {Rahman, Adam Munawar},
  title        = {Riprap: Composable, Citation-Grounded Civic Climate-Exposure Briefings for Any US Place},
  year         = {2026},
  url          = {https://github.com/msradam/riprap},
  version      = {v0.6.0},
  note         = {Originated as the AMD x lablab.ai Developer Hackathon submission; evolved into a multi-city, multi-hazard open-source framework}
}
```

---

## License

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

The three NYC fine-tunes above are also Apache 2.0; upstream models keep
their own permissive licences (see each model card). Public-record data
sources keep their own access terms, recorded in each manifest's
`provenance.license`.

---

## Acknowledgments

- **AMD Developer Cloud**, MI300X compute for the three NYC fine-tunes.
- **AMD × lablab.ai Developer Hackathon**, the venue.
- **IBM Research**, Granite 4.1, Granite Embedding 278M, Granite TTM r2,
  and the rest of the open-source Granite ecosystem.
- **NASA / IBM Prithvi-EO 2.0** and **IBM / ESA TerraMind 1.0**, the
  geospatial foundation models behind the NYC fine-tunes.
- **NYU CUSP / FloodNet**, the public sensor network whose data Riprap
  reads live.
- **Andrew Hicks**, civil-engineering review of the methodology.
- **The Riprap dam mark**, ["Dam" by Chintuza](https://thenounproject.com/icon/dam-4516918/)
  via the Noun Project, licensed CC-BY 3.0. The original SVG embedded
  the attribution as on-canvas text; Riprap's `assets/logo*.svg` strips
  the embedded text and carries the credit here in body copy instead,
  per the Creative Commons attribution requirement.
