# Data sources

The public sources behind the NYC deployment. Each manifest's `provenance`
block is the authority for its URL, licence and vintage; `list_sources` on
the MCP server prints them.

Riprap contacts only public-record federal, state and city sources at
runtime, plus NOAA's gauge and Hugging Face when the experimental surge
model is installed. No commercial APIs, no proprietary scores. The NYC
deployment has 41 manifests: 37 in `deployments/nyc/manifests/` and 4 in
`deployments/federal/manifests/`. A point manifest and its area version
read the same source, so the table has fewer rows than that: 23 public
sources, 20 of them read for an address and 18 for a neighbourhood or
district. Five more manifests are the experimental model layers, listed
after the table.

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

## Experimental model layers

Model output, not records. Each is labelled experimental wherever it
appears, with its limits and tested accuracy ([MODELS.md](MODELS.md)).

| Layer | Made from | Used for |
|---|---|---|
| Battery surge forecast | The author's Granite TTM r2 fine-tune on NOAA CO-OPS water levels and tide predictions at The Battery, run per request | How far above the predicted tide the water may run in the next four days |
| New surface water after storms | The author's Prithvi-EO 2.0 fine-tune on Copernicus Sentinel-2 L2A scenes (Microsoft Planetary Computer) after 15 heavy-rain events since 2017, picked from NOAA's daily rainfall at Central Park | What the satellite model showed near a place after Hurricane Ida and other storms |
| Land cover by year | The author's TerraMind adapter on Copernicus Sentinel-2 L2A scenes of 2018, 2021, 2024 and 2026; checked against ESA WorldCover 2021 | Paved and green shares of a place, and whether they changed |
