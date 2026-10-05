<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

**The flood and heat record for any New York City block, cited line by line.**

Ask about an address, a community district such as QN12, or a question such as
"Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
or "Is Hunts Point hotter than the rest of the city?" Riprap answers in seconds
with a one-page briefing, and every sentence cites a public record and its date.

Rules or an open Granite model read your question and choose the evidence.
Every sentence you read comes word for word from a public record, with its
source and date.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/msradam/riprap/actions/workflows/check.yml/badge.svg)](https://github.com/msradam/riprap/actions/workflows/check.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

**[Browse the briefings](https://msradam.github.io/riprap/)** ·
**[Run it on your laptop](#quickstart)** ·
**[Build with us](#get-involved)**

## What it does

- Joins FloodNet street sensors, 311 flood complaints, two FEMA flood maps, the
  city's four stormwater flood maps, the Sandy extent and USGS Ida high-water marks for
  one address or community district.
- Cites every sentence with its source and the date of its data, ready to quote.
- Names the schools, subway entrances, public housing and hospitals inside the
  flood extents, for all 59 community districts.
- For heat, joins Landsat surface temperature, the Health Department's Heat
  Vulnerability Index and heat illness visits, the city's land cover map,
  station records, the Weather Service's forecast and alerts and NPCC4
  projections, each sentence with the caveat its figure needs (surface is not
  air temperature; an index is a rank, not a measurement).
- Returns the same evidence to code and AI agents, as JSON over HTTP and as seven
  MCP tools. Open source, open data, no GPU and no API keys.

One open model fine-tuned for New York (paved and green land from the latest
satellite imagery) adds sentences labelled experimental with their tested
accuracy. A second, a Battery surge forecast, lost to a one-line rule on
held-out data and is out of default briefings; a third, a satellite water
layer, was tested twice and retired. The results are
[below](#experimental-models). Riprap reports evidence, not advice.

A real answer, from the gallery entry
[Hollis, "since Ida"](https://msradam.github.io/riprap/gallery/hollis-since-ida/):

> **Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?**
>
> Yes. 2 FloodNet sensors within 600 m have recorded 6 flood events (each a
> series of depth readings above 10 mm at the sensor, FloodNet's definition)
> since they were installed on 2023-10-26, the most recent starting 2026-08-20
> 22:57 UTC [floodnet]. FloodNet's API lists 8 more events labelled flood here
> that are still to be verified by a person; Riprap counts verified events
> only [floodnet]. The highest depth in FloodNet's record for these sensors in
> that period is 1172 mm (46.1 in) on 2026-05-20, at a sensor listed as
> "noisy" in FloodNet's API when this was read (2026-10-05); that is the
> sensor's status now, which the API does not give for the day of the event
> [floodnet]. Among the sensors listed as good, the highest depth is 815 mm
> (32.1 in) on 2026-05-20 [floodnet]. 1 sensor with a status other than good
> recorded 3 of the 6 events; Riprap, not FloodNet, chooses to rest a yes or
> no answer only on events from sensors listed as good [floodnet]. USGS
> surveyed 2 Hurricane Ida high-water marks within 800 m of this address; the
> highest stood 0.76 ft above ground [ida_hwm]. Nearest mark: Intersection of
> 182nd St. and 90th Ave., Jamaica, Queens (174 m away, 0.7 ft above ground)
> [ida_hwm]. 88 NYC 311 flood-related complaints filed within 200 m of this
> location in the last 5 years: 48 sewer backup, 27 catch basin, 10 street
> flooding, 3 manhole overflow [nyc311]. A count of complaints is a count of
> reports filed, not of floods: a low count can mean under-reporting and not
> the absence of flooding, because the propensity to file a 311 request
> varies with income, language and demographics (Kontokosta, Hong and
> Korsberg, arXiv:1710.02452; Boxer, Hong, Kontokosta and Neill, Annals of
> Applied Statistics 19(2), 2025, doi:10.1214/24-AOAS2003) [nyc311].

(Read from the app on 5 October 2026. The gallery page shows the answer as it
stood when the gallery was last built.)

The "Yes." is set by a rule: at least one observed source reports flooding
since Ida, on 1 September 2021. This answer, like every gallery entry, was
made by the rules alone: no language model ran. The two depths are the same
storm at two sensors. FloodNet's API lists the sensor that read 46.1 in as
"noisy" today and does not say what its status was on the day, so Riprap
gives both readings, says which sensor each is from, and rests its yes or no
only on sensors listed as good. That last choice is Riprap's, not FloodNet's.
Riprap counts only the events FloodNet's API marks as verified by a person
(6 here) and says how many more the API labels flood but has not verified (8
here), which is why its count can sit below a count of everything the API
returns.

A heat answer, from
[Brighton Beach, "heat score"](https://msradam.github.io/riprap/gallery/brighton-heat-score/):

> **What is the heat score for 2940 Brighton 3rd St, Brooklyn?**
>
> Riprap computes no score or rating of its own. The Health Department
> publishes an index for the neighbourhood, quoted here with what it is and is
> not: The NYC Health Department's Heat Vulnerability Index (2023, from 2016 to
> 2020 data) scores Brighton Beach, the neighbourhood around this address, at
> 4 out of 5 [hvi]. The index ranks neighbourhoods against each other by a
> model of heat deaths, from surface temperature, green space, air
> conditioning, income and the share of Black residents; it is not a
> measurement of heat at an address, and the department notes that every
> neighbourhood has residents at risk, whatever its score. For Brighton Beach
> the department's file gives 86.6% of households with air conditioning (a
> survey estimate it shares across neighbouring neighbourhoods) and 14.1%
> green space [hvi].

A query about outdoor heat gets the heat briefing; a bare address or district
gets its flood briefing, with a link to the heat one. The heat briefing was
added in October 2026. It is built by the same method and tested against
independent keys and questions written without sight of the code
([docs/GROUNDING.md](docs/GROUNDING.md#heat-questions)); it has not been
through the head-to-head comparison the flood briefing has.

## What it does in one step

(This section is about the flood briefing.)

The records are public and each has its own map or portal, and other tools
read many of the same ones ([Related work](docs/BACKGROUND.md#related-work)).
Riprap's part is to do these four things together for one New York City
place:

- reads the observed record (311, FloodNet events, Ida high-water marks) and
  the mapped one (two FEMA maps, the city's four stormwater flood maps, the Sandy
  extent) for the same address in one step, and for a district its 311
  requests, its Sandy and stormwater shares and the city's floodplain counts;
- puts a source and a data date on every sentence, so a figure can be quoted
  with its citation;
- names the exposed assets of a district (which schools, which public housing
  developments, which subway entrances), by one method for all 59 districts;
- returns the same evidence to a program: over [MCP](#quickstart), each item
  with its figures, source URL and vintage, a digest of the result and the
  list of sources that failed to answer; over HTTP, the full result as JSON
  with its trace.

It also carries rules for the traps in these sources: which 311 descriptors
record flooding (the city renamed them in 2026), which sensor readings FloodNet
flags, which datum a base flood elevation is in, and when a zero means "the
source failed" and not "none".

## Works alongside the official sources

Riprap is built to sit beside the city's and federal tools, and links to them
where they are the authority.

| For | Authority |
|---|---|
| What is flooding right now | The [FloodNet dashboard](https://dataviz.floodnet.nyc/) shows street depth by the minute, the [National Weather Service](https://www.weather.gov/okx/) issues the warnings and [Notify NYC](https://a858-nycnotify.nyc.gov/) sends them to a phone. Riprap quotes sensor readings with their times and links there |
| An official flood zone determination | FEMA's [Map Service Center](https://msc.fema.gov/portal/home) |
| Insurance and what to do at home | [FloodHelpNY](https://www.floodhelpny.org) |
| A district's people and housing in the floodplain, on a city-made page | NYC Planning's [Community District Profiles](https://communityprofiles.planning.nyc.gov/) (Riprap quotes their counts) |
| Heat warnings, and where to cool off in a heat emergency | The [National Weather Service](https://www.weather.gov/okx/) issues heat advisories and [Notify NYC](https://a858-nycnotify.nyc.gov/) sends them; the city lists its cooling centers at [Cool Options](https://finder.nyc.gov/coolingcenters/) only while a heat emergency is on. Riprap quotes the forecast and alerts as the Weather Service's and points to the finder |
| Heat and health, by neighbourhood | The NYC Health Department's [Environment and Health Data Portal](https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/) (Riprap quotes its Heat Vulnerability Index and heat illness visits) |
| Maps to explore | Rebuild by Design's [Rainproof NYC Flood Map](https://rebuildbydesign.org/rainproof-nyc-map/) for 311 reports, sensors and green infrastructure near an address; the [EJNYC Mapping Tool](https://experience.arcgis.com/experience/6a3da7b920f248af961554bdf01d668b) for citywide layers |

Riprap comes after FloodNet's own dashboard, Rebuild by Design's Rainproof NYC
map, the City's Stormwater Flood Maps viewer and EJNYC mapping tool,
FloodHelpNY, NYU's GeoFlood Studio, and BetaNYC's Urban Heat Portal, BoardStat
and MCP servers for city data. What each is, and how Riprap differs from or
defers to it, is in [Related work](docs/BACKGROUND.md#related-work).

**Riprap is not an alert or emergency service.** For emergency alerts, sign up
with [Notify NYC](https://a858-nycnotify.nyc.gov/); to report flooding or ask
the city for help, use [311](https://portal.311.nyc.gov/); for flood insurance
questions, see [FloodHelpNY](https://www.floodhelpny.org).

## Who it is for

Data journalists, community board and council staff, resilience analysts,
civic technologists and researchers who need source-linked numbers about flood
and heat exposure in a place. Not for resident decisions, real estate, lending,
insurance or hydraulic design. Riprap does not give advice, score a property
or make a regulatory flood determination, it does not say whether a
particular place will flood on a particular day or how hot one building will
get, and it gives no health or safety advice. More in
[docs/BACKGROUND.md](docs/BACKGROUND.md).

## What it cannot tell you

A briefing describes public records about a place. It is not a judgement on a
property or on the people who live there. The records have limits, and each
is sourced in [docs/METHODOLOGY.md](docs/METHODOLOGY.md#10-what-the-data-cannot-say):

- 311 counts are complaints filed, not floods measured, and research finds
  that some neighbourhoods report less often for the same conditions. A low
  count is not a dry block.
- The city's stormwater maps are modelled scenarios. The city says its map
  "does not provide the exact depth of flooding at any location".
- Outside a mapped area is not safe: NYC Emergency Management reports that in
  Hurricane Ida the most heavily impacted areas, "representing over half of
  all damaged buildings, were also outside of any flood risk scenario".
- A FloodNet depth is a point measurement under one sensor, not the depth
  along a street. "Within 600 m" is not "on this block".
- Surface temperature is not air temperature, and the Heat Vulnerability
  Index is a rank: the Health Department says "a neighborhood with low
  vulnerability does not mean no risk".
- Riprap is in English only.

The distances, time windows and complaint types behind each count are in one
table a count can be rerun from
([docs/METHODOLOGY.md](docs/METHODOLOGY.md#11-distances-time-windows-and-filters)).
Riprap is built by one person. No community group, agency or resident has yet
shaped or tested it. If a sentence is wrong, or you know of flooding or heat
the records miss, [open an issue](https://github.com/msradam/riprap/issues/new/choose):
corrections are recorded in the [changelog](CHANGELOG.md), and an account of
what the records miss is kept on the tracker, since Riprap has no way yet to
put it into a briefing.

## Status

| Area | Status |
|---|---|
| New York City flood | Production: 25 public sources (22 read for an address, 20 for a neighbourhood or district), questions, and all 59 community districts |
| New York City heat | New in October 2026: 10 public sources for an address and 11 for a district or borough, questions, comparisons of two places, and all 59 community districts. No model: the forecast is the National Weather Service's |
| Chicago, Seattle, Albany | Experimental: federal sources plus a reviewed 311 flood filter and a water-level gauge ([docs/multi-city.md](docs/multi-city.md)) |
| Models | None required, and none runs by default. An optional open LLM (Granite) routes questions the rules do not recognise and chooses among existing sentences; it writes no sentence or number of a briefing, and no yes or no stands on its word. One experimental model (paved and green land) adds sentences, always labelled; a second (a surge forecast) is off unless a server opts in, because a simple rule beat it ([below](#experimental-models)) |
| Checks | Citations and numbers on every claim, rules on answer leads, 13 disclosure checks. They are patterns and rules: they do not read meaning and can miss a wrong inference ([docs/GROUNDING.md](docs/GROUNDING.md)) |

## Quickstart

You need [uv](https://docs.astral.sh/uv/) and [Git LFS](https://git-lfs.com).
No GPU and no API keys.

```bash
git clone https://github.com/msradam/riprap && cd riprap
git lfs install && git lfs pull
uv sync
uv run uvicorn web.main:app --port 7860
```

Open <http://localhost:7860> and type an address (`90-01 183rd Street, Queens`),
a district (`QN12`) or a question (`Has 80 Pioneer Street, Brooklyn flooded?`).
A question is answered by rules, with no model (the JSON reports
`answer_path` as `rules`); one the rules do not recognise gets the
cited evidence for its place, and the page says it was not answered. The first
district query on a cold server takes about half a
minute while the layers load. Every briefing text opens, after its scope
statement, with a "Place described: ..." paragraph that names the place it was
answered for. The same briefing from the command line:

```bash
curl -s "http://localhost:7860/api/agent?q=QN12" | python3 -c "import json, sys; print(json.load(sys.stdin)['paragraph'])"
```

**With an LLM (optional).** The rules answer first; a model is called only
when no rule handles the query. Any
OpenAI-compatible endpoint works. With
[Ollama](https://ollama.com):

```bash
ollama pull hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 \
RIPRAP_LLM_MODEL=hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M \
  uv run uvicorn web.main:app --port 7860
```

**MCP server.** `uv run riprap-mcp` serves seven tools over stdio
(`get_evidence`, `get_district_summary`, `get_briefing`,
`nyc311_flood_requests`, `plan_query`, `list_sources`, `get_citation`); every
tool works without an LLM. Each evidence item carries its sentence, the
source's own figures (`value`), its `source_url` and `vintage`. Every result
carries a `record` block (query, time, version, commit, SHA-256 of the body)
and a `failed` list naming sources that did not answer. FloodNet items carry
their own licence (`license_notices`), and `place_note` says which area a
neighbourhood name was answered for. Over HTTP the same note is
`geocode.note`, `answer_path` (`rules` or `llm`) says which path answered,
`failed` lists the sources that were tried and did not answer, and
`not_checked` lists the sources that were not read.
Try one from the command line with the MCP Inspector (needs Node):

```bash
npx @modelcontextprotocol/inspector --cli uv run riprap-mcp \
  --method tools/call --tool-name get_district_summary --tool-arg community_district=QN12
```

**Gallery.** `uv run python scripts/build_gallery.py` rebuilds every entry in
`web/sveltekit/src/lib/gallery/` (35 entries: for flood 12 addresses, 3
community districts and 10 questions; for heat 3 places and 7 questions),
with no model. FloodNet's per-sensor and per-event records are taken out of
each saved file, since its licence forbids reposting them. To see them in the app, rebuild the frontend (needs
Node and [pnpm](https://pnpm.io)): `cd web/sveltekit && pnpm install && pnpm
build`. The landing's scrolling preview is the text of the Hollis "since Ida"
entry, read from its saved file at build time, so it follows a rebuild with
no screenshot to retake. Docker and the Modal host are in
[docs/DEPLOY.md](docs/DEPLOY.md).

## How it works

Every sentence is written by code from one record, and carries that record's
source and the date of its data. A question is answered by rules over its own
words: they pick which of those sentences answer it and whether the evidence
supports a yes or a no. No language model is needed. An optional LLM can route
questions the rules do not recognise; it chooses among the same cited
sentences and code checks its choice.

Each data source is a YAML manifest (a "pebble"). For every query they run in
parallel, grouped into five roles:

| Stone | Role | Examples |
|---|---|---|
| Cornerstone | What the ground remembers | Sandy extent, DEP and FEMA maps, Ida high-water marks, terrain |
| Keystone | What is exposed | Subway entrances, public housing, schools, hospitals |
| Touchstone | What has been observed | FloodNet sensors, 311 requests, weather, tide and stream gauges |
| Lodestone | What is coming | NWS alerts, the NWS water-level forecast, sea-level projections |
| Capstone | The briefing | The cited sentences, and the answer chosen from them |

More in [docs/METHODOLOGY.md](docs/METHODOLOGY.md),
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/GROUNDING.md](docs/GROUNDING.md).

## How Riprap was built and where a model runs

This section follows the City's guidance to "disclose when content is
generated or assisted by GenAI" and BetaNYC's practice of saying which model
was used, what for, and who checked it.

**In a briefing.** By default no language model runs: the public gallery and
a fresh install answer by rules. A person running their own copy can connect
an open model (tested with IBM's Granite 4.1 8B on a laptop). It is called
only when no rule handles the query. In planning it may set the intent among
six (code overrides it when the parser found an address or a district), the
target text, the focus, and which sources run beyond a fixed floor; it also
writes a rationale of at most 300 characters, which appears only in the JSON
plan and the stream's plan event, never in the briefing. In answering it may
propose a lead (yes, no, partly, a count, cannot answer) and pick up to four
existing sentences and their order. Code overrides the lead for questions
about a past event, about now and about a forecast, requires a yes-or-no
question shape, and checks the lead against the cited figures: a failure is
sent back once, then the lead and the picks are dropped. By default it cannot
write a sentence or a number in a briefing. Each answer says which path made
it (`answer_path`, also `grounding.answer_mode`, and a line on the page).
`RIPRAP_LLM_BARE=1`, off by default, is the one mode in which a model
rewrites evidence as sentences, checked for citation ids and numbers
([docs/GROUNDING.md](docs/GROUNDING.md#llm-mode)).

**Experimental models.** One fine-tuned open model adds labelled sentences;
a second is off by default after losing to a simple rule, and a third was
tested and retired ([below](#experimental-models)).

**In building Riprap.** AI coding agents wrote most of Riprap's code, tests
and documents, working from prompts written by the maintainer, and agent
sessions also reviewed that work. The maintainer, Adam Munawar Rahman,
directed it, decides what Riprap claims, and is accountable for all of it.
The output was checked by automated tests, by sets of test questions with
answer keys (some written without sight of the code,
[docs/GROUNDING.md](docs/GROUNDING.md)), and by an independent sanity check on
5 October 2026 that worked from the code, the public sources and the app's
output before reading any project document. It re-derived 487 briefing
sentences from the sources with separate code: 475 were confirmed, 10 were
wrong and 2 sat on a raster edge. The 10 came from three defects (an address
elevation read from a neighbouring cell, hospitals counted twice, a
construction permits count); the first two are corrected and the permits
sentence was taken out of plain briefings. The check was itself run by AI
coding agents, working read-only and independently of the agents that wrote
the code, under the maintainer's direction. Its method, its figures and what
was done about each of its 31 problems are in
[docs/history/SANITY-CHECK-2026-10-05.md](docs/history/SANITY-CHECK-2026-10-05.md).
The repository records no audit by a person outside the project.

## Experimental models

Riprap is an app in development, and its author fine-tuned three open models
for it. None has been shown to beat an official product, so their output is
never a measurement: every sentence from one opens with "Experimental" or
"Experimental forecast", states the model's limits and its tested accuracy,
and names the official source to rely on. For a question about the past or
the present they never set the answer's yes or no. One rule in
[`app/experimental.py`](app/experimental.py) writes all of it. Two of the
three are now out of default briefings, and the tests that put them there are
published with them.

| Model | Status | What the tests say |
|---|---|---|
| [NYC land-cover model](docs/MODELS.md#nyc-land-cover-model) (TerraMind 1.0 base, fine-tuned here) | In briefings, after the sentence from the city's 2017 land cover map | Trained on the city's 2017 six-inch land cover map and tested against The Nature Conservancy's 2021 map on squares it never trained on: a typical district's paved share reads 1.7 points above the map's, and two images of one year differ by under 2.0 points 19 times in 20. Its citywide tree canopy reads 4.2 to 5.0 points below the city's 2017 map in three of its four yearly maps and 3.2 above in one. Maps of different summers differ by more than the model's error, so it is not used to read change between years. The city's 2017 map, read as 2021, is still closer to the 2021 map (3.0 points mean error per group) than the model (4.8 at best), so the map is quoted first |
| [Granite TTM r2 Battery Surge](docs/model-cards/Granite-TTM-r2-Battery-Surge.md) | Out of default briefings since 2026-10-05; a server opts in | A negative result. On 639 held-out four-day windows (January 2025 to October 2026, none overlapping its training data) its mean error was 0.115 m. Damped persistence, a one-line rule, scored 0.108 m and beats it (difference 0.0065 m, 95% interval 0.0032 to 0.0096). The month's usual value scored 0.116 m, the mean of the input 0.119 m, the last value held 0.133 m and the tide table alone 0.167 m. It foresaw 1 of the 23 windows that reached flood stage, which are 5 distinct events |
| Satellite water layer (Prithvi-EO 2.0 NYC Pluvial) | Retired 2026-10-02 | On Hurricane Ida and on 44 coastal and tidal flood moments that FloodNet sensors recorded at the instant of a satellite pass, it and IBM and ESA's official flood model found flooding no more often than chance ([docs/MODELS.md](docs/MODELS.md#the-satellite-water-layer-retired-2026-10-02)) |

The surge forecast adds little to the tide table and the Weather Service's
own water-level forecast, which Riprap already quotes, so it no longer runs
unless a server sets `RIPRAP_EXTRA_MANIFESTS=deployments/nyc/optional` and
installs the `ml` extra (`uv sync --extra ml`); it never runs inland. The
[model card hosted on Hugging Face](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge)
is out of date: it claims a larger improvement than the held-out test shows
and gives the model's size as 1.5 million parameters where the published file
holds 2,964,960. The corrected card is
[docs/model-cards/Granite-TTM-r2-Battery-Surge.md](docs/model-cards/Granite-TTM-r2-Battery-Surge.md).

The land-cover model runs in a batch job with the `eo` extra, and the app
reads its saved maps with no extra. What each model can and cannot answer,
the backtests and how to rerun them are in [docs/MODELS.md](docs/MODELS.md).
The surge and water models are reproduced independently at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models).

## Data sources

A New York City flood briefing reads 25 public sources (a source read for a
point and for an area is counted once): 21 from the NYC deployment and 4 federal
ones (FEMA flood zones, NWS observations and alerts, USGS stream gauges). A
heat briefing reads 10 for an address and 11 for a district; two of them, the
city's land cover map and the area outlines, are shared with flood. All are
public-record city, state and federal data; there are no commercial APIs and
Riprap computes no scores. The land-cover model also reads Copernicus
Sentinel-2 imagery, and the surface temperature record is from USGS Landsat. Each manifest records its URL, licence and
vintage. The full list is in [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md).

## Privacy

No accounts, no cookies and no analytics. The server keeps a short-lived local
cache of public-data responses and no database of queries (a web server's access
log, if you keep one, holds the URLs asked). 311 free text is
redacted of email addresses and phone numbers when it is fetched; names are not
redacted. Addresses are sent to geocoders, the map loads its background tiles
from CARTO, and a configured LLM receives the question and evidence. Details and a do-no-harm note:
[docs/PRIVACY.md](docs/PRIVACY.md).

## Accessibility

The web app is built to meet WCAG 2.2 Level AA, the standard the City of New
York adopted in December 2025. It is tested with axe-core and a contrast
gate and was reviewed in the code; no assistive technology user has tested
it, and the statement does not claim conformance. What was tested, the known
limits (the map, the print view, English only) and how to report a barrier:
[docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md).

## Get involved

- Add your city: [docs/PORT-YOUR-CITY.md](docs/PORT-YOUR-CITY.md)
- [Contributing](.github/CONTRIBUTING.md) ·
  [Code of conduct](.github/CODE_OF_CONDUCT.md) ·
  [Security](.github/SECURITY.md) · [Changelog](CHANGELOG.md) ·
  [All docs](docs/INDEX.md)

## Cite, licence, acknowledgments

Cite with [CITATION.cff](CITATION.cff). Apache 2.0: see [LICENSE](LICENSE) and
[NOTICE](NOTICE). Data sources keep their own terms, recorded in each manifest.

Riprap is an independent project. It is not endorsed by or affiliated with
FloodNet, New York University, the City University of New York, FEMA, NOAA,
USGS, the City of New York or any agency, and it is not a City product. The
City publishes its open data for information only and does not warrant its
completeness, accuracy, content or fitness for any use (Local Law 11 of 2012).

**FloodNet data.** Sensor data: FloodNet (New York University and The City
University of New York), licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The
FloodNet sentences and figures in a briefing, in the JSON and in the MCP
results are derived from that data and carry the same licence, for
non-commercial use with attribution and under the same terms. They are not
covered by Riprap's Apache-2.0 licence ([NOTICE](NOTICE)), and each carries the
time it was read. References: Mydlarz, C., et al. (2024), "FloodNet: Low-cost
ultrasonic sensors for real-time measurement of hyperlocal, street-level
floods in New York City", *Water Resources Research* 60, e2023WR036806,
<https://doi.org/10.1029/2023WR036806>; Silverman et al. (2022), "Making
Waves", *Water Research*, 118648,
<https://doi.org/10.1016/j.watres.2022.118648>. Riprap reads FloodNet's Data
API (an early-access beta) and counts only the events it marks as verified by
a person. Questions about a reading belong to FloodNet.

Thanks, which imply no backing by anyone named: to AMD Developer Cloud and
the AMD x lablab.ai Developer Hackathon, where Riprap began and where its
first three models were trained; to IBM Research for publishing Granite; to
NYU's Center for Urban Science and Progress; and to Andrew Hicks for the
introduction to the ASCE network.

The experimental models are fine-tunes of other people's work: NASA and IBM's
[Prithvi-EO 2.0](https://huggingface.co/ibm-nasa-geospatial), IBM and ESA's
[TerraMind 1.0](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base)
and IBM's [Granite TTM r2](https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2),
all Apache 2.0 (Prithvi-EO 2.0 was the base of the retired water layer). The surge and water fine-tunes and their evaluation are at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models);
the land-cover model is trained and scored by `scripts/train_cover.py` and
`scripts/eval_cover.py` on NYC's land cover maps (2017 from NYC Open Data for
training; 2021 from The Nature Conservancy and the University of Vermont,
CC BY-NC-SA 4.0, used only to score it).
Their limits are Riprap's to state, not their makers'. Satellite imagery is
Copernicus Sentinel data, read through Microsoft's Planetary Computer.

The dam mark is ["Dam" by Chintuza](https://thenounproject.com/icon/dam-4516918/)
via the Noun Project, licensed CC-BY 3.0.
