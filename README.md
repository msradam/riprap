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
fan out across NYC datasets, satellite imagery, sensors, and forecasts.
Each pebble is one YAML manifest plus a small adapter; the framework
loads them from a deployment directory and groups them into five legible
roles, the **Five Stones**:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | What fires |
|---|---|---|
| **Cornerstone** | The Hazard Reader. What the ground remembers. | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, 2021 Ida USGS high-water marks, Prithvi-EO satellite-detected surface water after Ida (experimental), USGS 3DEP DEM + HAND/TWI |
| **Keystone** | The Asset Register. What's exposed. | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals, **TerraMind-NYC Buildings LoRA** |
| **Touchstone** | The Live Observer. Current state of the city. | FloodNet ultrasonic depth sensors, NYC 311 flood complaints, NWS hourly METAR, NOAA tide-gauge water levels, **Prithvi-EO 2.0 NYC-Pluvial v2** (live pass off by default, experimental), **TerraMind-NYC LULC LoRA** |
| **Lodestone** | The Projector. What's coming. | NWS public flood alerts, per-address 311 weekly forecast (experimental), FloodNet sensor recurrence forecast (experimental), **Granite-TTM-r2-Battery-Surge fine-tune** (96 h hourly horizon, experimental) |
| **Capstone** | The Synthesiser. Citation-grounded briefing. | Granite 4.1 + a hand-written grounding check |

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
pebble manifests out per Stone, manifest-rendered evidence, verified
structured claims, SSE streaming to a SvelteKit
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
NYC pluvial-flood fine-tune of Prithvi-EO 2.0. Test IoU is 0.598, but
the labels are the base model's own Ida polygons (self-distillation) and
the random split shares parent scenes, so this measures agreement with
pseudo-labels, not flood detection. The Sen1Floods11 base was never
scored on this test set. Lovász-Softmax loss with copy-paste
augmentation.

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
Address ──► Granite 4.1 3B planner ──► Plan{intent, targets, specialists}
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
                     evidence: manifest templates filled from values
                                              ▼
                  Capstone: no-LLM evidence briefing, or JSON claims
                  from any OpenAI-compatible model, verified in code
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
or run natively on a Mac Mini / Apple Silicon for MPS access. Granite
4.1 via vLLM is the same repo's second Modal app (its own GPU tier,
its own image); any other OpenAI-compatible vLLM endpoint works too.
See `docs/DEPLOY.md` for every combination.

Source-of-truth pointers:

- `riprap/core/pebbles/`: the pebble framework — manifest schema,
  registry, and the adapters / shapers that normalize each source.
- `riprap/core/burr/`: the Burr application — intake, per-Stone
  `MapActions` fan-out, and the reconciler tiers (`llm` / `no_llm`).
- `deployments/<city>/`: the manifests, `stones.yaml`, data, and corpus
  that define one deployment.
- `riprap/core/compliance/`: disclosure checks (substring tests for
  required caveat phrases), run per briefing. They do not measure quality.
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
NVML energy, grounding-check pass rate) in
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
└── compliance/            Disclosure checks (caveat-phrase substring tests)

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

The GPU/ML-specialist inference stack lives in a separate repo,
[`msradam/riprap-inference`](https://github.com/msradam/riprap-inference)
(LitServe specialists + Granite 4.1 via vLLM, deployable to Modal as
two apps, or a Mac Mini). `inference/` and `services/riprap-models/`
in this repo are lighter self-host sidecars that predate it — see
`docs/DEPLOY.md`.

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
