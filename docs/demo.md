# Riprap MVP demo: flood, heat, air

The "open-source climate briefing tool" MVP, in three deployments. Same
code, same Burr graph, same disclosure checks, same web UI. Three
hazards, three `deployments/` directories, no per-hazard code branches.

## What the demo shows

Today only the flood briefing runs. Per-query routing picks a deployment
by its coverage bounding box, and `deployments/heat` and `deployments/air`
have none, so items 2 and 3 describe scaffolds that a query never reaches
(and the planner refuses heat and air questions as out of scope).

1. **Flood briefing** at an NYC address, the reference deployment.
   31 pebbles (23 point, 8 area) across Cornerstone, Keystone, Touchstone
   and Lodestone, and the 13 disclosure checks.
2. **Heat briefing** at the same address (`deployments/heat/`): NYC HVI,
   NYC Forestry, NWS observations and NWS alerts. Same UI; the
   `stones.yaml` taglines drive different section headings.
3. **Air-quality briefing** at the same address (`deployments/air/`):
   NWS air alerts plus (optional) EPA AirNow. Same UI again.

Each is a real run end to end, and each passes the 13 disclosure checks:
substring tests for caveat phrases drawn from FEMA, IPCC AR6, TCFD,
ASTM E1527-21, EPA/CDC CERC, AP Stylebook and SPJ Code of Ethics
guidance. A pass means the phrases are present, not that the briefing
is good.

## Setup

```bash
uv sync --extra ml
uv run uvicorn web.main:app --port 7860
```

Open `http://127.0.0.1:7860/`. With no LLM endpoint configured, every
briefing is the no-LLM evidence briefing ([`GROUNDING.md`](GROUNDING.md)).

## The demo flow

### 1. Flood, the reference briefing

Default deployment (`deployments/nyc`). Open in the browser:

```
http://127.0.0.1:7860/q/189%20Atlantic%20Ave%2C%20Brooklyn
```

Or via the API:

```bash
curl "http://127.0.0.1:7860/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{intent, compliance, paragraph_chars: (.paragraph | length)}'
```

What lands: an "In brief" lead (Sandy footprint, FEMA zone, DEP
scenarios, 311 count, each part cited and checked by the claim verifier),
then one cited sentence per pebble that returned a value, grouped by
Stone, and the disclosure-check result under `compliance`.

### 2. LLM mode, same evidence

Restart with an OpenAI-compatible endpoint, for example local Ollama:

```bash
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 RIPRAP_LLM_MODEL=granite4:micro \
  uv run uvicorn web.main:app --port 7860
```

The model rewrites the same evidence as JSON claims; code checks each
claim's citations and numbers and drops the ones that fail. Dropped
claims are listed in `dropped_claims`, never rendered. The disclosure
checks run the same way. `RIPRAP_RECONCILER_TIER=no_llm` forces no-LLM
mode even when an endpoint is set.

### 3. Heat deployment: same code, different YAML directory

> **Historical.** Per-query routing picks a deployment by the bounding
> box in its `stones.yaml` (`coverage:`), and `deployments/heat` and
> `deployments/air` have none. The planner also refuses heat and air
> questions as out of scope. `RIPRAP_DEPLOYMENT` does not override the
> routing, so these commands produce the NYC flood briefing today.

Restart pointing at the heat manifests:

```bash
RIPRAP_DEPLOYMENT=deployments/heat \
RIPRAP_BRIEFING_SCOPE=heat-exposure \
  uv run uvicorn web.main:app --port 7860
```

```bash
curl "http://127.0.0.1:7860/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{compliance, paragraph}'
```

What lands:

```
This is an automated heat-exposure briefing produced by Riprap from live
and baked data sources. It is informational only and not a substitute
for a professional risk assessment.

**Heat Hazard Reader.**
NYC DOHMH Heat Vulnerability Index for the surrounding NTA, current
methodology [nyc_hvi]. NYC Forestry recorded 0 street tree(s) within
200 m of this address in the 2015 census [tree_canopy].

**Live Observer.**
Most recent NWS hourly observation at the nearest METAR station:
temperature, humidity, and dewpoint [nws_obs].

**Projector.**
Currently active NWS alerts intersecting this address: heat
advisories, excessive heat warnings, and related public-health alerts
[nws_alerts].

**Out of scope.** This briefing does not assess title, structural
condition, or compliance with specific zoning rules. Where a probe
was offline at run time, the relevant section omits that signal.
```

13/13 disclosure checks present. Section headings (`Heat Hazard Reader`, `Live Observer`,
`Projector`) auto-derived from `deployments/heat/stones.yaml`.

### 4. Air-quality deployment: third hazard, same architecture

```bash
RIPRAP_DEPLOYMENT=deployments/air \
RIPRAP_BRIEFING_SCOPE=air-quality \
  uv run uvicorn web.main:app --port 7860
```

```bash
curl "http://127.0.0.1:7860/api/agent?q=189%20Atlantic%20Ave%2C%20Brooklyn" \
  | jq '{compliance, paragraph}'
```

What lands:

```
This is an automated air-quality briefing produced by Riprap from live
and baked data sources. It is informational only and not a substitute
for a professional risk assessment.

**Live Observer.**
Currently active NWS alerts intersecting this address: air-quality,
smoke, and particulate advisories [nws_alerts].

**Out of scope.** ...
```

The air deployment is currently thinner (just `nws_alerts` working out
of the box). With an EPA AirNow API key set in `RIPRAP_AIRNOW_API_KEY`,
the `epa_airnow` pebble adds live AQI / PM2.5 / ozone for the address's
25-mile radius. Free key from [AirNow](https://docs.airnowapi.org/).

## What the demo proves

- **Architecture is hazard-agnostic in its code.** A deployment is a
  directory of manifests with no per-hazard code. Today only flood is
  reachable: making heat or air answer needs a coverage bounding box
  for them and planner support for heat and air questions.
- **Disclosures are present.** The flood briefing passes the 13 disclosure checks
  (caveat-phrase substring tests drawn from FEMA / IPCC / TCFD / ASTM /
  EPA / AP / SPJ). The check result ships in every response. It is not
  a quality score.
- **Two modes ship side by side.** No-LLM mode prints the evidence
  sentences; LLM mode returns claims checked in code for citations and
  numbers against the same evidence. Same disclosure checks, same UI.
- **In-process models stay on a clean lineage.** Granite TTM r2 (IBM,
  NOAA gauge data), Granite Embedding 278M (IBM), Flair NER (OntoNotes
  5.0, human-labeled LDC). The offline Prithvi-EO 2.0 layer is NASA/IBM
  on public HLS and Sentinel-2 imagery. None of these was trained on
  closed-LLM synthetic data.
- **BYOD works.** Anyone can drop a new pebble YAML pointing at a REST
  API, CSV, or GeoJSON (local or URL) and add it to any deployment.

## Demo cheat-sheet: switching deployments

> **Historical.** Per-query routing picks a deployment by the bounding
> box in its `stones.yaml` (`coverage:`), and `deployments/heat` and
> `deployments/air` have none. The planner also refuses heat and air
> questions as out of scope. `RIPRAP_DEPLOYMENT` does not override the
> routing, so these commands produce the NYC flood briefing today.

```
# Flood (the production reference)
RIPRAP_DEPLOYMENT=deployments/nyc

# Heat
RIPRAP_DEPLOYMENT=deployments/heat
RIPRAP_BRIEFING_SCOPE=heat-exposure

# Air quality
RIPRAP_DEPLOYMENT=deployments/air
RIPRAP_BRIEFING_SCOPE=air-quality
```

Restart the server after any change.

## Known gaps in the MVP

- **`nyc_hvi` pebble** in the heat deployment uses the canonical NYC
  Open Data HVI dataset (`4mhf-duep`), but HVI is keyed by ZCTA, not
  point. The spatial join hasn't been built yet, so the pebble returns
  no features and has no HVI rank to report. Followup:
  ZCTA-boundary join adapter.
- **NYC Community Air Survey** (NYCCAS) is a raster dataset; raster
  adapter isn't built yet. Followup: `baked_raster` adapter.
- **Wildfire and wind** are tier-1 hazards per the research scoping
  doc; not in the MVP three. Followup: `deployments/wildfire/` and
  `deployments/wind/`.
- **Equity overlay** (CDC SVI + EPA EJScreen) is the unique OSS
  differentiator vs commercial closed-source tools. Not in MVP three.
  Followup: cross-cutting layer that runs alongside the active hazard
  deployment.

None of these are blockers for "demonstrate the three-hazard MVP."
They're the obvious next moves.
