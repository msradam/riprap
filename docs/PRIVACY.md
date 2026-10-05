---
type: reference
---

# Privacy and do-no-harm

What Riprap stores, what it sends to other services, and what it is not
for. Each statement below was checked against the code on 2026-09-28,
the storage table and the 311 section again on 2026-10-01, and the whole
page against `web/main.py`, the logging calls and the frontend on
2026-10-05.

## What Riprap does not do

- **No accounts and no cookies.** The server (`web/main.py`) has no login,
  session or cookie code.
- **No analytics or tracking.** The frontend loads no analytics, error
  reporting or tag-manager script. Fonts are served from the app itself
  (`web/sveltekit/src/lib/fonts.css`), not from a font CDN.
- **No database of queries.** The application writes no record of who
  asked what. It does not log the addresses or questions people type. One
  thing outside the application's own code can still hold them, and it is
  in the table below: the web server's access log.

## What is stored, and where

| What | Where | Holds |
|---|---|---|
| HTTP cache | `~/.cache/riprap/http.sqlite` on the machine running the server (`riprap/core/http.py`; `RIPRAP_HTTP_CACHE=off` disables it) | Responses from public data APIs, kept for 10 minutes by default (`RIPRAP_HTTP_CACHE_TTL_S`). 311 records are never written to it (see below). |
| Run logs | `.burr/`, only when `RIPRAP_BURR_TRACKING=1` | Each pipeline run, including the query, for the Burr tracking UI. Off by default. |
| Server output | Standard output and standard error of the process | Startup messages. The web server (uvicorn) writes an access log by default, and its request URLs carry the address or question typed; run it with `--no-access-log` to turn that off. A failed geocoder request is logged by its error type only (`app/geocode.py`), without the request or the text typed. Where these lines go, and how long they are kept, depends on how you run the server. |
| Print snapshots | The visitor's own browser (`localStorage`, one entry per query under `riprap:print:`, `web/sveltekit/src/lib/stores/briefingState.svelte.ts`) | Each briefing run in that browser, so the print page can render it. Entries stay until the visitor clears the site's data. They never leave the browser. |

## What is sent to other services

- **Geocoding.** The address or place typed is sent to NYC Planning
  Labs Geosearch for NYC and to OpenStreetMap's Nominatim otherwise
  (`app/geocode.py`).
- **Public data APIs.** Coordinates or an area outline are sent to the
  city, state and federal APIs each manifest names (NYC Open Data, NOAA,
  NWS, USGS, FEMA, FloodNet and the city portals). Every request, the
  geocoders' included, carries the User-Agent `Riprap/0.8 (civic
  flood-evidence tool)`: a product name, with no contact address or
  personal identifier (`riprap/core/http.py`).
- **Map tiles.** The browser loads basemap tiles from CARTO
  (`basemaps.cartocdn.com`), which sees the map area being viewed.
- **An LLM, only if you configure one.** With `RIPRAP_LLM_BASE_URL` set,
  the question and the evidence text are sent to that endpoint. Without
  it, no model service is contacted.
- **Hugging Face, only with the `ml` extra on a server that opts in to the surge forecast.** The experimental surge
  model's weights are downloaded once from Hugging Face. Nothing about a
  query is sent there. The model reads NOAA's public gauge at The Battery,
  the same for every query.

The public gallery on GitHub Pages is static: it makes no API calls of
its own, and GitHub's own privacy terms apply to its hosting.

## Personal data in 311 records

311 free text (Albany SeeClickFix summaries and descriptions, a Socrata
feed's notes fields) can hold a resident's email address, phone number or
name. The Socrata and SeeClickFix adapters fetch these records with the
HTTP cache turned off and remove email addresses and phone numbers from
every string before anything else reads them (`riprap/core/redact.py`).
**Names are not removed**: telling a name from a street or an agency takes
more than a pattern. NYC's 311 query does not fetch free text at all.

## Where a 311 complaint is shown

A dated complaint at a house number is a record about a household, so
Riprap serves none. Each New York City 311 complaint in the JSON, in an MCP
result, in the page's list of map points and in a saved gallery file is
placed at its block: the street and cross streets from the record's own
fields, with no house number, and coordinates rounded to three decimal
places (about 100 m), so two houses on a block are not told apart. Counts
are of the unrounded records and do not change. A geocoded address no
longer carries the tax lot (BBL) or building number (BIN). The same
complaints remain public, with their addresses, on NYC Open Data; Riprap
does not repeat them at that precision.

## Do no harm

Riprap reports public flood and heat evidence for a place, with every
sentence cited. It is not advice, and it is not an alert or emergency
service: for alerts in New York City use
[Notify NYC](https://a858-nycnotify.nyc.gov/).

- It does not assess a person, a household or a property's value, and it
  should not be used to decide on buying, renting, lending or insuring.
- It is not a regulatory flood determination. For that, use FEMA's
  [Flood Map Service Center](https://msc.fema.gov).
- It is not resident flood guidance. For New York City, use
  [FloodHelpNY](https://www.floodhelpny.org).
- Its checks are patterns and rules with known gaps
  ([GROUNDING.md](GROUNDING.md)). A briefing can omit a relevant source,
  and a source can be out of date; each citation shows the source's
  vintage.
- Counts (311 complaints, sensor events) and complaints placed at a block
  describe places, not people. Do not use them to single out an individual
  or a household.

Report a privacy problem through the process in
[SECURITY.md](../.github/SECURITY.md).
