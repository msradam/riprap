# Port your city: a worked walkthrough

> NYC is the reference deployment for an open civic-tech framework.
> Adding your jurisdiction is a directory of YAML, not a fork.

This is the lived experience of porting Boston, Chicago, Seattle, and
San Francisco onto Riprap in two days, written up so anyone can do the
same for their city. Boston is the worked example because it's the
hardest case (different data platform: CKAN, not Socrata) — once Boston
is in your head, every Socrata city is easier.

If your city's open-data portal runs **Socrata** (data.cityofnewyork.us,
data.cityofchicago.org, data.sfgov.org, data.seattle.gov, opendata.dc.gov,
data.austintexas.gov, ...) or **CKAN** (data.boston.gov, opendataphilly.org,
open.toronto.ca, most EU portals): the existing adapters already
work. You write YAML.

## What a deployment is

```
deployments/<city>/
├── stones.yaml              # a coverage: block (bounding box, city, state)
│                            # and five entries, one per Stone (Cornerstone,
│                            # Keystone, Touchstone, Lodestone, Capstone),
│                            # with city-flavoured taglines and descriptions
└── manifests/
    ├── water_level.yaml     # NOAA tides, nearest station auto-resolves
    └── <city>_311.yaml      # your city's 311 / equivalent service-request feed
```

A city directory holds only its own manifests. The four federal pebbles
in `deployments/federal/manifests/` (`fema_nfhl`, `nws_alerts`,
`nws_obs`, `usgs_gauges`) are merged into every deployment
automatically, so do not copy them.

The Boston set (two city manifests plus the four federal pebbles) is
enough to pass the 13 disclosure checks (caveat-phrase substring tests)
on every city we've shipped. Passing them says the
briefing carries its caveats, not that it is useful. Add more for your local hazard signals
(historical inundation, regulatory floodplain, asset registers, etc.) —
those depend on what your jurisdiction publishes.

## Step 0 — Pick the address you'll test against

Pick something with a known street address and lat/lon. City halls work
great; they're publicly geocodable on Nominatim, they tend to have
311 records nearby, and they're inside whatever flood/heat/air dataset
coverage your portal exposes.

| City    | Test address                                   |
|---------|------------------------------------------------|
| Chicago | 233 S Wacker Dr (Willis Tower)                |
| Seattle | 2100 5th Ave (Climate Pledge Arena area)      |
| SF      | 1 Dr Carlton B Goodlett Pl (City Hall)        |
| Boston  | 1 City Hall Square                            |

## Step 1 — Find your 311 dataset

Most US cities publish 311 service requests. Find yours on the open-data
portal. The two things you need:

- **Resource ID** (Socrata: `xxxx-xxxx`; CKAN: a UUID)
- The **spatial field name**. Socrata datasets vary: NYC and Chicago use
  `location`, SF uses `point`, and Seattle uses `latitude_longitude`.
  CKAN datasets typically ship `latitude`/`longitude` numeric columns.

Verify with a tiny curl before writing YAML:

```bash
# Socrata: list fields + check spatial field
curl -s 'https://data.cityofchicago.org/resource/v6vf-nfxy.json?$limit=1' \
  | python3 -m json.tool | head -30

# CKAN: list fields
curl -s 'https://data.boston.gov/api/3/action/datastore_search?\
resource_id=1a0b420d-99f1-4887-9851-990b2a5a6e17&limit=1' \
  | python3 -m json.tool | head -30
```

If the spatial field is missing, you have two options:

1. **Different dataset** — many cities publish multiple 311 exports;
   one might have a `Point`-typed geo column even if another doesn't.
2. **Skip the 311 pebble**: a deployment with only the federal pebbles
   and a water-level gauge still passes the 13/13 disclosure checks.

## Step 2 — Scaffold the deployment directory

Easiest path: copy a sibling.

```bash
cp -r deployments/boston deployments/<your-city>
```

This gives you a `stones.yaml` and Boston's two city manifests
(`boston_311.yaml`, `water_level.yaml`); rename the 311 one. The federal
pebbles come in automatically. You'll edit `stones.yaml` for the coverage
box and taglines, and the 311 manifest for resource id, spatial field and
record filter; everything else can stay.

## Step 3 — Edit `stones.yaml`

```yaml
coverage:
  bbox: [-71.20, 42.23, -70.92, 42.40]   # [min_lon, min_lat, max_lon, max_lat], WGS84
  city: Boston
  state: MA
stones:
  - id: cornerstone
    name: Cornerstone
    tagline: The Hazard Reader
    description: Reads what <your city> remembers about flooding —
                 specific local terrain / shoreline / catchment notes.
    order: 1
  - id: touchstone
    name: Touchstone
    tagline: The Live Observer
    description: Watches current flood signals — <city> 311 cases,
                 NWS forecast office, NOAA tide/lake observations.
    order: 2
  ...
```

The `coverage:` block is required. Riprap routes each query by it:
`pick_deployment` in `riprap/core/pebbles/deployments.py` picks the
deployment whose `bbox` contains the geocoded point. A deployment without
a `bbox` is never picked, and `RIPRAP_DEPLOYMENT` does not override this
per-query routing. The example is Boston's box from
`deployments/boston/stones.yaml`; draw yours around your city.

The Stone taglines are the only "voice" you'll write. They are what
readers see at the top of each Stone section in the briefing. Keep them
short and local.

## Step 4 — Edit the 311 manifest

### Socrata cities

```yaml
id: <city>_311
type: live
title: <City> 311 service requests near this address
stone: touchstone
adapter: socrata_records

spatial: {scope: point, crs: EPSG:4326}

config:
  base_url: https://data.<city>.gov/resource/<resource-id>.json
  radius_m: 300
  location_field: location           # OR `point`, OR `the_geom`, check first
  limit: 200
  sample_fields: [<a few descriptive fields>]
  count_by_field: <category field>   # e.g. `service_name`, `reason`
  order: <date_field> DESC
  cache_ttl_s: 1800
  record_filter:                     # keep only flood-related records
    kind: category_table
    field: <category field>          # e.g. `sr_type`
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
  short: Flood-related <City> 311 service requests within 300 m of this address.
  template: >-
    {n_kept} of {n_before_phrase} <City> 311 service requests within {radius_m} m of this
    address {filter_note}.
```

Without `config.record_filter` the count is every service request in the
radius, and a count equal to `limit` is the query limit, not a flood
signal. The labels above are from `deployments/chicago/manifests/chicago_311.yaml`;
review every category value your feed has and list only the flood-related
ones (Chicago's comment records its review). A feed with free text instead
of categories can use `kind: flood_311_model` (see the SF, Boston and
Albany manifests), but that classifier needs locally built weights and
passes records unfiltered without them ([`docs/GROUNDING.md`](GROUNDING.md)).

### CKAN cities

```yaml
id: <city>_311
type: live
title: <City> 311 service requests near this address
stone: touchstone
adapter: ckan_records

spatial: {scope: point, crs: EPSG:4326}

config:
  ckan_base: https://data.<city>.gov
  resource_id: <ckan-uuid>
  lat_field: latitude
  lon_field: longitude
  radius_m: 300
  limit: 500
  sample_fields: [<a few descriptive fields>]
  count_by_field: <category field>
  order: <date_field> DESC
  cache_ttl_s: 1800
```

The CKAN adapter does bbox SQL push-down on the lat/lon columns and
then haversine-refines in Python, so it works for any CKAN datastore
with numeric lat/lon columns. Give it the same `provenance` and
`narration` blocks as the Socrata example.

Citations, source URLs and vintages come only from the manifest's
`provenance` block, so fill it in fully. A manifest is
`maturity: production` unless it says `maturity: experimental`; mark a
pebble experimental when its output needs a caveat, and its sentence
will start with "Experimental:".

## Step 5 — Adjust the NOAA station (optional)

`water_level.yaml` calls `app.context.noaa_tides.summary_for_point`,
which auto-resolves the nearest NOAA CO-OPS station for an address.
You usually don't need to touch this — the federal pebble figures it
out.

If you want the manifest comment to be accurate, look up your city's
nearest station at <https://tidesandcurrents.noaa.gov/>. Examples:

| City    | NOAA station             |
|---------|--------------------------|
| NYC     | 8518750 (Battery)        |
| Chicago | 9087044 (Calumet Harbor) |
| Seattle | 9447130 (Seattle)        |
| SF      | 9414290 (San Francisco)  |
| Boston  | 8443970 (Boston Harbor)  |

## Step 6 — Run the probe

```bash
RIPRAP_RECONCILER_TIER=no_llm \
uv run python -c "
import riprap.core.burr.app as a
r = a.run('<your test address>')
print(r['paragraph'])
print('compliance:', r['compliance'])
"
```

The query routes to your deployment only if the geocoded address falls
inside your `coverage:` bbox. Expected: a Markdown paragraph with
**Live Observer.**, **Projector.**, etc. headers, citations like `[<city>_311]` and `[nws_obs]`, and
`compliance: {'passed': True, 'n_passed': 13, 'n_total': 13, ...}`. The
`compliance` key holds the disclosure checks; the name is kept for API
compatibility and it is not a quality score.

Add your city to the sweep:

```python
# scripts/probe_cities_smoke.py — append to CITIES
{
    "name": "<your-city>",
    "query": "<your test address>",
    "expect_pebbles": ["<city>_311", "nws_obs", "nws_alerts"],
    "expect_narrative_pebbles": ["<city>_311", "nws_obs"],
    "no_leak": ["Lake Michigan", "San Francisco", "Boston Logan"],  # other cities' landmarks
}
```

Then:

```bash
uv run python scripts/probe_cities_smoke.py
# Look for: PASS on every city line, exit code 0
```

## Step 7 — Open a PR

The PR template asks for the address you tested against and the
disclosure-check result. If you got 13/13 from the probe, the caveats are in
place; check the briefing content by hand too.

If you can also include:

- Screenshots of the briefing rendered in the UI
- A line in `docs/multi-city.md` adding your city to the cities table
- A `CHANGELOG.md` entry under `[Unreleased]`

That's the polished version. None of those are strictly required to
ship the deployment.

## Common gotchas

**Geocoder picks the wrong place.** Riprap's geocoder tries NYC
Geosearch first for exact NYC matches and OSM Nominatim (rate limited to
1 request per second) for everything else. The fallback is triggered by a regex in
`app/geocode.py:_NON_NYC_HINT_RE` matching state codes + major city
names. If your address gets fuzzy-matched to a Brooklyn street, add
your state code or city name to that regex.

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
- `scope_declaration_present`: set `RIPRAP_BRIEFING_SCOPE` if your
  deployment is not a flood briefing.
- `firm_citation_has_vintage`: a FEMA map is cited without its effective
  date.
- `data_gap_disclosed_when_probe_offline`: set
  `fallback.on_offline: skip` (the default) so the briefing still emits
  and discloses the gap when your upstream is down.

**Spatial field returns 0 records.** Curl the dataset directly with a
hand-picked `within_circle` (Socrata) or `BETWEEN` (CKAN) to confirm
your spatial field name. Easy mistake: many Socrata datasets have a
`location_address` text field next to the `location` geometry field;
you want the latter.

## See also

- [`docs/byod.md`](byod.md) — for users who want to add their own
  data on top of any existing deployment, without forking.
- [`docs/multi-city.md`](multi-city.md) — current city roster +
  the framework claim.
- [`docs/history/VERIFICATION.md`](history/VERIFICATION.md): a dated snapshot of a
  deterministic verification pass.
- [`examples/byod/`](../examples/byod/) — real-data BYOD walkthrough
  using NYC FDNY firehouses (`hc8x-tcnd`).
