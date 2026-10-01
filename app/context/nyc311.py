"""NYC 311 — flood-related complaints around a point.

Live dataset: erm2-nwe9. Filter by descriptor (the flood signal is in
descriptor, not complaint_type) within a buffer.
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
    return _summarize(cs, years=years, radius_m=radius_m, limit=2000)


def complaints_in_polygon(polygon, polygon_crs: str = "EPSG:4326",
                          since: datetime | None = None,
                          limit: int = 5000,
                          simplify_tolerance: float = 0.0005) -> list[Complaint]:
    """Pull flood-related complaints inside an arbitrary polygon via
    Socrata's `within_polygon(location, 'MULTIPOLYGON(...)')` predicate.

    NYC NTA polygons can have thousands of vertices and exceed Socrata's
    URL length limit (414). We simplify in EPSG:4326 with a default
    ~50 m tolerance, which collapses vertex count ~10-20× without
    materially changing the contained-points result.

    Polygon must be EPSG:4326 (lat/lon) for the Socrata query.
    """
    import geopandas as gpd
    g = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs("EPSG:4326")
    geom = g.iloc[0].geometry.simplify(simplify_tolerance, preserve_topology=True)
    return _complaints_where(f"within_polygon(location, '{geom.wkt}')", since, limit)


def complaints_in_board(board: str, since: datetime | None = None, limit: int = 5000) -> list[Complaint]:
    """Flood-related complaints whose `community_board` field is `board`
    ('12 QUEENS'): the record's own district, the official definition."""
    return _complaints_where(f"community_board='{board}'", since, limit)


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _complaints_where(clause: str, since: datetime | None, limit: int, timeout: int = 60) -> list[Complaint]:
    """Flood-related complaints matching `clause`, newest first, each with
    its coordinates (one_per_incident needs them for intersection requests)."""
    where = f"{_DESC_CLAUSE} AND {clause}"
    if since:
        # Socrata floating-timestamp: drop tz suffix
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = http.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, status, latitude, longitude",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=timeout)
    r.raise_for_status()
    return [
        Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
            lat=_num(row.get("latitude")), lon=_num(row.get("longitude")),
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
    cs = complaints_in_polygon(polygon, polygon_crs=polygon_crs, since=_since(years), limit=5000)
    return _summarize(cs, years=years, radius_m=None, limit=5000)


def summary_for_district(code: str, years: int = 3) -> dict:
    """Counts for a community district (QN12) by the record's
    `community_board` field, and the sentence says so."""
    board = community_board(code)
    if board is None:
        raise ValueError(f"not a community district code like QN12: {code!r}")
    # QN12 holds about 4,500 rows in three years; the limit leaves room.
    cs = complaints_in_board(board, since=_since(years), limit=20000)
    where = f"in Community District {code.upper().replace(' ', '')} (by the record's community board field)"
    return _summarize(cs, years=years, radius_m=None, limit=20000, where=where)


def one_per_incident(cs: list[Complaint]) -> list[Complaint]:
    """Drop a request filed under both names. During the storm of 29
    September 2023 and the days after, 311 logged many requests twice, once
    under each descriptor name, a minute or two apart at the same place.
    The plain-name row goes when a coded-name row of the same kind at the
    same address or the same coordinates was created within ten minutes of
    it (an intersection request has coordinates and no address on its coded
    row, and a street-only address on its plain one)."""
    coded: dict[str | None, list[tuple[datetime, Complaint]]] = {}
    for c in cs:
        if c.descriptor not in _NEW_NAMES and c.created_date:
            coded.setdefault(KIND.get(c.descriptor), []).append((datetime.fromisoformat(c.created_date), c))

    def same_place(a: Complaint, b: Complaint) -> bool:
        if a.address and a.address == b.address:
            return True
        # Within 0.00001 degrees, about a metre: the two rows carry one geocode.
        return (None not in (a.lat, a.lon, b.lat, b.lon)
                and abs(a.lat - b.lat) < 1e-5 and abs(a.lon - b.lon) < 1e-5)

    def twin(c: Complaint) -> bool:
        if c.descriptor not in _NEW_NAMES or not c.created_date:
            return False
        t = datetime.fromisoformat(c.created_date)
        return any(abs(t - u) <= timedelta(minutes=10) and same_place(c, other)
                   for u, other in coded.get(KIND.get(c.descriptor), ()))

    return [c for c in cs if not twin(c)]


def _summarize(cs: list[Complaint], years: int, radius_m: float | None, limit: int | None = None,
               where: str | None = None) -> dict:
    # At the fetch limit the count is a floor; decide that before twins are dropped.
    capped = limit is not None and len(cs) >= limit
    cs = one_per_incident(cs)
    by_year: Counter = Counter(c.created_date[:4] for c in cs if c.created_date)
    by_descriptor: Counter = Counter(c.descriptor for c in cs)
    by_kind: Counter = Counter(KIND.get(c.descriptor, c.descriptor) for c in cs)
    # Cap at 60 most-recent points for the map layer — keeps the SSE
    # payload small while still showing meaningful clustering.
    points = [
        {"lat": c.lat, "lon": c.lon,
         "descriptor": c.descriptor,
         "date": c.created_date[:10],
         "address": c.address}
        for c in cs[:60]
        if c.lat is not None and c.lon is not None
    ]
    n = len(cs)
    by_year_sorted = dict(sorted(by_year.items()))
    kinds = dict(by_kind.most_common())
    where = where or (f"within {radius_m:.0f} m of this location" if radius_m else "inside this area")
    # The source answered: 0 here is a true zero, and the sentence says so.
    narrative = (f"{'At least ' if capped else ''}{n} NYC 311 flood-related complaint{'s' if n != 1 else ''} filed {where} "
                 f"in the last {years} years")
    narrative += (": " + ", ".join(f"{k} {kind}" for kind, k in kinds.items()) + "." if n
                  else " (the 311 service answered and none matched).")
    return {
        "n": n,
        "capped": capped,
        "radius_m": radius_m,
        "where": where,
        "years": years,
        "by_year": by_year_sorted,
        "by_descriptor": dict(by_descriptor.most_common()),
        "by_kind": kinds,
        "most_recent": [
            {"date": c.created_date[:10],
             "descriptor": c.descriptor,
             "address": c.address}
            for c in cs[:5]
        ],
        "points": points,
        # Normalized rendering fields the type-keyed histogram renderer
        # reads. `histogram` is the array the chart draws; `headline_value`
        # is the bold figure; `subhead_text` is the descriptor caption.
        "headline_value": f"{n} complaint{'s' if n != 1 else ''}",
        "subhead_text": ", ".join(f"{k} {kind}" for kind, k in kinds.items()) or "no flood-related complaints",
        "narrative": narrative,
        "histogram": list(by_year_sorted.values()) or [],
    }


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
                         "address": c.address, "status": c.status} for c in cs[:10]],
        "source": CITATION,
        "source_url": "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9",
    }
