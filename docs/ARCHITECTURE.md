# Riprap architecture

> **What it is.** A web tool that takes an address, a neighbourhood or a
> community district and produces a short, citation-grounded
> **climate-exposure briefing**: evidence where every sentence links back
> to the dataset or agency report it came from. New York City is
> the reference deployment, with a flood briefing (this document describes
> it end to end) and a heat briefing built the same way
> ([§4.1](#41-heat)); the same code runs three experimental city
> deployments for flood (see [`docs/multi-city.md`](multi-city.md)). Air
> quality questions are refused as out of scope.
>
> **Who it's for.** Urban planners, journalists on deadline, NYCEM grant
> writers filing FEMA BRIC sub-applications, agency capital planners,
> researchers under FOIL/IRB constraints. Not consumers shopping for flood
> insurance.
>
> **How it runs.** One CPU process with no GPU and no keys. By default the
> briefing is the evidence itself, with no language model. An LLM is
> optional and is any OpenAI-compatible endpoint you point it at, local or
> hosted. Deployment shapes are in [`docs/DEPLOY.md`](DEPLOY.md).

---

## 1. A 60-second primer on NYC flooding

Skip if you already know this. Most architecture docs assume you do.
This one doesn't.

### 1.1 Three kinds of flood

NYC gets hit by three flood mechanisms that look completely different
on a map and are caused by different physics:

- **Coastal / surge flooding**. The ocean rises into the city.
  Driven by storm surge (wind pushing water against the coast),
  astronomical high tide, and wave run-up. Affects the **shoreline:**
  Brighton Beach, Coney Island, Red Hook, Lower Manhattan, the
  Rockaways, Staten Island east shore. **Hurricane Sandy 2012** is
  the canonical event. Water came over the seawall and flooded
  subway tunnels, hospitals, and electrical substations. Affects
  buildings that were dry that morning.
- **Pluvial / stormwater flooding**. Rain falls faster than the
  drainage system can carry it away. Affects **inland low points,
  basement apartments, and chronically under-sewered neighborhoods**:
  Hollis (Queens), Carroll Gardens (Brooklyn), Jamaica. **Hurricane
  Ida 2021** is the canonical event for NYC. Most of the deaths
  were in basement apartments far from any coast. Optical satellites
  largely *can't see* this kind of flooding because the water drains
  fast and is often sub-surface.
- **Compound flooding**. Coastal + pluvial happening at the same
  time, with groundwater rising too. Currently the active research
  frontier (NPCC4 Ch. 3 calls it out explicitly). Most agencies model
  these mechanisms separately; reality combines them.

A good civic flood tool has to cover all three and be honest about
what each signal can and cannot see. Riprap surfaces evidence for all
three but **doesn't predict damage**. See scope below.

### 1.2 Empirical vs modeled vs proxy

Each piece of flood evidence falls into one of three classes, and the
distinction matters for how much weight to give it:

- **Empirical**. Something flooded a place and was measured. USGS
  high-water marks (people went out after Hurricane Ida and surveyed
  where water reached on building walls). The 2012 Sandy Inundation
  Zone (mapped by the city after the storm). FloodNet ultrasonic
  sensors that recorded an actual depth. **Highest-confidence**: this
  flood happened here.
- **Modeled scenarios**. Hydraulic models simulate "what if" cases.
  FEMA's regulatory floodplains (1 % and 0.2 % annual chance). NYC
  DEP's Stormwater Maps (modeled water depth under three rainfall
  scenarios with varying sea-level-rise assumptions). **Useful but
  scenario-bounded**: this could happen here under those conditions.
- **Proxy signals**. Indirect indicators of flooding. NYC 311
  complaints ("street flooding", "sewer backup") clustering around an
  address. Topographic indices (HAND, TWI) suggesting water *would*
  pool here based on terrain. **Useful but biased**: 311 reflects
  civic engagement as well as flooding; terrain says nothing about
  drainage capacity.

Riprap reports all three classes and labels each source with its class. It does not weight or combine them
([`METHODOLOGY.md`](METHODOLOGY.md)).

### 1.3 Hydrology indices used in this app

Two terrain-derived numbers come up repeatedly. They're cheap to
compute from a Digital Elevation Model (DEM) and they're the
hydrological literature's canonical exposure proxies:

- **HAND (Height Above Nearest Drainage)**. Vertical distance from
  the address up to the nearest river/drainage channel. **<1 m** = at
  drainage level (water *will* reach here in flood). **>10 m** =
  hillslope (very dry). Nobre et al. 2011.
- **TWI (Topographic Wetness Index)**. `ln(catchment_area / tan
  slope)`. **High TWI** = water tends to accumulate here (large
  contributing area, gentle slope). Beven & Kirkby 1979.

Neither is a flood prediction; both are exposure indicators that say
"water *would* pool here based on terrain alone."

---

## 2. What Riprap produces

For a query in any of the intents in [§4](#4-intents), Riprap returns:

1. **A briefing** with one section per Stone that has evidence. It is the
   evidence sentences themselves, opened for a bare address by an "In
   brief" lead (Sandy, FEMA zone, DEP scenarios, 311 count, each part
   passed through the claim verifier), with the three point DEP scenarios
   merged into one sentence. A question gets an answer first: a fixed lead
   and the sources' sentences word for word, chosen by rules or, when an
   LLM is configured, by the model, and checked in code. Every sentence
   carries `[doc_id]` citations. A section with no evidence is left out.
2. **Evidence cards.** One per pebble that returned a value, with the raw
   values and a link to the source dataset.
3. **Map overlay.** The address or area, with the empirical and modeled
   flood extents that overlap it.
4. **Provenance.** Source name, URL, licence, `date_modified` and
   `retrieved_at` for every cited document, read from the pebble's
   manifest. Pebbles marked `maturity: experimental` say so in their
   sentence.
5. **Disclosure checks.** 13 substring tests for required caveat phrases
   drawn from FEMA, IPCC AR6, TCFD, ASTM E1527-21, AP Stylebook and SPJ
   guidance (`riprap/core/compliance/predicates.py`), run against the
   rendered briefing and attached to every response under the key
   `compliance`. A pass means the phrases are present. It is not a
   measure of briefing quality.
6. **Energy ledger.** Tokens, duration and an energy status for each LLM
   call (`emissions`; see [`EMISSIONS.md`](EMISSIONS.md)).

Riprap computes no score or tier ([§5](#5-asset-registers)).

---

## 3. How a query flows

`riprap/core/burr/app.py` is the only orchestrator: one Burr application
for every intent. A deployment (`deployments/<city>/`) is a directory of
YAML **pebble** manifests plus a `stones.yaml`. Each pebble declares its
`stone`, its `spatial.scope` (`point` or polygon), its `coverage`, its
data source, its narration template and its provenance. There is no
hand-coded specialist list.

### 3.0 The graph

```
query
  │
  ▼
plan                LLM planner (app/planner.py) in LLM mode: intent,
  │                 targets, the question, its focus and the pebbles it
  │                 needs (an enum of registry ids); regex heuristic
  │                 (intake.heuristic_plan) in no-LLM mode
  ▼
geocode_target      point intents: NYC Geosearch first, then Nominatim
  or                (1 request per second), plus BBL/BIN for NYC
resolve_area        neighbourhood intents: a 2020 NTA polygon, or a
  │                 community district code such as QN12 as the union
  │                 of its NTAs
  ▼
select_deployment   which deployments/<city>/ bounding box contains the
  │                 target (out of coverage falls back to federal pebbles)
  ▼
select_sources      stones.select_pebbles: the sources of the plan's hazard
  │                 (flood or heat, plus the shared ones); within them the
  │                 planner's choice plus a per-intent floor, or every
  │                 pebble for a bare place. Records `consulted` and
  │                 `not_checked`
  ▼
stones              ONE parallel MapActions fan-out over the selected
  │                 Cornerstone, Keystone, Touchstone and Lodestone pebbles
  ▼
assemble_legacy_state   reshapes the DEP scenario values into one dict
  ▼
reconcile           evidence from manifest templates, then the briefing;
                    a question is answered by rules or by an LLM whose
                    answer is checked in code; disclosure checks
```

Which pebbles run depends on the intent. Point intents run pebbles with
`spatial.scope: point`. `neighborhood` and `development_check` run the
polygon pebbles (`area_boundary` and the `*_nta` manifests). `live_now`
runs only the `type: live` point pebbles. `compare` is two
`single_address` runs merged (`run_compare`).

If geocoding fails, no source runs and the briefing says the place could
not be located. If no deployment covers the point, only the federal
pebbles run. The decline logic
(an explicit non-US path and a "this names another deployment's city"
check) is in `app/geocode.py` and `riprap/core/burr/intake.py`.

Each step and each pebble writes a trace record (timing, ok or error, a
short result summary) that streams to the UI as `step` events on
`/api/agent/stream`. Burr's own tracking UI is off unless
`RIPRAP_BURR_TRACKING=1`.

### 3.1 NYC pebbles, plain language

The NYC deployment has 59 pebbles: 55 in `deployments/nyc/manifests/` and
4 federal ones from `deployments/federal/` (`fema_nfhl`, `nws_alerts`,
`nws_obs`, `usgs_gauges`) that are merged into every deployment. Each names
its briefing in a `hazard` field: 36 are flood sources, 18 are heat sources
([§4.1](#41-heat)) and 5 run in both. Of the flood and shared sources, 20
run for a point, 18 for a neighbourhood or district, and 3 for both
(`noaa_tides`, `nws_water_forecast` and the experimental
`ttm_battery_surge`, which read a harbour gauge). Three are experimental
model layers ([MODELS.md](MODELS.md)); the rest are public records. Other deployments
have their own, smaller, experimental sets (see
[`docs/multi-city.md`](multi-city.md)).

Point pebbles:

| Pebble | Plain-language description | Evidence class |
|---|---|---|
| **sandy** | Did Hurricane Sandy flood this address in 2012? Read from the NYC Sandy Inundation Zone. Within 50 m of the mapped edge, the sentence gives the distance. | empirical |
| **fema_nfhl** | FEMA National Flood Hazard Layer effective zone at this point, with the FIRM panel vintage. | modeled |
| **fema_pfirm** | FEMA preliminary flood zone (2015 PFIRM) and base flood elevation, with the datum the service reports. | modeled |
| **dep_moderate_current**, **dep_moderate_2050**, **dep_extreme_2080** | Three NYC DEP stormwater scenarios. Each reports a depth class at this point. | modeled |
| **ida_hwm** | USGS Hurricane Ida 2021 high-water marks near this address. | empirical |
| **microtopo** | Elevation and low-spot percentile from the USGS 3DEP DEM in the sentence; HAND, TWI and basin relief in the evidence table. | proxy |
| **mta_entrances**, **nycha_developments**, **doe_schools**, **doh_hospitals** | Transit entrances, public housing, schools and hospitals within range. The sentence names the exposed ones. | empirical |
| **floodnet** *(live)* | FloodNet depth sensors near this address and their flood events, the newest one dated. | empirical |
| **nyc311** *(live)* | NYC 311 flood-related complaints near this address over the past 5 years, counted under both the old and the new descriptor names. | proxy |
| **noaa_tides** *(live)* | Latest NOAA water level, predicted tide and the residual (roughly the surge) at the nearest station. | empirical |
| **nws_water_forecast** *(live)* | The National Weather Service's forecast peak water level at the nearest of The Battery, Kings Point and Bergen Point, and the flood stage it reaches. | modeled |
| **npcc4_slr** | NPCC4 (2024) sea-level rise projections for New York City. | modeled |
| **nws_alerts** *(live, federal)* | Active NWS alerts intersecting this address. | modeled |
| **nws_obs** *(live, federal)* | Latest NWS hourly observation at the nearest station. | empirical |
| **usgs_gauges** *(live, federal)* | Live stage at the nearest USGS stream gauge (OGC API). | empirical |
| **ttm_battery_surge** *(live, experimental)* | A 96-hour forecast of the surge at the Battery from the author's Granite TTM fine-tune, hedged. Says it is not installed without the `ml` extra. | modeled |
| **city_landcover** | Paved, green and tree canopy shares near this address, from the city's 2017 land cover map (6 inch). Quoted when a question asks. | empirical |
| **landcover** *(experimental)* | The same shares from the latest satellite imagery, a land-cover model's saved output, after the city map's sentence. | modeled |

Polygon pebbles, for a neighbourhood or a community district: `sandy_nta`,
the three `dep_*_nta` scenarios, `microtopo_nta`, `nyc311_nta`,
`floodnet_nta` (the sensors inside the area), `nws_alerts_nta`,
`npcc4_slr_nta`, `city_landcover_nta` and the experimental
`landcover_nta` are area versions of the point pebbles. The harbour gauge
pebbles run for an area too, read at its centre. The four register manifests (`mta_entrances_nta`,
`doe_schools_nta`, `nycha_developments_nta`, `doh_hospitals_nta`) name the
exposed assets inside the area. `dcp_floodplain_nta` quotes NYC Planning's
count of buildings, residential units and residents in a district's 1%
annual chance floodplain. `dob_permits_nta` lists DOB permits, and
`area_boundary` is the outline.

### 3.2 Worked example: 2940 Brighton 3rd St, Brooklyn

Values from a May 2026 run, to show what the pebbles return:

| Pebble | What it returned |
|---|---|
| geocode | `(40.5780, -73.9617)`, BBL `3-08660-0001`, Brooklyn |
| sandy | Inside the 2012 Sandy Inundation Zone |
| dep_moderate_2050, dep_extreme_2080 | depth 0.4 to 0.8 ft; depth 0.8 to 2.0 ft |
| floodnet | 2 sensors within 600 m; 1 event in the last 3 years (peak 14 cm) |
| nyc311 | 11 flood-related complaints within 200 m, 5-year window |
| noaa_tides | +0.49 ft residual at the time of the run |
| nws_alerts | 0 active alerts |
| microtopo | Elevation 2.36 m, HAND 0.7 m, TWI 11.3, percentile 8 |
| ida_hwm | 0 high-water marks within 800 m |

The briefing opens with an "In brief" lead (the Sandy
footprint, the FEMA zone, the DEP scenarios and the 311 count, each part
cited and passed through the claim verifier). Then each value becomes one
sentence from its manifest template, cited to its `doc_id` and grouped
under its Stone; the three point DEP scenarios are merged into one
sentence. A pebble whose template names a field its value lacks prints
nothing, and a plain place briefing leaves out live readings that are not
notable ([§8](#8-live-signals)).

---

## 4. Intents

The planner classifies every query into one intent. In LLM mode this is
one LLM call (`app/planner.py`); in no-LLM mode it is a regex heuristic
(`riprap/core/burr/intake.py`).

| Intent | Triggered by | What runs |
|---|---|---|
| `single_address` | A street address | geocode, all point pebbles |
| `neighborhood` | An NTA name, borough or community district code (e.g. `QN12`) | resolve_area, polygon pebbles |
| `development_check` | "what's being built at X" | resolve_area, polygon pebbles including DOB permits |
| `live_now` | "is it flooding now", "current alerts" | geocode, live point pebbles only |
| `compare` | "A vs B" | two `single_address` runs, merged |
| `not_implemented` | Retrospective, ranking, cross-city queries | Returns a rationale immediately |
| `out_of_scope` | Buy, rent, insure, legal, health or safety advice, a specific-day forecast, a hazard other than flooding or heat | A fixed refusal text |

With a question, only the planner's chosen pebbles and the intent's floor
run (`riprap/core/burr/stones.py`, `FLOOR` and `select_pebbles`); the
others are listed as not checked. The briefing then opens with an answer
whose lead and facts are checked in code (docs/GROUNDING.md, "Questions").

### 4.1 Heat

Every intent above also runs for heat. The hazard is read from the query's
words (`riprap/core/burr/heat_answer.py`): "heat QN12", "extreme heat at 90-01
183rd Street, Queens" and "Will it be dangerously hot this week at ..." plan
with `focus.hazard: heat`, and a plan with no such focus is a flood plan.
Each manifest carries `hazard: flood | heat | any`, and source selection
runs the plan's hazard plus `any` (the area outline, the city's land cover
map and the land-cover model). So a heat briefing has the same Stones:

| Pebble (each has an `_nta` area version) | What it says | Stone, class |
|---|---|---|
| **heat_surface** | Landsat surface temperature within 150 m, as a difference from the city's land average over 18 clear summer images, with the range image by image. Surface, not air, temperature. | Cornerstone, empirical |
| **hvi** | The Health Department's Heat Vulnerability Index for the neighbourhood or district: a rank from 1 to 5, quoted as the department's. | Cornerstone, modeled |
| **heat_visits** | Heat illness emergency visits by residents of the community district over five summers; a suppressed count is said to be suppressed. | Cornerstone, empirical |
| **city_landcover** | Tree canopy and paved shares from the city's 2017 map (shared with flood). | Cornerstone, empirical |
| **heat_station** *(live)* | Days at or above 90 F this year and last at the nearest long-record station, its 1991 to 2020 average and its record. | Touchstone, empirical |
| **heat_obs** *(live)* | The latest air temperature and heat index at the nearest station. Quoted in a plain briefing only at 85 F or above. | Touchstone, empirical |
| **cool_features** | NYC Parks spray showers and pools within 800 m, with a pointer to the city's cooling center finder. | Keystone, empirical |
| **nws_heat_alerts** *(live)* | Active heat advisories, watches and warnings. | Lodestone, modeled |
| **nws_heat_forecast** *(live)* | The Weather Service's seven-day highs and highest apparent temperature, with its advisory thresholds. Quoted in a plain briefing only when a high of 90 F is forecast. | Lodestone, modeled |
| **npcc4_heat** | NPCC4 projections of days at or above 90 F, for the city as a whole. | Lodestone, modeled |

A bare place gets its flood briefing, and the page links to the heat one;
the two together would be about 1,460 words and 35 sources. A borough or
the whole city is a place for a heat question and is read as an area. A
heat comparison of two places runs both, each answering the question
asked. The district route and the MCP tools take `hazard=heat`. The heat
rules and refusals are in [GROUNDING.md](GROUNDING.md) ("Heat questions"),
the traps each sentence carries in [METHODOLOGY.md](METHODOLOGY.md).

HTTP routes: `/api/agent` (JSON), `/api/agent/stream` (SSE),
`/api/agent/batch` (up to 25 addresses), `/api/district/{code}` (with
`?hazard=heat` for the heat evidence),
`/api/nyc311/flood_requests`, `/api/register/{asset_class}` (schools and
nycha) and the `/api/layers/*` map layers. Printing is the browser's own
print of the `/print/{query_id}` page. The
MCP server (`riprap/mcp/server.py`) exposes `list_sources`,
`get_evidence(address, hazard)`, `get_district_summary(code, hazard)`,
`get_citation`, `nyc311_flood_requests`, `plan_query` and
`get_briefing(address, question)`. Every tool works without an LLM. Each `get_evidence` and
`get_district_summary` item carries its sentence, the source's own figures
(`value`), its `source_url` and its `vintage`.

---

## 5. Asset registers

Riprap has no scoring rubric. An asset is in a register when its point is
inside the 2012 Sandy inundation zone or inside any of the three DEP
stormwater scenarios ([`METHODOLOGY.md`](METHODOLOGY.md)).

- `riprap-register --asset-class {schools,nycha,mta_entrances}` writes a
  CSV with one row per asset and a 0 or 1 per layer.
- `scripts/build_register.py {nycha,schools}` bakes
  `data/registers/<class>.json`, which `/api/register/{asset_class}`
  serves and the schools and NYCHA pebbles read.

---

## 6. Grounded synthesis

The full description is in [`GROUNDING.md`](GROUNDING.md). In short: the
evidence is each pebble's manifest template filled from its value
(`riprap/core/burr/evidence.py`). With no LLM configured, that evidence is
the briefing, and a question is answered by rules over its words
(`riprap/core/burr/rule_answer.py`).

With an OpenAI-compatible endpoint configured (`RIPRAP_LLM_BASE_URL`,
`RIPRAP_LLM_MODEL`, optional fallback endpoint), the model is used only
for a question. It returns a lead and the ids of up to four facts under a
per-request schema whose enum is the documents actually passed in. Code
checks the lead against those facts, retries once with the failures
listed, and falls back to a fixed cannot-answer line. The answer text is
the sources' sentences word for word (`riprap/core/burr/synthesis.py`).

`RIPRAP_LLM_BARE=1` also sends a bare address to the model, which rewrites
the evidence as JSON claims. Code checks every cited id and every number
against the cited documents and drops what fails into `dropped_claims`.
In that mode, on ten gallery addresses, `granite4:micro` kept 122 claims
and dropped 0 (`tests/probe_grounding_results.json`); `llama3.1:8b` kept
191 and dropped 0, with 37 retries, all caused by a verifier bug since
fixed (`tests/probe_grounding_results_llama3.1-8b.json`).

### 6.1 Why not Granite's native inline citations

We looked at Granite's native `<|start_of_cite|>` mode. It is deprecated
in 4.x: the Ollama chat template for `granite4.x` has no citation branch,
and `granite_common` and `granite-io` ship processors only for 3.2 and
3.3. IBM's 4.x grounding path is a separate Citation Generation LoRA that
needs HF transformers and LoRA loading, which a generic OpenAI-compatible
endpoint does not offer. Schema-constrained JSON claims with a code-side
check work with any model and any endpoint.

---

## 7. Models

A briefing needs no model. An LLM at any OpenAI-compatible endpoint is
optional (for example Granite 4.1 8B over Ollama), used as the planner and
to choose a question's lead and facts. Two experimental models, the
author's fine-tunes, add labelled sentences: a surge forecast that runs on
CPU in the server when the `ml` extra is installed, and a land-cover model
whose saved maps the app reads after the city's own map. Every sentence
from them goes through one hedging function. The heat briefing uses no
model. See
[MODELS.md](MODELS.md).

---

## 8. Live signals

Live pebbles (`noaa_tides`, `nws_alerts`, `nws_obs`, `usgs_gauges`,
`floodnet`, `nyc311`, `nws_water_forecast` and the experimental
`ttm_battery_surge`) are handled apart from the
static Cornerstone layers:

- They appear as evidence cards and a "Right now" section in the UI.
- A plain place briefing quotes the observation, the tide reading, the
  stream gauge and the water-level forecast only when notable: rain, a
  tide a foot or more above prediction, a gauge in the area, a forecast
  that reaches a flood stage (`templated_reconciler.py`, `_QUIET_UNLESS`).
  A right-now question quotes them all, and the evidence table has them
  either way.
- Their HTTP responses are cached for 10 minutes by default; NOAA tides
  update every 6 minutes, NWS observations roughly hourly.
- They fail quietly. If NOAA times out, no `noaa_tides` evidence is
  emitted and the briefing does not mention it.

---

## 9. Data access and provenance

Every adapter fetches through `riprap/core/http.py`: one httpx client with
hishel caching (SQLite, 10 minutes by default for live sources,
`RIPRAP_HTTP_CACHE_TTL_S`) and stamina retries. Nominatim goes through the
same client with a 1 request per second gate. USGS gauges use the OGC API
via `dataretrieval`. FloodNet TLS verification is on.

Provenance comes only from manifests. Every manifest `provenance` block
has `date_modified` and `retrieved_at`; live sources use `at_fetch`, and
live Socrata sources resolve `date_modified` from the Socrata metadata
API. Each manifest also carries `maturity: production` or
`maturity: experimental`.

---

## 10. Repository layout

The top-level tree is in [REPOSITORY.md](REPOSITORY.md).
Three things a file listing does not make obvious:

- **`riprap/core/`** is the framework: `pebbles/` (registry, schema,
  adapters, shapers), `burr/` (the app, intake, evidence, synthesis),
  `compliance/` (the 13 disclosure checks) and `http.py`.
- **`app/`** holds the Python functions that `python_call` manifests
  point at (`context/`, `flood_layers/`, `assets/`, `registers/`,
  `areas/`, and `live/` and `eo/` for the experimental models, with
  `experimental.py` holding the one rule for quoting them), plus the
  planner, geocoder, energy ledger and register builder. Adding a pebble usually means pointing a manifest at an
  existing function or a new one shaped the same way.
- **`deployments/<city>/`** is a directory of manifests and a
  `stones.yaml`. The NYC geospatial fixtures the manifests reference are
  in `data/`.

---

## 11. Honest scope (what Riprap does NOT do)

- **Not a damage probability.** Riprap is exposure triage. We have no
  labeled flood-damage outcomes (claim records, insurance loss data),
  so we cannot calibrate.
- **Not a flood insurance rating.** For that, see FEMA Risk Rating 2.0
  (claims-driven GLM over decades of labeled outcomes).
- **Not a vulnerability assessment.** Engineering fragility (foundation
  type, electrical hardening, drainage condition), social capacity,
  and financial absorption are out of scope.
- **No sub-surface flooding.** No source Riprap reads records water
  inside basement apartments, the dominant Hurricane Ida damage mode in
  NYC.
- **Vintage-bounded.** FEMA NFHL is years stale and the DEP Stormwater
  Maps are 2021. Each cited document carries its manifest's
  `date_modified`.
- **Public infrastructure only.** ConEd substations, water-supply
  components, and other adversarially-sensitive registers are not
  published. NYC OD has the same redaction posture; we follow it.

---

## 12. Why local models

1. **Data governance.** A newsroom with FOIL'd documents, an agency
   capital planner with internal data, or a researcher under IRB
   constraints can't paste organization context into a vendor LLM. The
   no-LLM mode contacts no model at all, and LLM mode works against a
   local endpoint such as Ollama. Public NYC and federal services receive
   resolved coordinates only.
2. **Inference energy.** A local endpoint can report a measured or
   estimated figure per call; a hosted endpoint reports none, so Riprap
   shows no per-query figure for it ([`EMISSIONS.md`](EMISSIONS.md)). The
   1.3 to 1.6 Wh per briefing in [`history/BENCHMARKS.md`](history/BENCHMARKS.md) came
   from the retired GPU stack and is historical.
3. **Reproducibility.** Apache-2.0 stack end to end; no commercial
   licenses required to reproduce the system.

---

## 13. Deployment

See [`DEPLOY.md`](DEPLOY.md): local with no LLM, local with an LLM,
Docker (`deploy/Dockerfile`; `docker-compose.yml` has the app and an
optional `local-llm` Ollama profile), and an optional GPU LLM endpoint on
Modal.

Local development:

```bash
git lfs install && git lfs pull
uv sync
uv run uvicorn web.main:app --reload --port 7860

# Frontend, only when changing components
cd web/sveltekit && pnpm install && pnpm run build
```

The HF Space `lablab-ai-amd-developer-hackathon/riprap-nyc` is the frozen
May 2026 hackathon build with inference disabled. It belongs to the
hackathon organisation, not this project, and does not track the code.

---

## 14. License

Apache-2.0. Riprap ships no model weights; the experimental models are
downloaded from Hugging Face at pinned commits when their extra is
installed. The input datasets (NYC Open Data, FEMA, USGS, NOAA, NWS,
FloodNet NYC, Copernicus Sentinel imagery) are public; each manifest
records its source's licence, and [NOTICE](../NOTICE) carries the
attributions. Visual idiom adapted from
[NYC Planning Labs](https://planninglabs.nyc/).
