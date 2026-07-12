<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/msradam/riprap/actions/workflows/check.yml/badge.svg)](https://github.com/msradam/riprap/actions/workflows/check.yml)
[![Deployments](https://img.shields.io/badge/deployments-NYC%20·%20Chicago%20·%20Seattle%20·%20SF%20·%20Boston%20·%20Albany-005EA2)](docs/multi-city.md)
[![Civic Hydrology](https://img.shields.io/badge/palette-civic%20hydrology-005EA2)](web/sveltekit/src/lib/tokens.css)
[![Apache-2.0 foundation models](https://img.shields.io/badge/models-Apache--2.0%20end--to--end-1A4480)](#nyc-specialised-foundation-models-apache-20)

## Flood risk analysis for any NYC address.

A multi-agent AI system that reads satellites, watches sensors, forecasts
surges, and refuses to ship a sentence it cannot ground in a citation.

![Riprap flood-exposure briefing for DUMBO, Brooklyn](assets/screenshots/hero.png)

Original hackathon demo (frozen at the AMD build, data probes only —
inferencing disabled): <https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>.
For a deployment with live inference, see the Quickstart below (Modal,
a Mac Mini, or docker-compose).

> **Now an open-source civic-tech framework.** NYC is the reference
> deployment. Six live deployments share the same code (NYC, Chicago,
> Seattle, San Francisco, Boston, Albany) — adding your city is a directory of
> YAML, not a fork.
>
> - **[`docs/multi-city.md`](docs/multi-city.md)** — six cities, three
>   311-platform paths (Socrata, CKAN, SeeClickFix), one codebase.
> - **[`docs/byod.md`](docs/byod.md)** — drop your own data in via
>   `.riprap/` auto-discovery or the `RIPRAP_EXTRA_MANIFESTS` env var.
> - **[`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md)** — walkthrough
>   for adding a new city, using the Boston port as the worked example.

---

## The problem Riprap solves

NYC has spent decades publishing the flood-exposure inputs an engineer needs:
Sandy 2012 inundation, NYC DEP stormwater scenarios, FloodNet sensors, NOAA
tide gauges, USGS 3DEP LiDAR, 311 complaints, MTA, NYCHA, schools, hospitals.
The data is public. None of it composes itself.

Every engineer doing a drainage review, every resilience office siting a
capital project, every climate-adaptation team prioritising blocks
reassembles the same evidence by hand, per address, from a dozen agencies. A
briefing that should be a tool call ends up as a half-day of manual joins.
Existing tools either return opaque vendor risk scores or skip the audit
trail a stamped engineering memo actually requires.

Riprap composes it. Type any NYC address, get a four-section,
citation-grounded briefing in about two minutes, with every claim pointing
back to a `[doc_id]` in public-record data.

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
  addendum** under ASTM E1527-21. The compliance-audit predicates
  are well-aimed at that scope.
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

Four ways to use Riprap, in increasing order of self-host:

### 1. Try the original hackathon demo

<https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space>

This is the original AMD hackathon build, frozen at its May 2026 commit.
It runs the full SvelteKit shell and every deterministic data probe
(Sandy, DEP, NOAA, FloodNet, 311, NPCC4, and the rest). The GPU half is
offline there, so the Granite reconciler returns a graceful "inference
offline" shape in place of the LLM-written prose. Methodology, evidence
cards, and citations all still render.

For the full LLM and specialist path, run the inference stack yourself.
Three options — see [`docs/DEPLOY.md`](docs/DEPLOY.md) for the full
walkthrough of each:

- **Modal (scale-to-zero, recommended).** `modal deploy` the ML
  specialists from [`msradam/riprap-inference`](https://github.com/msradam/riprap-inference)
  — the same LitServe backend the Mac Mini path below runs natively —
  plus a vLLM endpoint of your choice (the companion
  [`msradam/riprap-triton`](https://github.com/msradam/riprap-triton)
  repo bundles one with its own specialist stack, if you'd rather run
  one Modal app than two). Both cost nothing while idle and wake on the
  first request; a warm query returns a full cited briefing in about a
  minute. See `docs/DEPLOY.md` for the full setup.
- **Mac Mini / Apple Silicon, fully local.** No cloud, no GPU rental —
  Ollama-served Granite 4.1 plus every ML specialist run on one box,
  with real measured power draw via `powermetrics` instead of a
  data-sheet estimate. This is the reference "clone it and it just
  works" deployment.
- **Local Ollama** (`granite4.1:8b` pulled), for CPU-only development
  with no GPU at all.

The three NYC fine-tunes were trained on an AMD Instinct MI300X via the
AMD Developer Cloud; `RIPRAP_HARDWARE_LABEL="AMD MI300X"` swaps the
energy ledger back to MI300X figures if you deploy to your own AMD GPU
box (`docker-compose --profile with-models`). See
[`docs/DEPLOY.md`](docs/DEPLOY.md).

### 2. Run locally with Docker

```bash
git clone https://github.com/msradam/riprap
cd riprap
cp .env.example .env
# edit .env to point RIPRAP_LLM_BASE_URL / RIPRAP_ML_BASE_URL at
# a Modal deployment or your own self-hosted instance
docker compose up
```

Visit `http://localhost:7860`.

The GPU inference half lives in companion repos: ML specialists in
[`msradam/riprap-inference`](https://github.com/msradam/riprap-inference)
(deployable to Modal or run natively on a Mac Mini — same codebase
either way), vLLM in [`msradam/riprap-triton`](https://github.com/msradam/riprap-triton)
(or any OpenAI-compatible endpoint). Point this app at them via
`RIPRAP_LLM_BASE_URL` / `RIPRAP_ML_BASE_URL`. See
[`docs/DEPLOY.md`](docs/DEPLOY.md) for every deployment shape.

### 3. Develop

```bash
# Python 3.12 venv via uv
uv venv && uv pip install -r requirements.txt

# SvelteKit frontend (committed pre-built; only rebuild if sources change)
cd web/sveltekit && npm ci && npm run build && cd ../..

# Local server (Ollama primary)
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# Local server pointed at a remote GPU backend (Modal, or your own
# vLLM box), vLLM primary with Ollama fallback
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=<your backend's OpenAI-compatible URL> \
RIPRAP_LLM_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860

# End-to-end address suite (5 NYC addresses, intent-aware checks)
.venv/bin/python scripts/probe_addresses.py
```

### 4. Run with your city's data

Riprap ships with six working deployments (`deployments/{nyc,chicago,
seattle,sf,boston,albany}/`). Each is a directory of YAML pebble manifests plus
a `stones.yaml`. Switch deployments with one env var:

```bash
# Brief 233 S Wacker Dr, Chicago — no code changes, real upstream data
RIPRAP_DEPLOYMENT=deployments/chicago RIPRAP_RECONCILER_TIER=no_llm \
.venv/bin/python -c "import riprap.core.burr.app as a; \
  print(a.run('233 S Wacker Dr, Chicago, IL')['paragraph'])"
```

Layer your own data on top of any deployment via [`docs/byod.md`](docs/byod.md):

```bash
# .riprap/ in your CWD is auto-discovered
mkdir -p .riprap && cp examples/byod/fdny_firehouses.{yaml,csv} .riprap/

# Same effect via env var (a colon-separated list of dirs or yaml files)
RIPRAP_EXTRA_MANIFESTS=examples/byod \
RIPRAP_DEPLOYMENT=deployments/nyc \
.venv/bin/uvicorn web.main:app --port 7860
```

Add your own city: see [`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md).

---

## How Riprap works: the Five Stones

Behind every briefing, a couple dozen atomic data probes (**pebbles**)
fan out across NYC datasets, satellite imagery, sensors, and forecasts.
Each pebble is one YAML manifest plus a small adapter; the framework
loads them from a deployment directory and groups them into five legible
roles, the **Five Stones**:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | What fires |
|---|---|---|
| **Cornerstone** | The Hazard Reader. What the ground remembers. | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, 2021 Ida USGS high-water marks, baked Prithvi-EO Ida-attributable polygons, USGS 3DEP DEM + HAND/TWI |
| **Keystone** | The Asset Register. What's exposed. | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals, **TerraMind-NYC Buildings LoRA** |
| **Touchstone** | The Live Observer. Current state of the city. | FloodNet ultrasonic depth sensors, NYC 311 flood complaints, NWS hourly METAR, NOAA tide-gauge water levels, **Prithvi-EO 2.0 NYC-Pluvial v2**, **TerraMind-NYC LULC LoRA** |
| **Lodestone** | The Projector. What's coming. | NWS public flood alerts, Granite TTM r2 surge nowcast (zero-shot, 6-min cadence, 9.6 h horizon), per-address 311 weekly forecast, FloodNet sensor recurrence forecast, **Granite-TTM-r2-Battery-Surge fine-tune** (96 h hourly horizon) |
| **Capstone** | The Synthesiser. Citation-grounded briefing. | Granite 4.1 + Mellea rejection sampling |

Each Stone fans its pebbles out in parallel as a Burr `MapActions` group;
the Capstone then reconciles their documents into one cited briefing.
Adding a data source is a new manifest in the deployment directory, not a
code change.

---

## The Five Stones beyond NYC

The Five Stones taxonomy is a city-agnostic template for any
flood-vulnerable region with the right data scaffolding. The five roles
generalise; only the probes plugged into each Stone change.

| Stone | Role | What you replace |
|---|---|---|
| **Cornerstone** | Hazard memory | Local historical inundation extents, regional DEM, regulatory floodplain maps |
| **Keystone** | Asset registers | The transit, housing, education, and healthcare polygons your jurisdiction publishes |
| **Touchstone** | Live observation | Whatever live sensors and complaint streams the city or region exposes (FloodNet has analogues in Houston, Boston, Miami) |
| **Lodestone** | Forecasts | Local NWS forecast office output, regional surge or hydrologic models, time-series fine-tunes for your tide gauge |
| **Capstone** | Citation-grounded synthesis | Same |

The architectural commitments transfer unchanged: a Burr FSM that fans
pebble manifests out per Stone, Granite-native `role="document"`
reconciliation, Mellea four-check grounding, SSE streaming to a SvelteKit
map UI, every claim cited to its source. To port Riprap to a new city you
write a deployment directory of manifests against local data and, for the
satellite and time-series layers, retrain the EO and TTM fine-tunes on
your jurisdiction's imagery and gauges. The agentic shell stays the same.
See [`docs/PORT-YOUR-CITY.md`](docs/PORT-YOUR-CITY.md).

---

## NYC-specialised foundation models (Apache 2.0)

Three NYC-specific fine-tunes built on AMD Instinct MI300X via AMD
Developer Cloud, published under permissive licence.

**[`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters).**
LoRA family on TerraMind 1.0 base. LULC mIoU 0.5866 (+6.13 pp over
full-FT baseline), TiM 0.6023, Buildings 0.5511. Trained in around 18
minutes on a single MI300X.

**[`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial).**
NYC pluvial-flood fine-tune of Prithvi-EO 2.0. Test flood IoU 0.5979 vs
0.10 on the Sen1Floods11 base, a 6× lift. Lovász-Softmax loss with
copy-paste augmentation.

**[`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge).**
NYC Battery storm-surge nowcast fine-tune of Granite TimeSeries TTM r2.
Test MAE 0.1091 m, 41% better than persistence and 25% better than
zero-shot.

All three are loaded at runtime by their respective FSM probes in
`app/context/` and `app/live/`. Reproduction recipes live under
`experiments/18..21/`.

---

## Architecture

```
NYC address ──► Granite 4.1 3B planner ──► Plan{intent, targets, specialists}
                                                  │
                                                  ▼
                  Five-Stone Burr FSM (manifest pebbles, MapActions fan-out)
                            ┌───────────┬───────────┬───────────┬──────────┐
                            ▼           ▼           ▼           ▼          ▼
                       Cornerstone  Keystone   Touchstone   Lodestone  (cont.)
                       (hazard)    (assets)    (live)       (forecast)
                            │           │           │           │
                            └───────────┴─────┬─────┴───────────┘
                                              ▼
                         build_documents() — Granite-native
                         role="document <doc_id>" messages
                                              ▼
                  Capstone: Granite 4.1 8B + Mellea rejection sampling
                  ──► 4-check grounding loop, surgical feedback rerolls
                                              ▼
                       Four-section briefing with [doc_id] citations
                                              ▼
                       SSE stream → SvelteKit UI (briefing, trace, map)
```

The runtime is the manifest-driven framework under `riprap/core/`. A
deployment is a directory of YAML pebble manifests plus a `stones.yaml`;
the registry loads them and the Burr app fans each Stone's pebbles out in
parallel. Adding a data source, or a whole new city, is configuration,
not code. The legacy `app/` modules remain for the register and
multi-intent paths the framework has not yet absorbed.

LLM inference is dispatched through `app/llm.py`, a LiteLLM Router shim
with two backends: **Ollama** (local dev, CPU) and **vLLM**
(OpenAI-compatible, on Modal or a cloud GPU). Same `chat()` signature in
both directions; vLLM is primary when configured, Ollama is the
auto-failover.

Specialist ML inference (Prithvi-EO, TerraMind, TTM, GLiNER, Granite
Embedding) goes over HTTP to a bearer-authenticated proxy, which stamps
real GPU/Apple-Silicon power readings onto every response (see the
energy section below). The specialist server is
[`msradam/riprap-inference`](https://github.com/msradam/riprap-inference)
(LitServe) — one codebase, deployable to Modal (scale-to-zero, $0 idle)
or run natively on a Mac Mini / Apple Silicon for MPS access. The vLLM
endpoint is a separate concern: any OpenAI-compatible deployment works,
including [`msradam/riprap-triton`](https://github.com/msradam/riprap-triton),
which bundles vLLM with its own Triton-based specialist stack in one
container if you'd rather run a single Modal app. See `docs/DEPLOY.md`
for every combination.

Source-of-truth pointers:

- `riprap/core/pebbles/`: the pebble framework — manifest schema,
  registry, and the adapters / shapers that normalize each source.
- `riprap/core/burr/`: the Burr application — intake, per-Stone
  `MapActions` fan-out, and the reconciler tiers (`llm` / `no_llm`).
- `deployments/<city>/`: the manifests, `stones.yaml`, data, and corpus
  that define one deployment.
- `riprap/core/compliance/`: briefing-quality predicates audited per run.
- `web/main.py`: FastAPI + SSE. The stream emits
  `plan / step / token / mellea_attempt / final` events plus the
  `stone_start / stone_done` envelope around each Stone group.
- `riprap/mcp/server.py`: MCP server (`python -m riprap.mcp.server`) —
  lets an agent call Riprap as a tool: `get_briefing`, `list_sources`,
  `get_citation`.
- `web/sveltekit/`: primary UI (SvelteKit + adapter-static).
- `app/llm.py`: LiteLLM Router shim (Ollama / vLLM).
- `app/emissions.py`: per-query Tracker + hardware profiles. Records
  every LLM and ML inference call with `measured: bool`.

For the long-form architecture document, see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Methodology and
civil-engineering framing in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).
Lit review in [`docs/RESEARCH.md`](docs/RESEARCH.md). Deploy topology in
[`docs/DEPLOY.md`](docs/DEPLOY.md). Live measurements (wall-clock, real
NVML energy, Mellea grounding pass-rate) in
[`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

---

## Inference energy — measured, not estimated

Riprap reports the energy and token cost of every inference call it
makes during a briefing. The status row on the Findings region
displays a single chip:

```
✓ 1.4 Wh / 6.9K tok inference
```

The `✓` icon means every recorded call came back with a real reading
off the inference GPU via `nvmlDeviceGetPowerUsage`. The proxy
runs a 100 ms-cadence NVML sampler and stamps
`X-GPU-Power-W` / `X-GPU-Energy-J` on every response; the LLM client
brackets each completion with two GETs to `/v1/power` because LiteLLM
hides response headers. When the proxy is unreachable, the chip
shows `~` or `◐` and the row falls back to a data-sheet sustained-
power estimate.

Per-call records carry `prompt_tokens`, `completion_tokens`,
`duration_s`, `power_w`, `joules`, and a `measured: bool` flag. The
full ledger is shipped on the SSE `final` event under
`emissions.calls`, so any consumer (dashboard, billing model,
reproducibility check) can reuse the data.

Detailed pipeline + verification recipe in
[`docs/EMISSIONS.md`](docs/EMISSIONS.md).

---

## Data sources

Riprap contacts only public-record federal, state, and city sources at
runtime. No commercial APIs, no proprietary scores, no opaque
aggregators.

| Source | Hosting agency | Used for |
|---|---|---|
| Hurricane Sandy 2012 inundation zone | NYC OTI / NOAA Office for Coastal Management | Cornerstone hazard memory |
| NYC DEP Stormwater Flood Maps | NYC Department of Environmental Protection | DEP modeled-scenario layers |
| Hurricane Ida 2021 USGS high-water marks | USGS Short-Term Network | Empirical validation points |
| FloodNet ultrasonic sensor network | NYU CUSP / FloodNet | Historical flood-event log (labeled events, peak depths) |
| NYC 311 flood complaints | NYC Open Data | Empirical complaint history |
| NOAA tide gauge, The Battery | NOAA CO-OPS | Live tide and surge level |
| NWS METAR | National Weather Service | Hourly precipitation |
| NWS public flood alerts | National Weather Service | Active warnings and watches |
| MTA subway entrances | MTA / NYC Open Data | Transit asset register |
| NYCHA developments | NYC Housing Authority | Public-housing exposure |
| NYC DOE schools | NYC Department of Education | Education-asset exposure |
| NYS DOH hospitals | New York State Department of Health | Critical-facility exposure |
| USGS 3DEP 1 m DEM | USGS National Map | HAND / TWI microtopography |
| NYC DOB filings | NYC Department of Buildings | Development-check intent |
| NPCC4 SLR projections | NYC Mayor's Office of Climate & Environmental Justice | Policy-context corpus (RAG) |
| Sentinel-2 MSI imagery | ESA / Copernicus | Prithvi + TerraMind inputs |

The full data licence map and vintage table is enumerated in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Repository structure

```
riprap/core/               The manifest-driven framework (current runtime)
├── pebbles/               Pebble schema, registry, adapters, shapers
├── burr/                  Burr app: intake, per-Stone MapActions, reconcilers
└── compliance/            Briefing-quality predicates (FEMA / IPCC / TCFD / …)

riprap/mcp/                MCP server — Riprap as an agent-callable tool

deployments/               One directory per deployment
├── nyc/                   Reference: manifests, stones.yaml, data, corpus
└── chicago, seattle, sf, boston, …    Same shape, different city

app/                       Legacy modules still used by register + intent paths
├── llm.py                 LiteLLM Router shim (Ollama / vLLM)
├── emissions.py           Per-query energy + token ledger (real NVML)
└── geocode.py, registers/, intents/, context/, flood_layers/, live/

web/                       FastAPI + SvelteKit
├── main.py                FastAPI app, SSE streaming, layer endpoints
└── sveltekit/             Primary UI (adapter-static; build committed)

modal/                     Modal deploy of this app (CPU, scale-to-zero)
scripts/                   Probes, register builders, deploy commands
experiments/               Reproduction recipes for the three NYC fine-tunes
docs/                      ARCHITECTURE · DEPLOY · multi-city · PORT-YOUR-CITY · …
tests/                     pytest (pebbles, stones, routing) + vitest (UI)
```

The GPU/ML-specialist inference stack lives in separate repos:
[`msradam/riprap-inference`](https://github.com/msradam/riprap-inference)
(LitServe specialists, deployable to Modal or a Mac Mini) and
[`msradam/riprap-triton`](https://github.com/msradam/riprap-triton)
(vLLM, optionally bundled with its own specialist stack). `inference/`
and `services/riprap-models/` in this repo are lighter self-host
sidecars that predate both — see `docs/DEPLOY.md`.

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers dev setup, the probe
scripts, and house style. [`CHANGELOG.md`](CHANGELOG.md) tracks
changes since the v0.5.0 hackathon submission.

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

The three NYC-specialised fine-tunes above are also Apache 2.0;
underlying upstream models retain their own permissive licences (see
each `MODEL_CARD.md`). Public-record data sources retain their own
access terms; the licence map is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Acknowledgments

- **AMD Developer Cloud**, MI300X compute that made the three Apache-2.0
  NYC fine-tunes feasible.
- **AMD × lablab.ai Developer Hackathon**, the venue.
- **IBM Research**, Granite 4.1, Granite Embedding 278M, Granite TTM r2,
  Mellea, and the rest of the open-source Granite ecosystem.
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
