# Data sources

The public sources behind the NYC deployment. Each manifest's `provenance`
block is the authority for its URL, licence and vintage; `list_sources` on
the MCP server prints them. Data is used under each source's open-data
terms.

Riprap contacts only public-record federal, state and city sources at
runtime, plus NOAA's gauge and Hugging Face when the experimental surge
model is installed. No commercial APIs, no proprietary scores. The NYC
deployment has 59 manifests: 55 in `deployments/nyc/manifests/` and 4 in
`deployments/federal/manifests/`. Each manifest names its briefing in a
`hazard` field: 36 are flood sources, 18 are heat sources and 5 run in both
(the area outline, the city's land cover map and the land-cover model). A
point manifest and its area version read the same source, so the tables
have fewer rows than that. A flood briefing reads 24 public sources (21
for an address, 19 for a neighbourhood or district); a heat briefing reads
10 for an address and 11 for a district, two of them shared with flood (the
land cover map and the area outline). The experimental model layers are
listed after the tables.

## Flood

| Source | Publisher | Used for |
|---|---|---|
| Sandy Inundation Zone, 2012 | NYC Open Data (`5xsi-dfpx`) | Whether Sandy flooded the place, and the distance to the mapped edge when within 50 m |
| NYC Stormwater Flood Maps | NYC Department of Environmental Protection | Three modeled rainfall scenarios |
| National Flood Hazard Layer | FEMA | Effective flood zone (2007 FIRM) |
| Preliminary NFHL (2015 PFIRM) | FEMA | Preliminary flood zone and base flood elevation with its datum, adopted by NYC Building Code Appendix G for flood-resistant construction |
| Hurricane Ida 2021 high-water marks | USGS Short-Term Network | Surveyed flood marks |
| FloodNet sensor network | FloodNet NYC | Flood-event log near an address, and for the sensors inside a neighbourhood or district |
| 311 service requests | NYC Open Data (`erm2-nwe9`) | Flood requests, counted under both the coded descriptor names and the plain names the city introduced in 2026 |
| Tide gauges | NOAA CO-OPS | Water level, predicted tide and residual at the nearest of The Battery, Kings Point and Sandy Hook |
| Water-level forecast | National Weather Service, National Water Prediction Service | Forecast peak and the flood stage it reaches at the nearest of The Battery, Kings Point and Bergen Point |
| Stream gauges | USGS Water Data (OGC API) | Live stage |
| Observations and alerts | National Weather Service | Precipitation, active warnings |
| Subway entrances | MTA (`i9wp-a4ja`) | Transit assets |
| NYCHA developments | NYC Housing Authority (`phvi-damg`) | Public housing |
| School locations | NYC Department of Education (`wg9x-4ke6`) | Schools |
| Health facilities | New York State Department of Health (`vn5v-hh5r`) | Hospitals |
| 3DEP elevation model | USGS | Elevation, HAND and TWI |
| DOB permits | NYC Department of Buildings (`ipu4-2q9a`) | `development_check` intent |
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
| Heat Vulnerability Index, 2023 | NYC Department of Health and Mental Hygiene, Environment and Health Data Portal | The department's 1 to 5 rank for a neighbourhood or community district, with its air conditioning and green space figures |
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
appears, with its limits and tested accuracy ([MODELS.md](MODELS.md)). A
third layer, new surface water after storms from a satellite model, was
retired on 2026-10-02 after two tests showed no skill.

| Layer | Made from | Used for |
|---|---|---|
| Battery surge forecast | The author's Granite TTM r2 fine-tune on NOAA CO-OPS water levels and tide predictions at The Battery, run per request | How far above the predicted tide the water may run in the next four days |
| Land cover from the latest imagery | The NYC land-cover model (TerraMind 1.0 base fine-tuned on NYC Land Cover 2017, NYC Open Data) on Copernicus Sentinel-2 L2A scenes of 2018, 2021, 2024 and 2026; scored against NYC Land Cover 2021 (The Nature Conservancy and UVM, CC BY-NC-SA 4.0, used only as a local test key) | Paved, green and tree canopy shares of a place, from the latest year; no change between years is read |
