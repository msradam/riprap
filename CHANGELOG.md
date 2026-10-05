# Changelog

All notable changes to Riprap. The hackathon submission tag is
`v0.5.0` (build 2026-05-07); subsequent dates record polish work
that landed on the hackathon-period production deploys.

## [Unreleased] (the review fix pass) - 2026-10-05

A sanity check, run by AI agents separate from those that wrote the code,
re-derived 487 briefing sentences from the
public sources: 475 were confirmed, 10 were wrong and 2 sat on a raster edge
([docs/history/SANITY-CHECK-2026-10-05.md](docs/history/SANITY-CHECK-2026-10-05.md)).
This pass fixes what it found and says in the documents what it could not
fix. Nine reviewers then read the result as its audiences would (FloodNet,
NYU CUSP, BetaNYC, the City's Open Data team, a civic technologist,
planners, city climate staff, community groups, a data journalist), and
what they raised is fixed here too. Where a later fix replaced an earlier
one, the entry gives the final state. Branch `review/fix-pass`; not tagged,
and the version is unchanged.

### Fixed

- **Place.** Rockaway Park, Broad Channel, Belle Harbor and City Island
  resolve by name, for flood and heat. A house number and a name is an
  address whatever the street type ("1 Bowling Green", "15 Central Park
  West"). An address with no borough is looked up in the city's address file
  first, and a note says which borough was chosen when several have it.
- **Address elevation** reads the cell that contains the point, states
  NAVD88 and is rounded to what a cell about 22 m across supports (400
  Carroll Street: "about 1 m", was 0.0 m). A point in the lowest ground
  nearby is said to be "among the lowest ground within 200 m".
- **Hospitals** are counted once each (61, where the file's 67 rows had
  doubled some counts).
- **Public housing** counts as inside the Sandy extent when 10% or more of
  its outline is (39 of 218 developments, was 20 by centre point).
- **Neighbourhood 311 counts** use the exact outline.
- **Answers.** A question that names two areas compares both, side by side,
  under a note that nothing is scored or ranked. An insurance, price or
  advice question opens with an out-of-scope statement, then the FEMA zone
  and a pointer to FloodHelpNY. "Here is what they show." is never followed
  by nothing. A failed FEMA query is listed under "Not checked."
- NYC Planning floodplain zeros that the source does not support are no
  longer printed.
- **Failed sources.** For every source, one that was tried and did not
  answer is listed under "Not checked." in the text and in a `failed` list
  in the JSON, and a failed reply is not kept in the HTTP cache.
- **Heat sentences.** The heat illness sentence says its count is a five-year
  total and its rate the department's average annual age-adjusted rate. The
  cooling sentence names wading pools as wading pools, from a list copied
  again on 5 October, and gives that date.
- **Gallery.** All 35 entries were rebuilt twice on 5 October with no model,
  the second time after the audience-review fixes. Each saved file has
  FloodNet's per-sensor and per-event records and every 311 house number
  taken out, and is marked so. In the second build USGS refused the stream
  gauge request (HTTP 429) for the 19 address entries that ask it, and each
  lists the gauge as not answered; no other source failed. The surge entry
  is removed, and the blurbs were read against the briefings under them
  (East Harlem's now gives the figures of East Harlem (North)).
- Accessibility barriers found by reading the code: a focused control could
  sit under the sticky header (WCAG 2.4.11), the landing's moving preview
  had no stop control (2.2.2), the map could be panned only by dragging
  (2.5.7), and the header's query button had a name without its visible text
  (2.5.3).

### Changed

- **FloodNet sentences use FloodNet's terms.** No "above-curb", no
  "community sensors", no "flagged by FloodNet for maintenance". A sentence
  gives FloodNet's definition of a flood event (depth readings above 10 mm at
  the sensor), the period from the sensors' install dates, the number of
  separate UTC days and each year's count, and the highest depth on record,
  saying that its event is verified and quoting the sensor's status as the
  API lists it today. Only events the API marks as verified by a person are
  counted, and the sentence says how many more are labelled flood but
  unverified (Hollis: 6 events on 3 days, was 14; QN12: 40, was 54). A
  verified event counts toward a yes whatever its sensor's status today.
  The ten tide gauges in FloodNet's deployments table are not counted as
  sensors. A sentence about now says no event labelled flood was open and
  that one under way may not be labelled yet, and FloodNet's own depth
  caveats are quoted in its citation.
- **No FloodNet record is served.** The JSON, the MCP results, the page and
  the saved gallery files hold sentences, counts and each highest depth
  with its date: no deployment id, sensor name, street, coordinate or event
  row. `/api/floodnet_near` is removed (404), the map draws no sensor points
  and points to FloodNet's dashboard, and `flagged_peak_event` is
  `other_status_peak_event`.
- **FloodNet-derived output carries its licence.** Citations, JSON, MCP
  results (`license_notices`), the page's source list and NOTICE say the
  FloodNet sentences and figures are CC BY-NC-SA 4.0 and not under
  Apache-2.0, with the credit "FloodNet (New York University and The City
  University of New York)", Mydlarz et al. (2024) and Silverman et al.
  (2022), and a retrieval time.
- **The surge forecast is out of default briefings.** On 639 held-out
  four-day windows its mean error was 0.115 m; damped persistence scored
  0.108 m and beats it (difference 0.0065 m, 95% interval 0.0032 to 0.0096).
  It foresaw 1 of 23 flood-stage windows, which are 5 distinct events. Its
  manifest moved to `deployments/nyc/optional/`; a server opts in with
  `RIPRAP_EXTRA_MANIFESTS=deployments/nyc/optional`. The hosted model card is
  out of date; a corrected card is at
  `docs/model-cards/Granite-TTM-r2-Battery-Surge.md`.
- **Four stormwater maps, in the city's own words.** The fourth, "Limited
  Flood (1.77 inches/hr) with Current Sea Levels", is read from the vector
  tiles of DEP's viewer. Sentences use the city's map names, call them
  modelled scenarios and not forecasts, carry the city's disclaimer, say
  near a boundary that the point is "at the edge of flooding mapped on it
  (within about N m)", and say "Outside a mapped extent does not mean safe"
  with NYC Emergency Management's Ida finding, quoted in full. The JSON
  gives a `category` and `category_code`, never a depth.
- **311.** Every count ends with an under-reporting caveat, a lead says "a
  count of reports", and a district lead carries the breakdown by descriptor
  group. The count is named "flood and sewer complaints" in the sentence
  and in the leads, with the window's first day, and the citation carries
  the exact Socrata query, which the page's source list links.
- **311 complaints are placed at the block.** No house number and no
  per-house coordinate is served or saved: each complaint has its street
  and cross streets, with coordinates rounded to three decimal places
  (about 100 m). Counts do not change. A geocoded address no longer carries
  a tax lot or building number.
- **Asset lists.** Every school, subway entrance and hospital is read at its
  own point with no buffer, for an address and a district alike, so the two
  agree. Counts inside the city's "Extreme Flood (3.66 inches/hr) with 2080
  Sea Level Rise" map split its rainfall categories from its future high
  tides category, and each list carries the scenario caveat.
- **Construction permits** are out of plain briefings. A construction
  question gets a sentence that names the older DOB file, tests expiry and
  says DOB NOW is not counted.
- Schools are "public schools" from the 2019 to 2020 locations file
  (`a3nt-yts4`), charter schools included. Lists say "inside a mapped flood
  extent", not "flood-exposed".
- "wind alerts" is "flood, coastal or tropical storm alerts". The FEMA
  sentence names the effective map as the one in force for the National Flood
  Insurance Program.
- No stream gauge is quoted beyond 5 km; the tide sentence gives its
  station's distance and water body; the Ida sentence gives heights above
  ground; the Sandy sentence gives the flooded area beside the area's total.
- The land-cover sentence states how far its canopy reading sits from the
  city's map, and a change-over-time question is told first that the two
  figures are from different methods.
- The fixed disclaimer adds that a briefing is about records of a place, not
  an assessment of a property or of the people who live there.
- The landing's hero line: "Rules or an open Granite model read your question
  and choose the evidence. Every sentence you read comes word for word from a
  public record, with its source and date." The footer says "built to meet"
  WCAG 2.2 AA and no longer names Section 508 or the Plain Writing Act.
- The README's lead example is the live answer of 2026-10-05, and its claim
  that no other tool does these things together is gone.

### Added

- `geocode.note` (JSON), `place_note` (MCP) and the page's place line say
  which tabulation area a neighbourhood name was answered for, and that a
  district's shape is City Planning's approximation.
- `answer_path` ("rules" or "llm") on every response; the `models` block
  lists only models a sentence quotes.
- An accessibility statement (`/accessibility/` and
  `docs/ACCESSIBILITY.md`) and an about page (`/about/`) with the AI
  disclosure, linked from the footer of every page; pan buttons on the map
  and a pause button on the landing's preview.
- The README says where a language model can run, how Riprap was built and
  checked, and that it is built by one person with no community group,
  agency or resident yet involved.
- `docs/METHODOLOGY.md`: what the data cannot say (with sources), the
  distances, time windows and filters behind each count, and how to report
  an error. `docs/DATA-SOURCES.md`: every NYC Open Data dataset by name and
  ID with what Riprap does to it. `docs/BACKGROUND.md`: related work.
- The footer and README say Riprap is not an alert or emergency service
  (Notify NYC, 311, FloodHelpNY) and name every publisher it is independent
  of, FloodNet, New York University and the City University of New York
  among them.

### Removed

- `data/experimental/water_coastal_floodnet.json` (per-event FloodNet rows);
  an aggregate summary replaces it. History was not rewritten.
- The district clause on land "less than 1 m above the nearest drainage
  channel".
- The README's thanks to FloodNet by name; a data credit in the form FloodNet
  asks for replaces it.

### Answers after the audience reviews

- **A plain yes needs a record on the block.** For an address, "Yes." needs
  a verified sensor event or an Ida high-water mark within 100 m.
  Farther off the lead reads "Flooding was recorded near this address, not
  at it", with the distance (`near`). A yes about an area names the
  tabulation area in the lead.
- **Unanswered questions say so.** A question the records cannot answer
  (people and households, income, basements, law, aid, advice to an agency,
  a flood score, a ranking, a trend, rainfall on a past day, another 311
  topic) opens with what Riprap does not hold, in the text as well as on
  the page, with `answered: false` and `grounding.not_held`. A question not
  in English gets one line each in Spanish, Chinese and Bengali
  (`not_english`); a place with an ask no rule reads is `not_recognised`.
- **Safety, flood zone and now.** A "safe?" or basement question is declined
  and then shown the observed record first, the stormwater maps, FEMA and
  "Outside a mapped extent does not mean safe", with a pointer to Notify
  NYC. A flood zone answer says it is not a determination and points to
  FEMA's Map Service Center. A named past day is read from the records
  dated that day (`day`); "right now" questions get the live readings;
  "which schools will flood" gets the no-prediction lead before the list
  (`no_prediction_register`).
- **One year of sensor events.** A question about FloodNet events in one
  year leads with that year's count.
- **Heat.** The Heat Vulnerability Index sentence gives the Health
  Department's four factors in its words and quotes its sentence on
  structural racism. A heat "safe" question is declined first
  (`no_advice_heat`), and an air temperature question is told Riprap has
  none at an address (`no_air_temp`). The out-of-scope line points to the
  NYC Urban Heat Portal for air temperature.
- **Other.** The MCP district tool rejects a code that is not a district; a
  park, cemetery or airport area says so; a failed source's reason is in
  plain words; the fixed out-of-scope line no longer speaks of title and
  zoning.

### Documents, landing and repository files after the audience reviews

- **Stale images removed.** The landing sets the saved Hollis answer as
  text read at build time, with no screenshot and no map; the README's
  screenshot is gone and its quoted examples were read again from the app.
- **Landing cards.** The 311 "No." card says it is a No about reports,
  carries the under-reporting caveat and says the address is in the
  wholesale food markets; the heat card for the same address says so too.
  The gallery question now asks about "the last five years", the window its
  sentence counts. Cards lead with a count and extent, facility names below.
- **Plain headings.** Briefing sections are headed "Mapped hazards", "Live
  readings", "Places and facilities" and "Projections" (stone taglines in
  every deployment), "Trace, by Stone" is "What each source returned", and
  the page glossary explains PFIRM and METAR.
- **FloodNet's licence** is linked and its clauses quoted in `NOTICE` and
  `docs/DATA-SOURCES.md`, with what Riprap does about each and the plain
  statement that FloodNet has not been asked and has not approved the use.
  The README badge and `CITATION.cff` point to the exception.
- **What the checks are.** "Head-to-head comparison" is explained (rule path
  against model path, judged by AI agents); the sanity check is described
  as the work of separate AI agents; the absence of any validation against
  observed flooding is stated in the README, the methodology and the about
  page.
- **A count can be rerun.** `docs/METHODOLOGY.md` lists the eleven 311
  descriptors as the portal spells them, the 1,825 day window and the
  duplicate rule, and recounts the Hollis example (90, 89, 88). The plain
  descriptor names are not new in 2026: 2,791 rows of 2023 carry them.
- **`docs/API-FIELDS.md`**, a data dictionary for the JSON and each MCP
  tool's result, read from live responses.
- **A plain correction form** (`.github/ISSUE_TEMPLATE/correction.yml`) with
  no technical fields; blank issues are on; the chooser's dead links are
  gone; `CONTRIBUTING.md` opens with residents, students and researchers.
- `CITATION.cff` and `NOTICE` no longer describe the surge forecast as in
  briefings, the gallery as made with a model, or the project as only
  "assisted" by language models.
- The NYC Urban Heat Portal is in the README's table of official sources;
  the about page lists the NYC Open Data datasets by ID; `docs/PRIVACY.md`
  says 311 complaints are shown at the block; `docs/BACKGROUND.md` is
  rewritten for the readers the README names; source counts agree (25).

### Still open

- The hosted surge model card is unchanged.
- The Health Department's heat illness count and rate still disagree in its
  file for most districts. The sentence now says what each figure is and
  that both are printed as published; the gap has not been reported to the
  department.
- A pool just outside an area's outline is still missed by the cooling
  sentence.
- The landing's preview image and the README screenshot showed the Hollis
  answer's earlier sentences and a map of sensor points. Both were removed,
  with the scripts that captured them; a new screenshot needs a browser.
- The public site still serves the earlier build.
- The USGS stream gauge did not answer during the second gallery build, so
  no saved address briefing quotes a gauge.
- The hero line says every sentence comes word for word from a public
  record, and the about page says the sentences are written by Riprap's
  code from records. Seven reviewers read the two as in conflict; the
  wording is the owner's to settle.
- Nothing tests the joined evidence against observed flooding.
- FloodNet has not been asked about Riprap's use of its data. Event rows
  removed from the tree on 2026-10-05 remain in git history.

## [Unreleased] (a heat briefing, and the models settled) - 2026-10-02

Riprap becomes a climate briefing: the same method, proved on a second
hazard. Branches `models/terramind-nyc` and `climate/heat`; not tagged.

### Added

- **A heat briefing for New York City.** A query about outdoor heat ("heat
  QN12", "extreme heat at 90-01 183rd Street, Queens", "Will it be dangerously
  hot this week at ...") gets a briefing built like the flood one, from ten
  public sources: Landsat surface temperature against the city's average
  (18 clear summer images, 2023 to 2026), the Health Department's Heat
  Vulnerability Index and heat illness emergency visits, the city's 2017
  land cover map, days at or above 90 F at the nearest long-record station,
  the latest observation, the Weather Service's forecast and heat alerts,
  NPCC4 projections, and NYC Parks spray showers and pools. Each sentence
  carries the caveat its figure needs. A bare place still gets its flood
  briefing, and each page links to the other.
- Heat questions answered by rules (`riprap/core/burr/heat_answer.py`): now,
  the coming days (the Weather Service's forecast, named as its own), the
  coming decades, counts of hot days, hotter or cooler than the city,
  comparisons of two places, and the named sources. A borough or the city
  is a place for a heat question.
- Heat refusals: health or safety advice, a score or a ranking (the Health
  Department's index is quoted as the department's), the temperature in one
  building or on a named day, and indoor heating in winter, which is named
  as such and sent to 311.
- A `hazard` field on every manifest (`flood`, `heat` or `any`), and
  `hazard=heat` on `/api/district/{code}`, `get_evidence` and
  `get_district_summary`.
- The city's 2017 land cover map as a measured source (`city_landcover`),
  quoted before the land-cover model's estimate.
- Ten heat entries in the gallery, a surface temperature overlay on the
  map, and heat on the landing page.
- Independent heat keys (`tests/golden/keys_heat.py`) and a question set
  written without sight of the code (`tests/golden/unseen_heat.json`).

### Changed

- The land-cover layer is the NYC land-cover model (TerraMind 1.0 base
  with a per-pixel branch, trained on the city's 2017 map), replacing the
  `lulc_nyc` adapter. Its sentence states its measured error and that the
  2017 map read as 2021 is closer to the 2021 map than the model is.
- The place parser takes a named building or park in a question as the
  place, and no longer takes a sentence's first capitalised word or a lone
  compass word for one.
- A question about what satellite imagery showed of a flood gets a lead
  that says Riprap quotes none and why, then the surveyed record.

### Removed

- The satellite water layer (`prithvi_water`, `prithvi_water_nta`, its
  fifteen rasters and its registry entry). Tested on Hurricane Ida and on
  44 coastal and tidal flood moments that FloodNet sensors recorded at the
  instant of a satellite pass, it and IBM and ESA's official flood model
  found flooding no more often than chance (`docs/MODELS.md`).

### Breaking

For a program that reads Riprap's output:

- `prithvi_water` and `prithvi_water_nta` are gone from results, the
  catalogue and `/api/models`.
- The land-cover value's `by_year`, `first_year`, `built_pct_first`,
  `built_change_points` and `noise_points` are gone; `tree_pct` is
  `tree_canopy_pct` (part of `green_pct`); `model` is the model's name.
- `final.models[].repo` is null for a model whose weights are not
  published, and `/api/models` keys that model by its name.
- A heat question is no longer `out_of_scope`: it plans with
  `focus.hazard: "heat"` and runs.

## [0.8.0] - 2026-10-01

Four passes since 0.7.0, newest first: an independent review that restored
three experimental models and fixed what it found, a comparison with the
public alternatives, a pass over the live experience, and a polish pass for
demos.

### Breaking

For a program that reads Riprap's output, between 0.7.0 and 0.8.0:

- `POST /api/print` (the server-side PDF) and the `pdf` extra are gone; the
  print view remains. `GET /api/layers/prithvi_water` and
  `/api/register/mta_entrances` are gone.
- `/api/register/{schools,nycha}` rows no longer carry `score` or `tier`;
  `riprap-register` writes plain flags to `outputs/<class>_flood_flags.csv`
  and has no `--top`.
- `?deployment=` with a name that is not a shipped deployment (for example
  `boston`, `sf`) returns 404, not New York data. `/api/district/{code}`
  returns 404 for a code that is not a district. `/api/agent` needs a
  non-empty `q`.
- The stream no longer sends `plan_token`, `stone_start`, `stone_done` or
  `token` events, and the `plan` event has no `specialists`.
- `grounding.tier` is `no_llm` whenever no model was called in synthesis
  (a refusal was `llm` with zero attempts). `grounding.answer_mode` is null
  when nothing answered. `grounding.answer_lead` has two new values,
  `experimental` and `no_prediction`.
- `/api/models` reports `in_process`, `precomputed`, `installed` and
  `llm_endpoints`; a result's `models` rows have `how`: `loaded`,
  `precomputed` or `endpoint`.
- Manifests: the adapters `ckan_records`, `local_corpus_with_ner` and
  `model_call`, the record filter `flood_311_model`, the pebble type `model`
  and the tier `synthetic` no longer exist. `spatial.scope` is `point`,
  `polygon` or `any`.
- The San Francisco and Boston deployments and the heat and air scaffolds
  are gone.

### Second independent review (2026-10-01)

Experimental models, restored and labelled:

- The author's three fine-tunes are back as experimental sources:
  `msradam/Granite-TTM-r2-Battery-Surge` (a 96-hour surge forecast at the
  Battery, on CPU with the `ml` extra), `msradam/Prithvi-EO-2.0-NYC-Pluvial`
  (new surface water in satellite scenes after 15 heavy-rain events since
  2017) and `msradam/TerraMind-NYC-Adapters` (land cover by year), the last
  two as saved batch output the app reads with no extra. Weights are pinned
  by commit and loaded from safetensors.
- One function, `app.experimental.hedge`, writes every sentence from them:
  "Experimental" or "Experimental forecast", the value with unit, window and
  place, the model's limits and tested accuracy, and the official source to
  rely on. The accuracy comes from result files the test scripts write
  (`data/experimental/`).
- Questions about the future get an answer: a surge question quotes the
  Weather Service's forecast and then the model's; land-cover questions get
  the model's sentence under "From an experimental model, not a
  measurement:"; "will it flood here next week" is no longer refused, it
  gets "Riprap cannot predict whether a particular place floods on a given
  day" followed by what the Weather Service expects and the maps show. For a
  question about past flooding a model never sets the yes or no, and a
  question about what a model showed gets no yes or no from the record
  above it.
- What the tests found, stated in the sentences and in `docs/MODELS.md`: the
  surge model beats holding the last day's mean (11.5 cm against 13.3 cm on
  635 windows) and foresaw 1 of 23 minor-flood windows; the satellite water
  layer is no better than chance against 153 surveyed Ida marks, and is not
  used to say a place is prone to standing water; the land-cover adapter's
  radar and elevation inputs carry nothing, its model card names its
  classes wrongly, its paved share for a district reads about 8 points above
  ESA WorldCover's, and it claims no trend: differences between years beyond
  its noise turned up in 3 of 59 districts, which is what the noise alone
  produces.

Added:

- A district or neighbourhood reads the FloodNet sensors inside it, and the
  harbour gauge and its Weather Service forecast, read at its centre.
- MCP `get_briefing` reports `answered`, `answer_mode` and `answer_lead`.
- A school or public housing development whose point is outside the Sandy
  outline but within 50 m of it is named as near the edge. The registers held
  only assets inside, so one 3 m outside was left out without a word.
- The FloodNet sentence says how many of the events came from sensors
  flagged for maintenance, and whether an event was under way when read.
- A fourth golden question set written by an agent that saw nothing else,
  with questions about the future and queries that should be declined. The
  golden runner scores a neutral lead strictly and a district's sensors
  against its own key.

Fixed, each reproduced first:

- The NPCC4 sea-level sentence quoted figures that are in no table of the
  report: 15 in at the median and 29 in at the 90th percentile for the 2050s,
  on a 2000 to 2004 baseline. The published table (Braneon et al. 2024,
  Table 1) gives 14 to 19 in as the middle range and 23 in at the 90th
  percentile, relative to 1995 to 2014, and no median. The sentence now
  quotes the table. A blind judge found it by checking the paper.

- "Has it flooded at 100 Main St. since Sandy?" was cut at the abbreviation
  and answered "No." from sources that do not reach 2012.
- "Did any water reach it during Ida" said "Yes." from marks up to 800 m
  away; "any street flooding" said "Yes." on 311 complaints alone; a school
  question about the FEMA flood zone said "No." from Sandy and stormwater
  counts; a sensor FloodNet flags for maintenance could stand behind a
  "Yes."; a district with 0.8% inside the Sandy extent was "Yes." and is
  "In part.".
- "Did it flood on Monday", "last summer" or "recently" got "Yes." from a
  three-year total. A day, a month or a season gets the record with no yes
  or no. "Before Sandy, had it flooded?" said "Yes." from the Sandy extent.
- "Is there flood risk here?" was read as "did it flood" and could get "No."
  from sensors with no events.
- "New Brighton" resolved to Brighton Beach, "City Island" to Hart Island
  and "Murray Hill in Queens" to Manhattan. A house number such as 2100 or
  2050 was read as a future year.
- FloodNet events stopped at 200 rows: City Island's 436 read as 200.
- "How many complaints since Ida" got the window's total.
- "Flushing Avenue, Brooklyn", "Jamaica Hospital" and "woodlawn chicago"
  were briefed as New York neighbourhoods; "450 St. Nicholas Avenue" lost
  its number; "my place at Ocean Parkway" was refused as an intersection;
  "Pike Place Market in Seattle ... right now" was sent to New York.
- Advice and heat questions phrased another way ("should I take it", "the
  hottest in summer") were briefed, not declined.
- An offline source with no fallback message was recorded as fine.
- MCP read an out-of-coverage run against the New York registry.
- The disclosure checks joined "flood zone X. 3 sensors" into one sentence,
  missed the citation on a sentence with a percentage, and did not count a
  dated forecast as stating its horizon.
- A review of the restored models found more, fixed before release: "green",
  "surge" and "ozone" matched place names and the Sandy surge zone ("100 Green
  Street", "Ozone Park"); "standing water right now" was not read as live; a
  flood question after a preamble about renting or summer heat was refused;
  the satellite layer always reported 100% of an area observed; the
  land-cover year map broke ties toward paved; the surge model spliced over
  gaps in the gauge record; a language model could rest a "Yes." on an
  experimental source.
- The same-incident rule for 311 compared every pair of rows.
- In the page: a server error set the header to "Outside the covered
  cities"; a rules answer that found nothing said "Answered by rules"; a
  gallery snapshot's live region kept saying "Resolving the place".

Removed: the stream's stone envelope and plan tokens (nothing read them),
the synthetic tier, test data and a probe with no reader (about 5.4 MB),
unused development dependencies.

### The live experience (2026-09-30)

- An intersection, a ZIP code alone and an invalid district are refused
  with the reason, before any model call. A numbered address resolves to
  its own street or not at all. A query naming another city skips the New
  York lookup, and coverage is the city's polygon, so Hoboken no longer
  gets New York's Sandy layer.
- FEMA zone X reads as an absence in the lead rules; the source a question
  is about leads its answer; a question stays a question when the planner
  cannot reach the model; a temperature-only observation is not an answer.
- Every source has a 45 second budget (`RIPRAP_SOURCE_BUDGET_S`); past it
  the briefing goes on and names the source.
- The page says what it is waiting for, holds a long query in the header,
  announces "Briefing ready" and offers a next step on a refusal.

### What Riprap does that other tools do not (2026-10-01)

A comparison with the public alternatives on eight fixed tasks, and an audit
of every part against a plain baseline, led to these changes.

Fixed:

- 311 flood requests were undercounted. The city renamed the flood
  descriptors in 2026 (`Sewer Maintenance`: `Backup`, `Catch Basin Clogged`,
  `Manhole Overflow`, `Flooding on Street`, `Flooding on Highway`) and Riprap
  counted the old names. Both are counted now, one per incident, and a live
  test fails when a descriptor that looks like flooding is not on the list.
- FloodNet's event table holds events dated in the future; the event window
  now ends at the time of the query. A flagged sensor's highest reading is
  stated with its flag, in millimetres and inches.
- Place parsing: a borough after the street with no comma, borough
  abbreviations, a Queens house number, "311 street flooding" read as an
  address, one address read as a comparison of two, a neighbourhood typed in
  lower case, and the city's three-digit district codes.
- Found by an independent review of this branch: an asset question could
  take its yes from the wrong count; a null resident count printed as zero;
  311 requests logged twice at an intersection counted twice; a hospital
  just outside the mapped Sandy edge counted as outside with no remark.
- A district briefing leads with the 311 count, not the Sandy share, and a
  district question no longer waits for the construction permits source.
- Found by a walkthrough of the running app: "how many last year" led with
  the three-year total (a one-year count now comes from that year); "has it
  flooded" said Yes on 311 complaints alone (complaints are quoted with no
  yes or no unless a sensor or a surveyed mark reports flooding); a named
  future day was declined as a past date.
- A FloodNet sensor 599 m away was left out of a 600 m search by the
  service's own radius function; the app now applies its own distance.

Added:

- A question is answered with no language model, by rules over its own
  words (`riprap/core/burr/rule_answer.py`), part by part when it has two
  parts. With a model configured the rules still answer first and the model
  is asked only for what they do not recognise (`RIPRAP_RULES_FIRST=0`
  reverses it). On 130 unseen questions judged blind the rule answers were
  preferred on 54 and the model's on 21 (`docs/GROUNDING.md`).
- District and neighbourhood briefings name the exposed subway entrances,
  schools, public housing developments and hospitals, and quote NYC
  Planning's counts of buildings, units and residents in the floodplain.
- The National Weather Service's water-level forecast for the nearest tide
  gauge, with its issue time and the flood stage it reaches.
- MCP evidence items carry `value`, `source_url` and `vintage`.
- The Sandy sentence says how near the mapped edge a point is (within 50 m);
  the preliminary FIRM sentence names its datum.
- A "right now" answer dates each reading and points to the FloodNet
  dashboard, the Weather Service and Notify NYC.

Removed, each because it did not beat a plain baseline on Riprap's own data
or served no target user (the code is in history at `8b87165`):

- The two zero-shot Granite TTM forecasts (311 volume, sensor recurrence).
  The Battery surge forecast and the Prithvi-EO satellite layer were removed
  in this pass too and came back, labelled experimental, in the review above.
- The policy corpus with its embedding and entity models. A default install
  has no torch.
- The composite exposure score. `riprap-register` writes plain flags.
- The server-side PDF export (the print view remains), the heat and air
  scaffolds, the San Francisco and Boston deployments, the unfiltered 311
  feeds, the unused model adapter and `experiments/`.

Said less: the terrain sentence gives elevation and the low-spot percentile
only; a plain briefing quotes a live reading only when it is notable; a
district briefing does not lead with one large figure.

### Polish for stakeholder demos (2026-09-30)

- A golden set (`tests/golden/`) scores the app against keys computed by a
  separate implementation that reads the public datasets directly; half of
  it stayed unseen until the final scoring.
- Fixes it found: registers counted assets only within 750 m east to west of
  an 800 m radius (a degree box drawn without the cosine of the latitude); a
  query naming no place blamed every source instead of saying so; a
  Washington address became a Brooklyn briefing; a "what is the flood zone"
  question was answered "Yes."; a "right now" question was answered "No."
  from the absence of an alert.
- FEMA's 2015 preliminary flood map (PFIRM) is cited beside the 2007 FIRM,
  with the issue date from FEMA's own availability layer; NYC Building Code
  Appendix G adopts it for flood-resistant construction.
- MCP evidence and briefing results carry a `record` block (query, time,
  version, commit, SHA-256) and a `failed` list; `plan_query` says which
  planner ran (`planner`: `llm` or `regex`); `get_briefing`'s docstring says
  it works without an LLM.
- A community district's 311 count is by the record's own `community_board`
  field, the official definition, and the sentence says so; the NTA-union
  outline stays on the map. The FIRM panel cited is from the zone's own
  study when panels overlap along the water. The PFIRM caveat is its own
  sentence, so the lead rules do not read it as a map reporting no zone. A
  district's rainfall share quotes the classes the cited sentence states.
- Removed: the guarded answer mode and its entailment model (see
  `docs/GROUNDING.md` for the tag that keeps the experiment citable), the
  `/q/sample` redirect, `/api/agent/plan` (use the MCP `plan_query` tool),
  `/api/layers/nta`, the `RIPRAP_NYCHA_REGISTERS` and
  `RIPRAP_TTM_BATTERY_SURGE_DEVICE` variables, `riprap.core.llm.chat_text`,
  and the `--offline` and `--skip-e2e` flags of `scripts/test_all.sh`.
  `nws_alerts` reports `retrieved_at` (ISO, uncached) instead of `checked_at`.
- Reader-facing texts: live sources say when they were fetched, figures carry
  units, `not_implemented` renders as a response, the public copy says it has
  no backend, experimental deployments say so in the header, the refusal
  names FloodHelpNY.
- Smaller: the four register modules are one table-driven module; the
  browser BYOD flow, dead scripts, unused packages (js-yaml, papaparse,
  idb-keyval) and dead frontend tables are gone; one deployment
  resolver and one registry cache; one StaticFiles mount serves the
  prerendered gallery locally; the Playwright suite runs on one Playwright.

## [0.7.0] - 2026-09-28 (a presentable public repository)

- The README is rewritten to about 170 lines: what Riprap does with a real
  cited answer from the gallery, who it is for and not for, a status table,
  a Quickstart whose commands were run from a fresh clone, the Five Stones,
  data sources, privacy and how to get involved. The long sections it
  dropped moved, unchanged, to `docs/BACKGROUND.md`, `docs/MODELS.md`,
  `docs/DATA-SOURCES.md` and `docs/REPOSITORY.md`.
- `docs/PRIVACY.md` says what Riprap stores and sends, how 311 free text is
  redacted, and what it should not be used for.
- The gallery can be published on GitHub Pages
  (`.github/workflows/pages.yml`). The public build has no backend: it makes
  no API calls, puts the gallery one click from the landing page, and points
  to the Quickstart for your own questions.
- A tidier root: community files in `.github/`, `PRODUCT.md` and `DESIGN.md`
  in `docs/`, the Dockerfile and Modal host in `deploy/`, the policy corpus
  in `deployments/nyc/corpus/`, the load tests in `tests/load/`, historical
  docs in `docs/history/`, and `riprap.py` as the `riprap-register` command.
  Unused files (an old Space entrypoint, May screenshots) are deleted.
- A new hero image from the current Hollis "since Ida" answer.
- `scripts/check_links.py --local` checks every relative link in the docs.

## [Unreleased] (refactors 2 to 6 and the design pass)

Plain-language summary of the work on branches `refactor/mvp-2` to
`refactor/mvp-6` and `design/impeccable-pass`, in the order it landed.

### Questions and answers (refactors 2 to 4)
- Riprap answers a question about a place, not only an address. A
  planner (an LLM when one is configured, else fixed rules) decides
  whether there is a question, whether it is in scope, and which sources
  to run. Some sources always run for a given kind of question.
- The briefing opens with an Answer section. The default answer mode is
  extractive: the model picks a lead ("Yes.", "No.", "In part.", a count)
  and which source sentences answer the question, and those sentences
  are shown word for word. Guarded mode lets the model write the answer,
  then checks it against its sources.
- Deterministic answer checks catch six ways an answer can misstate its
  evidence: an absence stated against a positive source, "all" over a
  partial count, a conclusion joining two sources, an omitted count, an
  elevation without its datum, and a "no" or a zero resting on a source
  that could not answer. These six answer checks are word patterns and
  rules. Guarded answers also get an entailment check: a classifier that
  scores whether the cited text supports a claim, and it misses
  paraphrased inferences. See `docs/GROUNDING.md`.
- Named-day forecasts ("will it flood next Tuesday?") and advice
  (insurance, buying) are refused with fixed text.
- A 30-question set and a 20-question held-out set with an A/B harness
  (`scripts/question_eval.py`). The held-out set has since informed
  several rules and is no longer a clean test.
- Non-NYC 311 feeds: Chicago and Seattle are filtered to flood-related
  requests with reviewed category tables. Boston, San Francisco and
  Albany can use an experimental text classifier when one is installed
  (`RIPRAP_311_FILTER_PATH`); it is documented as unreliable on live
  feeds, and without it the count is unfiltered and says so.

### Design pass
- Citations are reachable from every claim, and the page says which
  place a briefing covers ("Briefing for:").
- The answer comes first, the map loads only when needed, and the print
  packet works.
- Landmarks, heading order, the skip link and small targets were fixed.
  Real-usage journeys run in Playwright with an axe check on every
  state.

### Places, counts and honesty about missing data (refactor 5)
- Without an LLM, places are resolved from the words that name them: a
  community district code checked against the 59 real districts, a
  street address, or a short place name. Before, any question naming a
  borough resolved to that borough's first neighbourhood. Accuracy on 65
  test cases went from 15 to 64. An uncertain match is flagged.
- 311 counts are split by complaint kind. A question about street
  flooding gets the street flooding count.
- A source that failed or could not be read is reported as unavailable,
  never as 0; a true zero says the source answered and nothing matched.
- Address briefings open with a short cited summary ("In brief"). The
  three DEP scenario sentences are one, and technical terms (percentile,
  HAND, TWI) are explained.
- District pages draw the district outline. Map points are also listed
  for keyboard users. Evidence cards that repeat the briefing are behind
  a "Show all evidence cards" button.
- The print footer names the project's repository; addresses the
  project does not control were removed. Source links were checked
  (`scripts/check_links.py`) and the dead USGS link fixed.

### Personal data and final polish (refactor 6)
- Email addresses and phone numbers are removed from 311 records when
  they are fetched, before they reach a briefing, a cache, a log or a
  file. The training pool for the 311 classifier is no longer in the
  repository and is git-ignored.
- District and neighbourhood cards show their figure (for example
  "38.5% inside the 2012 Sandy extent"), and sources not chosen for a
  question say "Not run".
- Question pages say each thing once and hide empty sections.
- Yes or no questions about past flooding get their lead from a rule
  over the observed-event sources, not from the model.
- A stream-gauge search with no gauge nearby is a true "none nearby";
  when no source produces evidence, the briefing names the sources that
  failed.

## [Unreleased] (MVP refactor)

- One orchestrator: the Burr app in `riprap/core/burr/app.py` now runs
  every intent (`single_address`, `neighborhood`, `development_check`,
  `live_now`, `compare`, `not_implemented`) with one parallel fan-out
  over the intent's pebbles. `app/fsm.py`, `app/intents/`, `app/stones/`
  and `app/reconcile.py` are removed.
- No-LLM mode is the default: every pebble value is rendered through its
  manifest `narration.template` (`riprap/core/burr/evidence.py`) and
  printed as the briefing.
- LLM mode talks to any OpenAI-compatible endpoint through the `openai`
  client (`RIPRAP_LLM_BASE_URL`, `RIPRAP_LLM_MODEL`, optional fallback).
  The model returns JSON claims; code checks citations and numbers,
  retries once and drops what fails (`docs/GROUNDING.md`). LiteLLM,
  Mellea and the reroll banners are removed.
- Neighbourhood intents accept a community district code such as `QN12`
  (the union of its NTAs). New `/api/district/{code}` and
  `/api/nyc311/flood_requests` routes; `/api/stream`, `/api/compare` and
  the debug endpoints are removed.
- MCP server rebuilt on the official `mcp` SDK with `list_sources`,
  `get_evidence`, `get_district_summary`, `get_citation`,
  `nyc311_flood_requests` and `get_briefing`. All but `get_briefing` work
  without an LLM.
- Static gallery: `scripts/build_gallery.py` precomputes ten NYC
  briefings that SvelteKit prerenders at `/gallery` with no backend, for
  GitHub Pages (`BASE_PATH`).
- Provenance comes only from manifests. Every provenance block has
  `date_modified` and `retrieved_at`, and every manifest has
  `maturity: production` or `maturity: experimental`.
- Experimental labels on `prithvi_water` (now "satellite-detected surface
  water after Ida", with no inside or outside verdict),
  `ttm_311_forecast`, `floodnet_forecast`, `ttm_battery_surge` and
  `policy_corpus`. The zero-shot `ttm_forecast` pebble is deleted and
  `prithvi_live` is removed from the app.
- The remote ML server (`app/inference.py`, `services/riprap-models`,
  `inference/`, `load/triton-local`) and all per-request Prithvi and
  TerraMind code are removed. TTM, Granite Embedding (query only) and
  Flair NER run in process on CPU; GLiNER is gone. Earth observation
  runs as a batch job (`scripts/run_eo_batch.py`).
- Light install: `uv sync` is the core with no torch. Extras: `ml`, `eo`,
  `pdf`, `energy`. The Makefile and `web/static` are removed.
- One HTTP client (`riprap/core/http.py`, httpx with hishel caching and
  stamina retries) for every adapter, including Nominatim with a 1
  request per second gate; geopy is removed. USGS gauges use the OGC API.
  FloodNet TLS verification is on. Dataset IDs fixed for HVI, NYCHA and
  NYS DOH hospitals.
- Energy ledger labels each LLM call measured (zeus-apple-silicon on a
  local endpoint), estimated (`RIPRAP_ENERGY_WATTS`) or unknown; hosted
  endpoints are always unknown. The NVML proxy headers and the sudo
  `powermetrics` path are removed, and `docs/BENCHMARKS.md` is marked
  historical.
- The `compliance` substring checks are described as disclosure checks,
  never a quality score.
- Docker: `Dockerfile.app` installs core plus `ml`; `docker-compose.yml`
  has the app and an optional `local-llm` Ollama profile. Modal is
  optional. Burr tracking is opt-in (`RIPRAP_BURR_TRACKING=1`).

## [Unreleased] — 2026-07-10 (Albany deployment)

### Fixed
- **NYC compliance 12/13 → 13/13 in the no-LLM tier.** Multi-sentence
  pebble narratives (`ida_hwm`, `microtopo`, `nyc311`) carried one
  trailing citation, but `every_numeric_claim_cited` (SPJ 7.1) audits
  per sentence, so their leading numeric sentences failed the audit.
  `_cite_numeric_sentences` in the templated reconciler now suffixes
  every uncited numeric-claim sentence with its `[doc_id]`, sharing the
  predicate's own regexes so repair and audit can't drift. Regression
  tests in `tests/test_templated_reconciler.py`.

### Added
- **Sixth city: Albany, NY** (`deployments/albany/`). First city with no
  open-data 311 export — its 311 intake runs on SeeClickFix, so
  `albany_311` calls the SeeClickFix public API via a new
  `app/context/seeclickfix.py` module (`python_call` pebble) that
  fetches nearest-first, haversine-filters to 300 m, and emits the same
  records shape as `socrata_records`. Water level resolves to NOAA
  8518995 (Albany, Hudson River — already in the station table). 13/13
  compliance at 24 Eagle St (City Hall); added to
  `scripts/probe_cities.py` and the deployment-routing tests. Any other
  SeeClickFix city reuses the module with just a manifest.
- **`albany_flood_311`** — flood-filtered variant of the Albany 311
  pebble: server-side `request_types` filter on Albany's flood-adjacent
  SeeClickFix categories (Water Issues/flooding 3418, Sinkholes 12499,
  Sewers/Drainage 12500) at 800 m radius.
- **Federal pebble: `fema_nfhl`** (`app/context/fema_nfhl.py`). Effective
  FEMA flood zone at any mapped US point from the NFHL ArcGIS layer 28,
  plus the FIRM panel effective year from layer 3 — satisfying the
  `firm_citation_has_vintage` predicate (FEMA 1.5). Fills the Hazard
  Reader section for every non-NYC city.
- **Federal pebble: `usgs_gauges`** (`app/context/usgs_gauges.py`). Live
  stage/discharge at the nearest active USGS stream gauge within a
  ~14 km box (NWIS instantaneous values, 15-minute cadence, one retry
  on NWIS's intermittent 503s). For Albany that's Patroon Creek at
  Albany (01359135), 1.5 km from City Hall; cities with no gauge in the
  box skip the pebble cleanly.
- **MCP server** (`riprap/mcp/server.py`, `python -m riprap.mcp.server`).
  Exposes Riprap as three agent-callable tools instead of a 1:1 wrap of
  the HTTP API: `get_briefing(address)`, `list_sources(deployment)`,
  `get_citation(deployment, doc_id)`. `list_sources` shares its
  stones+pebbles description with the HTTP `/api/pebbles` route via the
  new `riprap/core/pebbles/describe.py` helper. Defaults to stdio
  transport (Claude Desktop / local agent config); `--http` serves
  streamable-http for a remote agent.

### Changed
- **README scope-boundary section names the FEMA NFIP appeal process
  explicitly** as the contrast case: the 90-day appeal window and the
  scientific-or-technical-evidence-only standard (44 CFR Part 67) that
  a Riprap briefing is not part of.

## [Unreleased] — 2026-05-17 (Sunday, rebrand + BYOD + PDF route)

### Added — rebrand surface (Claude Design handoff)
- **New positioning copy across the marketing surface.** Hero H1 cycles
  through "A climate-exposure briefing for {New York City | Chicago |
  Seattle | San Francisco | Boston}." in federal-blue italic; deck
  names the four primary source families (FEMA / NOAA / USGS / city
  open data) so the trust-strip claim is foreshadowed inline. Browser
  title + meta description rewritten for any-US-place framing.
- **Dynamic header chip.** `/api/deployment` returns active deployment
  `{name, city, hazard}` from `stones.yaml`'s optional new
  `deployment:` block (with sensible deployment-dir-name fallback —
  `nyc → NYC`, `sf → SF`, `heat → NYC + "Heat-exposure briefing"`,
  etc.). `AppHeader` reads it through a Svelte 5 store; chip pill
  swaps as you change `RIPRAP_DEPLOYMENT`.
- **Six new trust components** (per civic-tech compliance registers
  USWDS · GOV.UK Design System · Section 508 · WCAG 2.2 AA · Plain
  Writing Act 2010):
  - `PhaseBanner.svelte` — open-beta banner, GOV.UK pattern
  - `UseBand.svelte` — responsible-use disclaimer + non-affiliation
  - `SourceStrip.svelte` — trust-signal counts (23 · 9 · 5 · 3)
  - `StandardsStrip.svelte` — compliance badges
  - `CityPicker.svelte` — five-city pill row, jumps to canonical
    anchor addresses that probe_cities.py exercises in CI
  - `SkipLink.svelte` — USWDS-canonical "Skip to main content"
- **BYOD client-side dialog** (`ByodDialog.svelte` + `client/byod.ts`
  + `stores/byodRegistry.svelte.ts`). Three-section workflow: file
  drop → adapter auto-detection → pebble mapping. Files stay on the
  user's machine; manifest persisted to IndexedDB via idb-keyval.
  Parsers: PapaParse for CSV, native JSON for `.json` / `.geojson`,
  js-yaml for `.yaml` / `.yml`.
- **Server-side PDF route** at `/api/print` via WeasyPrint
  (`app/print_pdf.py`). POST briefing JSON, get back a tagged PDF
  with cover · briefing · citations · verification stamp. SHA-256
  document hash on the stamp page lets two reviewers verify
  bit-for-bit equivalence. The header "export PDF" button now POSTs
  the cached `PrintSnapshot` from localStorage and opens the PDF in
  a new tab via a blob URL (replacing the legacy
  `/print/<queryId>` print-stylesheet path).

### Changed
- **Deleted `LandPreview.svelte`** — its "Briefing excerpt" pane
  carried synthetic numbers ("1% AE flood zone", "4.7 ft Sandy HWM",
  "14 nuisance floods since 2023") dressed in real-looking citation
  chrome on a page whose standards strip badges `✓ Plain Writing Act`.
  Removed. `LandStones` below is the structural explainer for "what
  you'll get back" and contains no fabricated data.
- **`LandStones` taglines** rewritten hazard- and city-agnostic
  (was NYC-specific: "what NYC's ground remembers", "MTA · NYCHA
  · DOE · DOH · PLUTO"; now: "what the ground remembers", "Transit
  entrances · public housing · schools · hospitals · whatever asset
  registers a jurisdiction publishes").
- **Provenance correctness fixes.** `floodnet.yaml` license
  `CC-BY-NC-4.0` → `CC-BY-NC-SA 4.0` (ShareAlike was missing; FloodNet
  data terms require it). `npcc4_slr.yaml` license
  `NYC Open Data Terms of Use` → `CC-BY-NC 4.0 (Annals of the New
  York Academy of Sciences)` with parent DOI `10.1111/nyas.15116` in
  the citation string.
- **AppFooter disclaimer reworded** from "does not predict damage"
  to "is a reference dossier, not a stamped engineering memo, risk
  score, or disclosure." Lists explicit out-of-scope uses (real-estate
  transactions, mortgage / insurance, personal property decisions).
- README adds a **"What this is. What this isn't."** block naming the
  user types Riprap is for (resilience consultants, ASTM E1527-21 BER
  addenda preparers, journalists, agency analysts) and explicitly NOT
  for (drainage / hydraulic design, residents — defer to FloodHelpNY,
  mortgage / insurance underwriting, real-estate transactions).

## [Unreleased] — 2026-05-16 (Saturday, post-hackathon OSS polish)

### Added
- **Five-city framework generalisation.** NYC is now the reference
  deployment; four new deployments ship alongside it on the same code:
  - `deployments/chicago/` — Socrata 311 (`v6vf-nfxy`), NOAA Calumet Harbor 9087044
  - `deployments/seattle/` — federal pebbles only (Seattle CSR lacks point geometry)
  - `deployments/sf/` — DataSF 311 (`vw6y-z8j6`, `point` field), NOAA SF Bay
  - `deployments/boston/` — Analyze Boston 311 via CKAN, NOAA Boston Harbor 8443970
- **`ckan_records` adapter** (`riprap/core/pebbles/adapters/ckan_records.py`)
  — bbox SQL push-down + haversine refine, since CKAN datasets usually
  ship lat/lon as numeric columns rather than a geometry-typed field.
  Unlocks Boston, Philadelphia, Toronto, EU portals.
- **BYOD load paths.** `load_registry` now merges manifests from
  `${CWD}/.riprap/` and from `RIPRAP_EXTRA_MANIFESTS` (colon-separated
  paths). Relative paths in BYOD manifests resolve against the
  manifest's own directory, so a user can ship a manifest + data file
  side-by-side anywhere on disk. Worked example in `examples/byod/`
  using real FDNY firehouses data (NYC Open Data `hc8x-tcnd`, 219
  records). Full walkthrough in `docs/byod.md`.
- **`scripts/probe_cities.py`** — 5-deployment sweep, runs in ~110 s
  against real upstream APIs, asserts 13/13 compliance per city.
  Reproducible regression check.
- **`docs/multi-city.md`, `docs/byod.md`, `docs/VERIFICATION.md`,
  `docs/PORT-YOUR-CITY.md`** — open-source onboarding surface.
- **`tests/test_byod_load.py`** — 7 tests covering both load paths,
  manifest-dir path resolution, cross-deployment portability, and
  override warnings.

### Changed
- `web/main.py:_run_compare` — fixed B023 loop-variable closure capture
  in the per-target trace wrapper (`_TaggedQ` now binds via `__init__`
  params, not closure). Latent footgun made deterministic.
- `tests/test_stone_envelope.py::test_step_to_stone_mapping_covers_known_steps`
  — was grep-based on `web/main.py` source; the pebble refactor moved
  `_STEP_TO_STONE` to a runtime dict comp. Test now asserts against the
  imported runtime dict.
- README banner re-pitched for OSS: framework, not just NYC.
- CONTRIBUTING re-framed from "hackathon submission" to "civic-tech
  framework that began as a hackathon project."
- `.github/ISSUE_TEMPLATE/port_to_new_city.yml` — refreshed to cite
  the 5 existing deployments + Socrata/CKAN adapters as starting points.

## [Unreleased] — 2026-05-09 (Saturday)

### Added
- **Per-query inference energy ledger** with real NVML readings off
  the L4 GPU. The status row on the Findings region now reports
  total Wh + total tokens for every briefing, with a leading icon
  (`✓` / `◐` / `~`) disclosing whether the number was measured or
  estimated. Full breakdown documented in
  [`docs/EMISSIONS.md`](docs/EMISSIONS.md).
- `inference-vllm/proxy.py`: 100 ms-cadence NVML sampler, response
  headers `X-GPU-Power-W` / `X-GPU-Energy-J` on every forwarded
  POST, and a `GET /v1/power` endpoint for bracket-sampling clients.
- `app/emissions.py` — new module with a thread-local `Tracker` that
  records every LLM and ML inference call (model, hardware, tokens,
  duration, joules) with a `measured: bool` flag per row.
- `scripts/probe_stones_fire.py` — programmatic CI that runs an
  address query against the lablab UI and asserts all five Stones
  fire, no `torchvision::nms` / `deps unavailable` dep regression,
  and the `emissions` block carries `nvidia_l4` hardware.
- `scripts/probe_benchmarks.py` — collects the canonical
  four-address verification set into `outputs/benchmarks.json`
  for the `docs/BENCHMARKS.md` page.
- `docs/EMISSIONS.md`, `docs/DEPLOY.md`, `docs/BENCHMARKS.md`,
  `CHANGELOG.md`, `CONTRIBUTING.md`.

### Changed
- The `RunHealthStrip` chip dropped the cloud-energy comparison
  (the sign convention was misleading and the comparison is now
  redundant given real measurements). New format:
  `<icon> X.X Wh / Y.YK tok inference`.
- `app/llm.py:_default_hardware_label` defaults to `"NVIDIA L4"`
  when remote vLLM is configured (was `"AMD MI300X"`, a stale
  string from the droplet days).
- `app/llm.py:chat()` now brackets every completion with two GETs
  to the inference Space's `/v1/power` endpoint; the average powers
  the LLM-call energy reading instead of the data-sheet estimate.
- `app/inference.py:_post()` reads NVML headers off the proxy
  response and forwards real joules into `emissions.record_ml`.

### Fixed
- `app/flood_layers/prithvi_live.py`: when the configured remote
  inference call fails (`RemoteUnreachable`), the specialist no
  longer falls through to the local terratorch path. The local
  path crashes with `RuntimeError: operator torchvision::nms does
  not exist` on the cpu-basic UI Space; surfacing a clean
  `remote prithvi-pluvial unreachable` skip is correct.
- `app/context/terramind_nyc.py:_try_remote()`: returns a
  `{"ok": False, "skipped": "remote terramind/<adapter>: ..."}`
  sentinel on remote failure, instead of `None` which was
  silently masked as `deps unavailable on this deployment`.
- `web/main.py`: explicit `/favicon.svg`, `/favicon.png`,
  `/favicon.ico`, `/robots.txt` routes — they were 404-ing under
  the SvelteKit SPA fallback because only `/_app` was mounted off
  the build directory.

### Documentation
- Full README rewrite reflecting the post-droplet L4 topology, the
  new emissions feature, and updated repo structure. Hackathon
  framing preserved.
- New `docs/DEPLOY.md` with the production topology, env-var
  reference, and per-Space deploy commands.
- New `docs/EMISSIONS.md` documenting what's measured vs. estimated,
  the NVML pipeline, and how to verify.

### Infrastructure note
- The DigitalOcean MI300X droplet was decommissioned 2026-05-06.
  All production inference now serves from `msradam/riprap-vllm`
  (NVIDIA L4). The MI300X runbook is kept outside this repository;
  setting
  `RIPRAP_HARDWARE_LABEL=AMD MI300X` swaps the emissions profile
  back when redeploying to that hardware.

---

## [v0.5.0] — 2026-05-07

Hackathon submission tag.

### Added
- Five-Stone Burr FSM with Granite-native document-role messages
- Mellea four-check rejection sampling for the Capstone
- SvelteKit UI with SSE streaming, briefing prose, evidence-card
  grid, MapLibre overlay, citation drawer
- Three NYC-specialised foundation models published Apache-2.0:
  `msradam/TerraMind-NYC-Adapters` (LULC + Buildings + TiM LoRAs),
  `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
  `msradam/Granite-TTM-r2-Battery-Surge`
- 30+ FSM specialists across hazard memory, asset registers, live
  observation, forecasting, and citation-grounded synthesis
