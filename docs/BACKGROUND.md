# Background

Why Riprap exists, who it is for, and how the Five Stones generalise beyond NYC.

## The problem Riprap solves

The flood and heat records for a New York City block are public, and they
sit in separate places: FEMA's flood maps, the city's stormwater scenarios,
the Sandy inundation extent, Ida high-water marks, 311 requests, street
sensors, the Health Department's heat index, satellite surface temperature.
Each has its own portal, its own vocabulary and its own traps.

A reporter on deadline, a community board member preparing for a meeting,
a council staffer answering a constituent, or a student starting a project
has to open each of them, learn what each field means, and write down
where every number came from. That is half a day for one address, and the
citation trail is the first thing to go.

Riprap reads the records for one address or one community district and
quotes each with its source and date, so a sentence can go into a story, a
board resolution or a memo with its citation. It adds nothing of its own:
no score, no model of flooding, no advice.

## What this is. What this isn't.

Riprap is a reference tool for people who need source-linked numbers
about a place. It is not a risk score, a real-estate disclosure, an
engineering study or a substitute for a professional.

**Riprap is for:**

- A data journalist or civic researcher who needs primary-source numbers
  about flooding, heat, and the schools, subway entrances and public
  housing inside a mapped flood extent, each with a citation that can be
  checked.
- Community board members and staff, and council offices, who want a
  district's record on one printable page for a meeting or a budget
  request.
- A resilience or climate analyst, in an agency or outside one, who would
  otherwise open six tabs and cite by hand.
- A civic technologist or researcher who wants the same evidence as JSON
  or over MCP, and the code that produced it.

Residents can read a briefing, and the page is written to be read without
training. But no resident or community group has yet shaped or tested it,
it is in English only, and it holds nothing a neighbour would know that
the records miss.

**Do not use Riprap for:**

- **A decision about your home or your safety.** For New York City, use
  [FloodHelpNY](https://www.floodhelpny.org) (Center for NYC
  Neighborhoods) for flood zones, insurance and what to do at home, and
  [FloodNet](https://www.floodnet.nyc) for what its sensors read.
- **Buying, selling, lending or insuring.** A briefing describes public
  records about a place. It is not an assessment of a property and should
  not be used as one.
- **Drainage or hydraulic design.** That needs a hydraulic model and a
  licensed engineer.

Riprap is not an alert or emergency service. For emergency alerts in New
York City use [Notify NYC](https://a858-nycnotify.nyc.gov/), and to report
flooding or ask the city for help use [311](https://portal.311.nyc.gov/).

**On FEMA determinations.** Riprap quotes the flood zone FEMA's map shows
at a point. That is not a flood zone determination. If a decision turns on
the official flood zone of a parcel, use FEMA's
[Flood Map Service Center](https://msc.fema.gov).


## Related work

Riprap comes after these tools and leans on several of them. It claims no
advance over any of them: it reads many of the same public records and
writes them out as cited sentences for one place. Each description below was
checked against the tool's own page on 5 October 2026, except where marked.

| Tool | What it is | How Riprap differs or defers |
|---|---|---|
| [FloodNet data dashboard](https://dataviz.floodnet.nyc/) | FloodNet's own view of its sensors: the project describes itself as "a network for real-time urban flood monitoring and community flood resilience" ([floodnet.nyc](https://www.floodnet.nyc/)) and publishes its reviewed flood events on NYC Open Data | FloodNet is the authority on its sensors and readings. Riprap quotes event counts and peak depths for the sensors near a place, with their times, beside other records, and sends readers to the dashboard for the readings themselves and for anything happening now |
| [Rainproof NYC Flood Map](https://rebuildbydesign.org/rainproof-nyc-map/) (Rebuild by Design, with community partners) | A map that "combines submitted personal stories with official public data, including 311 reports since Hurricane Ida, FloodNet Sensors, and City-led built and in-progress green infrastructure" | It holds what Riprap does not: residents' own accounts, and green infrastructure. Its 311 totals use its own categories and distances, so they differ from Riprap's; neither is wrong. Riprap has no channel for community knowledge and points there |
| [NYC Stormwater Flood Maps viewer](https://experience.arcgis.com/experience/e83a49daef8a472da4a7e34dc25ac445/) (NYC Department of Environmental Protection) | The City's own viewer for its stormwater flood scenarios (title and owner read from the map's public record; the page itself needs a browser) | The City's maps and its disclaimer are the authority. Riprap reads the four published scenarios at a point or over an area, under the City's names, and repeats the map's disclaimer ([METHODOLOGY.md](METHODOLOGY.md#10-what-the-data-cannot-say)) |
| [EJNYC Mapping Tool](https://experience.arcgis.com/experience/6a3da7b920f248af961554bdf01d668b) (Mayor's Office of Climate and Environmental Justice) | The City's environmental justice mapping tool, published with the EJNYC report in 2024 (title and owner read from the map's public record; the description is from the City's report, not verified on the page) | It joins hazards to who lives in a place, which Riprap does not: Riprap carries no demographic layer of its own and quotes only what a source publishes |
| [FloodHelpNY](https://www.floodhelpny.org/) (Center for NYC Neighborhoods) | Help for residents on flood insurance, flood zones and retrofits, in nine languages | The place for insurance and what to do at home. Riprap gives no advice and sends those questions there |
| [GeoFlood Studio](https://engineering.nyu.edu/news/nyu-tandon-researchers-launch-interactive-3d-flood-map-help-new-yorkers-visualize-climate) (NYU Tandon, Climate, Energy, and Risk Analytics Lab) | "An interactive 3D flood visualization" in which "users can explore scenarios based on Hurricane Sandy (coastal flooding) and Hurricane Ida (rainfall-driven flooding), each combined with projected sea level rise" | It models and shows depth; Riprap models nothing and shows only what was recorded or already mapped. The two answer different questions |
| [NYC Urban Heat Portal](https://urbanheat.nyc/) (BetaNYC and Dr. Mehdi Heris, with NASA support) | A portal to "visualize and switch between different data layers, such as the new Outdoor Heat Exposure Index, Air Temperature, Mean Radiant Temperature, and Surface Temperature", with links to the city's heat resources ([announcement](https://www.beta.nyc/2025/05/28/announcing-the-nyc-urban-heat-portal-explore-understand-and-act-on-urban-heat/)) | It has air temperature and an exposure index, which Riprap's heat briefing lacks: Riprap quotes Landsat surface temperature, the Health Department's index and the Weather Service as text for one place. For a map of heat across the city, use the portal |
| [BoardStat](https://www.beta.nyc/featured-tools/boardstat/) (BetaNYC) | A 311 tool "designed with community boards for community boards" | It covers all of 311 for a board. Riprap counts only flood-related 311 complaints for a district and says how |
| [AI Tools for NYC's Democracy](https://www.beta.nyc/featured-tools/ai-tools-for-nyc-democracy/) (BetaNYC) | Open-source MCP servers, under the MIT licence, that connect an AI assistant to city data such as 311 services, legislation and spending | Riprap's MCP tools cover a different subject (flood and heat records for a place) and follow the same idea. BetaNYC's disclosure of how its tools were built is the model for [Riprap's own](../README.md#how-riprap-was-built-and-where-a-model-runs) |

Also worth knowing: NYC Planning's
[Community District Profiles](https://communityprofiles.planning.nyc.gov/),
whose floodplain counts Riprap quotes, and the Health Department's
[Environment and Health Data Portal](https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/),
the source of the Heat Vulnerability Index.

## How Riprap works: the Five Stones

Behind every briefing, a set of small data readers (**pebbles**) run in
parallel across public datasets, sensors and forecasts: 22 sources for a
New York City address, 20 for a neighbourhood or district. Each pebble is one
YAML manifest plus a small adapter; the framework loads them from a
deployment directory and groups them into five roles, the **Five Stones**:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | NYC pebbles |
|---|---|---|
| **Cornerstone** (Mapped hazards) | What the ground remembers | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, FEMA effective and preliminary flood zones, 2021 Ida USGS high-water marks, USGS 3DEP elevation |
| **Keystone** (Places and facilities) | What is exposed | MTA subway entrances, NYCHA developments, public schools, NYS DOH hospitals, named when inside a mapped flood extent; for a district, NYC Planning's floodplain counts (DOB permits only when a question asks about construction) |
| **Touchstone** (Live readings) | Current state of the city | FloodNet depth sensors, NYC 311 flood complaints, NWS hourly observations, NOAA tide-gauge water levels, USGS stream gauges |
| **Lodestone** (Projections) | What is coming | NWS flood alerts, the NWS water-level forecast at the nearest harbor gauge, NPCC4 sea-level projections |
| **Capstone** | The briefing | An "In brief" lead and the evidence sentences as written, with the point DEP scenarios merged into one sentence. A question is answered from those sentences, by rules or by any OpenAI-compatible model whose choice of lead and facts is checked in code |

One Burr application runs every intent. All pebbles for the intent fan out
in one parallel `MapActions` group; the Capstone then turns their evidence
into one cited briefing. Adding a data source is a new manifest in the
deployment directory, not a code change.


## The Five Stones beyond NYC

The Five Stones are a city-agnostic template. The five roles stay the
same; only the pebbles plugged into each Stone change.

| Stone | Role | What you replace |
|---|---|---|
| **Cornerstone** | Hazard memory | Local historical inundation extents, regional DEM, regulatory floodplain maps |
| **Keystone** | Asset registers | The transit, housing, education and healthcare layers your jurisdiction publishes |
| **Touchstone** | Live observation | Whatever live sensors and complaint streams the city or region exposes |
| **Lodestone** | Forecasts | Local NWS forecast office output, regional surge or hydrologic models |
| **Capstone** | Citation-grounded synthesis | Same |

What transfers unchanged: one Burr graph that fans pebble manifests out in
parallel, evidence rendered from manifest templates, answers checked in
code when an LLM is configured, and every sentence cited to its source.
To port Riprap to a new city you write a deployment directory of manifests
against local data. See [`docs/PORT-YOUR-CITY.md`](PORT-YOUR-CITY.md).

