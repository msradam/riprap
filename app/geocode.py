"""Address geocoding — Nominatim primary, NYC Geosearch as NYC enrichment.

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
from dataclasses import dataclass
from functools import lru_cache

import httpx

log = logging.getLogger("riprap.geocode")

URL = "https://geosearch.planninglabs.nyc/v2/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = (
    "Riprap/0.6 (civic-climate-exposure-tool; +https://github.com/msradam/riprap)"
)

# NYC-bbox guard: lat 40.49–40.92, lon -74.27 to -73.69.
NYC_BBOX = (40.49, -74.27, 40.92, -73.69)

_UPSTATE_ZIP_RE = re.compile(r"\b1[2-4]\d{3}\b")
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


def geocode(text: str, limit: int = 5) -> list[GeocodeHit]:
    """NYC Geosearch primary."""
    try:
        r = httpx.get(URL, params={"text": text, "size": limit}, timeout=5)
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
        log.warning("Geosearch failed: %r", e)
        return []


def geocode_nominatim(
    text: str, *, viewbox: list | None = None, bounded: bool = False,
    country_codes: str | None = "us",
) -> GeocodeHit | None:
    """National OSM Nominatim fallback.

    Uses geopy's Nominatim client, which enforces the OSM Nominatim
    Usage Policy: a non-default User-Agent (required), and the 1 req/s
    rate limit (we apply it explicitly via RateLimiter — geopy doesn't
    rate-limit by default).
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
    from geopy.extra.rate_limiter import RateLimiter  # noqa: PLC0415
    from geopy.geocoders import Nominatim  # noqa: PLC0415

    geocoder = Nominatim(user_agent=NOMINATIM_UA, timeout=10)
    geocode_call = RateLimiter(geocoder.geocode, min_delay_seconds=1.0, swallow_exceptions=False)
    call_kwargs: dict = {
        "addressdetails": True,
        "exactly_one": True,
    }
    if country_codes is not None:
        call_kwargs["country_codes"] = country_codes
    if viewbox is not None:
        call_kwargs["viewbox"] = viewbox
        call_kwargs["bounded"] = bounded
    try:
        location = geocode_call(text, **call_kwargs)
    except Exception as e:  # noqa: BLE001 — log + None per the rest of this module
        log.warning("Nominatim fetch failed: %r", e)
        return None
    if location is None:
        return None
    row = location.raw  # the same dict the JSON API returns
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
        lat=location.latitude,
        lon=location.longitude,
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

        name = os.environ.get("RIPRAP_DEPLOYMENT", "").rstrip("/").split("/")[-1]
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
    if _looks_non_us(text) or (scope_hint and _looks_non_us(scope_hint)):
        check = geocode_nominatim(text, country_codes=None)
        cc = ((check.raw.get("address") or {}).get("country_code") or "").lower() if check else ""
        if cc != "us":
            log.info("geocode_one: %r named a non-US place (resolved country=%r) — "
                     "out of scope, not forcing a US match", text, cc or None)
            return None
    # Region-bias the resolver to the active deployment so ambiguous names
    # land in-area. bounded=True returns only in-region hits; if the query is
    # genuinely outside (or no deployment bbox is known), fall back to the
    # national resolver and let downstream scope logic handle it.
    bbox = _active_deployment_bbox()
    primary = None
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        primary = geocode_nominatim(
            text, viewbox=[(min_lat, min_lon), (max_lat, max_lon)], bounded=True
        )
    if primary is None:
        primary = geocode_nominatim(text)
    if primary is None:
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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance, kilometres."""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))
