# Riprap architecture

> **What it is.** A web tool that takes an address, a neighbourhood or a
> community district and produces a short, citation-grounded
> **climate-exposure briefing**: evidence where every sentence links back
> to the dataset, agency report or model output it came from. NYC/flood is
> the reference deployment (this document describes it end to end); the
> same code runs five experimental city deployments (see
> [`docs/multi-city.md`](multi-city.md)). Heat and air-quality scaffolds
> (see [`docs/multi-hazard.md`](multi-hazard.md)) are not reachable today:
> they have no `coverage:` bounding box, so no query routes to them, and
> the planner refuses heat and air questions as out of scope.
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

Riprap surfaces all three classes. The offline register tier weights them in that
order (empirical > modeled > proxy), with empirical hits granted a
**floor rule**. See [§5](#5-the-scoring-rubric).

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

1. **A briefing** with one section per Stone that has evidence. In no-LLM
   mode it is the evidence sentences themselves, opened for a bare address
   by an "In brief" lead (Sandy, FEMA zone, DEP scenarios, 311 count, each
   part passed through the claim verifier), with the three point DEP
   scenarios merged into one sentence; in LLM mode it is the claims that
   passed the citation and number checks. Every sentence carries `[doc_id]`
   citations. A section with no evidence is left out.
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

The deterministic tier 1 to 4 rubric ([§5](#5-the-scoring-rubric),
`app/score.py`) is not part of the live response. Its callers are the
offline register builders (`scripts/build_*_register.py`), whose output
is served at `/api/register/{asset_class}`.

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
select_sources      stones.select_pebbles: the planner's choice plus a
  │                 per-intent floor; every pebble for a bare place.
  │                 Records `consulted` and `not_checked`
  ▼
stones              ONE parallel MapActions fan-out over the selected
  │                 Cornerstone, Keystone, Touchstone and Lodestone pebbles
  ▼
assemble_legacy_state   reshapes the DEP scenario values into one dict
  ▼
policy_corpus       Granite Embedding query + Flair NER over the corpus
  ▼
reconcile           evidence from manifest templates, then the no-LLM
                    briefing or LLM claims checked in code for citations
                    and numbers; disclosure checks
```

Which pebbles run depends on the intent. Point intents run pebbles with
`spatial.scope: point`. `neighborhood` and `development_check` run the
polygon pebbles (`area_boundary`, `sandy_nta`, `dep_extreme_2080_nta`,
`dep_moderate_2050_nta`, `dep_moderate_current_nta`, `nyc311_nta`,
`microtopo_nta`, `dob_permits_nta`). `live_now` runs only the
`type: live` point pebbles. `compare` is two `single_address` runs merged
(`run_compare`).

If geocoding fails or no deployment covers the point, the pebbles degrade
to a trace record saying why, and the briefing says the place could not
be located or is outside coverage instead of guessing. The decline logic
(an explicit non-US path and a "this names another deployment's city"
check) is in `app/geocode.py` and `riprap/core/burr/intake.py`.

Each step and each pebble writes a trace record (timing, ok or error, a
short result summary) that streams to the UI as `step` events on
`/api/agent/stream`. Burr's own tracking UI is off unless
`RIPRAP_BURR_TRACKING=1`.

### 3.1 NYC pebbles, plain language

The NYC deployment has 31 pebbles: 19 point pebbles in
`deployments/nyc/manifests/`, the 8 polygon pebbles listed above (in the
same directory), and 4 federal pebbles from `deployments/federal/`
(`fema_nfhl`, `nws_alerts`, `nws_obs`, `usgs_gauges`) that are merged into
every deployment. Other deployments have their own, smaller, experimental
sets (see [`docs/multi-city.md`](multi-city.md) and
[`docs/multi-hazard.md`](multi-hazard.md)).

| Pebble | Plain-language description | Evidence class |
|---|---|---|
| **sandy** | Did Hurricane Sandy flood this address in 2012? Point-in-polygon over the NYC Sandy Inundation Zone. | empirical |
| **fema_nfhl** | FEMA National Flood Hazard Layer effective zone at this point, with the FIRM panel vintage. | modeled |
| **dep_moderate_current**, **dep_moderate_2050**, **dep_extreme_2080** | Three NYC DEP stormwater scenarios. Each reports a depth class at this point. | modeled |
| **ida_hwm** | USGS Hurricane Ida 2021 high-water marks near this address. | empirical |
| **prithvi_water** *(experimental)* | Satellite-detected surface water after Ida: Prithvi-EO 2.0 polygons from a pass about 14 hours after the heaviest rain, baked offline. It mostly shows marsh, shoreline and park water, gives no inside or outside verdict for the address, and says nothing about street or basement flooding. | modeled |
| **microtopo** | Elevation percentile, HAND, TWI and basin relief from the USGS 3DEP DEM. | proxy |
| **policy_corpus** *(experimental)* | Granite Embedding 278M retrieves passages from five NYC agency PDFs; Flair NER adds coarse entity tags. | policy context |
| **mta_entrances**, **nycha_developments**, **doe_schools**, **doh_hospitals** | Transit entrances, public housing, schools and hospitals within range, and their flood exposure. | empirical |
| **nws_alerts** *(live)* | Active NWS alerts intersecting this address. | modeled |
| **ttm_battery_surge** *(live, experimental)* | Granite TTM r2 fine-tuned on Battery gauge history, forecasting the surge residual over the next 96 hours. No wind or pressure input. | modeled |
| **ttm_311_forecast** *(live, experimental)* | Forecast of weekly NYC 311 flood-complaint volume near this address. | modeled |
| **floodnet_forecast** *(live, experimental)* | Forecast of flood-event recurrence at the nearest FloodNet sensor. | modeled |
| **npcc4_slr** | NPCC4 (2024) sea-level rise projections at the Battery. | modeled |
| **floodnet** *(live)* | FloodNet depth sensors near this address and their flood events. | empirical |
| **nyc311** *(live)* | NYC 311 flood-related complaints near this address over the past 5 years. | proxy |
| **nws_obs** *(live)* | Latest NWS hourly observation at the nearest station. | empirical |
| **noaa_tides** *(live)* | Latest NOAA water level, predicted tide and the residual (roughly the surge) at the nearest station. | empirical |
| **usgs_gauges** *(live)* | Live stage at the nearest USGS stream gauge (OGC API). | empirical |

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
| policy_corpus | NPCC4 Ch. 3, MTA resilience roadmap, Comptroller report |

In no-LLM mode the briefing opens with an "In brief" lead (the Sandy
footprint, the FEMA zone, the DEP scenarios and the 311 count, each part
cited and passed through the claim verifier). Then each value becomes one
sentence from its manifest template, cited to its `doc_id` and grouped
under its Stone; the three point DEP scenarios are merged into one
sentence. Pebbles that
returned nothing (no Ida marks, no alerts) print nothing, so the briefing
never mentions them.

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
| `out_of_scope` | Buy, rent, insure, legal advice, a specific-day forecast, a hazard other than flooding | A fixed refusal text |

With a question, only the planner's chosen pebbles and the intent's floor
run (`riprap/core/burr/stones.py`, `FLOOR` and `select_pebbles`); the
others are listed as not checked. The LLM briefing then opens with an
answer section whose lead and claims are checked in code (docs/GROUNDING.md,
"Questions").

HTTP routes: `/api/agent` (JSON), `/api/agent/stream` (SSE),
`/api/agent/batch` (up to 25 addresses), `/api/district/{code}`,
`/api/nyc311/flood_requests`, `/api/print` (PDF, needs the `pdf` extra),
`/api/register/{asset_class}` and the `/api/layers/*` map layers. The
MCP server (`riprap/mcp/server.py`) exposes `list_sources`,
`get_evidence`, `get_district_summary`, `get_citation`,
`nyc311_flood_requests`, `plan_query` and `get_briefing(address,
question)`; all but `get_briefing` work without an LLM.

---

## 5. The scoring rubric

This is the part of the system that produces the tier 1 to 4. It is
**deterministic, published, and not done by the language model**.
It is used only by the offline register builders; the live briefing
does not compute or show a tier.
See `METHODOLOGY.md` for the full citation list; here's the
high-level structure.

### 5.1 Three thematic sub-indices

Following Cutter et al. 2003 (SoVI hazards-of-place) and Tate 2012
(uncertainty analysis), indicators are grouped into thematic sub-
indices, equal-weighted within each group, normalized to [0, 1]:

| Sub-index       | What it captures                                         | Top weights |
|-----------------|----------------------------------------------------------|-------------|
| **Regulatory**  | Inside FEMA / DEP / NPCC4 modeled or regulated zones     | FEMA 1 %; DEP-2050; DEP Tidal |
| **Hydrological**| Terrain-based exposure (HAND, TWI, percentile, relief)   | HAND (Nobre 2011); TWI half-weighted (urban DEM noise) |
| **Empirical**   | Did flooding actually happen here (Sandy, Ida HWMs, 311) | Sandy + HWM<100m → also trigger floor |

The **composite** is the sum of the three sub-indices (range 0 to 3).
Tier breakpoints: ≥1.5 → Tier 1, ≥1.0 → Tier 2, ≥0.5 → Tier 3, >0 →
Tier 4, 0 → Tier 0.

### 5.2 Max-empirical floor

If **Sandy 2012 inundation** OR **a USGS Ida HWM within 100 m** fired,
the tier is capped at **2 (Elevated)**. It cannot be worse,
regardless of the additive composite.

This recovers the *important* multiplicative behaviour Balica 2012
argues for (empirical observations should not be cancelled by
terrain or modeled scenarios) without giving up additive transparency.
The 100 m radius is chosen because USGS HWM positional uncertainty is
typically 5 to 30 m. 100 m gives ~3σ headroom for a confident "this
address was inundated" signal.

### 5.3 Live signals stay out

NWS alerts, NOAA tide residual, and NWS hourly precipitation are
**not** in the static tier. Per IPCC AR6 WG II glossary and NPCC4
Ch. 3, exposure is a quasi-stationary property of place; event
occurrence is time-varying. They appear separately as live evidence
cards.

---

## 6. Grounded synthesis

The full description is in [`GROUNDING.md`](GROUNDING.md). In short: the
evidence is each pebble's manifest template filled from its value
(`riprap/core/burr/evidence.py`). With no LLM configured, that evidence is
the briefing. With an OpenAI-compatible endpoint configured
(`RIPRAP_LLM_BASE_URL`, `RIPRAP_LLM_MODEL`, optional fallback endpoint),
the model returns JSON claims under a per-request schema whose `doc_ids`
enum is the documents actually passed in; code checks every cited id and
every number against the cited documents, retries once with the failures
listed, and drops what still fails into `dropped_claims`. Only surviving
claims are rendered (`riprap/core/burr/synthesis.py`).

On the ten gallery addresses, `granite4:micro` kept 122 claims and dropped
0 (`tests/probe_grounding_results.json`); `llama3.1:8b` kept 191 and
dropped 0, with 37 retries, all caused by a verifier bug since fixed
(`tests/probe_grounding_results_llama3.1-8b.json`).

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

| Model | Params | Runtime | Role | Maturity |
|---|---|---|---|---|
| Any OpenAI-compatible LLM (e.g. `granite4:micro`, Granite 4.1 8B) | varies | External endpoint | Planner and claim writer, LLM mode only | Optional |
| Granite TimeSeries TTM r2 | 1.5 M | granite-tsfm, in process on CPU | `ttm_battery_surge` (fine-tune `msradam/Granite-TTM-r2-Battery-Surge`), `ttm_311_forecast`, `floodnet_forecast` | Experimental |
| Granite Embedding 278M | 278 M | sentence-transformers, in process on CPU | Embeds the query for `policy_corpus`; the corpus index is built offline by `scripts/build_rag_index.py` into `data/rag_index.npz` | Experimental |
| Flair NER (`flair/ner-english-ontonotes-fast`) | about 150 MB | flair, in process on CPU | Coarse entity tags on retrieved passages | Experimental |
| Prithvi-EO 2.0 (`msradam/Prithvi-EO-2.0-NYC-Pluvial` by default) | 300 M | TerraTorch, batch only (`eo` extra) | `scripts/run_eo_batch.py`; the app reads only the baked Ida polygons | Experimental |
| GLiClass large v3.0 (`knowledgator/gliclass-large-v3.0`) | see model card | gliclass, in process on CPU | Entailment check on guarded answer claims (`riprap/core/burr/entailment.py`); misses paraphrased inferences | Experimental |
| GLiClass modern-base v3.0, distilled 311 filter | see model card | gliclass, in process on CPU; weights built locally by `scripts/train_311_filter.py`, found through `RIPRAP_311_FILTER_PATH` | Flood filter for SF, Boston and Albany 311 records; unreliable on live feeds | Experimental |

The in-process models need the `ml` extra; without it their pebbles skip
themselves. TerraMind and the NYC TerraMind adapters are not used by the
app. See the README's Models section for what each evaluation supports.

**Granite 4.1 is not Granite TimeSeries.** Granite 4.1 is IBM's chat LLM
family. Granite TimeSeries TTM is a separate IBM Research model line
(Ekambaram et al. 2024). They share a brand, not an architecture.

### 7.1 Earth observation runs as a batch job

Prithvi-EO 2.0 needs a GPU or minutes of CPU per tile, so it never runs
per request. The Ida layer was segmented once (pre 2021-08-25, post
2021-09-02, a pass about 14 hours after the heaviest rain) and filtered
into 166 polygons in `data/prithvi_ida_2021.geojson`; `prithvi_water`
reads them.

`scripts/run_eo_batch.py` is the repeatable version: it picks the least
cloudy Sentinel-2 L2A scene within 48 hours after a rain date, masks water
already present in a pre-event scene, and writes a Cloud Optimized GeoTIFF
plus a per-NTA GeoParquet summary. The app does not read those outputs
yet. Street and basement flooding usually drains within hours and cannot
be seen at 10 to 20 m, so an empty result is not evidence of no flooding.

### 7.2 TTM runs in process

TTM r2 is small enough to run in milliseconds on CPU, so its three
pebbles run inside the request. All three are experimental. The surge
forecast covers only the residual, not the astronomical tide (NOAA
already publishes that), and its sentence tells readers to use NOAA ETSS
or the Stevens Flood Advisory System for storm decisions.

---

## 8. Live signals

Live pebbles (`noaa_tides`, `nws_alerts`, `nws_obs`, `usgs_gauges`,
`floodnet`, `nyc311` and the TTM forecasts) are handled apart from the
static Cornerstone layers:

- They appear as evidence cards and a "Right now" section in the UI.
- They are excluded from the register tier rubric (§5): a live reading
  changing between two register builds should not retier an asset whose
  hazard class has not changed.
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

The top-level tree is in the README's "Repository structure" section.
Three things a file listing does not make obvious:

- **`riprap/core/`** is the framework: `pebbles/` (registry, schema,
  adapters, shapers), `burr/` (the app, intake, evidence, synthesis),
  `compliance/` (the 13 disclosure checks) and `http.py`.
- **`app/`** holds the Python functions that `python_call` manifests
  point at (`context/`, `flood_layers/`, `live/`, `assets/`, `areas/`),
  plus the planner, geocoder, energy ledger, PDF export and register
  builder. Adding a pebble usually means pointing a manifest at an
  existing function or a new one shaped the same way.
- **`deployments/<city>/`** is a directory of manifests, `stones.yaml`
  and, for NYC, the geospatial fixtures and policy corpus the manifests
  reference.

---

## 11. Honest scope (what Riprap does NOT do)

- **Not a damage probability.** Riprap is exposure triage. We have no
  labeled flood-damage outcomes (claim records, insurance loss data),
  so we cannot calibrate. The tier is a literature-grounded prior,
  not a prediction.
- **Not a flood insurance rating.** For that, see FEMA Risk Rating 2.0
  (claims-driven GLM over decades of labeled outcomes).
- **Not a vulnerability assessment.** Engineering fragility (foundation
  type, electrical hardening, drainage condition), social capacity,
  and financial absorption are out of scope.
- **No sub-surface flooding.** Optical satellites can't see basement
  apartments or subway entrances, the dominant Hurricane Ida damage
  mode in NYC. Prithvi emits no polygons for Hollis or Carroll
  Gardens, and that absence says nothing about whether they flooded.
- **Vintage-bounded.** FEMA NFHL is years stale; DEP Stormwater Maps
  are 2021; corpus PDFs are point-in-time. Each cited document carries
  its manifest's `date_modified`.
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
Docker (`deploy/Dockerfile` installs core plus `ml`; `docker-compose.yml` has
the app and an optional `local-llm` Ollama profile), and an optional GPU
LLM endpoint on Modal.

Local development:

```bash
git lfs install && git lfs pull
uv sync --extra ml
uv run uvicorn web.main:app --reload --port 7860

# Frontend, only when changing components
cd web/sveltekit && pnpm install && pnpm run build
```

The HF Space `lablab-ai-amd-developer-hackathon/riprap-nyc` is the frozen
May 2026 hackathon build with inference disabled. It belongs to the
hackathon organisation, not this project, and does not track the code.

---

## 14. License

Apache-2.0. The foundation models Riprap uses (Granite Embedding,
Granite TimeSeries TTM r2, Prithvi-EO 2.0) are Apache-2.0, and the input
datasets (NYC Open Data, USGS, NOAA, NWS, FloodNet NYC, Sentinel-2 via
Microsoft Planetary Computer) are public; each manifest records its
source's licence. Visual idiom adapted from
[NYC Planning Labs](https://planninglabs.nyc/).
