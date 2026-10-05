# Data sources

The public sources behind the NYC deployment. Each manifest's `provenance`
block is the authority for its URL, licence and vintage; `list_sources` on
the MCP server prints them. Data is used under each source's open-data
terms.

Riprap contacts only public-record federal, state and city sources at
runtime (and Hugging Face, once, if a server opts in to the experimental
surge model). No commercial APIs, no proprietary scores. The NYC
deployment has 60 manifests: 56 in `deployments/nyc/manifests/` and 4 in
`deployments/federal/manifests/`. Each manifest names its briefing in a
`hazard` field: 37 are flood sources, 18 are heat sources and 5 run in both
(the area outline, the city's land cover map and the land-cover model). A
point manifest and its area version read the same source, so the tables
have fewer rows than that. A flood briefing reads 25 public sources (22
for an address, 20 for a neighbourhood or district); a heat briefing reads
10 for an address and 11 for a district, two of them shared with flood (the
land cover map and the area outline). The experimental model layers are
listed after the tables.

## NYC Open Data datasets

Every dataset Riprap reads from [NYC Open Data](https://opendata.cityofnewyork.us/),
by the name the portal gives it and its four-by-four ID. The names, agencies
and update dates below were read from
`https://data.cityofnewyork.us/api/views/<id>.json` on 5 October 2026.
"Modification" is what Riprap does to the data before a sentence is written
from it; the exact filters are in
[METHODOLOGY.md](METHODOLOGY.md#11-distances-time-windows-and-filters).

Riprap is an independent project. It is not a product of the City of New
York, and no City agency has reviewed or endorsed it. Under the City's open
data law, public data sets on the portal "are provided for informational
purposes. The city does not warranty the completeness, accuracy, content or
fitness for any particular purpose or use of any public data set made
available on the web portal"
([Local Law 11 of 2012, section 23-504](https://cityofnewyork.github.io/opendatatsm/LocalLaw11of2012.html)).
Errors in a briefing are Riprap's unless the issue tracker shows otherwise.

| Dataset (portal name) | ID | Agency | Version read | Modification by Riprap |
|---|---|---|---|---|
| [311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9) | `erm2-nwe9` | Office of Technology and Innovation (311) | Live at each query; the portal updates it daily | Filtered to complaint types "Sewer" and "Sewer Maintenance" and eleven flood descriptors; counted within 200 m of an address over 5 years, or by `community_board` or a neighbourhood outline over 3 years; a complaint filed twice within ten minutes at one address counts once. No free text is fetched |
| [Sandy Inundation Zone](https://data.cityofnewyork.us/Environment/Sandy-Inundation-Zone/5xsi-dfpx) | `5xsi-dfpx` | Department of Small Business Services | Historical; rows last updated 2015-11-09; copied 2026-07-11 | Polygons rasterised; read at the cell under an address, with the distance to the edge when within 50 m; for an area, the share of its land inside |
| [NYC Stormwater Flood Maps](https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Maps/9i7c-xyvv) | `9i7c-xyvv` | Department of Environmental Protection | Rows last updated 2024-07-03; three maps copied 2026-07-11, the fourth read 2026-10-05 | All four maps are read, under the city's own names: Limited Flood (1.77 inches/hr) with Current Sea Levels, Moderate Flood (2.13 inches/hr) with Current Sea Levels, Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise, and Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise. Three come from the geodatabases on the portal. The Limited map's geodatabase there is compressed in a way open GDAL cannot read, so it is read from the vector tiles of DEP's own viewer, and its citation says so. Polygons rasterised to 10 ft cells; read at the cell under an address, with the distance to the nearest mapped edge when close, or as a share of an area. No depth is stated beyond the map's own category. Each sentence calls the maps modelled scenarios, not forecasts, and carries the city's disclaimer |
| [FloodNet: Street Flooding Events Measured by FloodNet Sensors](https://data.cityofnewyork.us/Environment/FloodNet-Street-Flooding-Events-Measured-by-FloodN/aq7i-eu5q) | `aq7i-eu5q` | Department of Environmental Protection, for FloodNet (New York University and The City University of New York) | The portal table updates every 2 weeks | **Not read directly.** Riprap reads the same project's Data API (`api.floodnet.nyc`, an early-access beta), and counts only the events the API marks as verified by a person, the same rule as this table, so the two differ only by events verified since the table's last update. The sentence says how many more events the API labels flood but has not verified. Sensors within 600 m or inside an area, over each sensor's period since it was installed. FloodNet data and the sentences and figures derived from it are licensed CC BY-NC-SA 4.0 and are not under Riprap's Apache-2.0 licence; the credit is "FloodNet (New York University and The City University of New York)", with Mydlarz et al. (2024, doi:10.1029/2023WR036806) and Silverman et al. (2022, doi:10.1016/j.watres.2022.118648) |
| [NYCHA Public Housing Developments](https://data.cityofnewyork.us/Housing-Development/NYCHA-Public-Housing-Developments/phvi-damg) | `phvi-damg` | New York City Housing Authority | Copied 2026-05-01 | A development counts as inside the Sandy zone when 10% or more of its outline is; for a stormwater scenario its centre point is tested, and the sentence says so. Named within 2,000 m of an address or inside an area |
| [2019 - 2020 School Point Locations](https://data.cityofnewyork.us/d/a3nt-yts4) | `a3nt-yts4` | Department of Education | Historical: the 2019 to 2020 school year, rows last updated 2019-09-04 | Points tested against the Sandy zone and the extreme 2080 scenario; named within 1,500 m or inside an area. Called "public schools": the file includes charter schools |
| [DOB Permit Issuance](https://data.cityofnewyork.us/Housing-Development/DOB-Permit-Issuance/ipu4-2q9a) | `ipu4-2q9a` | Department of Buildings | Live; the portal updates it daily | Read only when a question asks about construction; it is in no plain briefing. This is the older permit file: jobs filed in DOB NOW (`rbx6-tga4`) are not read, so it undercounts current construction, and the sentence says so and tests each permit's expiry date |
| [2020 Neighborhood Tabulation Areas (NTAs)](https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd) | `9nt8-h7nd` | Department of City Planning | Copied 2026-07-11 | Used as area outlines; a community district is drawn as the union of its NTAs, which approximates the official district |
| [Land Cover Raster Data (2017), 6in Resolution](https://data.cityofnewyork.us/Environment/Land-Cover-Raster-Data-2017-6in-Resolution/he6d-2qns) | `he6d-2qns` | Office of Technology and Innovation | 2017 map; rows last updated 2018-12-07; copied 2026-10-01 | Resampled to 30 m shares of tree canopy, grass, paving and roof; read within a circle or an area. Also the training data of the experimental land-cover model |
| [NYC Parks Spray Showers](https://data.cityofnewyork.us/d/ckaz-6gaa) | `ckaz-6gaa` | Department of Parks and Recreation | Copied 2026-10-02 | Points within 800 m of an address or inside an area |
| [NYC Parks Pools](https://data.cityofnewyork.us/d/y5rm-wagw) | `y5rm-wagw` | Department of Parks and Recreation | Copied 2026-10-02 | The same |

Three more sources are city data published elsewhere than the portal: the
Health Department's Heat Vulnerability Index and heat illness visits (its
Environment and Health Data Portal), NYC Planning's Community District
Profiles, and NYC Planning Labs' GeoSearch geocoder. Two are New York State
open data: [MTA Subway Entrances and Exits: 2024](https://data.ny.gov/Transportation/MTA-Subway-Entrances-and-Exits/i9wp-a4ja)
(`i9wp-a4ja`, data.ny.gov) and
[Health Facility General Information](https://health.data.ny.gov/Health/Health-Facility-General-Information/vn5v-hh5r)
(`vn5v-hh5r`, health.data.ny.gov).

## Flood

| Source | Publisher | Used for |
|---|---|---|
| Sandy Inundation Zone, 2012 | NYC Open Data (`5xsi-dfpx`) | Whether Sandy flooded the place, and the distance to the mapped edge when within 50 m |
| NYC Stormwater Flood Maps | NYC Department of Environmental Protection (`9i7c-xyvv`; the Limited map from DEP's viewer tiles) | Four modelled rainfall scenarios, under the city's names |
| National Flood Hazard Layer | FEMA | Effective flood zone (2007 FIRM) |
| Preliminary NFHL (2015 PFIRM) | FEMA | Preliminary flood zone and base flood elevation with its datum, adopted by NYC Building Code Appendix G for flood-resistant construction |
| Hurricane Ida 2021 high-water marks | USGS Short-Term Network | Surveyed flood marks |
| FloodNet sensor network | FloodNet (New York University and The City University of New York), CC BY-NC-SA 4.0 | Flood-event log near an address, and for the sensors inside a neighbourhood or district |
| 311 service requests | NYC Open Data (`erm2-nwe9`) | Flood requests, counted under both the coded descriptor names and the plain names the city introduced in 2026 |
| Tide gauges | NOAA CO-OPS | Water level, predicted tide and residual at the nearest of The Battery, Kings Point and Sandy Hook |
| Water-level forecast | National Weather Service, National Water Prediction Service | Forecast peak and the flood stage it reaches at the nearest of The Battery, Kings Point and Bergen Point |
| Stream gauges | USGS Water Data (OGC API) | Live stage |
| Observations and alerts | National Weather Service | Precipitation, active warnings |
| Subway entrances | MTA (`i9wp-a4ja`) | Transit assets |
| NYCHA developments | NYC Housing Authority (`phvi-damg`) | Public housing |
| School locations | NYC Department of Education (`a3nt-yts4`, 2019 to 2020) | Public schools, charter schools included |
| Health facilities | New York State Department of Health (`vn5v-hh5r`) | Hospitals |
| 3DEP elevation model | USGS | Elevation and low-spot percentile |
| DOB permits | NYC Department of Buildings (`ipu4-2q9a`) | Only a question about construction |
| Community District Profiles | NYC Department of City Planning | Buildings, residential units and residents in a district's 1% annual chance floodplain |
| 2020 Neighborhood Tabulation Areas | NYC Department of City Planning (`9nt8-h7nd`) | Area outlines |
| NPCC4 sea-level projections | NYC Panel on Climate Change | Projected sea-level rise for New York City (the report's Table 1, relative to 1995-2014) |
| NYC Land Cover 2017, 6 inch | NYC Office of Technology and Innovation, NYC Open Data (`he6d-2qns`) | Paved, green and tree canopy shares near an address or in an area; quoted when a question asks, and in every heat briefing |

## Heat

Why each is in, and what was left out, is in
`research_notes/fable/climate/heat_sources.md` in the working notes; the
traps each sentence carries are in [METHODOLOGY.md](METHODOLOGY.md).

| Source | Publisher | Used for |
|---|---|---|
| Landsat 8 and 9 Collection 2 Level 2 surface temperature | USGS, read through Microsoft Planetary Computer | How much warmer or cooler the surface is than the city's land average, over 18 clear summer images of 2023 to 2026 (`data/heat/surface_temp.tif`, baked by `scripts/bake_surface_temperature.py`) |
| Heat Vulnerability Index, 2023 | NYC Department of Health and Mental Hygiene, Environment and Health Data Portal | The department's 1 to 5 rank for a neighbourhood or community district; for a neighbourhood, also the file's air conditioning share (a survey estimate shared across neighbouring neighbourhoods) and green space share |
| Heat stress emergency department visits, 2018 to 2022 | NYC Health Department, from New York State SPARCS | Visits by residents of a community district, borough or the city, with the age-adjusted rate; suppressed counts are stated as suppressed |
| NYC Land Cover 2017, 6 inch | NYC Open Data (`he6d-2qns`) | Tree canopy and paved share (shared with flood) |
| Daily station records | NOAA Regional Climate Centers, ACIS | Days at or above 90 F this year and last, the 1991 to 2020 average, the year's highest reading and the record, at the nearest of Central Park, LaGuardia and JFK |
| Latest station observation | National Weather Service | Air temperature and heat index now, at the nearest station |
| Gridpoint forecast | National Weather Service | Seven-day daytime highs and the highest apparent temperature for the 2.5 km cell, quoted as the Weather Service's, with the New York office's advisory thresholds |
| Active alerts, heat events | National Weather Service | Heat advisories, extreme heat watches and warnings in effect |
| NPCC4 extreme heat projections | NYC Panel on Climate Change | Days at or above 90 F and 95 F and heat waves a year for the 2030s, 2050s and 2080s (the report's Table 4, baseline 1981-2010), for the city as a whole |
| Spray showers and pools | NYC Parks, NYC Open Data (`ckaz-6gaa`, `y5rm-wagw`) | Places to cool off within 800 m or in an area. Cooling centers are not copied: the city lists them only during a heat emergency, at finder.nyc.gov/coolingcenters |
| 2020 Neighborhood Tabulation Areas | NYC Department of City Planning | Area outlines, and the neighbourhood an address is in (shared with flood) |

## Experimental model layers

Model output, not records. Each is labelled experimental wherever it
appears, with its limits and tested accuracy ([MODELS.md](MODELS.md)). The
surge forecast is out of default briefings since 2026-10-05, and a third
layer, new surface water after storms from a satellite model, was retired on
2026-10-02 after two tests showed no skill.

| Layer | Made from | Used for |
|---|---|---|
| Battery surge forecast (off by default) | The author's Granite TTM r2 fine-tune on NOAA CO-OPS water levels and tide predictions at The Battery. Its manifest is in `deployments/nyc/optional/`; a server opts in with `RIPRAP_EXTRA_MANIFESTS=deployments/nyc/optional` | Nothing in a default briefing. On 639 held-out four-day windows its mean error was 0.115 m against 0.108 m for damped persistence, which beats it, and it foresaw 1 of 23 flood-stage windows (5 distinct events). The hosted model card is out of date; the corrected one is [model-cards/Granite-TTM-r2-Battery-Surge.md](model-cards/Granite-TTM-r2-Battery-Surge.md) |
| Land cover from the latest imagery | The NYC land-cover model (TerraMind 1.0 base fine-tuned on NYC Land Cover 2017, NYC Open Data) on Copernicus Sentinel-2 L2A scenes of 2018, 2021, 2024 and 2026; scored against NYC Land Cover 2021 (The Nature Conservancy and UVM, CC BY-NC-SA 4.0, used only as a local test key) | Paved, green and tree canopy shares of a place, from the latest year; no change between years is read |
