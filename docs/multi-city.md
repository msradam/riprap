# Multi-city: Riprap outside New York

Four city deployments run on one codebase. NYC is the production
deployment. Chicago, Seattle and Albany are experimental: each has the four
federal pebbles plus a filtered 311 feed and a water-level gauge. Each of
the three sets `deployment.experimental: true` in its `stones.yaml`, and the
header and the briefing say so. Only NYC has local hazard, asset and
forecast layers.

## Deployments

| Deployment | Pebbles | 311 data | Platform | Water level |
|---|---|---|---|---|
| `nyc/` | 41 | NYC Open Data `erm2-nwe9` | Socrata | NOAA Battery 8518750 |
| `chicago/` | 6 | Chicago Data Portal `v6vf-nfxy`, reviewed category table | Socrata | NOAA Calumet Harbor 9087044 |
| `seattle/` | 6 | Seattle Open Data `5ngg-rpne`, reviewed category table | Socrata | NOAA Seattle 9447130 |
| `albany/` | 6 | SeeClickFix public API, flood request types | SeeClickFix | NOAA Albany, Hudson River 8518995 |

Pebble counts include the four federal pebbles in
`deployments/federal/manifests/` (`fema_nfhl`, `nws_alerts`, `nws_obs`,
`usgs_gauges`), which are merged into every deployment. An address outside
every deployment's coverage gets a briefing from those four alone.

## Checking a deployment

`scripts/probe_cities_smoke.py` sends one address per city to a running
server and checks the routed deployment, the pebbles that fired, the
narrative fields and that no other city's content leaks in:

```bash
uv run python scripts/probe_cities_smoke.py http://127.0.0.1:7860
# PASS on every city line expected; exits non-zero if any fail.
```

To see one briefing without a server:

```bash
RIPRAP_RECONCILER_TIER=no_llm \
uv run python -c "
import riprap.core.burr.app as a
r = a.run('233 S Wacker Dr, Chicago, IL')
print(r['deployment'])
print(r['paragraph'])
"
```

The query routes to `deployments/chicago/` because the geocoded point falls
in its `coverage:` bounding box. It calls live Chicago Data Portal, NWS,
NOAA, FEMA and USGS endpoints, so the counts change from run to run.

## Per-city notes

- **Chicago 311 (`v6vf-nfxy`)** gives a category name. `chicago_311` keeps
  the records within 200 m whose `sr_type` is in a table reviewed against
  all 110 values (water on street, water in basement, sewer inspections).
- **Seattle 311 (`5ngg-rpne`)** gives only a category name too.
  `seattle_311` queries the `latitude_longitude` field within 300 m and
  keeps records through a reviewed table on `webintakeservicerequests`.
  Only "Clogged Storm Drain" is flood-related; the feed has no
  street-flooding or sewer-backup category.
- **Albany has no open-data 311 export.** Its 311 intake runs on
  SeeClickFix, so `albany_flood_311` calls the SeeClickFix public API
  through `app/context/seeclickfix.py` (a `python_call` pebble) for the
  flooding, sewers/drainage and sinkhole request types within 800 m. The
  API has no trustworthy server-side radius cutoff, so the module fetches
  nearest-first and filters by distance in Python.

A 311 feed is counted only through a reviewed filter. A feed with free
text and no usable categories is left out, since an unfiltered count of
service requests says nothing about flooding.

## What every deployment gets

- `fema_nfhl`: the effective FEMA flood zone and FIRM panel date at any
  mapped US point (`app/context/fema_nfhl.py`).
- `nws_alerts`: active NWS alerts at any US address.
- `nws_obs`: the latest observation at the nearest station in
  `app/context/nws_obs.py`'s list. Add your city's station to that list.
- `usgs_gauges`: live stage at the nearest active USGS stream gauge
  (`app/context/usgs_gauges.py`); it skips cleanly where no gauge exists.

A water-level pebble is a per-city manifest that calls
`app.context.noaa_tides.summary_for_point`, which picks the nearest NOAA
CO-OPS station in that module's list.

## Bring your own data

`load_registry` also merges manifests from `${CWD}/.riprap/` and from a
colon-separated `RIPRAP_EXTRA_MANIFESTS` env var, on top of the active
deployment. See [`docs/byod.md`](byod.md).

## Sources

- [Chicago 311, `v6vf-nfxy`](https://data.cityofchicago.org/Service-Requests/311-Service-Requests/v6vf-nfxy)
- [Seattle Customer Service Requests, `5ngg-rpne`](https://data.seattle.gov/d/5ngg-rpne)
- [NOAA Calumet Harbor 9087044](https://tidesandcurrents.noaa.gov/stationhome.html?id=9087044)
- [NOAA Seattle 9447130](https://tidesandcurrents.noaa.gov/stationhome.html?id=9447130)
- [SeeClickFix, Albany, NY](https://seeclickfix.com/albany)
- [NOAA Albany, Hudson River 8518995](https://tidesandcurrents.noaa.gov/stationhome.html?id=8518995)
