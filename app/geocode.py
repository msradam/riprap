"""Address geocoding: NYC Geosearch for exact NYC matches, Nominatim otherwise.

`geocode_one()` is the entry point every deployment (NYC, Chicago,
Seattle, ...) actually calls: OpenStreetMap Nominatim (no key, free,
rate-limited per usage policy) resolves the address, region-biased
to the active deployment's bbox. Only when the resolved point falls
inside NYC does it call NYC DCP Geosearch (geosearch.planninglabs.nyc,
no auth, NYC-only) to enrich the hit with BBL/BIN identifiers the
NYC-specific pebbles need (NYCHA / MTA / DOE / DOH joins) — Geosearch
never runs as a first-pass resolver, since its aggressive fuzzy-match
will silently map an out-of-city address to the nearest NYC street
(e.g. '257 Washington Ave, Albany NY' -> Clinton Hill, Brooklyn). See
`geocode_one`'s docstring for why the order used to be reversed and
what broke.

Includes a borough-hint post-filter so Queens hyphenated-style addresses
(e.g. '153-09 90 Ave, Jamaica, Queens') preferentially resolve to the
borough the user named.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from riprap.core import http
from riprap.core.burr.place import geocode_matches

log = logging.getLogger("riprap.geocode")

URL = "https://geosearch.planninglabs.nyc/v2/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = http.USER_AGENT  # the application's name; no personal identifier is sent to any service

# NYC-bbox guard: lat 40.49–40.92, lon -74.27 to -73.69.
NYC_BBOX = (40.49, -74.27, 40.92, -73.69)

_BOROUGHS = ("Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island")


def _detect_borough(text: str) -> str | None:
    t = text.lower()
    for b in _BOROUGHS:
        if b.lower() in t:
            return b
    # neighborhood -> borough hints
    hints = {
        "queens": "Queens",
        "jamaica": "Queens",
        "rockaway": "Queens",
        "astoria": "Queens",
        "flushing": "Queens",
        "manhattan": "Manhattan",
        "harlem": "Manhattan",
        "soho": "Manhattan",
        "brooklyn": "Brooklyn",
        "bushwick": "Brooklyn",
        "red hook": "Brooklyn",
        "bronx": "Bronx",
        "fordham": "Bronx",
        "staten island": "Staten Island",
    }
    for needle, boro in hints.items():
        if needle in t:
            return boro
    return None


@dataclass
class GeocodeHit:
    address: str
    borough: str | None
    lat: float
    lon: float
    bbl: str | None
    bin: str | None
    raw: dict
    note: str | None = None  # what a reader must be told about the choice of this place


def geocode(text: str, limit: int = 5) -> list[GeocodeHit]:
    """NYC Geosearch primary."""
    try:
        r = http.get(URL, params={"text": text, "size": limit}, timeout=5, ttl_s=86400)
        r.raise_for_status()
        feats = r.json().get("features", [])
        out = []
        for f in feats:
            p = f.get("properties", {})
            coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
            out.append(
                GeocodeHit(
                    address=p.get("label") or p.get("name") or text,
                    borough=p.get("borough"),
                    lat=coords[1],
                    lon=coords[0],
                    bbl=p.get("addendum", {}).get("pad", {}).get("bbl"),
                    bin=p.get("addendum", {}).get("pad", {}).get("bin"),
                    raw=p,
                )
            )
        return out
    except Exception as e:
        # The exception's type only: its text can hold the request URL, and so the address typed.
        log.warning("Geosearch failed: %s", type(e).__name__)
        return []


_NOMINATIM_LOCK = threading.Lock()
_nominatim_last = 0.0


def _nominatim_search(params: dict) -> list:
    """One Nominatim search through the shared client. A process-wide lock
    holds real requests to 1 per second (OSMF usage policy); cached
    answers (kept a day) do not count against it."""
    global _nominatim_last
    with _NOMINATIM_LOCK:
        wait = 1.0 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        r = http.get(NOMINATIM_URL, params={**params, "format": "jsonv2"}, timeout=10,
                     headers={"User-Agent": NOMINATIM_UA}, ttl_s=86400)
        if not r.extensions.get("hishel_from_cache"):
            _nominatim_last = time.monotonic()
    r.raise_for_status()
    return r.json()


def geocode_nominatim(
    text: str, *, viewbox: list | None = None, bounded: bool = False,
    country_codes: str | None = "us",
) -> GeocodeHit | None:
    """National OSM Nominatim fallback.

    Follows the OSM Nominatim Usage Policy: an identifying User-Agent and
    at most 1 request/s across the process (`_nominatim_search`).
    See https://operations.osmfoundation.org/policies/nominatim/

    `viewbox` (a list of two (lat, lon) corner points) plus `bounded=True`
    restricts results to that box, used to keep an ambiguous name resolving
    inside the served region.

    `country_codes="us"` by default — Riprap only has coverage data for
    US addresses, so biasing here is normally correct. Pass `None` to
    disable it: with the restriction on, a query naming a real foreign
    place (e.g. "10 Downing Street, London") doesn't fail, it silently
    resolves to whatever US street best matches on leftover tokens
    ("Downing Street" alone, once "London" can't contribute) — a
    confident-looking wrong answer, not an honest "out of scope" one.
    See geocode_one, which detects a non-US signal in the query and
    reruns unrestricted specifically to catch this.
    """
    params: dict = {"q": text, "addressdetails": 1, "limit": 1}
    if country_codes is not None:
        params["countrycodes"] = country_codes
    if viewbox is not None:
        (lat1, lon1), (lat2, lon2) = viewbox
        params["viewbox"] = f"{lon1},{lat1},{lon2},{lat2}"
        params["bounded"] = 1 if bounded else 0
    try:
        rows = _nominatim_search(params)
    except Exception as e:  # noqa: BLE001 — log + None per the rest of this module
        log.warning("Nominatim fetch failed: %s", type(e).__name__)  # not its text: see geocode()
        return None
    if not rows:
        return None
    row = rows[0]
    addr = row.get("address") or {}

    # Try to map Nominatim borough/county back to NYC standard
    boro = addr.get("suburb") or addr.get("city_district") or addr.get("county")
    if boro and "Kings" in boro:
        boro = "Brooklyn"
    if boro and "New York County" in boro:
        boro = "Manhattan"
    if boro and "Queens" in boro:
        boro = "Queens"
    if boro and "Bronx" in boro:
        boro = "Bronx"
    if boro and "Richmond" in boro:
        boro = "Staten Island"

    return GeocodeHit(
        address=row.get("display_name") or text,
        borough=boro,
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        bbl=None,  # Nominatim doesn't have BBLs
        bin=None,
        raw={"source": "nominatim", **row},
    )


# Any of these in the query string strongly signals NOT-NYC — skip
# the NYC Geosearch step entirely. NYC Geosearch will fuzzy-match
# e.g. "401 N Wabash Ave, Chicago, IL" to "401 AVENUE N, Brooklyn"
# if we let it try, which then passes the broad NYC-bbox check
# downstream because the bad match happens to fall inside NYC.
_NON_NYC_HINT_RE = re.compile(
    r"(?:,|\s)\s*(?:"
    # US state codes other than NY (the ones with significant cities)
    r"AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|"
    r"MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY|"
    # Major non-NYC US cities (common quick-test names)
    r"chicago|los angeles|san francisco|seattle|boston|philadelphia|"
    r"philly|houston|dallas|austin|miami|atlanta|denver|portland|"
    r"san diego|phoenix|minneapolis|detroit|baltimore|washington dc|"
    # Non-US countries (catches "Tokyo Tower, Minato, Tokyo, Japan"
    # which NYC Geosearch otherwise fuzzy-matches to a Manhattan
    # building called MELTZER TOWER). Nominatim handles these
    # globally — better to defer to it than return a wrong NYC hit.
    r"japan|china|korea|mexico|canada|uk|united kingdom|france|germany|"
    r"italy|spain|portugal|netherlands|belgium|sweden|norway|denmark|"
    r"australia|new zealand|india|brazil|argentina|chile|colombia|"
    r"russia|poland|turkey|egypt|south africa|israel|"
    # Common country/region suffix tokens that hint non-US.
    r"prefecture|province|kingdom of"
    r")\b",
    re.IGNORECASE,
)


def _looks_non_nyc(text: str) -> bool:
    """Returns True only when the query explicitly names a non-NYC
    place. Bare addresses without city/state info still try NYC
    Geosearch first (the NYC bias is intentional — most callers are
    NYC users)."""
    return bool(_NON_NYC_HINT_RE.search(text))


# Same non-US country tokens as _NON_NYC_HINT_RE, isolated so geocode_one
# can tell "this is probably Chicago" (still worth a US-bounded Nominatim
# lookup) apart from "this is probably London" (worth checking whether
# it actually resolves outside the US before ever calling it a match —
# see _looks_non_us below).
_NON_US_HINT_RE = re.compile(
    r"(?:,|\s)\s*(?:"
    r"japan|china|korea|mexico|canada|uk|united kingdom|france|germany|"
    r"italy|spain|portugal|netherlands|belgium|sweden|norway|denmark|"
    r"australia|new zealand|india|brazil|argentina|chile|colombia|"
    r"russia|poland|turkey|egypt|south africa|israel|"
    r"prefecture|province|kingdom of|"
    # Major foreign cities named without their country — a real user
    # asking about "London" rarely also types "UK" (this is the exact
    # phrasing that silently mis-geocoded to Oklahoma before this fix).
    r"london|paris|tokyo|beijing|shanghai|mumbai|delhi|toronto|"
    r"vancouver|sydney|melbourne|berlin|rome|madrid|amsterdam|dublin|"
    r"seoul|hong kong|singapore|dubai|cairo|lagos|nairobi|"
    r"mexico city|sao paulo|buenos aires|moscow|istanbul"
    r")\b",
    re.IGNORECASE,
)


def _looks_non_us(text: str) -> bool:
    """Returns True only when the query explicitly names a country (or
    country-shaped token) outside the US."""
    return bool(_NON_US_HINT_RE.search(text))


@lru_cache(maxsize=1)
def _active_deployment_bbox() -> tuple[float, float, float, float] | None:
    """Coverage bbox (min_lon, min_lat, max_lon, max_lat) of the deployment
    selected by RIPRAP_DEPLOYMENT. Used to bias geocoding to the served
    region so an ambiguous name ("Red Hook") resolves in-area instead of to a
    same-named place elsewhere ("Red Hook, Dutchess County"). None if it
    can't be resolved (geocoding then runs unbiased, as before)."""
    import os  # noqa: PLC0415

    try:
        from riprap.core.pebbles.deployments import deployment_by_name  # noqa: PLC0415

        name = os.environ.get("RIPRAP_DEPLOYMENT", "nyc").rstrip("/").split("/")[-1]
        dep = deployment_by_name(name) if name else None
        return dep.bbox if dep else None
    except Exception:  # noqa: BLE001 — bias is best-effort
        return None


def geocode_one(text: str, *, scope_hint: str | None = None) -> GeocodeHit | None:
    """Dynamic geocoder — Nominatim first, NYC Geosearch as enrichment.

    `scope_hint`: the original raw user query, when `text` is a narrower
    target string a planner LLM already extracted from it (e.g. text=
    "10 Downing Street" pulled out of "what's the flood risk at 10
    Downing Street in London?"). Target extraction routinely drops the
    city/country — the planner's own rationale can say "this is about
    London" while the extracted target string never mentions it. The
    non-US scope check below needs to see whatever locality context
    exists *anywhere* in the request, not just what survived extraction,
    so it scans `text` and `scope_hint` together.

    Previous order had NYC Geosearch as the primary and Nominatim as a
    fallback. That gave NYC Geosearch's aggressive fuzzy-match free
    rein over every query — typos like "189 Atantic Avnue, Broklyn"
    silently became "189 McKinley Avenue, Brooklyn", and bare ZIPs
    like "11201" became "11201 70 Road, Forest Hills". Both wrong,
    both impossible for the user to notice without comparing rendered
    address to input.

    The cleaner shape: Nominatim is the canonical resolver (it
    handles typos by failing honestly, parses ZIPs as regions, works
    uniformly across every shipped city). NYC Geosearch is only
    called when Nominatim resolves to a NYC point — and only to
    enrich the hit with BBL / BIN identifiers the NYC-specific
    pebbles need (NYCHA / MTA / DOE / DOH joins). When Nominatim
    fails or returns non-NYC, we never touch Geosearch.

    Before any of that: if the query names a real foreign country
    ("London", "Tokyo, Japan"), every US-restricted lookup below is
    guaranteed to force-fit the wrong country rather than fail — that's
    what country_codes="us" does by construction, not an edge case.
    Confirm the mismatch with one unrestricted lookup and return None
    (honest "not covered") instead of a confident wrong-country hit.
    """
    exact = _geosearch_exact(text) or _geosearch_in_city(text, scope_hint)
    if exact is not None:
        return exact
    if _looks_non_us(text) or (scope_hint and _looks_non_us(scope_hint)):
        check = geocode_nominatim(text, country_codes=None)
        cc = ((check.raw.get("address") or {}).get("country_code") or "").lower() if check else ""
        if cc != "us":
            # The text typed is never logged.
            log.info("geocode_one: a non-US place (resolved country=%r) is out of scope, not forcing a US match",
                     cc or None)
            return None
    # Region-bias the resolver to the active deployment so ambiguous names
    # land in-area. bounded=True returns only in-region hits; if the query is
    # genuinely outside (or no deployment bbox is known), fall back to the
    # national resolver and let downstream scope logic handle it.
    bbox = _active_deployment_bbox()
    primary = None
    # "Ferry Building, San Francisco" once matched a Jersey City ferry
    # building inside the NYC viewbox: a query that names another city or
    # state goes to the national lookup directly.
    if _looks_non_nyc(text) or (scope_hint and _looks_non_nyc(scope_hint)):
        bbox = None
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        primary = geocode_nominatim(
            text, viewbox=[(min_lat, min_lon), (max_lat, max_lon)], bounded=True
        )
    if primary is None:
        primary = geocode_nominatim(text)
    elif re.match(r"\s*\d", text) and not geocode_matches(text, primary.address):
        # The region-biased lookup returned the nearest street, not the
        # house asked for ("1600 Pennsylvania Ave NW" landed on a Brooklyn
        # avenue). The national lookup wins when it has the house. A
        # landmark or phrase has no house number to win with, so it makes
        # no second request.
        national = geocode_nominatim(text)
        if national is not None and geocode_matches(text, national.address):
            primary = national
    if primary is None:
        return None
    if re.match(r"\s*\d", text) and not geocode_matches(text, primary.address):
        # A numbered address whose nearest hit is another street is not a
        # "closest match": "90-01 183rd Steet, Quens" once became a Harlem
        # corner, and a house number that does not exist became a point on
        # the street 7 km away. Not resolved is the honest answer.
        log.info("geocode_one: a house number whose nearest hit is another street; not resolved")
        return None
    # Enrich with NYC Geosearch when the resolved point is inside the
    # NYC bbox. Geosearch may add bbl/bin/borough refinements we
    # otherwise lose. If Geosearch returns nothing or a hit that
    # disagrees on coordinates (>500 m apart), trust Nominatim.
    in_nyc = (
        primary.lat is not None
        and primary.lon is not None
        and NYC_BBOX[0] <= primary.lat <= NYC_BBOX[2]
        and NYC_BBOX[1] <= primary.lon <= NYC_BBOX[3]
    )
    if not in_nyc:
        return primary
    try:
        hits = geocode(text)
    except Exception:  # noqa: BLE001 — enrichment is best-effort
        return primary
    if not hits:
        return primary
    # Match-or-skip: only adopt Geosearch's identifiers if it agrees
    # with Nominatim's geometry. Avoids the old fuzzy-match drift.
    for h in hits:
        if h.lat is None or h.lon is None:
            continue
        if _haversine_km(primary.lat, primary.lon, h.lat, h.lon) > 0.5:
            continue
        # Geosearch confirms — keep Nominatim's address+coords, take
        # Geosearch's BBL/BIN/borough refinements where missing.
        return GeocodeHit(
            address=primary.address,
            borough=primary.borough or h.borough,
            lat=primary.lat,
            lon=primary.lon,
            bbl=h.bbl or primary.bbl,
            bin=h.bin or primary.bin,
            raw={**primary.raw, "geosearch_enrichment": True},
        )
    return primary


_NYC_PLACE_RE = re.compile(
    r"\b(manhattan|brooklyn|queens|bronx|staten island|new york,? ny|nyc|1[01]\d{3})\b",
    re.IGNORECASE,
)
_STREET_ABBREV = {
    "AVE": "AVENUE", "AV": "AVENUE", "ST": "STREET", "RD": "ROAD", "BLVD": "BOULEVARD",
    "PL": "PLACE", "DR": "DRIVE", "PKWY": "PARKWAY", "LN": "LANE", "CT": "COURT",
    "TER": "TERRACE", "HWY": "HIGHWAY", "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH",
}


def _norm_street(text: str) -> str:
    """Uppercase, drop punctuation and ordinal suffixes, expand common
    abbreviations: '189 Atlantic Ave.' and 'E 14th St' compare equal to
    Geosearch's '189 ATLANTIC AVENUE' and 'EAST 14 STREET'."""
    words = re.sub(r"[^\w\s-]", " ", text.upper()).split()
    words = [re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w) for w in words]
    return " ".join(_STREET_ABBREV.get(w, w) for w in words)


def _geosearch_exact(text: str) -> GeocodeHit | None:
    """NYC Geosearch as the first resolver, but only when the match is
    unambiguous. Geosearch fuzzy-matches everything it is given (see
    geocode_one), so a hit is accepted only if the query names a NYC
    borough, ZIP or 'New York, NY', the hit's house number and street
    both appear in the query, and the hit is in the borough the query
    names (if any). Anything else falls through to Nominatim."""
    if not _NYC_PLACE_RE.search(text) or _looks_non_nyc(text):
        return None
    # Several hits, not the first alone: the first hit for "100 Broadway, Brooklyn" is in Manhattan, and the
    # address was refused. '560 Grand St, Manhattan' must still not land in Brooklyn.
    named = _detect_borough(text)
    hits = [h for h in _exact_hits(text) if not (named and h.borough and h.borough.lower() != named.lower())]
    return hits[0] if hits else None


def _exact_hits(text: str) -> list[GeocodeHit]:
    """Geosearch hits whose house number and street both appear in the
    query, in its order."""
    # ponytail: the first 10 hits; ask borough by borough if an address in a second borough is ever missed.
    query = f" {_norm_street(text)} "
    out = []
    for hit in geocode(text, limit=10):
        number = str(hit.raw.get("housenumber") or "")
        street = _norm_street(str(hit.raw.get("street") or ""))
        if hit.lat is not None and number and street and f" {number} {street} " in query:
            out.append(hit)
    return out


def _geosearch_in_city(text: str, scope_hint: str | None = None) -> GeocodeHit | None:
    """A house number and street with no borough, city or ZIP ("45 Main
    Street"), on a server whose city is New York: the city's own address
    file before the national lookup, which once placed it in St. Lawrence
    County, 472 km away. When the address exists in more than one borough
    the first is taken and the hit's note says so, with the others."""
    import os  # noqa: PLC0415

    if not re.match(r"\s*\d", text) or _NYC_PLACE_RE.search(text) or _looks_non_nyc(text) or (
            scope_hint and (_looks_non_nyc(scope_hint) or _looks_non_us(scope_hint))) or "," in text or not os.environ.get(
            "RIPRAP_DEPLOYMENT", "nyc").rstrip("/").endswith("nyc"):
        return None
    hits = _exact_hits(text)
    if not hits:
        return None
    hit = hits[0]
    boroughs = list(dict.fromkeys(h.borough for h in hits if h.borough))
    if len(boroughs) > 1:
        hit.note = (f"{text.strip()} is an address in more than one borough ({', '.join(boroughs)}). This briefing is "
                    f"for the one in {hit.borough}. Add the borough to the address to choose another.")
    return hit


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance, kilometres."""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))
