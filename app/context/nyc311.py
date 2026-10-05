"""NYC 311: complaints about flooding and sewer backups around a point or inside an area.

Live dataset: erm2-nwe9. Filter by descriptor (the flood signal is in
descriptor, not complaint_type) within a buffer.

A dated complaint at a house number is a record about a household (fifteen
sewer backups at one house is a list for an insurer or a buyer), so no
house number and no per-house coordinate leaves this module: a complaint
is placed at its block (`block_of`) and its coordinates are rounded to
three decimal places, about 100 m (`COORD_DECIMALS`). Counts are of the
records themselves and do not change.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from riprap.core import http

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
DOC_ID = "nyc311"
CITATION = "NYC 311 service requests (Socrata erm2-nwe9, 2020 to present)"

# What a count of complaints is not. One sentence, and it travels with every
# count: in the sentence, and as `caveat` in the value for JSON and MCP readers.
# Kontokosta, Hong and Korsberg (arXiv:1710.02452) find that "socioeconomic
# status, household characteristics, and language proficiency have a
# non-trivial effect on the propensity to use 311"; the second reference is
# The Annals of Applied Statistics 19(2), 2025.
CAVEAT = ("A count of complaints is a count of reports filed, not of floods: a low count can mean under-reporting "
          "and not the absence of flooding, because the propensity to file a 311 request varies with income, language "
          "and demographics (studies of other 311 complaint types: Kontokosta, Hong and Korsberg, arXiv:1710.02452; "
          "Boxer, Hong, Kontokosta and Neill, Annals of Applied Statistics 19(2), 2025, doi:10.1214/24-AOAS2003).")

# The kind of complaint each descriptor records, in the words a question
# uses ("street flooding"). NYC renamed the descriptors: complaint type
# "Sewer" (coded names) ends on 2026-07-29 and "Sewer Maintenance" (plain
# names) carries the same kinds from then on, so each kind has two names.
# tests/test_311_vocabulary_live.py fails when the dataset grows a third.
KIND = {
    "Street Flooding (SJ)": "street flooding",
    "Flooding on Street": "street flooding",
    "Sewer Backup (Use Comments) (SA)": "sewer backup",
    "Backup": "sewer backup",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)": "catch basin",
    "Catch Basin Clogged": "catch basin",
    "Highway Flooding (SH)": "highway flooding",
    "Flooding on Highway": "highway flooding",
    "Manhole Overflow (Use Comments) (SA1)": "manhole overflow",
    "Manhole Overflow": "manhole overflow",
    "RAIN GARDEN FLOODING (SRGFLD)": "rain garden flooding",
}
FLOOD_DESCRIPTORS = list(KIND)
# What the count is and is not, inside the sentence that states it (a test holds "eleven" to len(KIND)).
SCOPE = "eleven descriptors; other sewer complaints, such as odors or missing covers, are not counted"
# The days Hurricane Ida's flooding was reported on. The address window (5 years) now starts after them.
IDA_DAYS = ("2021-09-01", "2021-09-03")
COMPLAINT_TYPES = ("Sewer", "Sewer Maintenance")
# The plain names are common words ("Backup"), so the complaint type is part of the filter.
_DESC_CLAUSE = ("(" + " OR ".join(f"descriptor='{d}'" for d in FLOOD_DESCRIPTORS) + ") AND ("
                + " OR ".join(f"complaint_type='{t}'" for t in COMPLAINT_TYPES) + ")")
_NEW_NAMES = frozenset(d for d in KIND if "(" not in d)


@dataclass
class Complaint:
    unique_key: str
    descriptor: str
    created_date: str
    address: str | None
    status: str | None
    lat: float | None = None
    lon: float | None = None
    block: str | None = None  # the only place name that is served: see block_of


# Three decimal places of a degree: about 111 m north to south and 84 m east
# to west in New York, so two houses on a block share a point.
COORD_DECIMALS = 3


def block_of(row: dict) -> str | None:
    """Where a complaint is shown: its street between its cross streets
    ("183 STREET between 90 AVE and 91 AVE"), or its intersection ("90
    AVENUE and 184 STREET"), from the record's own street_name and
    cross_street fields. Never the house number (incident_address)."""
    street, a, b = (" ".join((row.get(k) or "").split()) or None for k in ("street_name", "cross_street_1", "cross_street_2"))
    if not street:
        return None
    if a and b and street in (a, b):  # an intersection lists its own street as a cross street
        return f"{street} and {b if a == street else a}"
    return f"{street} between {a} and {b}" if a and b else street


def _point(c: Complaint) -> dict:
    """A complaint as it is served: date, descriptor, block, and (when it has
    them) coordinates rounded so the house is not told apart."""
    out = {"date": c.created_date[:10], "descriptor": c.descriptor, "block": c.block}
    if c.lat is not None and c.lon is not None:
        out |= {"lat": round(c.lat, COORD_DECIMALS), "lon": round(c.lon, COORD_DECIMALS)}
    return out


def complaints_near(lat: float, lon: float, radius_m: float = 200,
                    since: datetime | None = None,
                    limit: int = 1000) -> list[Complaint]:
    return _complaints_where(f"within_circle(location, {lat}, {lon}, {radius_m})", since, limit, timeout=30)


def summary_for_point(lat: float, lon: float, radius_m: float = 200,
                      years: int = 5) -> dict:
    # Midnight UTC, not the current second: the query text (and so the HTTP
    # cache key) stays the same all day, so a repeat query is served from cache.
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365 * years)
    cs = complaints_near(lat, lon, radius_m, since=since, limit=2000)
    return _summarize(cs, years=years, radius_m=radius_m, limit=2000,
                      query_url=query_url(f"within_circle(location, {lat}, {lon}, {radius_m})", since, 2000))


def complaints_in_polygon(polygon, polygon_crs: str = "EPSG:4326",
                          since: datetime | None = None,
                          limit: int = 50000) -> list[Complaint]:
    """Flood-related complaints inside a polygon, counted with its exact
    outline. An NTA outline has thousands of vertices, too long for a query
    URL, so Socrata is asked for the polygon's bounding box and the rows
    are tested against the outline here. (A simplified outline in the query
    once undercounted: Red Hook's area read 483 against 515.)"""
    import geopandas as gpd
    import shapely

    geom = gpd.GeoSeries([polygon], crs=polygon_crs).to_crs("EPSG:4326").iloc[0]
    west, south, east, north = geom.bounds
    rows = _complaints_where(f"within_box(location, {north}, {west}, {south}, {east})", since, limit)
    if len(rows) >= limit:
        # ponytail: one fetch of the box; page through it if a box ever holds this many rows.
        raise ValueError(f"more than {limit} flood-related 311 requests in the area's bounding box; not counted")
    rows = [c for c in rows if c.lat is not None and c.lon is not None]
    inside = shapely.contains_xy(geom, [c.lon for c in rows], [c.lat for c in rows])
    return [c for c, ok in zip(rows, inside, strict=True) if ok]


def complaints_in_board(board: str, since: datetime | None = None, limit: int = 5000) -> list[Complaint]:
    """Flood-related complaints whose `community_board` field is `board`
    ('12 QUEENS'): the record's own district, the official definition."""
    return _complaints_where(f"community_board='{board}'", since, limit)


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# What the fetch reads, and what the published query link selects: the link leaves out the house number and the
# coordinates (one click on it once returned the house numbers Riprap does not show), and still returns one row
# per complaint with its date, descriptor and block, so the count can be redone.
_SELECT = ("unique_key, descriptor, created_date, incident_address, status, latitude, longitude, "
           "street_name, cross_street_1, cross_street_2")
_PUBLIC_SELECT = "unique_key, created_date, descriptor, street_name, cross_street_1, cross_street_2"


def _params(clause: str, since: datetime | None, limit: int, select: str = _SELECT) -> dict[str, str]:
    where = f"{_DESC_CLAUSE} AND {clause}"
    if since:
        # Socrata floating-timestamp: drop tz suffix
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    return {
        "$select": select,
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }


def query_url(clause: str, since: datetime | None, limit: int) -> str:
    """The Socrata query a count was read from, for its citation: a reader
    opens it and gets the rows, without house numbers or coordinates
    (_PUBLIC_SELECT). A request filed under both descriptor names within
    ten minutes at one place is then counted once."""
    from urllib.parse import urlencode

    return f"{URL}?{urlencode(_params(clause, since, limit, _PUBLIC_SELECT))}"


def _complaints_where(clause: str, since: datetime | None, limit: int, timeout: int = 60) -> list[Complaint]:
    """Flood-related complaints matching `clause`, newest first, each with
    its coordinates (one_per_incident needs them for intersection requests)."""
    r = http.get(URL, params=_params(clause, since, limit), timeout=timeout)
    r.raise_for_status()
    return [
        Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
            lat=_num(row.get("latitude")), lon=_num(row.get("longitude")),
            block=block_of(row),
        )
        for row in r.json()
    ]


def _since(years: int) -> datetime:
    # Midnight UTC, not the current second: the query text (and so the HTTP
    # cache key) stays the same all day, so a repeat query is served from cache.
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365 * years)


def summary_for_polygon(polygon, polygon_crs: str = "EPSG:4326",
                        years: int = 5) -> dict:
    """Polygon-mode aggregation: counts of flood-related 311 complaints
    inside the polygon over the trailing window."""
    cs = complaints_in_polygon(polygon, polygon_crs=polygon_crs, since=_since(years))
    # (No query_url: the service is asked for the outline's bounding box and the rows are tested here.)
    return _summarize(cs, years=years, radius_m=None)


def summary_for_district(code: str, years: int = 3) -> dict:
    """Counts for a community district (QN12) by the record's
    `community_board` field, and the sentence says so."""
    board = community_board(code)
    if board is None:
        raise ValueError(f"not a community district code like QN12: {code!r}")
    # QN12 holds about 4,500 rows in three years; the limit leaves room.
    cs = complaints_in_board(board, since=_since(years), limit=20000)
    where = f"in Community District {code.upper().replace(' ', '')} (by the record's community board field)"
    return _summarize(cs, years=years, radius_m=None, limit=20000, where=where,
                      query_url=query_url(f"community_board='{board}'", _since(years), 20000))


def one_per_incident(cs: list[Complaint]) -> list[Complaint]:
    """Drop a request filed under both names. During the storm of 29
    September 2023 and the days after, 311 logged many requests twice, once
    under each descriptor name, a minute or two apart at the same place.
    The plain-name row goes when a coded-name row of the same kind at the
    same address or the same coordinates was created within ten minutes of
    it (an intersection request has coordinates and no address on its coded
    row, and a street-only address on its plain one)."""
    from bisect import bisect_left

    coded: dict[str | None, list[tuple[datetime, Complaint]]] = {}
    for c in cs:
        if c.descriptor not in _NEW_NAMES and c.created_date:
            coded.setdefault(KIND.get(c.descriptor), []).append((datetime.fromisoformat(c.created_date), c))
    for rows in coded.values():
        rows.sort(key=lambda r: r[0])
    times = {kind: [t for t, _ in rows] for kind, rows in coded.items()}
    window = timedelta(minutes=10)

    def same_place(a: Complaint, b: Complaint) -> bool:
        if a.address and a.address == b.address:
            return True
        # Within 0.00001 degrees, about a metre: the two rows carry one geocode.
        return (None not in (a.lat, a.lon, b.lat, b.lon)
                and abs(a.lat - b.lat) < 1e-5 and abs(a.lon - b.lon) < 1e-5)

    def twin(c: Complaint) -> bool:
        kind = KIND.get(c.descriptor)
        if c.descriptor not in _NEW_NAMES or not c.created_date or kind not in coded:
            return False
        t = datetime.fromisoformat(c.created_date)
        # Only the coded rows of this kind within ten minutes are compared (a
        # district has thousands of rows; every pair was once compared).
        rows, i = coded[kind], bisect_left(times[kind], t - window)
        while i < len(rows) and rows[i][0] <= t + window:
            if same_place(c, rows[i][1]):
                return True
            i += 1
        return False

    return [c for c in cs if not twin(c)]


def _summarize(cs: list[Complaint], years: int, radius_m: float | None, limit: int | None = None,
               where: str | None = None, query_url: str | None = None) -> dict:
    # At the fetch limit the count is a floor; decide that before twins are dropped.
    capped = limit is not None and len(cs) >= limit
    cs = one_per_incident(cs)
    by_year: Counter = Counter(c.created_date[:4] for c in cs if c.created_date)
    by_descriptor: Counter = Counter(c.descriptor for c in cs)
    by_kind: Counter = Counter(KIND.get(c.descriptor, c.descriptor) for c in cs)
    # Cap at 60 most-recent points for the map layer — keeps the SSE
    # payload small while still showing meaningful clustering.
    points = [_point(c) for c in cs[:60] if c.lat is not None and c.lon is not None]
    n = len(cs)
    by_year_sorted = dict(sorted(by_year.items()))
    kinds = dict(by_kind.most_common())
    where = where or (f"within {radius_m:.0f} m of this location" if radius_m else "inside this area")
    # The source answered: 0 here is a true zero, and the sentence says so.
    # "About flooding and sewer backups", with what is left out: "flood and sewer complaints" named more than the
    # filter counts (BX02 had 285 complaints under 311's Sewer types where this counts 181).
    # The window is 365 days a year back from midnight UTC, so its first day is said.
    start = _since(years).date().isoformat()
    narrative = (f"{'At least ' if capped else ''}{n} NYC 311 complaint{'s' if n != 1 else ''} about flooding and sewer "
                 f"backups filed {where} in the last {years} years (since {start}; {SCOPE}")
    narrative += ("): " + ", ".join(f"{k} {kind}" for kind, k in kinds.items()) + "." if n
                  else "; the 311 service answered and none matched).")
    narrative += f" {CAVEAT}"
    return {
        "n": n,
        "capped": capped,
        "radius_m": radius_m,
        "where": where,
        "years": years,
        "since": start,
        "by_year": by_year_sorted,
        "by_descriptor": dict(by_descriptor.most_common()),
        "by_kind": kinds,
        # Each at its block with rounded coordinates, never a house number (see _point).
        "most_recent": [{k: v for k, v in _point(c).items() if k not in ("lat", "lon")} for c in cs[:5]],
        "points": points,
        **({"query_url": query_url} if query_url else {}),
        # Normalized rendering fields the type-keyed histogram renderer
        # reads. `histogram` is the array the chart draws; `headline_value`
        # is the bold figure; `subhead_text` is the descriptor caption.
        "headline_value": f"{n} complaint{'s' if n != 1 else ''}",
        "subhead_text": ", ".join(f"{k} {kind}" for kind, k in kinds.items()) or "no flood or sewer complaints",
        "narrative": narrative,
        "caveat": CAVEAT,
        "histogram": list(by_year_sorted.values()) or [],
    }


def days_sentence(lat: float, lon: float, radius_m: float, first: str, last: str, what: str) -> str:
    """The complaints filed near a point on the days asked about (`first`
    to `last`, ISO dates), as their own sentence: the same descriptors, the
    same one-per-incident rule and no house number. For a question about
    Hurricane Ida or a day older than the briefing's window, whose count
    does not reach back that far."""
    from datetime import date

    until = date.fromisoformat(last) + timedelta(days=1)
    cs = one_per_incident(_complaints_where(
        f"within_circle(location, {lat}, {lon}, {radius_m}) AND created_date < '{until.isoformat()}T00:00:00'",
        datetime.fromisoformat(first), 2000, timeout=30))
    n, kinds = len(cs), Counter(KIND.get(c.descriptor, c.descriptor) for c in cs)
    days = first if first == last else f"from {first} to {last}"
    out = (f"For {what}, which the briefing's 311 window does not reach: {n} NYC 311 complaint{'s' if n != 1 else ''} about flooding "
           f"and sewer backups {'were' if n != 1 else 'was'} filed within {radius_m:.0f} m of this location {days}")
    out += (": " + ", ".join(f"{k} {kind}" for kind, k in kinds.most_common()) if n else "; the 311 service answered and none matched")
    return f"{out}. A count of complaints is a count of reports filed, not of floods, and a low count can mean under-reporting."


def kind_named(question: str) -> str | None:
    """The complaint kind a question names ("street flooding", "sewer
    backup"), or None when it asks about flood complaints in general."""
    q = (question or "").lower()
    for kind in dict.fromkeys(KIND.values()):
        if kind in q or kind.replace("backup", "back-up") in q or kind.replace("basin", "basins") in q:
            return kind
    return None


_BORO_BY_PREFIX = {"MN": "MANHATTAN", "BX": "BRONX", "BK": "BROOKLYN", "QN": "QUEENS",
                   "SI": "STATEN ISLAND"}


def community_board(code: str) -> str | None:
    """'QN12' or 'qn 12' -> '12 QUEENS', the 311 dataset's community_board value."""
    m = re.fullmatch(r"\s*(MN|BX|BK|QN|SI)\s*0?(\d{1,2})\s*", code.upper())
    return f"{int(m.group(2)):02d} {_BORO_BY_PREFIX[m.group(1)]}" if m else None


def flood_requests(*, lat: float | None = None, lon: float | None = None,
                   radius_m: float = 200, community_district: str | None = None,
                   days: int = 365) -> dict:
    """Flood-related 311 requests near a point or inside a community
    district over the last `days`: counts by descriptor, kind and month and
    the ten most recent, by the same rule as a briefing (a request filed
    under both descriptor names counts once)."""
    since = datetime.now(UTC) - timedelta(days=days)
    if community_district:
        board = community_board(community_district)
        if board is None:
            return {"error": f"not a community district code like QN12: {community_district!r}"}
        where_place = f"community_board='{board}'"
        area = {"community_district": community_district.upper().replace(" ", ""),
                "community_board": board,
                "definition": f"requests whose community_board field is '{board}', the same field a "
                              "district briefing counts by"}
    elif lat is not None and lon is not None:
        where_place = f"within_circle(location, {lat}, {lon}, {radius_m})"
        area = {"lat": lat, "lon": lon, "radius_m": radius_m,
                "definition": f"requests geocoded within {radius_m:g} m of the point"}
    else:
        return {"error": "give lat and lon, or a community district"}
    fetched = _complaints_where(where_place, since, limit=50000)
    cs = one_per_incident(fetched)
    by_desc = Counter(c.descriptor for c in cs)
    by_month = Counter(c.created_date[:7] for c in cs)
    return {
        **area,
        "days": days,
        "n": len(cs),
        "capped": len(fetched) >= 50000,  # at the fetch limit `n` is a floor
        "by_descriptor": dict(by_desc.most_common()),
        "by_kind": dict(Counter(KIND.get(c.descriptor, c.descriptor) for c in cs).most_common()),
        "by_month": dict(sorted(by_month.items())),
        "most_recent": [{"date": c.created_date[:10], "descriptor": c.descriptor,
                         "block": c.block, "status": c.status} for c in cs[:10]],
        "query_url": query_url(where_place, since, 50000),
        "caveat": CAVEAT,
        "source": CITATION,
        "source_url": "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9",
    }
