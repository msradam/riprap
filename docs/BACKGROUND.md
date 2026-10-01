# Background

Why Riprap exists, who it is for, and how the Five Stones generalise beyond NYC. Moved from the README in refactor 7.

## The problem Riprap solves

Cities publish the hazard-exposure inputs an engineer needs. NYC alone has
decades of it: Sandy 2012 inundation, NYC DEP stormwater scenarios,
FloodNet sensors, NOAA tide gauges, USGS 3DEP LiDAR, 311 complaints, MTA,
NYCHA, schools, hospitals. Other cities publish their own equivalents. The
data is public. None of it composes itself.

Every engineer doing a drainage review, every resilience office siting a
capital project, every climate-adaptation team prioritising blocks
reassembles the same evidence by hand, per address, from a dozen agencies. A
briefing that should be a tool call ends up as a half-day of manual joins.
Existing tools either return opaque vendor risk scores or skip the audit
trail a stamped engineering memo actually requires.

Riprap composes it. Type an address in any deployed city and get a
citation-grounded briefing with one section per Stone that has evidence,
every claim pointing back to a `[doc_id]` in public-record data.


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
a flood hazard determination, a Base Flood Elevation, an SFHA
boundary, a floodway, federal regulation gives the affected community
a 90-day appeal window, and an appeal must rest solely on scientific or
technical evidence, not policy or economic argument (44 CFR Part 67).
Riprap does not issue, contest, or substitute for a determination made
through that process. If a decision turns on the official flood zone
at a parcel, use FEMA's [Flood Map Service Center](https://msc.fema.gov)
or the community's Flood Zone Determination process, not a Riprap
citation.


## How Riprap works: the Five Stones

Behind every briefing, up to twenty atomic data probes (**pebbles**)
fan out across public datasets, sensors and forecasts. Each pebble is one
YAML manifest plus a small adapter; the framework loads them from a
deployment directory and groups them into five roles, the **Five Stones**:

> **Cornerstone** remembers. **Keystone** tallies. **Touchstone**
> watches. **Lodestone** projects. **Capstone** writes it all down with
> citations.

| Stone | Role | NYC pebbles |
|---|---|---|
| **Cornerstone** | What the ground remembers | Sandy 2012 inundation extent, NYC DEP stormwater scenarios, FEMA effective and preliminary flood zones, 2021 Ida USGS high-water marks, USGS 3DEP DEM with HAND and TWI |
| **Keystone** | What is exposed | MTA subway entrances, NYCHA developments, NYC DOE schools, NYS DOH hospitals, named when exposed; for a district, NYC Planning's floodplain counts and DOB permits |
| **Touchstone** | Current state of the city | FloodNet depth sensors, NYC 311 flood complaints, NWS hourly observations, NOAA tide-gauge water levels, USGS stream gauges |
| **Lodestone** | What is coming | NWS flood alerts, the NWS water-level forecast at the nearest harbor gauge, NPCC4 sea-level projections |
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

