# Riprap methodology

Every claim cites its source: a public record from FEMA, NOAA, USGS, NASA
and USGS Landsat, the city's Health Department or city open data, or, where
it is labelled experimental, a model. For New York City a flood briefing
reads 24 public data sources and a heat briefing 10 or 11
([DATA-SOURCES.md](DATA-SOURCES.md)). This methodology was last updated
2026-10-05.

> Riprap reports evidence. It computes no score, tier or ranking, and no
> language model scores anything. Each source's finding is one cited
> sentence, and the reader weighs them.

Rules or an open Granite model read your question and choose the evidence.
Every sentence you read comes word for word from a public record, with its
source and date. In full: code writes one sentence from each record, and
those sentences are shown unchanged. Rules answer a question first. An
optional open Granite model, off by default, is called only when no rule
handles the query. In planning it may set the intent among six (code
overrides it when the parser found an address or a district), the target
text, the focus and which sources run beyond a fixed floor, and it writes a
rationale of at most 300 characters that appears only in the JSON plan and
the stream's plan event, never in the briefing. In answering it may propose a
lead (yes, no, partly, a count, cannot answer) and pick up to four existing
sentences and their order. Code overrides the lead for past-event, now and
forecast questions, requires a yes-or-no question shape, and checks the lead
against the cited figures (a failure is sent back once, then the lead and the
picks are dropped). By default it cannot write a sentence or a number in a
briefing; `RIPRAP_LLM_BARE=1`, off by default, is the one mode in which a
model rewrites evidence as sentences, checked for citation ids and numbers
([GROUNDING.md](GROUNDING.md), [MODELS.md](MODELS.md)). The sentences are
Riprap's wording of a record, not a publisher's own prose, and some state a
figure Riprap computed from a record (a share of a district, a percentile of
terrain). Section 10 lists what the records cannot say, and section 11 the
distances and time windows behind each count.

Earlier versions built a composite exposure tier (1 to 4) for the offline
asset registers. Nothing in a briefing showed it, and it was removed. The
rubric and its weights are in git history at `8b87165` (`app/score.py`).

## 1. Why no score

A score without a published method is hard to cite in civic work. A grant
writer can't quote "0.73" in a FEMA BRIC sub-application without an audit
trail behind it. A
score emitted by an LLM would be non-reproducible and uncalibrated. A
composite of weighted layers hides which layer put a place on the list.
Riprap states each layer's finding separately, with its source and vintage.

## 2. Evidence classes

A manifest's `tier` field names its evidence class, shown as a chip on its
evidence card.

| Class | Meaning | NYC examples |
|---|---|---|
| empirical | Measured or observed | Sandy 2012 extent, Ida high-water marks, FloodNet sensors, tide and stream gauges, asset registers; Landsat surface temperature, station records, heat illness visits, the city's land cover map |
| modeled | A scenario, a regulatory map, an index or a forecast | FEMA flood zones, DEP stormwater scenarios, NWS alerts and forecasts, NPCC4 projections; the Heat Vulnerability Index |
| proxy | An indirect indicator | 311 flood requests, terrain indices |

The class is a label. It does not change how a sentence is weighted, since
nothing is weighted.

## 3. Asset registers

For a community district a briefing names the schools, subway entrances,
public housing developments and hospitals inside the mapped flood extents.
A school, subway entrance or hospital is in a register when its point is
inside the 2012 Sandy inundation zone or inside a modelled DEP stormwater
scenario. A public housing development counts as inside the Sandy zone when
10% or more of its outline is, and is tested against a stormwater scenario
by its centre point; the sentence says which. The school and public housing
registers test three of the city's four stormwater maps (Moderate Flood with
current and with 2050 sea levels, Extreme Flood with 2080) and not the
Limited Flood map, and their sentences say so. There is no other rule.

- `riprap-register --asset-class {schools,nycha,mta_entrances}` writes a
  CSV with one row per asset and a 0 or 1 per layer
  (`riprap/cli/register.py`). `--all` writes every asset, not only the
  exposed ones.
- `scripts/build_register.py {nycha,schools}` bakes
  `data/registers/<class>.json`, served at `/api/register/{asset_class}`.

The Keystone sentences in a briefing name the exposed assets near an
address, or inside a neighbourhood or district.

## 4. Terrain indices

- **HAND** (height above nearest drainage): the vertical distance from the
  point to the nearest drainage channel (Nobre et al. 2011).
- **TWI** (topographic wetness index): `ln(catchment area / tan slope)`
  (Beven & Kirkby 1979). It is noisy on flat urban elevation models
  (Sørensen et al. 2006).

Both are computed from the USGS 3DEP elevation model. They say where water
would pool on terrain alone, and nothing about drainage capacity. The
terrain sentence gives the elevation and the low-spot percentile. Neither
index is printed in a briefing or on the page: an address's HAND stays in
the JSON value (`hand_m`), and TWI and the district drainage figures are no
longer in the values.

## 5. The Sandy edge

The Sandy zone is a mapped outline, not exact to a building. A point within
50 m of the mapped edge, inside or outside, gets its distance to the edge
in the sentence (`app/flood_layers/sandy_inundation.py`), and a question
about that point gets no flat yes or no. A hospital or subway entrance whose
mapped point is outside the outline but within 50 m of it is named in its
register sentence: two hospitals that Sandy closed have points 3 m and 46 m
outside the mapped edge.

## 6. Live signals

NWS alerts, tide and stream gauges, FloodNet readings and the NWS
water-level forecast are dated readings, and their sentences say when
they were taken. Exposure is a slow-changing property of a place; an event
is not (IPCC AR6 WG II glossary; NPCC4).

## 7. Scope

A Riprap briefing is not:

- a flood-damage probability or expected loss;
- a flood-insurance rating. For that, see FEMA Risk Rating 2.0 (FEMA
  2021), which uses claims data Riprap does not have;
- a vulnerability assessment. Foundation type, electrical hardening,
  drainage condition and social capacity are out of scope;
- a prediction. DEP 2050 and 2080 and FEMA 0.2% are bounding scenarios,
  not forecasts.

Caveats that travel with the evidence:

- 311 counts are complaints filed and under-count flooding where fewer
  people call (section 10).
- Compound flooding (rain, tide and groundwater together) is not modeled
  separately by any source Riprap reads (NPCC4).
- A source that did not answer is named as unavailable. It supports
  neither a "no" nor a zero.

## 8. Heat

A heat briefing is the same method on a second hazard. A query that asks
about outdoor heat gets it; a bare place gets its flood briefing, with a
link to the heat one. The two are kept apart because together they come to
about 1,460 words and 35 sources for one place.

Each heat sentence carries the trap that goes with its figure:

- **Surface temperature is not air temperature.** Landsat measures roofs,
  pavement and treetops at about 11:35 on clear summer mornings. A place's
  temperature in one image depends on the day, so the sentence gives the
  difference from the city's land average in the same image, as a mean over
  every clear image with the range image by image
  (`scripts/bake_surface_temperature.py`). The 90 m cells are three by three blocks of Landsat's own 30 m pixels, drawn where
  those pixels are. A district's or neighbourhood's reading takes in its parks and open land, and tall
  buildings shade the ground at the late-morning overpass, so a dense district can read
  cool. The reading is of land only:
  cells over water are left out, so a pier is not cooled by the river beside
  it, and a 150 m circle weighs each 90 m cell by the share of it inside the
  circle. A yes or no to "is it hotter here" is given only "at the
  surface", only against the city, and only when every image agrees.
- **A vulnerability index is a rank, not a measurement.** The Health
  Department's Heat Vulnerability Index scores a neighbourhood 1 to 5
  against the others from a model of heat deaths. Riprap quotes it as the
  department's, says what it is built from, and computes no score of its
  own. Parks, airports and cemeteries have none.
- **A suppressed count is not a zero.** Heat illness emergency visits are
  published by community district over five summers, counted by where the
  patient lives; counts under 11 are withheld, and the sentence says so.
- **A station is one point.** Days at or above 90 F come from the nearest
  of Central Park, LaGuardia and JFK, named with its distance. The three
  read differently.
- **A forecast is the Weather Service's.** A question about the coming
  days gets its forecast and alerts, quoted as issued, with the New York
  office's advisory thresholds beside them. Riprap forecasts nothing and
  does not predict the temperature inside a building.
- **Cooling centers exist only in a heat emergency.** The city lists them
  then, on its own finder. Riprap lists NYC Parks spray showers and pools
  (summer only) and points to the finder.
- **311 "heat" is winter.** A question about no heat or hot water is about
  indoor heating; Riprap says so and points to 311.

A heat briefing is not health or safety advice, and it does not say what
to do in the heat.

## 9. The five Stones

A briefing sorts its sources into five Stones. Each Stone is a class of
evidence. Together they form the briefing, and every claim in the output
traces back to the Stone that produced it.

| Stone | Role | Flood sources | Heat sources |
|---|---|---|---|
| Cornerstone | The hazard reader | FEMA flood maps, DEP stormwater scenarios, the Sandy extent, Ida high-water marks, terrain | Landsat surface temperature, the Heat Vulnerability Index, heat illness visits, the city's land cover map |
| Keystone | The asset register | Public schools, subway entrances, public housing, hospitals, floodplain counts (construction permits only when a question asks) | NYC Parks spray showers and pools |
| Touchstone | The live observer | FloodNet sensors, 311 flood complaints, tide and stream gauges, weather observations | The station record of 90 F days, the latest air temperature |
| Lodestone | The projector | NWS alerts and water-level forecasts, NPCC4 sea-level projections | The NWS forecast and heat alerts, NPCC4 heat projections |
| Capstone | The synthesizer | Writes one cited sentence per record, and answers a question by rules over its words | The same |

## 10. What the data cannot say

Each statement here is the publisher's own or comes from published research,
with its source. A briefing sentence carries the short form; this is the long
one.

**311 counts are complaints filed, not floods measured.** A complaint needs
someone who knows 311, trusts it and has the time and the language to use it.
Kontokosta, Hong and Korsberg write that models trained on 311 data "can
suffer from biases in the propensity to make a request that can vary based on
socio-economic and demographic characteristics of an area"
([arXiv:1710.02452](https://arxiv.org/abs/1710.02452)). Boxer, Hong,
Kontokosta and Neill, studying heating complaints in New York City, write
that "resident-generated data suffer from reporting bias, with some
subpopulations reporting at lower rates than others" (*Annals of Applied
Statistics* 19(2), 2025,
[doi:10.1214/24-AOAS2003](https://doi.org/10.1214/24-AOAS2003)). Neither
paper measures flood complaints, but the caution carries: a low count in a
lower-income or immigrant neighbourhood can mean fewer reports, not less
water. The dataset also counts requests, not events: one storm on one block
can be many complaints or none. Riprap never turns a 311 count alone into a
"Yes." to "has it flooded".

**The city's stormwater maps are modelled scenarios.** They are design storms
paired with a sea level, not forecasts and not observations. The city's own
geodatabase, as published on NYC Open Data
([`9i7c-xyvv`](https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Maps/9i7c-xyvv)),
carries this disclaimer in its metadata:

> This map was developed by the City of New York and is provided solely for
> informational purposes. The map shows areas of potential flooding of at
> least 0.25 contiguous acres with flood depths of 4 inches or more. The map
> is intended to be an informational tool and does not provide the exact
> depth of flooding at any location.
>
> [...] The models do not account for site-specific conditions that may
> affect flooding, e.g., private drainage infrastructure, obstructed or
> clogged drains or future conditions such as new development and
> construction, or deterioration and replacement of existing infrastructure.
> The maps are intended to show the relative risk of flooding in public areas
> from stormwater runoff due to rain only. While the hydrologic and hydraulic
> models account for the effect of sea level rise on stormwater drainage
> infrastructure, they do not represent flood risk from coastal inundation
> due to sea level rise and/or storm surge.

The same text says the map "shall not be used for the design, modification,
or construction of improvements to real property or for flood plain
determination". Riprap reads the map at a point, one 10 ft cell with no
margin, so "inside" or "outside" a scenario at an address is a reading of
that cell and not a finding about a lot; near a mapped edge the sentence
gives the distance to it. Riprap reads all four published maps under the
city's own names. Three come from the Open Data geodatabases. The fourth,
"Limited Flood (1.77 inches/hr) with Current Sea Levels", is read from the
vector tiles of DEP's own viewer, because its geodatabase on the portal is
compressed in a way open GDAL cannot read; its citation says so.

**Outside a mapped area is not safe.** NYC Emergency Management's hazard
profile says of Hurricane Ida: "The most heavily impacted areas, representing
over half of all damaged buildings, were also outside of any flood risk
scenario, including FEMA floodplain maps and the NYC Stormwater Resiliency
Plan's Extreme and Moderate stormwater scenarios"
([NYC Hazard Mitigation, flooding](https://nychazardmitigation.com/documentation/hazard-profiles/flooding/)).
A sentence that says a place is outside a map says only that.

**A FloodNet depth is a point measurement under one sensor.** FloodNet
defines a flood event as "a series of water depth measurements greater than
10 mm" at a sensor
([NYC Open Data `aq7i-eu5q`](https://data.cityofnewyork.us/Environment/FloodNet-Street-Flooding-Events-Measured-by-FloodN/aq7i-eu5q)).
A depth is the water under that sensor, not the depth along the street or at
a building, and a sensor records nothing before it was installed or while it
is down. No sensor nearby is silence, not a dry record. Riprap counts only
the events FloodNet's API marks as verified by a person and says how many
more are labelled flood but unverified. The API gives a sensor's status as
it is today, not as it was on the day of an event, and does not publish what
a status such as "noisy" means for a reading, so Riprap quotes the status
and does not interpret it. Resting a yes or no only on sensors listed as
good is Riprap's choice, not FloodNet's. Questions about the
readings themselves belong to FloodNet's own
[dashboard](https://dataviz.floodnet.nyc/) and data pages.

**Surface temperature is not air temperature.** Landsat measures roofs,
pavement and treetops late on clear summer mornings (section 8). It is not
what a person feels, and it says nothing about the inside of a building.

**The Heat Vulnerability Index is a rank.** The Health Department scores
neighbourhoods from 1 to 5 against each other and says: "a neighborhood with
low vulnerability does not mean no risk. All neighborhoods have residents at
risk for heat illness and death"
([Environment and Health Data Portal](https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/)).
It is not a measurement at an address.

**A briefing is about records, not about people or property.** It describes
what public records say about a place. It is not a judgement on a property,
its value or its insurability, and it is not a judgement on the people who
live there. Riprap gives no score, no rank of neighbourhoods and no advice.

**The page is in English only.** No briefing or page is translated.

## 11. Distances, time windows and filters

Every count in a briefing depends on these choices. They are judgement calls
made for this tool, not standards, and the code records no calibration for
them: a different radius gives a different count. Each sentence states its
own radius and window, and "within 600 m" does not mean "on this block". The
table is enough to rerun a count against the source.

| Source | Where | When | Which records | Why this choice |
|---|---|---|---|---|
| 311 complaints at an address (`erm2-nwe9`) | Within 200 m of the geocoded point (`within_circle`) | The last 5 years, from midnight UTC | `complaint_type` "Sewer" or "Sewer Maintenance" and one of eleven flood descriptors (street flooding, sewer backup, catch basin, highway flooding, manhole overflow, rain garden flooding, under the coded names and the plain names of 2026); a complaint filed twice within ten minutes at one address counts once (`app/context/nyc311.py`) | About the blocks around an address; wider circles mix in other streets' drains |
| 311 complaints in a district or neighbourhood | A community district by the record's own `community_board` field; a neighbourhood by its exact outline | The last 3 years | The same filter; the lead gives the breakdown by descriptor group, and every count ends with the under-reporting caveat | The district is the unit the city files the complaint under |
| FloodNet sensors at an address | Sensors within 600 m | The period since the sensors were installed, stated with the install date, within the last 3 years | Events the API labels `flood` and marks `annotated_by: human` (verified by a person); a flood event is a series of depth readings above 10 mm at the sensor, FloodNet's definition. The sentence gives the highest depth on record with that sensor's status as the API lists it when read, then the highest among sensors listed as good | Sensors are sparse (a few hundred citywide), so a block-sized circle would usually hold none |
| FloodNet sensors in an area | Sensors inside the outline | The same | The same | |
| Hurricane Ida high-water marks | USGS marks within 800 m; a mark counts toward "the block flooded" only within 250 m | 1 to 2 September 2021 | All 159 New York marks in the USGS file | The marks are few and were surveyed where crews went; 800 m finds the nearest ones, 250 m keeps a "Yes." local |
| Sandy inundation zone (`5xsi-dfpx`) | The cell under the point; the distance to the edge is stated within 50 m of it | 2012 | | The mapped outline is not exact to a building |
| Stormwater scenarios (`9i7c-xyvv`) | The 10 ft cell under the point, with the distance to the mapped edge when near it; for an area, the share of its land inside | Scenario years as published | All four maps | See section 10 |
| Subway entrances, hospitals, schools, public housing near an address | 800 m, 3,000 m, 1,500 m and 2,000 m | The file dates in [DATA-SOURCES.md](DATA-SOURCES.md) | Each asset's point against the Sandy zone and the extreme 2080 scenario; a public housing development by 10% or more of its outline for Sandy | Rough walking and service distances; a campus is one point, so one that is partly inside a zone can be missed |
| Terrain at an address | The elevation cell that contains the point, in metres NAVD88, compared with the ground within 200 m | USGS 3DEP | | |
| Surface temperature at an address | A 150 m circle of 90 m cells | 18 clear summer images, 2023 to 2026 | Land cells only | The thermal sensor samples at about 100 m (`app/heat/surface_temp.py`) |
| Spray showers and pools | Within 800 m | As published | | About a ten minute walk (`app/heat/cooling.py`) |

A community district in an area briefing is drawn as the union of City
Planning's neighbourhood tabulation areas, which approximates the official
district. Counts of points (subway entrances, schools) can differ from a
count inside the official boundary, and the 311 count in the same briefing
uses the official district. The page's place line, `geocode.note` in the
JSON and `place_note` over MCP say so, and say which tabulation area a
neighbourhood name was answered for when the name covers only part of one
or more than one (Roosevelt Island, East Harlem, Murray Hill). A question
that names two areas gets the two briefings side by side under a note that
nothing is scored or ranked.

## 12. Corrections

If a sentence is wrong, or says more than its record does, open an issue at
<https://github.com/msradam/riprap/issues/new/choose> with the address or
question and the sentence. Corrections are made in the code, with a test, and
recorded in the [changelog](../CHANGELOG.md). When the error is in a source
dataset, the issue says so and points to the publisher (FloodNet asks for
data problems at
[floodnet-nyc/floodnet-data](https://github.com/floodnet-nyc/floodnet-data/issues)).
An independent check on 5 October 2026 re-derived 487 briefing sentences from
the sources: 475 were confirmed, 10 were wrong and 2 sat on a raster edge
([history/SANITY-CHECK-2026-10-05.md](history/SANITY-CHECK-2026-10-05.md)
lists every problem it found and what was done about each).

## References

Boxer, K. S., Hong, B., Kontokosta, C. E., & Neill, D. B. (2025).
"Estimating reporting bias in 311 complaint data." *The Annals of Applied
Statistics* 19(2). doi:10.1214/24-AOAS2003.

Kontokosta, C., Hong, B., & Korsberg, K. (2017). "Equity in 311 Reporting:
Understanding Socio-Spatial Differentials in the Propensity to Complain."
arXiv:1710.02452.

Beven, K. J., & Kirkby, M. J. (1979). "A Physically Based, Variable
Contributing Area Model of Basin Hydrology." *Hydrological Sciences
Bulletin* 24(1): 43-69.

FEMA (2021). *NFIP Risk Rating 2.0 Methodology and Data Sources.*

Nobre, A. D. et al. (2011). "Height Above the Nearest Drainage: A
Hydrologically Relevant New Terrain Model." *Journal of Hydrology*
404(1-2): 13-29.

NYC NPCC4 (2024). *4th NYC Climate Assessment.* New York City Panel on
Climate Change. *Annals of the New York Academy of Sciences* 1539.

Sørensen, R., Zinko, U., & Seibert, J. (2006). "On the Calculation of
the Topographic Wetness Index." *Hydrology and Earth System Sciences*
10: 101-112.
