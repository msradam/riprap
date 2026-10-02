<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

**The flood record for any New York City block, cited line by line.**

Ask about an address, a community district such as QN12, or a question such as
"Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
Riprap answers in seconds with a one-page briefing, and every sentence cites a
public record and its date.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/msradam/riprap/actions/workflows/check.yml/badge.svg)](https://github.com/msradam/riprap/actions/workflows/check.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

![Riprap answering "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?" with a cited "Yes."](assets/screenshots/hero.png)

**[Browse the briefings](https://msradam.github.io/riprap/)** ·
**[Run it on your laptop](#quickstart)** ·
**[Build with us](#get-involved)**

## What it does

- Joins FloodNet street sensors, 311 flood complaints, two FEMA flood maps, three
  city stormwater scenarios, the Sandy extent and USGS Ida high-water marks for
  one address or community district.
- Cites every sentence with its source and the date of its data, ready to quote.
- Names the schools, subway entrances, public housing and hospitals inside the
  flood extents, for all 59 community districts.
- Returns the same evidence to code and AI agents, as JSON over HTTP and as seven
  MCP tools. Open source, open data, no GPU and no API keys.

Three open models fine-tuned for New York (a Battery surge forecast, satellite
water after storms, paved and green land) are labelled experimental with their
tested accuracy: [help improve them](#experimental-models). Riprap reports evidence, not advice.

A real answer, from the gallery entry
[Hollis, "since Ida"](https://msradam.github.io/riprap/gallery/hollis-since-ida/):

> **Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?**
>
> Yes. 2 FloodNet community sensors within 600 m have logged 14 above-curb
> flood events in the last 3 years, the most recent starting 2026-09-01 05:39
> UTC [floodnet]. Peak depth recorded by the sensors in good working order: 815
> mm (32.1 in) on 2026-05-20 [floodnet]. 1 sensor that logged 11 of these
> events is flagged by FloodNet for maintenance, so its depths are not used for
> the peak [floodnet]. The highest depth a flagged sensor recorded was 1172 mm (46.1 in)
> on 2026-05-20 [floodnet]. USGS surveyed 2 Hurricane Ida high-water marks
> within 800 m of this address; the highest stood 0.76 ft above ground; the
> highest water surface elevation was 48.2 ft NAVD88 [ida_hwm]. Nearest mark:
> Intersection of 182nd St. and 90th Ave., Jamaica, Queens (174 m away)
> [ida_hwm]. 89 NYC 311 flood-related complaints filed within 200 m of this
> location in the last 5 years: 48 sewer backup, 28 catch basin, 10 street
> flooding, 3 manhole overflow [nyc311].

The "Yes." is set by a rule: at least one observed source reports flooding
since Ida, on 1 September 2021. No language model wrote or chose any of it.
The two depths are the same storm at two sensors: FloodNet flags the one that
read 46.1 in, so Riprap takes the peak from the other and says so.

## What it does that other tools do not

The records are public and each has its own map or portal. As of October 2026
we know of no other tool that does these four things together for New York
City:

- reads the observed record (311, FloodNet events, Ida high-water marks) and
  the mapped one (two FEMA maps, three city stormwater scenarios, the Sandy
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
| Maps to explore | Rebuild by Design's [Rainproof NYC Flood Map](https://rebuildbydesign.org/rainproof-nyc-map/) for 311 reports, sensors and green infrastructure near an address; the [EJNYC Mapping Tool](https://experience.arcgis.com/experience/6a3da7b920f248af961554bdf01d668b) for citywide layers |

## Who it is for

Data journalists, community board and council staff, resilience analysts,
civic technologists and researchers who need source-linked numbers about flood
exposure in a place. Not for resident decisions, real estate, lending,
insurance or hydraulic design. Riprap does not give advice, score a property
or make a regulatory flood determination, and it does not say whether a
particular place will flood on a particular day. More in
[docs/BACKGROUND.md](docs/BACKGROUND.md).

## Status

| Area | Status |
|---|---|
| New York City flood | Production: 23 public sources (20 read for an address, 18 for a neighbourhood or district), questions, and all 59 community districts |
| Chicago, Seattle, Albany | Experimental: federal sources plus a reviewed 311 flood filter and a water-level gauge ([docs/multi-city.md](docs/multi-city.md)) |
| Models | None required, and none writes a sentence or sets a yes or no. An optional LLM routes questions the rules do not recognise. Three experimental models (a surge forecast, satellite water, paved and green land) add sentences, always labelled ([below](#experimental-models)) |
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
`grounding.answer_mode` as `rules`); one the rules do not recognise gets the
cited evidence for its place, and the page says it was not answered. The first
district query on a cold server takes about half a
minute while the layers load. `uv sync --extra ml` adds the
[experimental](#experimental-models) surge forecast. The same briefing from the command line:

```bash
curl -s "http://localhost:7860/api/agent?q=QN12" | python3 -c "import json, sys; print(json.load(sys.stdin)['paragraph'])"
```

**With an LLM (optional).** The rules answer first; a model is asked only
when they do not recognise a question or cannot read its place. Any
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
and a `failed` list naming sources that did not answer.
Try one from the command line with the MCP Inspector (needs Node):

```bash
npx @modelcontextprotocol/inspector --cli uv run riprap-mcp \
  --method tools/call --tool-name get_district_summary --tool-arg community_district=QN12
```

**Gallery.** `uv run python scripts/build_gallery.py` rebuilds every entry in
`web/sveltekit/src/lib/gallery/` (12 addresses, 3 community districts and 12
questions), with no model. To see them in the app, rebuild the frontend (needs
Node and [pnpm](https://pnpm.io)): `cd web/sveltekit && pnpm install && pnpm
build`. The landing's scrolling preview is a screenshot of the Hollis "since
Ida" entry: after rebuilding that entry, retake it with the app running
(`cd web/sveltekit && node scripts/capture-hero-preview.mjs
http://127.0.0.1:7860`), then build again. Docker and the Modal host are in
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

## Experimental models

Riprap is an app in development, and three models its author fine-tuned are
part of it (the land-cover one in this repository, with its weights kept
local). None has been shown to beat an official product, so their output
is never a measurement: every sentence from one opens with "Experimental" or
"Experimental forecast", states the model's limits and its tested accuracy, and
names the official source to rely on. For a question about the past or the
present they never set the answer's yes or no. One rule in
[`app/experimental.py`](app/experimental.py) writes all of it.

| Model | What it answers | What the tests say |
|---|---|---|
| [Granite TTM r2 Battery Surge](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge) | How far above the predicted tide the water at the Battery may run in the next four days, and whether the total reaches the gauge's flood stage | On 635 four-day windows since January 2025 its mean error was 11.5 cm, against 13.3 cm for holding the last day's mean. It foresaw 1 of the 23 windows in which the water reached the minor flood stage |
| [Prithvi-EO 2.0 NYC Pluvial](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial) | Where satellite scenes showed new surface water after Hurricane Ida, and after which other heavy rains it showed any | Of 153 high-water marks surveyed after Ida, it showed new water within 500 m of 17 (11%), not yet better than chance (14%). It cannot see street or basement flooding, and it is not used to say a place is prone to standing water |
| [NYC land-cover model](docs/MODELS.md#nyc-land-cover-model) (TerraMind 1.0 base, fine-tuned here) | How much of a place is paved or built over, how much is green and how much is tree canopy, from the latest summer's satellite scenes, after the sentence from the city's own 2017 land cover map | Trained on the city's 2017 six-inch land cover map and tested against its 2021 map on squares it never trained on: a typical district's paved share reads 1.7 points above the map's, and two images of one year differ by under 2.0 points 19 times in 20. The adapter it replaced read 16 to 18 points high against the same map. Maps of different summers differ by more than that, so it is not used to read change between years. The city's 2017 map, read as 2021, is still closer to the 2021 map (3.0 points mean error per group) than the model (4.8 at best), so the map is quoted first |

The surge model runs on CPU when the `ml` extra is installed
(`uv sync --extra ml`); without it the app says the model is not installed.
The two satellite models run in batch jobs with the `eo` extra, and the app
reads their saved output with no extra. What each can and cannot answer, the
backtests and how to rerun them are in [docs/MODELS.md](docs/MODELS.md). The
surge and water models are reproduced independently at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models).

## Data sources

A New York City briefing reads 23 public sources (a source read for a point
and for an area is counted once): 19 from the NYC deployment and 4 federal ones
(FEMA flood zones, NWS observations and alerts, USGS stream gauges). All are
public-record city, state and federal data; there are no commercial APIs and no
scores. The experimental satellite layers also read Copernicus Sentinel-2
imagery. Each manifest records its URL, licence and
vintage. The full list is in [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md).

## Privacy

No accounts, no cookies and no analytics. The server keeps a short-lived local
cache of public-data responses and no database of queries (a web server's access
log, if you keep one, holds the URLs asked). 311 free text is
redacted of email addresses and phone numbers when it is fetched; names are not
redacted. Addresses are sent to geocoders, the map loads its background tiles
from CARTO, and a configured LLM receives the question and evidence. Details and a do-no-harm note:
[docs/PRIVACY.md](docs/PRIVACY.md).

## Get involved

- Add your city: [docs/PORT-YOUR-CITY.md](docs/PORT-YOUR-CITY.md)
- [Contributing](.github/CONTRIBUTING.md) ·
  [Code of conduct](.github/CODE_OF_CONDUCT.md) ·
  [Security](.github/SECURITY.md) · [Changelog](CHANGELOG.md) ·
  [All docs](docs/INDEX.md)

## Cite, licence, acknowledgments

Cite with [CITATION.cff](CITATION.cff). Apache 2.0: see [LICENSE](LICENSE) and
[NOTICE](NOTICE). Data sources keep their own terms, recorded in each manifest.

Riprap is independent and not affiliated with FEMA, NOAA, USGS, the City of New
York or any agency. Thanks to AMD Developer Cloud and the AMD x lablab.ai
Developer Hackathon, where it began and where the three models were trained;
to IBM Research for Granite; to NYU's Center for Urban Science and Progress;
to FloodNet (researchers at New York University and the City University of New
York working with city agencies) for the sensor network and its open data; and
to Andrew Hicks for the introduction to the ASCE network.

The experimental models are fine-tunes of other people's work: NASA and IBM's
[Prithvi-EO 2.0](https://huggingface.co/ibm-nasa-geospatial), IBM and ESA's
[TerraMind 1.0](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base)
and IBM's [Granite TTM r2](https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2),
all Apache 2.0. The surge and water fine-tunes and their evaluation are at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models);
the land-cover model is trained and scored by `scripts/train_cover.py` and
`scripts/eval_cover.py` on NYC's land cover maps (2017 from NYC Open Data for
training; 2021 from The Nature Conservancy and the University of Vermont,
CC BY-NC-SA 4.0, used only to score it).
Their limits are Riprap's to state, not their makers'. Satellite imagery is
Copernicus Sentinel data, read through Microsoft's Planetary Computer.

The dam mark is ["Dam" by Chintuza](https://thenounproject.com/icon/dam-4516918/)
via the Noun Project, licensed CC-BY 3.0.
