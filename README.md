<p align="left">
  <img src="assets/logo@2x.png" width="72" height="72" alt="Riprap dam mark" />
</p>

# Riprap

Cited flood-evidence briefings for New York City places, built from public data.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/msradam/riprap/actions/workflows/check.yml/badge.svg)](https://github.com/msradam/riprap/actions/workflows/check.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

![Riprap answering "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?" with a cited "Yes."](assets/screenshots/hero.png)

**[Browse the gallery](https://msradam.github.io/riprap/)** · **[Run it locally](#quickstart)**

## What it does

Ask Riprap about an NYC address, a question about one, or a community district
such as QN12. It gathers the public flood evidence for that place: the 2012
Sandy footprint, FEMA and DEP flood maps, Hurricane Ida high-water marks, 311
flood complaints, FloodNet street sensors, tide and stream gauges, and nearby
subway entrances, public housing, schools and hospitals.

Every sentence in the briefing cites its source, and each citation links to the
dataset with its vintage. With no model configured, the sentences come straight
from the data. An optional LLM can phrase an answer, and code then checks its
citations and numbers and drops what fails.

Riprap reports evidence. It does not give advice, predict a particular day, or
make a regulatory flood determination.

A real answer, from the gallery entry
[Hollis, "since Ida"](https://msradam.github.io/riprap/gallery/hollis-since-ida/):

> **Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?**
>
> Yes. 2 FloodNet community sensors within 600 m have logged 14 above-curb flood
> events in the last 3 years [floodnet]. Peak depth recorded by the sensors in
> good working order: 815 mm on 2026-05-20 [floodnet]. 1 sensor that logged events
> is flagged by FloodNet for maintenance, so its depths are not used for the peak
> [floodnet]. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this
> address; the highest stood 0.76 ft above ground; the highest water surface
> elevation was 48.2 ft NAVD88 [ida_hwm]. Nearest mark: Intersection of 182nd St.
> and 90th Ave., Jamaica, Queens (174 m away) [ida_hwm]. 82 NYC 311 flood-related
> complaints filed within 200 m of this location in the last 5 years: 47 sewer
> backup, 22 catch basin, 10 street flooding, 3 manhole overflow [nyc311].

The "Yes." is set by a rule, not by the model: at least one observed source
reports flooding since Ida, on 1 September 2021.

## Who it is for, and not for

For data journalists, community board and council staff, city resilience
analysts, civic researchers and open-data communities who need defensible,
source-linked numbers about flood exposure in a place.

Not for resident decisions, real estate, lending, insurance or hydraulic design.
Residents should use [FloodHelpNY](https://www.floodhelpny.org); for an official
flood zone, use FEMA's [Map Service Center](https://msc.fema.gov). More in
[docs/BACKGROUND.md](docs/BACKGROUND.md).

## Status

| Area | Status |
|---|---|
| New York City flood | Production: 32 data sources (5 marked experimental), addresses, questions and all 59 community districts |
| Chicago, Seattle, San Francisco, Boston, Albany | Experimental: federal sources plus a 311 feed and a water-level gauge ([docs/multi-city.md](docs/multi-city.md)) |
| Heat and air quality | Not reachable yet: scaffolds with no coverage area ([docs/multi-hazard.md](docs/multi-hazard.md)) |
| LLM | Optional. Without one, the briefing is the cited evidence itself |
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
Without an LLM, a question gets the cited evidence for its place, and the app
says it was not answered directly (the JSON reports `grounding.tier` as
`no_llm`). The first district query on a cold server takes about half a
minute while the layers load. The same briefing from the command line:

```bash
curl -s "http://localhost:7860/api/agent?q=QN12" | python3 -c "import json, sys; print(json.load(sys.stdin)['paragraph'])"
```

`uv sync --extra ml` adds the optional in-process models (forecasts, policy
retrieval); without them those sources skip themselves.

**With an LLM.** Any OpenAI-compatible endpoint works. With
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
tool works without an LLM, and `get_briefing` answers a question when the
server has one (set the two `RIPRAP_LLM_*` variables in your client's server
config). Every result carries a `record` block (query, time, version, commit,
SHA-256 of the body) and a `failed` list naming sources that did not answer.
Try one from the command line with the MCP Inspector (needs Node):

```bash
npx @modelcontextprotocol/inspector --cli uv run riprap-mcp \
  --method tools/call --tool-name get_district_summary --tool-arg community_district=QN12
```

**Gallery.** `uv run python scripts/build_gallery.py` rebuilds the address and
district entries in `web/sveltekit/src/lib/gallery/`; the question entries are
kept as they are unless an LLM is configured. To see them in the app, rebuild the frontend
(needs Node and [pnpm](https://pnpm.io)): `cd web/sveltekit && pnpm install &&
pnpm build`. Docker and the Modal host are in [docs/DEPLOY.md](docs/DEPLOY.md).

## How it works

Each data source is a YAML manifest (a "pebble"). For every query they run in
parallel, grouped into five roles:

| Stone | Role | Examples |
|---|---|---|
| Cornerstone | What the ground remembers | Sandy extent, DEP and FEMA maps, Ida high-water marks, terrain |
| Keystone | What is exposed | Subway entrances, public housing, schools, hospitals |
| Touchstone | What is happening now | FloodNet sensors, 311 complaints, weather, tide and stream gauges |
| Lodestone | What is coming | NWS alerts, sea-level projections, experimental forecasts |
| Capstone | The briefing | The cited sentences, or an LLM's claims checked in code |

More in [docs/METHODOLOGY.md](docs/METHODOLOGY.md),
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/GROUNDING.md](docs/GROUNDING.md).

## Data sources

The NYC deployment reads 32 sources: 28 NYC manifests and 4 federal ones (FEMA
flood zones, NWS observations and alerts, USGS stream gauges). All are
public-record city, state and federal data; there are no commercial APIs or
proprietary scores. Each manifest records its URL, licence and vintage. The full
list is in [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md), and the models in
[docs/MODELS.md](docs/MODELS.md).

## Privacy

No accounts, no cookies and no analytics. The server keeps a short-lived local
cache of public-data responses and no database of queries (a web server's access
log, if you keep one, holds the URLs asked). 311 free text is
redacted of email addresses and phone numbers when it is fetched; names are not
redacted. Addresses are sent to geocoders, and a configured LLM receives the
question and evidence. Details and a do-no-harm note:
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
York or any agency. Thanks to AMD Developer Cloud, the AMD x lablab.ai Developer
Hackathon, IBM Research (Granite), NASA and IBM (Prithvi-EO 2.0), IBM and ESA
(TerraMind), NYU CUSP and FloodNet, and Andrew Hicks for civil-engineering
review. The dam mark is ["Dam" by Chintuza](https://thenounproject.com/icon/dam-4516918/)
via the Noun Project, licensed CC-BY 3.0.
