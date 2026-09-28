# Data sources

The public sources behind the NYC deployment. Each manifest's `provenance` block is the authority for its URL, licence and vintage. Moved from the README in refactor 7.

## Data sources

Riprap contacts only public-record federal, state and city sources at
runtime. No commercial APIs, no proprietary scores. Source URLs, licences,
`date_modified` and `retrieved_at` for each come from the pebble's manifest
`provenance` block; `list_sources` on the MCP server prints them.

| Source | Hosting agency | Used for |
|---|---|---|
| Hurricane Sandy 2012 inundation zone | NYC OTI / NOAA Office for Coastal Management | Hazard memory |
| NYC DEP Stormwater Flood Maps | NYC Department of Environmental Protection | Modeled scenarios |
| FEMA National Flood Hazard Layer | FEMA | Regulatory flood zone |
| Hurricane Ida 2021 USGS high-water marks | USGS Short-Term Network | Empirical points |
| FloodNet ultrasonic sensor network | NYU CUSP / FloodNet | Flood-event log |
| NYC 311 flood complaints | NYC Open Data | Complaint history |
| NOAA tide gauge, The Battery | NOAA CO-OPS | Tide and surge level |
| USGS stream gauges | USGS Water Data (OGC API) | Live stage |
| NWS observations and alerts | National Weather Service | Precipitation, active warnings |
| MTA subway entrances | MTA / NYC Open Data | Transit assets |
| NYCHA developments | NYC Housing Authority (`phvi-damg`) | Public housing |
| NYC DOE schools | NYC Department of Education | Schools |
| NYS DOH hospitals | New York State Department of Health (`vn5v-hh5r`) | Hospitals |
| USGS 3DEP 1 m DEM | USGS National Map | HAND and TWI |
| NYC DOB permits | NYC Department of Buildings | `development_check` intent |
| NPCC4 sea-level projections and agency PDFs | NYC Panel on Climate Change, NYC agencies | Policy context |
| Sentinel-2 MSI imagery | ESA / Copernicus | Offline Prithvi layers |

