# Sanity check by separate AI agents, 5 October 2026

A summary of a check of whether what Riprap tells people is right and
meaningful, and of what was done about each problem it found. The full report
was written for the maintainer and is not in the repository; this page keeps
its method, its figures and its table of problems so that the numbers quoted
in the README and on the about page can be followed.

## Who ran it and how

The check was run by AI coding agents under the maintainer's direction: a
lead reviewer and six reviewers, one each for flood sources, heat sources,
place, flood briefings, heat briefings and models. They were not the agents
that wrote the code, and they were told to form their own view first: to work
from the code, the public sources and the app's output, and to read no
project document or earlier report until afterwards. The check was read-only.
Nothing in the repository was changed by it. No person outside the project
took part. "Independent", where other documents use the word for this
check, means only that: separate agents, working read-only.

The check confirms that sentences match their sources. It did not test the
joined evidence against observed flooding, and nothing else in the project
does yet.

It ran against branch `main` at commit `abb1c4e`, with the app started
locally and no language model configured. Every finding had to rest on a
command and its output, a file and line, or a URL and the passage on it. The
lead reviewer reproduced the most serious findings of each reviewer before
writing them down.

What each part did:

- **Sources.** For every source, a reviewer read the manifest and the code,
  opened the dataset at its publisher to confirm its title, vintage, fields
  and units, and re-derived at least one number with separate code.
- **Place.** 85 queries: 15 tax lots drawn at random from the city's PLUTO
  file (3 per borough, fixed seed), 49 edge cases chosen by hand, and
  follow-ups. Each resolved point was compared with the city's GeoSearch
  service and the Census geocoder; all 59 community districts were compared
  in shape with the official boundaries.
- **Briefings.** For flood, 21 queries (9 addresses, 5 districts, 7
  questions). For heat, 33 answers. Every check queried the public source
  directly and called no Riprap function.
- **Models.** The surge backtest was rebuilt from scratch on 638 four-day
  windows with scoring that imported nothing from Riprap. The land cover
  rasters were compared with the 2021 six-inch land cover map on 60 random
  1 km squares.

## The figures

The count is of briefing sentences that end in a citation.

| | Sentences read | Re-derived and confirmed | Wrong | On a raster edge | Not re-derived |
|---|---|---|---|---|---|
| Flood | 378 | 195 | 10 | 2 | 171 |
| Heat | 302 | 280 | 0 | 0 | 22 |
| Both | 680 | 475 | 10 | 2 | 193 |

So 487 sentences were re-derived (475 + 10 + 2), and 193 were read but not
re-derived, mostly lists of named assets, the terrain percentile and the sea
level sentence (the last was confirmed separately against the paper).

The report's verdict, in its own first sentence: "The numbers Riprap prints
are right, and it is fit to demo and share once a short list of fixes is
made." Every count, depth, distance, date, flood zone and temperature from
the core sources matched. The 10 wrong sentences came from three defects:
address elevation read from a neighbouring map cell (6 sentences), hospitals
counted by row in a file that repeats some (3), and a construction permits
count from the older of two permit files (1).

On the claim that every sentence comes word for word from a public record,
the report says: the claim that every sentence cites a public record and its
date holds for the factual sentences, but "the sentences are written by
Riprap's code from records, and 'word for word' in the app means only that
the answer repeats those sentences unchanged." Many sentences are Riprap's
own computation over a record, and the date is in the citation list, not in
the sentence.

## Every problem, and what was done

Severity is the report's: stops a demo, should be fixed or disclosed, or
minor. "Done in this pass" is the state on branch `review/fix-pass` on 5
October 2026: **fixed** (the code changed, with a test), **disclosed** (the
briefing or the documents now say it) or **open**.

| # | What was wrong | Severity | Done in this pass |
|---|---|---|---|
| 1 | Rockaway Park, Broad Channel, Belle Harbor and City Island by name returned "could not build this briefing" | Stops a demo | Fixed: an area is routed by a point inside it |
| 2 | "1 Bowling Green" and "87 Dover Green, Staten Island" were answered for Greenpoint; "15 Central Park West" for Central Park | Stops a demo | Fixed: a house number and a name is an address, whatever the street type |
| 3 | Address elevation read a neighbouring cell ("Elevation 0.0 m" at 400 Carroll Street) and stated no datum | Should be fixed before a demo | Fixed: reads the containing cell and states NAVD88 (1.07 m there). The gallery was rebuilt on 5 October 2026 and its saved page says so too |
| 4 | Permits counted from the older DOB file only, and "active" untested | Should be fixed or removed | Fixed and disclosed: out of plain briefings; a construction question gets a sentence that names the older file, tests expiry and says DOB NOW is not counted |
| 5 | The hospitals file held 67 rows for 61 hospitals, so counts doubled | Should be fixed | Fixed: each hospital counted once |
| 6 | A comparison of two named areas silently dropped the second | Should be fixed | Fixed: both are shown side by side under a note that nothing is scored or ranked; a place outside the city is named as not matched |
| 7 | An insurance question got no out-of-scope statement and no FEMA zone | Should be fixed | Fixed: it opens with the out-of-scope statement, then the FEMA zone, then a pointer to FloodHelpNY |
| 8 | A street with no house number plus Ida: "Here is what they show." followed by nothing | Should be fixed | Fixed: the reader is told to add a house number for the Ida marks |
| 9 | A failed FEMA preliminary query was dropped with an empty not-checked list | Should be fixed | Fixed: for every source, one that was tried and did not answer is listed under "Not checked" in the text and in a `failed` list in the JSON and MCP results, and a failed reply is no longer kept in the HTTP cache |
| 10 | A neighbourhood name was answered for a larger area or one half, called only "this area" | Should be fixed or disclosed | Disclosed: the place line, `geocode.note` and `place_note` say which tabulation area was used |
| 11 | The gallery index blurb for East Harlem contradicted the briefing under it | Should be fixed | Fixed: the gallery was rebuilt, and the blurb now gives the figures of the briefing under it (East Harlem (North), the tabulation area the name was answered for) |
| 12 | "wind alerts" were claimed and none was checked | Should be fixed | Fixed: "flood, coastal or tropical storm alerts" |
| 13 | "above-curb" is not in FloodNet's data; unreviewed and very shallow events were counted; "last 3 years" with younger sensors | Should be fixed or disclosed | Fixed: FloodNet's own definition, only events verified by a person, the period from the install date, and the sensor's status as the API lists it |
| 14 | Public housing counted as inside the Sandy extent only by its centre point | Should be fixed or disclosed | Fixed for Sandy (10% or more of the outline; 39 developments, was 20). Disclosed for stormwater scenarios, which still test the centre point |
| 15 | A stormwater scenario at an address is one cell with no edge distance | Should be disclosed | Fixed and disclosed: an edge distance near a boundary, the city's disclaimer, and "Outside a mapped extent does not mean safe" |
| 16 | The district sentence on land "less than 1 m above the nearest drainage channel" was not meaningful | Should be removed or reworded | Fixed: removed |
| 17 | The surge forecast does not beat damped persistence and adds little to the tide table | Should be fixed or disclosed | Fixed: out of default briefings; the six baselines and the decision are in `docs/MODELS.md` |
| 18 | The public model card claims a 41.4% improvement and an impossible data split | Should be fixed | Open: a corrected card is at `docs/model-cards/Granite-TTM-r2-Battery-Surge.md`; the hosted card is unchanged and the documents say it is out of date |
| 19 | Land cover: tree canopy reads low, unstated; "more paved since 2018" read as a rise | Should be fixed or disclosed | Fixed: the sentence states the canopy difference, and a change question is told first that the two figures are from different methods |
| 20 | A district is City Planning's tabulation approximation, which changes counts of points | Should be disclosed | Disclosed: the place note and `docs/METHODOLOGY.md` section 11 |
| 21 | In the Health Department's heat illness file the count and the rate disagree | Should be disclosed and reported upstream | Disclosed: the sentence says the count is the five-year total and the rate the department's average annual age-adjusted rate, and for a district that the two do not reconcile, that the file does not say why, and that both are printed as published. The portal's metadata was read and does not explain the gap. Not yet reported to the department |
| 22 | An address without a borough could resolve far outside the city | Should be fixed | Fixed: the city's address file is searched first, and a note says which borough was chosen |
| 23 | The neighbourhood 311 count used a simplified outline and undercounted | Should be fixed | Fixed: the exact outline |
| 24 | NYC Planning floodplain zeros that look like missing values were printed | Should be disclosed | Fixed: unsupported zeros are not printed |
| 25 | Schools file is from 2019 to 2020, charter schools labelled "DOE", wrong dataset link | Minor | Fixed and disclosed: "public schools", charter schools included, dataset `a3nt-yts4`. The file is still the 2019 to 2020 one |
| 26 | Cooling sentence: wading pools counted as pools, a stale list, pools just offshore missed | Minor | Partly fixed: the 23 wading pools are named and counted as wading pools, the list was copied again (1,133 spray shower rows) and the sentence gives the day it was copied. A pool just outside an area's outline is still missed |
| 27 | A district's "In brief" led with the 311 total and no breakdown | Minor | Fixed: the lead gives the breakdown by descriptor group and says it is a count of reports |
| 28 | Low-value sentences: a distant stream gauge, a hillside mark's elevation, a Sound tide station for an inland district, a district area that read as a flooded area | Minor | Fixed: no gauge beyond 5 km, the tide station's distance and water body, Ida heights above ground, the flooded area beside the area's total |
| 29 | The `models` block listed models no sentence used; a docstring said the language model is the only model run | Minor | Fixed |
| 30 | Surge and land cover details: 23 windows are fewer events; 2.96 million parameters, not 1.5 million; the 2021 map is The Nature Conservancy's | Minor | Fixed in the documents: 5 distinct events, 2,964,960 parameters, the map's owner named |
| 31 | Other place cases: "100 Broadway, Brooklyn" refused; "Murray Hill" and "100 Broadway" chose a borough silently; the nearest weather station is one of three | Minor | Partly fixed: the two names now carry a note. The weather station choice is unchanged, and its distance is printed |

Of the 31: 25 are fixed or fixed and disclosed, 3 are disclosed only (10, 20
and 21), 2 are partly fixed (26 and 31), and 1 is open (18).

## Checks the report could not run

- The web page in a browser. What the page shows for a failed source was read
  from its code.
- The MCP server; only the HTTP interface was used.
- The optional language model path. No model was running, so rules were not
  compared with Granite routing.
- Any sentence that needs an active weather alert, a heat advisory or a
  forecast near a threshold. None was active on the day.
- The six-inch land cover rasters at source, the surge model's training data,
  and a scored comparison with an official surge forecast.
- The lists of named assets beyond a small sample, and the permits finding
  outside one district.
- The Chicago, Seattle and Albany deployments.
