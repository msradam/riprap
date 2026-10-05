# Fields of the JSON and MCP results

A data dictionary for what Riprap returns to a program: the response of
`GET /api/agent?q=...` and the result of each MCP tool. `/openapi.json`
gives the `/api/agent` response as an open object, so this page is the
description of it.

Every field name below was read from live responses of a local server with
no language model on 5 October 2026: an address
(`90-01 183rd Street, Queens`), a community district (`QN12`), two
comparisons (`Compare Red Hook and Hollis`, `Is Mott Haven hotter than
Riverdale?`), answered questions with a `yes` and a `near` lead, a question
the records cannot answer (`What is the median income in Hunts Point?`), and
heat briefings for an address (`heat 2940 Brighton 3rd St, Brooklyn`) and a
district (`heat QN12`). Each MCP tool was called in the same process. A
response holds only the sources that ran for its query, so no single
response has every field. The interface has no version
of its own yet and is not frozen: a field can be renamed between releases,
and the [changelog](../CHANGELOG.md) says when one is.

Three rules hold for every source block:

- `narrative` is the sentence a briefing prints, word for word. The other
  fields are the figures that sentence was written from.
- A source that was tried and did not answer has no block. It is named in
  `failed`, and its absence is not a zero.
- Dates are ISO 8601. Times are UTC unless a field name says otherwise.

## The envelope

| Field | Type | Meaning |
|---|---|---|
| `query` | string | The text that was asked, unchanged |
| `intent` | string | How the query was read: `single_address`, `neighborhood` (a neighbourhood, community district or borough), or one of the question and refusal intents |
| `plan` | object | The reading of the query: `intent`, `targets` (each a `type` and `text`), `place` (`kind`, `text`, `certain`, `message`), `question` when there is one, `focus` (for heat: `hazard`, `time_frame`, `assets`), and `rationale` (a fixed phrase when rules planned the query; a model's note of at most 300 characters when a model did) |
| `geocode` | object | The place the briefing describes: `address` (the matched name), `borough`, `lat`, `lon` (WGS84 degrees), `match` (`exact` or an approximate match) and `note`, which says which tabulation area a neighbourhood name was answered for, or that a district's shape is an approximation. From NYC Planning Labs' GeoSearch, then Nominatim |
| `lat`, `lon` | number | The same point, WGS84 degrees. For an area, a point inside it |
| `nta` | object or null | For an area: `nta_code`, `nta_name`, `borough`, `bbox` (west, south, east, north, WGS84 degrees) and `n_matches`, from the 2020 Neighborhood Tabulation Areas (NYC Open Data `9nt8-h7nd`). Null for an address |
| `deployment` | string | Which city's sources ran: `nyc`, `chicago`, `seattle`, `albany` or `federal` |
| `paragraph` | string | The whole briefing as text, in Markdown: the scope statement, "Place described: ...", the answer or "In brief", the sections, "Out of scope" and "Not checked". This is the text to print or quote |
| `answer_path` | string | Which path ran: `rules` or `llm`. With no model configured it is always `rules`, also when the question was not answered |
| `answered` | boolean or null | On a question: `false` when the records cannot answer it. The text then opens with what Riprap does not hold and gives the evidence for the place. Null on a bare place and on a comparison |
| `targets` | list | On a comparison only (`intent` is `compare`): one item per place with `label` ("PLACE A", "PLACE B"), `address` (the name as asked) and `state`, that place's own result with the fields of this table. The top-level source blocks are the first place's |
| `grounding` | object | How the text was made and checked; see [Grounding](#grounding) |
| `audit` | object | The same check in its older form: `raw` (text before checking), `dropped` (sentences removed) and `tier` |
| `citations` | object | One record per cited source, keyed by the id in the text's `[doc_id]` markers; see [A citation](#a-citation) |
| `consulted` | list | Every source that ran: `id`, `title`, `stone` (the group it belongs to) |
| `not_checked` | list | Sources that were not read for this query: `id`, `title`, `stone` |
| `failed` | list | Sources that were tried and did not answer: `id`, `title`, `reason` (in plain words, such as "the service refused the request: too many requests"), `started_at` (Unix seconds). Nothing in the briefing is a reading of them |
| `trace` | list | One record per step: `step`, `ok`, `started_at` (Unix seconds), `elapsed_s` (seconds), `err`, `result` |
| `models` | list | The models a sentence in this briefing quotes. Empty when none does |
| `compliance` | object | The 13 disclosure checks: `passed`, `n_passed`, `n_total`, `failed`. They test for caveat phrases and are not a quality score; the name is kept for compatibility |
| `emissions` | object | Energy of any model calls: `n_calls`, `n_measured`, `energy_status` (`measured`, `estimated`, `unknown` or `none`), `total_wh` (watt-hours), `total_duration_s`, `tokens`, `calls`, `method` |
| `dep` | object | The four stormwater readings again, keyed by scenario, for the map |

### Grounding

| Field | Meaning |
|---|---|
| `tier` | `no_llm` when no model wrote or chose anything |
| `model` | The model's name, or null |
| `answer_mode` | `rules` or `extractive` (a model chose among existing sentences) |
| `answer_lead` | The kind of opening: `yes`, `no`, `partly`, `count`, `facts`, `near` (a record was found, farther than 100 m from the address; the lead gives the distance), `day` (a question about a named past day, read from the records dated that day), `cannot_answer`, `not_held`, `not_english`, `not_recognised`, or the kind of a fixed phrase: `no_prediction`, `no_prediction_register` (which places will flood, before an asset list), `no_advice`, `no_score`, `no_ranking`, `needs_address`, `no_satellite`, `no_change_record`, `experimental`, and for heat `heat_forecast`, `no_prediction_heat`, `no_prediction_far`, `no_advice_heat` (whether a home is safe in the heat), `no_air_temp` (no air temperature at an address), `no_deaths`, `cooling_centers`, `surface_yes`, `surface_no` |
| `not_held` | With the `not_held` lead: the topic the question asked for that Riprap does not hold, one of `people`, `income`, `basements`, `law`, `benefits`, `advice`, `score`, `ranking`, `trend`, `rain_on_a_day`, `other_311`. With the `not_english` lead it is `language` |
| `answered` | Whether the question was answered. `false` means the briefing gives the evidence for the place and says it does not answer the question |
| `lead_fact` | The source and figure the opening rests on |
| `claims` | Each sentence kept: `section`, `text`, `doc_ids`, `numbers` |
| `dropped_claims`, `retried_claims`, `n_kept`, `n_dropped` | What the check removed or sent back (model path only) |
| `checks`, `answer_flags` | The rules that were applied to the opening, and any that fired |
| `question`, `n_documents`, `attempts`, `llm_calls` | The question as read, how many source sentences were available, and model calls made |

For a bare place, which asks nothing, `grounding` holds only `tier`,
`claims` and `dropped_claims`.

### A citation

`citations.<doc_id>` holds `doc_id`, `source` (the publisher's name), `title`
(the full citation text, with the source's own caveats), `url`, `license`,
`date_modified` (the date of the data, from the publisher where it gives
one), `retrieved_at` (when Riprap read it), `vintage` (the date shown beside
the sentence) and `maturity` (`production` or `experimental`). The 311
record for an address or a community district adds `query_url`, the exact
Socrata request the count came from. The FloodNet
record adds `license_url`, `attribution`, `references` and `license_notice`:
FloodNet content is CC BY-NC-SA 4.0 and is not under Riprap's Apache-2.0
licence.

## Flood sources for an address

| Block | Source and dataset | Fields |
|---|---|---|
| `sandy` | Sandy Inundation Zone, NYC Open Data `5xsi-dfpx` | `inside` (true or false), `inside_or_outside` and `inside_phrasing` (the same as words), `edge_m` (metres to the mapped edge when within 50 m), `edge_note` |
| `fema_nfhl` | FEMA National Flood Hazard Layer, effective map | `fld_zone` (FEMA's zone code), `zone_subty`, `sfha` (inside the Special Flood Hazard Area), `firm_panel`, `effective_date`, `effective_year` |
| `fema_pfirm` | FEMA Preliminary NFHL (the 2015 preliminary map) | `fld_zone`, `zone_subty`, `sfha`, `static_bfe_ft` (base flood elevation, feet, in `vertical_datum`), `community`, `issue_date` |
| `dep_extreme_2080`, `dep_moderate_2050`, `dep_moderate_current`, `dep_limited_current` | NYC Stormwater Flood Maps, NYC Open Data `9i7c-xyvv` (the Limited map from DEP's viewer tiles) | `category_code` (0 outside, 1 and 2 the two rainfall categories, 3 the future high tides category), `category` (the city's words for it, or null outside), `edge_m` (metres to the nearest mapped flooding when close). A modelled scenario, not a forecast, and no depth beyond the category |
| `ida_hwm` | USGS Short-Term Network, Hurricane Ida 2021 high-water marks | `n_within_radius`, `radius_m` (800), `max_elev_ft` (water surface, feet, in `vertical_datum`), `max_height_above_gnd_ft`, `nearest_dist_m`, `nearest_site`, `nearest_elev_ft`, `sample_sites`, `points` (the marks, for the map) |
| `microtopo` | USGS 3DEP elevation model | `point_elev_m` (metres, NAVD88, from the cell that contains the point; a cell's value can differ from a survey point by a metre or more), `resolution_m` (the cell size, about 22), `rel_elev_pct_200m` and `rel_elev_pct_750m` (the share of ground within that distance that is lower), `basin_relief_m`, `aoi_min_m`, `aoi_max_m`, `aoi_radius_m`, `hand_m` (height above the nearest drainage channel, metres) |
| `floodnet` | FloodNet Data API (`api.floodnet.nyc`), CC BY-NC-SA 4.0 | Counts and summaries only: `n_sensors` within `radius_m` (600), `n_flood_events_3y` (events FloodNet marks as verified by a person), `n_flood_events_good_3y` (those at sensors listed as good), `n_event_days` (distinct UTC days with an event), `by_year` (events by the UTC year they started), `n_events_unreviewed` (labelled flood, not yet verified, not counted), `period_start` (the first day the count covers), `n_sensors_with_events`, `n_sensors_not_good` (sensors with a status other than good when read), `highest_event`, `peak_event` and `other_status_peak_event` (each a depth in mm and its UTC date), `latest_event_start`, `n_events_open_24h`, `status_read_at`, `license`, `license_url`, `attribution`. No sensor id, name, street or coordinate, and no event row, is served |
| `nyc311` | 311 Service Requests, NYC Open Data `erm2-nwe9` | `n` (complaints after the duplicate rule), `radius_m` (200), `years`, `since` (first day of the window), `where`, `capped` (true if the query limit was reached), `by_year`, `by_descriptor` (the portal's descriptor strings), `by_kind`, `histogram`, `most_recent` (each a `date`, `descriptor` and `block`) and `points` (the same, with `lat` and `lon` rounded to three decimal places; `block` is the street and its cross streets, never a house number), `query_url` (the exact Socrata query; absent for a neighbourhood, which is counted inside its outline after a wider request), `caveat` (the under-reporting caveat) |
| `nws_obs` | National Weather Service, latest observation at the nearest station | `station_id`, `station_name`, `distance_km`, `obs_time`, `weather`, `raining`, `temp_c`, `precip_last_hour_mm`, `precip_last_3h_mm`, `precip_last_6h_mm`, `error` |
| `noaa_tides` | NOAA CO-OPS water levels and tide predictions | `station_id`, `station_name`, `station_lat`, `station_lon`, `distance_km`, `datum`, `observed_ft`, `observed_ft_mllw` and `predicted_ft_mllw` (feet above mean lower low water), `residual_ft` (observed less predicted), `obs_time`, `error` |
| `usgs_gauges` | USGS Water Data, latest continuous values | `site_no`, `site_name`, `distance_km`, `stage_ft` (feet), `discharge_cfs` (cubic feet per second, where published), `obs_time`, `n_gauges_in_area`. Field names read from `app/context/usgs_gauges.py`: the service refused the requests on the day this page was written, so no live block was seen. No gauge is quoted beyond 5 km |
| `nws_alerts` | National Weather Service active alerts | `n_active`, `alerts` (flood, coastal and tropical storm alerts at the point), `retrieved_at`, `error` |
| `nws_water_forecast` | NWS National Water Prediction Service | `gauge_id`, `gauge_name`, `distance_km`, `forecast_peak_ft_mllw`, `forecast_peak_time_utc`, `issued_utc`, `forecast_until_utc`, `flood_stages_ft` (the gauge's flood stages, feet), `flood_category` |
| `npcc4_slr` | NPCC4 (2024), sea-level rise projections, Table 1 | `baseline`, `place`, and for `2030s`, `2050s`, `2080s` and `2100` the projected rise. Citywide, not for the address |
| `mta_entrances` | MTA Subway Entrances and Exits, data.ny.gov `i9wp-a4ja` | `n_entrances` within `radius_m` (800), `n_checked`, `n_ada_accessible`, `n_inside_sandy_2012`, `n_in_dep_extreme_2080` with `n_in_dep_extreme_2080_rainfall` and `n_in_dep_extreme_2080_tidal` (the map's rainfall categories and its future high tides category, counted apart), `entrances` (each with its station, routes, coordinates, `distance_m`, `elevation_m`, `hand_m`, `inside_sandy_2012` and, as `dep_extreme_2080_category` and `dep_moderate_2050_category`, `outside` or the category name; each entrance is read at its own point, with no buffer) |
| `nycha_developments` | NYCHA Public Housing Developments, NYC Open Data `phvi-damg` | `n_developments` within `radius_m` (2,000), `n_inside_sandy_2012` (10% or more of the outline), `n_in_dep_extreme_2080` (centre point) with its `_rainfall` and `_tidal` parts, `developments` |
| `doe_schools` | 2019 - 2020 School Point Locations, NYC Open Data `a3nt-yts4` | `n_schools` within `radius_m` (1,500), `n_inside_sandy_2012`, `n_in_dep_extreme_2080` with its `_rainfall` and `_tidal` parts, `schools` |
| `doh_hospitals` | Health Facility General Information, health.data.ny.gov `vn5v-hh5r` | `n_hospitals` within `radius_m` (3,000), `n_checked`, `n_inside_sandy_2012`, `n_in_dep_extreme_2080` with its `_rainfall` and `_tidal` parts, `hospitals` (each read at the one point the state file gives) |
| `city_landcover` | Land Cover Raster Data (2017), NYC Open Data `he6d-2qns` | `year`, `radius_m`, and the shares of ground, in percent: `built_pct`, `green_pct`, `tree_canopy_pct`, `water_pct`, `bare_pct` |
| `landcover` | Riprap's experimental land-cover model on Copernicus Sentinel-2 | The same shares, with `dates` (the images) and `model`. Experimental: a model's estimate, not a record |

Each block also has `narrative`. Some have `headline_value` or
`subhead_text`, which are the page's display strings and repeat the
narrative's figures; `available` (false when a source's saved file could not
be read); and `citation`, the source's citation text, which `citations`
also holds.

## Flood sources for an area

A neighbourhood, community district or borough gets the area version of a
source, with `_nta` on the name.

| Block | Source and dataset | Fields |
|---|---|---|
| `area_boundary` | 2020 Neighborhood Tabulation Areas, NYC Open Data `9nt8-h7nd` | `geojson` (the outline that was used) |
| `sandy_nta` | Sandy Inundation Zone `5xsi-dfpx` | `overlap_area_m2`, `polygon_area_m2` (square metres), `fraction` (0 to 1), `inside` |
| `dep_extreme_2080_nta`, `dep_moderate_2050_nta`, `dep_moderate_current_nta`, `dep_limited_current_nta` | NYC Stormwater Flood Maps `9i7c-xyvv` | `scenario`, `label` (the city's map name), `fraction_any` (share of the area's land in any mapped category, 0 to 1), `fraction_class` (the share in each category code: 1 and 2 rainfall, 3 future high tides), `polygon_area_m2` |
| `microtopo_nta` | USGS 3DEP | `n_cells`, `elev_min_m`, `elev_p10_m`, `elev_median_m`, `elev_max_m` (metres, NAVD88) |
| `floodnet_nta` | FloodNet Data API | The address fields, for the sensors inside the outline |
| `nyc311_nta` | 311 Service Requests `erm2-nwe9` | The address fields. A community district is counted by the record's `community_board`; a neighbourhood by its exact outline. Three years |
| `dcp_floodplain_nta` | NYC Planning, Community District Profiles | `community_district`, `n_buildings`, `n_residential_units`, `n_residents_2010`, `floodplain_sq_mi`, all for the district's 1% annual chance floodplain as the profile prints them |
| `mta_entrances_nta`, `nycha_developments_nta`, `doe_schools_nta`, `doh_hospitals_nta` | As for an address | Counts for the facilities inside the outline, with `n_near_sandy_edge` and the list of those inside a mapped extent |
| `city_landcover_nta`, `landcover_nta`, `npcc4_slr_nta`, `nws_alerts_nta` | As for an address | The address fields, for the area |

## Heat sources

A heat briefing for an area has the same blocks with `_nta` on the name:
`heat_surface_nta`, `hvi_nta`, `heat_visits_nta`, `heat_station_nta`,
`heat_obs_nta`, `nws_heat_forecast_nta`, `nws_heat_alerts_nta`,
`npcc4_heat_nta` and `cool_features_nta`.

| Block | Source and dataset | Fields |
|---|---|---|
| `heat_surface` | Landsat 8 and 9 Collection 2 Level 2 surface temperature (USGS) | `mean_diff_f`, `min_diff_f`, `max_diff_f` (degrees Fahrenheit warmer than the city's land average; surface, not air), `n_images`, `first`, `last`, `latest_surface_f`, `latest_city_mean_f`, `warmer_in_every_image`, `cooler_in_every_image`, `by_image`, `radius_m` (150) |
| `hvi` | Heat Vulnerability Index 2023, NYC Health Department, Environment and Health Data Portal | `hvi` (1 to 5, a rank among neighbourhoods), `area`, `area_code`, `year`, `ac_pct` (households with air conditioning, a survey estimate), `green_pct`, `median_income` (dollars); for a district, `neighbourhoods` |
| `heat_visits` | Heat stress emergency department visits 2018 to 2022, NYC Health Department from New York State SPARCS | `district`, `period`, `n` (a five-year total), `age_adjusted_rate` and `citywide_age_adjusted_rate` (average annual, per 100,000 residents), `suppressed` (true when the department withholds a small count) |
| `heat_station` | NOAA Regional Climate Centers, ACIS daily records | `station`, `station_id`, `distance_km`, `year`, `through`, `days_ge_90` and `days_ge_90_last_year` (days at or above 90°F), `normal_days_ge_90` (1991 to 2020 average), `max_f`, `max_date`, `record_f`, `record_date`, `record_since`, `by_year`, `max_by_year` |
| `heat_obs` | National Weather Service, latest observation | `station`, `station_id`, `distance_km`, `observed`, `temp_f`, `heat_index_f`, `humidity_pct` |
| `nws_heat_forecast` | National Weather Service gridpoint forecast | `office`, `grid`, `issued`, `highs` (seven days), `max_high_f`, `max_high_date`, `max_apparent_f`, `max_apparent_at`. The Weather Service's forecast for a 2.5 km cell, not Riprap's and not for a building |
| `nws_heat_alerts` | National Weather Service active alerts | `n_active`, `alerts`, `retrieved_at`, `error` |
| `npcc4_heat` | NPCC4 (2024), extreme heat projections, Table 4 | `baseline_period`, `baseline`, `place`, and `2030s`, `2050s`, `2080s`. Citywide |
| `cool_features` | NYC Parks Spray Showers `ckaz-6gaa` and Pools `y5rm-wagw`, NYC Open Data | `n_spray_shower_sites`, `n_outdoor_pools`, `n_indoor_pools`, `n_wading_pools`, `n_sites`, the lists `spray_shower_sites`, `pools` and `wading_pools`, `radius_m` (800) |
| `city_landcover`, `landcover` | As for flood | Tree canopy and paved share |

## MCP tools

`uv run riprap-mcp` serves seven tools. Each of the three that run a
briefing returns a `record` (`query`, `run_at`, `riprap_version`, `commit`,
`sha256` of the body) so a result can be filed and checked later.

| Tool | Returns |
|---|---|
| `get_evidence(address, hazard)` | `place`, `place_match`, `place_note`, `lat`, `lon`, `deployment`, `intent`; `evidence`, one item per source with `doc_id`, `stone`, `text` (the sentence), `value` (the source block above, without `narrative`, `headline_value` and `citation`), `maturity`, `source_url`, `vintage`; `citations`; `license_notices` (for FloodNet: `doc_id`, `license`, `license_url`, `attribution`, `references`, `retrieved_at`, `notice`); `failed`; `record` |
| `get_district_summary(community_district, hazard)` | The same shape, for a community district such as `QN12`. A code that is not a district (`QN99`) returns only `error`, which names the borough's range |
| `get_briefing(address, question)` | `address`, `question`, `place`, `place_match`, `place_note`, `deployment`, `intent`, `paragraph` (the briefing text), `mode`, `answered`, `answer_mode`, `answer_lead`, `answer_path`, `dropped_claims`, `citations`, `license_notices`, `consulted`, `not_checked`, `failed`, `disclosure_checks`, `record` |
| `nyc311_flood_requests(address or lat and lon, radius_m, days)` | `lat`, `lon`, `radius_m`, `definition`, `days`, `n`, `capped`, `by_descriptor`, `by_kind`, `by_month`, `most_recent` (each a `date`, `descriptor`, `block` and `status`; no house number), `query_url`, `caveat`, `source`, `source_url`. Dataset `erm2-nwe9` |
| `plan_query(question, address)` | How a query would be read, without running it: `planner`, `intent`, `targets`, `place`, `question`, `focus`, `chosen`, `floor`, `selected` (the sources that would run), `deployment`, `rationale` |
| `list_sources(deployment)` | `stones` (the five groups) and `pebbles`, one per source manifest with its `id`, `title`, `stone`, `hazard`, `tier`, `maturity`, `scope`, `narration`, `type`, `display`, `provenance` (URL, licence, dates) and `fallback` |
| `get_citation(deployment, doc_id)` | One citation record: `doc_id`, `source`, `title`, `url`, `license`, `date_modified`, `retrieved_at`, `vintage`, `maturity`, or `error` when the id is unknown |
