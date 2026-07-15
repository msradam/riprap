# Riprap architecture

> **Update, July 2026.** The MI300X DigitalOcean droplet that hosted
> the original AMD-judging deploy was decommissioned 2026-05-06. Post-
> hackathon, HF Spaces serve the deterministic data probes only
> (inferencing disabled); live inference now runs on Modal — specialists
> and Granite 4.1 (vLLM) both via companion repo `msradam/riprap-inference`
> (two scale-to-zero apps), or your own OpenAI-compatible vLLM endpoint —
> or fully locally on a Mac Mini (same `riprap-inference` codebase, run
> natively) with real Apple Silicon power measurement.
> The MI300X language preserved elsewhere in this document remains
> accurate for the original AMD-judging deploy, reproducible against
> your own AMD GPU box via `docker-compose --profile with-models` +
> `RIPRAP_HARDWARE_LABEL=AMD MI300X`. Current deployment topology and
> commands live in [`docs/DEPLOY.md`](DEPLOY.md); the emissions ledger
> — including the Mac Mini `powermetrics` path — is documented in
> [`docs/EMISSIONS.md`](EMISSIONS.md).

> **What it is.** A web tool that takes an address and produces a
> short, citation-grounded **climate-exposure briefing** — a paragraph
> of evidence where every numeric claim links back to the specific
> dataset, agency report, or model output it came from. NYC/flood is
> the production-grade reference deployment (this document describes
> it end to end); the same architecture ships five more city
> deployments (see [`docs/multi-city.md`](multi-city.md)) and, as a
> proven experiment, heat- and air-quality hazards on top of the same
> pebble/Stone framework (see [`docs/multi-hazard.md`](multi-hazard.md)).
>
> **Who it's for.** Urban planners, journalists on deadline, NYCEM
> grant writers filing FEMA BRIC sub-applications, agency capital
> planners, researchers under FOIL/IRB constraints. Not consumers
> shopping for flood insurance.
>
> **Why local foundation models.** A newsroom with FOIL'd documents
> can't paste them into a vendor LLM. We run Granite 4.1 (3 B-param
> chat model), Granite Embedding 278M (RAG), Prithvi-EO 2.0 (300 M-param
> Earth-observation model, offline pre-compute) and Granite TimeSeries
> TTM r2 (1.5 M-param zero-shot forecaster) inside one container. No
> vendor LLM is contacted at runtime.

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

Riprap surfaces all three classes. The score weights them in that
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

## 2. What Riprap actually produces

For a given address (or any of five intents; see [§4](#4-five-planner-intents)),
Riprap returns:

1. **A 4-section briefing paragraph** synthesised by Granite 4.1 with
   `[doc_id]` citations after every numeric claim. Sections:
   *Status*, *Empirical evidence*, *Modeled scenarios*, *Policy
   context*. A section is omitted entirely if no pebble fired for
   it (silence-over-confabulation contract).
2. **Evidence cards**. One per fired pebble, with the raw values
   and a link to the source dataset.
3. **Map overlay**. The address pinned, with the empirical and
   modeled flood extents that overlap it.
4. **Live "right now" signals**. Active NWS flood alerts, current
   tide residual at the nearest gauge, recent precipitation at the
   nearest ASOS, and a Granite TTM short-horizon forecast of the surge
   residual.
5. **A compliance audit**. The 13 briefing-standards predicates
   (FEMA / IPCC AR6 / TCFD / ASTM E1527-21 / AP Stylebook / SPJ — see
   `riprap/core/compliance/`) evaluated against the actual rendered
   paragraph, attached to every response.

**The deterministic tier 1–4 rubric** ([§5](#5-the-scoring-rubric),
`app/score.py`) still exists and is still exactly what it says —
empirical-floor-weighted, published, not LLM-computed — but it is not
part of the live single-query response today. Its live callers are the
offline bulk register builders (`scripts/build_*_register.py`, the
`/register/{schools,nycha,mta_entrances}` browsable pages), which tier
thousands of assets to decide which get a full reconciled paragraph
vs. a bare listing. §5 documents the rubric itself; if you're looking
for where a single query's tier appears in the JSON response, it
doesn't — that's the gap between this section's older framing and
the current wiring.

The full output is a JSON blob with all specialist outputs preserved,
so a journalist or planner can audit every number that appears in the
prose.

---

## 3. The manifest-driven pebble framework, and how a query actually flows

Riprap is a **state machine**, a Burr Application (DAGWorks). Two
generations of that state machine currently coexist in this codebase:

- **`riprap/core/burr/app.py`** — the current, manifest-driven runtime.
  A deployment (`deployments/<city>/`) is a directory of YAML **pebble**
  manifests plus a `stones.yaml`. Each pebble declares its own `stone`
  (which of the Five Stones it belongs to), `coverage` (the bbox it's
  eligible to fire in), data source, and citation metadata — no
  hand-coded specialist list. This is the path a `single_address` query
  takes by default (`RIPRAP_USE_BURR_APP=1`, the default — see
  [§12](#12-deployment)), and it's what makes adding a city or a hazard
  a directory of YAML rather than a code change (see
  [`docs/multi-city.md`](multi-city.md), [`docs/multi-hazard.md`](multi-hazard.md)).
- **`app/fsm.py`** — the original linear FSM this replaced for
  `single_address`. It's not dead: `riprap/core/burr/capstone.py`
  reuses its `step_reconcile` action as-is (the Mellea-grounded Granite
  call), and it's still the full execution path for the other four
  intents — `neighborhood`, `development_check`, `live_now`, and
  `compare` each have their own orchestration module under
  `app/intents/` that calls point/polygon-scoped specialist functions
  directly, not the pebble registry. `RIPRAP_USE_BURR_APP=0` also
  falls `single_address` back to this path entirely, for regression
  testing against the pebble-framework path.

This section describes the `single_address` pebble-framework path in
detail, since it's both the default and the architecture the rest of
this codebase is migrating toward.

### 3.0 The shape of a query

```
            ┌───────────────────────────────┐
  query ──► │ plan_intent (Granite 4.1:3b)  │  free text → {intent, targets, specialists}
            └───────────────┬───────────────┘
                            ▼
            ┌───────────────────────────────┐
            │ geocode_target (Nominatim,     │  target text → lat, lon
            │ NYC Geosearch enrichment)      │  (+ BBL/BIN for NYC pebbles)
            └───────────────┬───────────────┘
                            ▼
            ┌───────────────────────────────┐
            │ select_deployment              │  (lat, lon) → which deployments/<city>/
            └───────────────┬───────────────┘  bbox contains this point (or none)
                            ▼
       ┌───────────────────────────────────────────────────────────┐
       │   STONE FAN-OUT — MapActions parallel over 4 of the 5       │
       │   Stones (Capstone follows below). Each Stone reads the     │
       │   deployment's pebble registry at call time and fans out    │
       │   to every pebble tagged with that stone whose `coverage`   │
       │   contains the point.                                       │
       │                                                              │
       │   Cornerstone (hazard memory) │ Touchstone (live observation)│
       │   Lodestone (forecasts)       │ Keystone (assets)            │
       └──────────────────────────┬───────────────────────────────────┘
                                    ▼
                     ┌──────────────────────────────┐
                     │ assemble_legacy_state          │  reshapes the 3 DEP-scenario
                     └───────────────┬────────────────┘  pebble values into one dict
                                    ▼
                     ┌──────────────────────────────┐
                     │ step_policy_corpus             │  retrieval + NER in one pebble
                     └───────────────┬────────────────┘  (Granite Embedding 278M + GLiNER)
                                    ▼
                     ┌──────────────────────────────┐
                     │ step_reconcile (from app.fsm)  │  Granite 4.1 + Mellea
                     │ reads every fired pebble's      │  rejection-sampling loop
                     │ "document" and writes the       │  (up to loop_budget attempts)
                     │ 4-section cited paragraph       │
                     └───────────────┬────────────────┘
                                    ▼
                     cited briefing + evidence cards + map
                     + 13-predicate compliance audit
```

If geocoding fails or no deployment covers the resolved point, the
Stones still run (each pebble degrades to its `no coords` /
`no deployment` trace record) and the reconciler produces an honest
"couldn't locate this" or "outside coverage" briefing instead of
silently guessing — see `app/geocode.py` and `riprap/core/burr/intake.py`
for the specific decline logic (Nominatim-primary resolution, an
explicit non-US decline path, and a deployment-registry-based "this
query names a different Riprap deployment's city" check).

Each Stone's fan-out and each of the three Capstone steps
(`assemble_legacy_state`, `step_policy_corpus`, `step_reconcile`) are
Burr actions with their own trace record (timing, ok/err, a small
result summary) that streams to the frontend live as `step` SSE events.

### 3.1 What every pebble does, plain language

The NYC deployment's registry (`deployments/nyc/manifests/`) currently
carries 25 pebbles. Every other deployment has its own, smaller set —
see [`docs/multi-city.md`](multi-city.md) for the per-city pebble
counts and [`docs/multi-hazard.md`](multi-hazard.md) for heat/air.
`geocode` and `reconcile` below aren't pebbles — they're the two fixed
framework steps that bracket the Stone fan-out (§3.0).

| Pebble | Plain-language description | Tier |
|---|---|---|
| **geocode** *(framework, not a pebble)* | Resolve the query text to (lat, lon). Nominatim resolves any US address; when the point falls inside NYC, NYC DCP Geosearch additionally enriches the hit with BBL/BIN identifiers the NYC-specific pebbles below need. | n/a |
| **sandy** | Did the address get flooded by Hurricane Sandy in 2012? Point-in-polygon over the official NYC Sandy Inundation Zone. | empirical |
| **fema_nfhl** | FEMA's National Flood Hazard Layer effective flood zone at this point. | modeled |
| **dep_moderate_current**, **dep_moderate_2050**, **dep_extreme_2080** | Three modeled NYC DEP stormwater scenarios — current SLR baseline, 2050 moderate, 2080 extreme. Each reports a depth class at this point. | modeled |
| **ida_hwm** | USGS Hurricane Ida 2021 high-water marks near this address — actual measured water heights surveyed after the storm. | empirical |
| **prithvi_water** | Prithvi-EO 2.0-derived Hurricane Ida pre/post flood inundation polygons (offline pre-compute; instant at request time). | modeled |
| **microtopo** | LiDAR/DEM-derived micro-topography at the point: elevation percentile, HAND, TWI, basin relief. | proxy |
| **policy_corpus** | Granite Embedding 278M retrieves the most-relevant passages from 5 NYC agency PDFs, and GLiNER extracts typed entities (agency, dollar amount, date, location) from them — one pebble owning retrieval + NER, replacing the older separate rag/gliner_extract steps. | empirical |
| **mta_entrances**, **nycha_developments**, **doe_schools**, **doh_hospitals** | MTA subway/rail entrances, NYCHA developments, NYC DOE schools, and NYS DOH hospitals within range of this address, and their flood exposure. | empirical |
| **nws_alerts** *(live)* | Currently active NWS alerts (flood/coastal/wind) intersecting this address. | modeled |
| **ttm_forecast** *(live)* | Granite TTM r2 zero-shot forecast of the Battery storm-surge residual, 9.6-hour horizon at 6-minute cadence. | modeled |
| **ttm_battery_surge** *(live)* | Granite-TTM-r2-Battery-Surge — a fine-tuned nowcast of Battery storm-surge over the next 96 hours. | modeled |
| **ttm_311_forecast** *(live)* | 4-week forecast of NYC 311 flood-complaint volume at this address. | modeled |
| **floodnet_forecast** *(live)* | 28-day forecast of flood-event recurrence at the nearest FloodNet sensor. | modeled |
| **npcc4_slr** | NYC Panel on Climate Change (2024) sea-level rise projections at the Battery. | modeled |
| **floodnet** *(live)* | FloodNet ultrasonic depth sensors near this address and their historical flood events. | empirical |
| **nyc311** *(live)* | NYC 311 flood-related complaints filed near this address over the past 5 years. | proxy |
| **nws_obs** *(live)* | Most recent NWS hourly observation at the nearest METAR station. | empirical |
| **noaa_tides** *(live)* | Recent NOAA tide-gauge water-level reading — observed level, predicted astronomical tide, and the **residual** (≈ surge) — at the nearest station. | empirical |
| **usgs_gauges** *(live)* | Live stage at the nearest USGS stream gauge. | empirical |
| **prithvi_live** *(live)* | Live Sentinel-2 water segmentation around this address (Prithvi-EO 2.0 NYC-Pluvial fine-tune). | modeled |
| **terramind_lulc**, **terramind_buildings** *(live, not yet manifest-driven)* | TerraMind land-cover and building-footprint synthesis over a fresh EO chip. Still an `app/fsm.py` step rather than a pebble manifest — one of the pieces README's "legacy `app/` modules... the framework has not yet absorbed" refers to. | modeled |
| **reconcile** *(framework, not a pebble)* | Granite 4.1 reads every fired pebble's "document" and writes the 4-section cited briefing paragraph. Mellea rejection-sampling validates the invariants in `app/mellea_validator.py`'s module docstring; up to `loop_budget` attempts. See [§6](#6-document-grounded-reconciliation). | LLM synthesis |

### 3.2 Worked example: 2940 Brighton 3rd St, Brooklyn

To make the pipeline concrete, here's what fires for a Brighton Beach
address:

| Pebble | What it returns |
|---|---|
| geocode    | `(40.5780, -73.9617)`, BBL `3-08660-0001`, Brooklyn |
| sandy      | **YES**. Inside the 2012 Sandy Inundation Zone |
| dep_moderate_2050, dep_extreme_2080 | `dep_moderate_2050`: depth 0.4-0.8 ft; `dep_extreme_2080`: depth 0.8-2.0 ft |
| floodnet   | 2 sensors within 600 m; 1 trigger event in last 3 yr (peak 14 cm) |
| nyc311     | 11 flood-related complaints in 200 m, 5-yr window |
| noaa_tides | Sandy Hook gauge, +0.49 ft residual *(today's reading)* |
| nws_alerts | 0 active alerts |
| nws_obs    | KJFK ASOS, no recent precipitation |
| ttm_forecast | Forecast peak residual +0.6 ft in 4.2 h *(today's run)* |
| microtopo  | Elevation 2.36 m, HAND 0.7 m, TWI 11.3, percentile 8 (very low) |
| ida_hwm    | 0 USGS HWMs within 800 m (Ida hit Queens hardest, not Brighton) |
| prithvi_water | Inside an Ida-attributable polygon? **NO** (Ida was pluvial-inland) |
| policy_corpus | Top hits: NPCC4 Ch.3 (coastal), MTA Resilience (Coney Island D-train), Comptroller |
| reconcile  | (see below) |

(An offline register build would additionally tier this address 1
"High exposure" under the empirical-floor rubric — [§5](#5-the-scoring-rubric)
— but that tier isn't part of this live response; see [§2](#2-what-riprap-actually-produces).)

The reconciler then writes:

```
**Status.** This Brighton Beach address sits **inside the 2012 Sandy
Inundation Zone** [sandy], on relatively low ground with HAND of 0.7 m
[microtopo].

**Empirical evidence.** NYC 311 records show **11 flood-related
complaints** within 200 m over the last 5 years [nyc311]; 2 FloodNet
sensors are within 600 m and one logged a 14 cm event in the last 3
years [floodnet].

**Modeled scenarios.** The address sits inside **DEP Moderate-2050**
with depth class 0.4-0.8 ft and **DEP Extreme-2080** with depth class
0.8-2.0 ft [dep_moderate_2050][dep_extreme_2080].

**Policy context.** The **MTA Climate Resilience Roadmap** flags the
nearby Coney Island D-train infrastructure for coastal-flood exposure
[rag_mta].
```

Note what *didn't* fire: no Ida HWM doc (Ida didn't flood here), no
Prithvi doc (no Ida-attributable polygon), no NWS alerts (clear day),
no TTM doc (forecast residual under threshold). The reconciler never
saw those headers and didn't invent them.

---

## 4. Five planner intents

The planner (`app/planner.py`) classifies every free-text query into one of
five intents before anything else runs. This happens in a single Granite
4.1 call that streams its JSON output to the client as `plan_token` events.

| Intent                | Triggered by                                  | Execution path                         |
|-----------------------|-----------------------------------------------|----------------------------------|
| `single_address`      | Fully-qualified street address                | The manifest-driven pebble framework by default (§3): geocode → Five-Stone fan-out → policy_corpus → reconcile. Falls back to the legacy linear `app/fsm.py` FSM when `RIPRAP_USE_BURR_APP=0`. |
| `neighborhood`        | NTA name, borough name, bare zip              | `app/intents/neighborhood.py` — its own orchestration, NTA-polygon-scoped specialist calls (not the pebble registry) |
| `compare`             | "A vs B", "compare X to Y"                   | Two sequential single_address runs; merged two-column paragraph |
| `development_check`   | "what's being built at X", "is Y risky"       | `app/intents/development_check.py` — DOB filings + flood layers, own orchestration |
| `live_now`            | "is it flooding now", "current alerts"        | `app/intents/live_now.py` — live-only specialists (tides, alerts, obs), non-strict reconcile (no Mellea) |
| `not_implemented`     | Retrospective, ranking, cross-city queries    | Returns rationale immediately |

`neighborhood`, `development_check`, and `live_now` each have their own
orchestration module under `app/intents/` — they call point/polygon-scoped
specialist functions directly and don't go through the pebble registry
that `single_address` uses by default. This is the concrete shape of the
"legacy `app/` modules remain for... multi-intent paths the framework
has not yet absorbed" note in the top-level README.

### Compare intent detail

`_run_compare()` in `web/main.py` executes the full `single_address`
path sequentially for each target, then merges the two paragraphs under
`## PLACE A: …` / `## PLACE B: …` headers separated by `---`. The
`CompareBriefing.svelte` component renders this as a two-column layout with
a "Key differences" delta bar above. During streaming the tokens are rendered
in a single column (sequential); the two-column layout appears when the
`final` event lands.

**Registered routes**

| Path                                      | Serves |
|-------------------------------------------|--------|
| `/`                                       | SvelteKit landing + live query UI |
| `/api/agent/stream?q=…`                   | SSE stream — planner + all intent paths |
| `/register/{schools,nycha,mta_entrances}` | Pre-computed bulk register browser |
| `/legacy`, `/single`, `/compare`, `/register/*` | Legacy custom-element bundle (compatibility) |

Registers are pre-computed because running 1,900 reconciler calls at request
time is a non-starter; the register build runs offline
(`scripts/build_*_register.py`) and results are loaded from
`data/registers/*.json` at boot.

---

## 5. The scoring rubric

This is the part of the system that produces the tier 1–4. It is
**deterministic, published, and not done by the language model**.
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

The **composite** is the sum of the three sub-indices (range 0–3).
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
typically 5–30 m. 100 m gives ~3σ headroom for a confident "this
address was inundated" signal.

### 5.3 Live signals stay out

NWS alerts, NOAA tide residual, and NWS hourly precipitation are
**not** in the static tier. Per IPCC AR6 WG II glossary and NPCC4
Ch. 3, exposure is a quasi-stationary property of place; event
occurrence is time-varying. They appear separately as live evidence
cards.

---

## 6. Document-grounded reconciliation

`app/reconcile.py` builds a list of OpenAI-style chat messages where
each specialist's emission is its own message with a stable `doc_id`
ride-along on the role. Granite 4.1's Ollama chat template recognises
any `role: "document <doc_id>"` message and lifts it into a
`<documents>` block, prepending IBM's official grounded-generation
system message ("Write the response by strictly aligning with the
facts in the provided documents").

Example packet for the Brighton Beach address (abbreviated):

```python
[
    {"role": "system", "content": "<citation-discipline + 4-section skeleton>"},
    {"role": "document sandy",            "content": "Address is INSIDE the 2012 Sandy zone. ..."},
    {"role": "document dep_extreme_2080", "content": "Depth class 0.8-2.0 ft. ..."},
    {"role": "document floodnet",         "content": "2 sensors; peak 14 cm. ..."},
    {"role": "document nyc311",           "content": "11 flood complaints in 200 m. ..."},
    {"role": "document microtopo",        "content": "Elev 2.36 m, HAND 0.7 m, TWI 11.3. ..."},
    {"role": "document rag_npcc4",        "content": "<retrieved paragraph>"},
    {"role": "user", "content": "Write the cited briefing now."},
]
```

The four-section structure (`**Status.** / **Empirical evidence.** /
**Modeled scenarios.** / **Policy context.**`) is enforced by the
`EXTRA_SYSTEM_PROMPT`. Sections without supporting documents are
omitted entirely.

### 6.1 Two reconciler models

- **`granite4.1:3b`** runs the planner and `live_now` (short outputs,
  routing decisions). Always streamed.
- **`granite4.1:8b`** runs the synthesis path for `single_address`,
  `neighborhood`, and `development_check` (long outputs, dense
  citations). Pre-warmed into VRAM in `entrypoint.sh` so the first
  query doesn't pay the model-load tax. Both fit warm on the T4 with
  `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=24h`.

### 6.2 Mellea-validated rejection sampling

`app/mellea_validator.py` wraps the Granite-via-Ollama call in IBM
Research's [Mellea](https://github.com/generative-computing/mellea)
framework. Instruct, validate, repair. The synthesis intents call
`reconcile_strict_streaming(...)` which:

1. **Streams** each generation attempt's tokens to the user (via the
   FSM threadlocal `set_token_callback` for `single_address` or a
   `progress_q` for the polygon intents).
2. After each attempt, runs **four deterministic checks** on the
   accumulated paragraph:
   - **`numerics_grounded`**. Every non-trivial number in the output
     appears verbatim in a source document.
   - **`no_placeholder_tokens`**. Output contains no leaked
     `[source]` / `<document>` template markup.
   - **`citations_dense`**. Every non-trivial number has a
     `[doc_id]` citation **somewhere in the same sentence** (sentence
     boundaries: `. ` / `.\n` / end-of-text).
   - **`citations_resolve`**. Cited `doc_id`s are a subset of the
     input doc_ids.
3. If any check fails, fires a `mellea_attempt` SSE event with the
   failed-requirement names, then **rerolls** with a feedback prompt
   that names the specific failing sentences (the model usually
   responds well to surgical corrections). Loop budget: 3 attempts.

The frontend renders an inline banner above the briefing. Amber on
reroll (with the failed-req list), green on first-try pass. The final
reconcile step in the trace shows the `passed: N/4 · rerolls: M`
metadata for full audit transparency.

### 6.3 Number recognition is identifier-aware

The numeric guardrail uses `\b-?\d[\d,]*(?:\.\d+)?\b` so that
identifier codes embedded in prose (`QN1206` NTA codes, `BBL
3-00589-0003` parcels, `BIN`, `B12` community boards) are *not*
treated as numeric claims demanding citation. This was the dominant
false-positive in early probing; without it, almost every neighborhood
briefing failed `citations_dense` because the opening sentence
typically reads "*X (NTA QN1206) in Queens…*".

### 6.4 Why no native Granite 4.x inline citations

We investigated using Granite's native `<|start_of_cite|>{document_id:
X}fact<|end_of_cite|>` mode. **It's deprecated in 4.x.** Verified:

- The official Ollama chat template for `granite4.x` has no citation
  branch (the 3.3 / 4.0-preview templates did).
- `granite_common` ships only `granite3/granite32` and
  `granite3/granite33` subdirs. No 4.x equivalent.
- `granite-io` has only `granite_3_2/` and `granite_3_3/` processor
  dirs.

The base 4.1 weights still contain the cite tokens (training residue),
so the model emits them as real tokens when nudged. But only as an
end-of-response list, not inline in prose. IBM's published 4.x
grounding path is a separate **Citation Generation LoRA** (built on
`granite-4.0-micro`, not 4.1) requiring HF transformers + LoRA
loading. Mellea's `OllamaBackend` explicitly raises
`NotImplementedError` for activated LoRAs. So our hand-rolled
`[doc_id]` regex + reroll **is** the right pattern for our setup
(Granite 4.1 via Ollama, inline placement).

---

## 7. The four foundation models

| Model | Params | Runtime | Role |
|-------|--------|---------|------|
| **Granite 4.1 :3b alias**   | 8 B†   | Ollama or vLLM (AMD MI300X)          | Planner (intent + specialist routing) + `live_now` reconciler. †Production alias `RIPRAP_OLLAMA_3B_TAG=granite4.1:8b` — planner runs 8b in production. Same knob, opposite direction, on a memory-constrained box: `docs/DEPLOY.md`'s "Memory-constrained boxes" section remaps it to a real 1B tag instead. |
| **Granite 4.1 :8b**         | 8 B    | Ollama or vLLM (AMD MI300X)          | Synthesis reconciler for `single_address`, `neighborhood`, `development_check`, `compare`. Validated by Mellea (4 grounding requirements + reroll). |
| **Granite Embedding 278M**  | 278 M  | sentence-transformers (CPU)          | RAG retrieval over 5 policy PDFs at query time.    |
| **Prithvi-EO 2.0**          | 300 M  | TerraTorch (offline pre-compute)     | NYC-Pluvial fine-tune; segmented Hurricane Ida 2021 pre/post Sentinel-2 polygons baked into `data/`. Fine-tune: `msradam/Prithvi-EO-2.0-NYC-Pluvial`. |
| **Granite TimeSeries TTM r2** | 1.5 M | granite-tsfm (CPU)                  | Zero-shot forecast of the Battery surge residual, ~9.6 h horizon. Fine-tune: `msradam/Granite-TTM-r2-Battery-Surge`. |
| **GLiNER medium-v2.1**      | ~200 M | gliner (CPU)                         | Named-entity extraction over RAG hits (locations, agencies, dates, infrastructure). `urchade/gliner_medium-v2.1`. |

**Granite 4.1 ≠ Granite Time Series.** Granite 4.1 is IBM's chat-LLM
family. Granite TimeSeries TTM is a separate IBM Research product
line (Ekambaram et al. 2024, NeurIPS). Both happen to share the
"Granite" brand but have different architectures, training data, and
authors.

**LiteLLM Router.** All LLM calls go through `app/llm.py`, a ~250-line
shim over a LiteLLM Router. Two backends are wired: `RIPRAP_LLM_PRIMARY=ollama`
(local + HF Space default) and `RIPRAP_LLM_PRIMARY=vllm` (AMD MI300X demo
path, auto-fails over to Ollama). The shim normalizes role names and
citation-token format so the rest of the codebase is backend-agnostic.

### 7.1 Why Prithvi runs offline

Prithvi-EO 2.0 with TerraTorch needs a GPU and minutes per HLS tile.
We segmented Hurricane Ida 2021 once (pre: 2021-08-25, post:
2021-09-02 ~12 h after peak), filtered the output (>30 000 sqft to
drop noise, <1 km² to drop tidal artifacts) into **166 polygons**
baked into `data/prithvi_ida_2021.geojson`. The runtime FSM does a
point-in-polygon test, not fresh inference. This is honest about
where foundation models earn their keep: **once, to produce a
defensible event-level signal. Not per request**.

### 7.2 Why TTM r2 runs live

TTM r2 is **1.5 M params**. Vastly smaller than Prithvi or Granite
4.1. Inference is millisecond-scale even on CPU. It forecasts only
the residual (surge component) at the Battery, which complements the
NOAA snapshot specialist; it does **not** try to forecast the
astronomical tide (NOAA already publishes that exactly).

---

## 8. Live signals separation

Live pebbles (`noaa_tides`, `nws_alerts`, `nws_obs`, `ttm_forecast` and
the rest of the Touchstone/Lodestone Stones — §3.1) are fundamentally
different from the static Cornerstone layers and are handled
separately:

- **Surface**: in evidence cards and a "Right now" section in the UI.
- **Score**: explicitly excluded from the tier rubric (§5) — a live
  reading changing between two runs of the register builder
  shouldn't retier an asset that hasn't actually changed hazard class.
- **Cadence**: NOAA tides update every 6 min; NWS alerts on push;
  NWS obs ~hourly; TTM is computed per query (cheap).
- **Failure mode**: graceful. If NOAA times out, no `noaa_tides`
  doc is emitted; the reconciler simply doesn't see it.

This mirrors how First Street separates Flood Factor (static, 30-yr)
from event-day Flood Lab products, and how Fathom separates Global
Flood Map from real-time intelligence.

---

## 9. Repository layout

The repo root is `riprap/` (this document used to say `riprap-nyc/` —
that was the frozen HF Space's name, not the repo's). See README's
"Repository structure" section for the current top-level tree; it's
kept there rather than duplicated here, since a second copy is a
second place to go stale.

Two things worth calling out that aren't obvious from a file listing
alone:

- **`riprap/core/`** is the manifest-driven framework Section 3
  describes — `pebbles/` (registry, schema, adapters, shapers),
  `burr/` (the current Application: intake, per-Stone `MapActions`,
  capstone), `compliance/` (the 13 briefing-standards predicates).
  `riprap/mcp/` exposes Riprap as an MCP tool (`get_briefing`,
  `list_sources`, `get_citation`) on top of the same framework.
- **`app/`** predates that framework and still does real work: the
  original linear FSM (`fsm.py`, whose `step_reconcile` action
  `riprap/core/burr/capstone.py` reuses directly), the planner, the
  four `intents/` orchestration modules (`neighborhood.py`,
  `development_check.py`, `live_now.py`, and `single_address.py`'s
  `RIPRAP_USE_BURR_APP=0` fallback path), and every specialist data
  probe under `context/`, `flood_layers/`, `live/`, `assets/` — the
  actual Python functions a pebble manifest's `config.module` /
  `config.function` points at. Adding a pebble to a manifest usually
  doesn't mean writing new Python; it means pointing a manifest at one
  of these existing functions, or a new one shaped the same way.
- **`deployments/<city>/`** is a directory of pebble manifests +
  `stones.yaml` + (for NYC) the geospatial fixtures and policy corpus
  the manifests reference. `deployments/nyc/` is the reference
  deployment this whole document is written against.

---


## 10. Honest scope (what Riprap does NOT do)

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
  apartments or subway entrances. The dominant Hurricane Ida damage
  mode in NYC. Prithvi correctly emits no polygons for Hollis or
  Carroll Gardens. That silence is a feature, not a bug.
- **Vintage-bounded.** FEMA NFHL is years stale; DEP Stormwater Maps
  are 2021; corpus PDFs are point-in-time. All vintages are cited in
  the methodology panel.
- **Public infrastructure only.** ConEd substations, water-supply
  components, and other adversarially-sensitive registers are not
  published. NYC OD has the same redaction posture; we follow it.

---

## 11. Why local foundation models

1. **Data governance.** A newsroom with FOIL'd documents, an agency
   capital planner with internal data, or a researcher under IRB
   constraints can't paste organization context into a vendor LLM.
   All four models run inside this container; the org boundary
   holds. Public NYC and USGS services receive resolved address
   coordinates only; no LLM vendor does.
2. **Inference energy.** Granite 4.1 :3b draws roughly **0.03 Wh per
   query** vs an estimated **~0.3 Wh per query** for GPT-4o-class
   frontier models ([Epoch AI, 2025](https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use)).
   Order of magnitude lower per-query inference energy. The
   methodology panel reports a per-query Wh estimate so users can
   verify.
3. **Reproducibility.** Apache-2.0 stack end to end; no commercial
   licenses required to reproduce the system.

---

## 12. Deployment

### 12.1 Production topology (current)

Three live deployment shapes — full instructions in
[`docs/DEPLOY.md`](DEPLOY.md):

- **Modal** (scale-to-zero cloud GPU) — companion repo
  `msradam/riprap-inference` deploys two apps: the ML specialists
  (same codebase as the Mac Mini path below, GPU=L4) and Granite 4.1
  via vLLM (GPU=A100, its own image since vLLM pins its own torch).
  `modal/riprap_frontend.py` in this repo serves the app. $0 idle,
  roughly a minute or two cold start on a warm Volume.
- **Mac Mini / Apple Silicon** (fully local, no cloud) — Ollama-served
  Granite 4.1 + `riprap-inference`'s specialists run natively on one
  box, with real measured power via `powermetrics` (`app/power_mac.py`).
- **docker-compose** (self-host, any Linux box) — `Dockerfile.app` +
  an optional bundled-Ollama or GPU-specialist profile.

**HF Space** `lablab-ai-amd-developer-hackathon/riprap-nyc` (cpu-basic)
is a legacy, frozen demo: it serves the FastAPI + SvelteKit UI and
every deterministic data probe, but inferencing is disabled — no GPU
backend is wired to it.

<details>
<summary>Historical: the original AMD-judging deploy (MI300X droplet, decommissioned 2026-05-06)</summary>

The hackathon submission ran the HF Space against a separate AMD
MI300X droplet (vLLM + `services/riprap-models/` containers over
HTTP, `RIPRAP_LLM_BASE_URL` / `RIPRAP_ML_BASE_URL` pointed at it).
Verified warm query times on that setup (2026-05-06 probe):

- `single_address`: 5–12 s (4/4 Mellea, 0–2 rerolls)
- `neighborhood`: 3–5 s
- `compare` (two sequential legs): ~15 s

Cold-start after container restart: ~30 s for vLLM kernel JIT compile
+ prefix cache warmup. Reproducible against your own AMD GPU box via
`docker-compose --profile with-models` — see `docs/DEPLOY.md`.

</details>

### 12.2 Local development

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
ollama pull granite4.1:3b
ollama pull granite4.1:8b
uvicorn web.main:app --reload --port 8000

# Frontend (only when changing components)
cd web/sveltekit && npm install && npm run build
```

The fixtures in `data/` and the policy PDFs in `corpus/` are LFS-
tracked. Granite Embedding and TTM download on first query.

### 12.3 Diagnostic probes

```bash
# Drive the live stream N times, dump per-attempt Mellea outcomes:
.venv/bin/python scripts/probe_mellea.py --query "Hollis" --runs 5
# Output: outputs/probe_*.csv with per-attempt pass/fail, paragraph,
#         elapsed time, reroll count.
```

---

## 13. License

Apache-2.0. All foundation models (Granite 4.1, Granite Embedding,
Prithvi-EO 2.0, Granite TimeSeries TTM r2) and all input datasets
(NYC OpenData, USGS, NOAA, NWS, FloodNet NYC, NASA/MS Planetary
Computer for HLS Sentinel-2) are public. Visual idiom adapted from
[NYC Planning Labs](https://planninglabs.nyc/).
