# Port your city: a worked walkthrough

> NYC is the reference deployment. Adding your jurisdiction is a directory
> of YAML, not a fork.

Chicago is the worked example. If your city's open-data portal runs
Socrata (data.cityofchicago.org, data.seattle.gov, opendata.dc.gov,
data.austintexas.gov, ...), the `socrata_records` adapter already works
and you write YAML. For another platform, use `rest_json`, or `python_call`
with a small module (Albany's SeeClickFix feed is one,
`app/context/seeclickfix.py`).

## What a deployment is

```
deployments/<city>/
├── stones.yaml              # a coverage: block (bounding box, city, state)
│                            # and five entries, one per Stone (Cornerstone,
│                            # Keystone, Touchstone, Lodestone, Capstone),
│                            # with city-flavoured taglines and descriptions
└── manifests/
    ├── water_level.yaml     # NOAA water level at the nearest listed station
    └── <city>_311.yaml      # your city's 311 or equivalent service-request feed
```

A city directory holds only its own manifests. The four federal pebbles
in `deployments/federal/manifests/` (`fema_nfhl`, `nws_alerts`,
`nws_obs`, `usgs_gauges`) are merged into every deployment
automatically, so do not copy them.

Two city manifests plus the four federal pebbles is what Chicago, Seattle
and Albany ship. Add more for your local hazard signals (historical
inundation, regulatory floodplain, asset registers); those depend on what
your jurisdiction publishes.

## Step 0: pick the address you'll test against

Pick something with a known street address. City halls work well: Nominatim
geocodes them and they tend to have 311 records nearby.

| City    | Test address                     |
|---------|----------------------------------|
| Chicago | 233 S Wacker Dr (Willis Tower)   |
| Seattle | 400 Broad Street                 |
| Albany  | 24 Eagle St (City Hall)          |

## Step 1: find your 311 dataset

Most US cities publish 311 service requests. Find yours on the open-data
portal. You need two things:

- the resource ID (Socrata: `xxxx-xxxx`);
- the spatial field name. Socrata datasets vary: NYC and Chicago use
  `location`, and Seattle uses `latitude_longitude`.

Verify with a small request before writing YAML:

```bash
curl -s 'https://data.cityofchicago.org/resource/v6vf-nfxy.json?$limit=1' \
  | python3 -m json.tool | head -30
```

If the feed has no category field you can review, skip the 311 pebble. A
deployment with only the federal pebbles and a water-level gauge still
produces a briefing, and an unfiltered count of service requests says
nothing about flooding.

## Step 2: scaffold the deployment directory

Copy a sibling:

```bash
cp -r deployments/chicago deployments/<your-city>
```

This gives you a `stones.yaml` and Chicago's two city manifests
(`chicago_311.yaml`, `lake_michigan_water_level.yaml`); rename them. The
federal pebbles come in automatically. You'll edit `stones.yaml` for the
coverage box and taglines, and the 311 manifest for resource id, spatial
field and record filter.

## Step 3: edit `stones.yaml`

```yaml
deployment:
  experimental: true
coverage:
  bbox: [-87.95, 41.64, -87.52, 42.02]   # [min_lon, min_lat, max_lon, max_lat], WGS84
  city: Chicago
  state: IL
stones:
  - id: cornerstone
    name: Cornerstone
    tagline: The Hazard Reader
    description: Reads what <your city> remembers about flooding.
    order: 1
  - id: touchstone
    name: Touchstone
    tagline: The Live Observer
    description: Watches current flood signals in <your city>.
    order: 2
  ...
```

The `coverage:` block is required. Riprap routes each query by it:
`pick_deployment` in `riprap/core/pebbles/deployments.py` picks the
deployment whose `bbox` contains the geocoded point. A deployment without
a `bbox` is never picked, and `RIPRAP_DEPLOYMENT` does not override this
per-query routing. The example is Chicago's box; draw yours around your
city. `deployment.experimental: true` labels the deployment as
experimental in the header.

## Step 4: edit the 311 manifest

```yaml
id: <city>_311
type: live
title: <City> flood-related 311 service requests near this address
stone: touchstone
maturity: experimental
adapter: socrata_records

spatial: {scope: point, crs: EPSG:4326}

config:
  base_url: https://data.<city>.gov/resource/<resource-id>.json
  radius_m: 200
  location_field: location           # check your dataset's field name first
  limit: 200
  sample_fields: [<a few descriptive fields>]
  count_by_field: <category field>   # e.g. `sr_type`
  order: <date_field> DESC
  cache_ttl_s: 1800
  record_filter:                     # keep only flood-related records
    kind: category_table
    field: <category field>
    labels:                          # category value: flood class
      Water On Street Complaint: street_flooding
      Water in Basement Complaint: basement_or_building_flooding
      Sewer Cleaning Inspection Request: drainage_infrastructure

provenance:
  date_modified: at_fetch           # live Socrata sources resolve this from the metadata API
  retrieved_at: at_fetch
  source_name: <City> Open Data, 311 (<resource-id>)
  source_url: https://data.<city>.gov/d/<resource-id>
  license: <portal's stated license>
  doc_id: <city>_311

narration:
  short: Flood-related <City> 311 service requests within 200 m of this address.
  template: >-
    {n_kept} of {n_before_phrase} <City> 311 service requests within {radius_m} m of this
    address {filter_note}.
```

The `record_filter` is what makes the count mean something. The labels
above are from `deployments/chicago/manifests/chicago_311.yaml`; review
every category value your feed has and list only the flood-related ones
(Chicago's comment records its review). Without the filter the count is
every service request in the radius, and a count equal to `limit` is the
query limit, not a flood signal.

Citations, source URLs and vintages come only from the manifest's
`provenance` block, so fill it in fully. A manifest is
`maturity: production` unless it says `maturity: experimental`; mark a
pebble experimental when its output needs a caveat, and its sentence
will start with "Experimental:".

## Step 5: add your stations

`water_level.yaml` calls `app.context.noaa_tides.summary_for_point`,
which picks the nearest station in that module's `STATIONS` list. Look up
your city's station at <https://tidesandcurrents.noaa.gov/> and add it
to the list (a Great Lakes station also goes in `_GREAT_LAKES_STATIONS`).
The federal `nws_obs` pebble picks the nearest station in
`app/context/nws_obs.py` the same way, so add your nearest airport
station there.

| City    | NOAA station             |
|---------|--------------------------|
| NYC     | 8518750 (Battery)        |
| Chicago | 9087044 (Calumet Harbor) |
| Seattle | 9447130 (Seattle)        |
| Albany  | 8518995 (Albany, Hudson) |

## Step 6: run the probe

```bash
RIPRAP_RECONCILER_TIER=no_llm \
uv run python -c "
import riprap.core.burr.app as a
r = a.run('<your test address>')
print(r['deployment'])
print(r['paragraph'])
print('compliance:', r['compliance'])
"
```

The query routes to your deployment only if the geocoded address falls
inside your `coverage:` bbox. Expected: your deployment's name, then a
Markdown briefing with **Hazard Reader.**, **Live Observer.** and
**Projector.** sections and citations like `[<city>_311]` and
`[fema_nfhl]`. The `compliance` key holds the 13 disclosure checks; the
name is kept for API compatibility and it is not a quality score.

Add your city to the sweep:

```python
# scripts/probe_cities_smoke.py, append to CITIES
{
    "name": "<your-city>",
    "query": "<your test address>",
    "expect_pebbles": ["<city>_311", "nws_obs", "nws_alerts"],
    "expect_narrative_pebbles": ["water_level", "nws_obs"],
    "no_leak": ["Lake Michigan", "Sandy 2012"],  # other cities' landmarks
}
```

Then, with a server running:

```bash
uv run python scripts/probe_cities_smoke.py
# Look for: PASS on every city line, exit code 0
```

## Step 7: open a PR

The PR template asks for the smoke probe's output. Check the briefing
content by hand too: the disclosure checks say the caveats are present,
not that the briefing is useful.

A line in `docs/multi-city.md` adding your city to the table and a
`CHANGELOG.md` entry under `[Unreleased]` are welcome.

## Common gotchas

**Geocoder picks the wrong place.** Riprap's geocoder tries NYC
Geosearch first for NYC matches and OSM Nominatim (rate limited to
1 request per second) for everything else. A query that names another
state or a large city goes to Nominatim directly, by a regex in
`app/geocode.py` (`_NON_NYC_HINT_RE`). If your address gets matched to a
Brooklyn street, add your state code or city name to that regex.

**A disclosure check fails.** Read the `failed` list:

```bash
RIPRAP_RECONCILER_TIER=no_llm \
uv run python -c "
import riprap.core.burr.app as a
r = a.run('<addr>')
print(r['compliance']['failed'])
"
```

Each entry names the check (`riprap/core/compliance/predicates.py`).
Common ones:

- `every_numeric_claim_cited`: a sentence with a number has no
  `[doc_id]`. Check that the pebble has a `provenance.doc_id`.
- `firm_citation_has_vintage`: a FEMA map is cited without its effective
  date.
- `data_gap_disclosed_when_probe_offline`: set
  `fallback.on_offline: skip` (the default) so the briefing still emits
  and discloses the gap when your upstream is down.

**Spatial field returns 0 records.** Request the dataset directly with a
hand-picked `within_circle` to confirm your spatial field name. Many
Socrata datasets have a `location_address` text field next to the
`location` geometry field; you want the latter.

## See also

- [`docs/byod.md`](byod.md): add your own data on top of any existing
  deployment, without forking.
- [`docs/multi-city.md`](multi-city.md): the current city roster.
- [`examples/byod/`](../examples/byod/): a BYOD walkthrough with real
  data, NYC FDNY firehouses (`hc8x-tcnd`).
