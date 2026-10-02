# Riprap methodology

Every claim cites its source: a public record from FEMA, NOAA, USGS, NASA
and USGS Landsat, the city's Health Department or city open data, or, where
it is labelled experimental, a model. For New York City a flood briefing
reads 24 public data sources and a heat briefing 10 or 11
([DATA-SOURCES.md](DATA-SOURCES.md)). This methodology was last updated
2026-10-02.

> Riprap reports evidence. It computes no score, tier or ranking, and no
> language model scores anything. Each source's finding is one cited
> sentence, and the reader weighs them.

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
An asset is in a register when its point is inside the 2012 Sandy
inundation zone or inside any of the three DEP stormwater scenarios. There
is no other rule.

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
terrain sentence gives the elevation and the low-spot percentile; HAND and
TWI are in the evidence table.

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

- 311 counts reflect neighbourhood reporting habits and may under-count
  flooding where fewer people call.
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
  those pixels are. The reading is of land only:
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
| Keystone | The asset register | Schools, subway entrances, public housing, hospitals, construction permits, floodplain counts | NYC Parks spray showers and pools |
| Touchstone | The live observer | FloodNet sensors, 311 flood complaints, tide and stream gauges, weather observations | The station record of 90 F days, the latest air temperature |
| Lodestone | The projector | NWS alerts and water-level forecasts, NPCC4 sea-level projections | The NWS forecast and heat alerts, NPCC4 heat projections |
| Capstone | The synthesizer | Writes one cited sentence per record, and answers a question by rules over its words | The same |

## References

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
