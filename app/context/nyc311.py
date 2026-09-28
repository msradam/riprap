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
CITATION = "NYC 311 service requests (Socrata erm2-nwe9, 2010-present)"

FLOOD_DESCRIPTORS = [
    "Street Flooding (SJ)",
    "Sewer Backup (Use Comments) (SA)",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)",
    "Highway Flooding (SH)",
    "Manhole Overflow (Use Comments) (SA1)",
    "Flooding on Street",
    "RAIN GARDEN FLOODING (SRGFLD)",
]

_DESC_CLAUSE = "(" + " OR ".join(f"descriptor='{d}'" for d in FLOOD_DESCRIPTORS) + ")"

# The kind of complaint each descriptor records, in the words a question
# uses ("street flooding"). Two descriptors record street flooding.
KIND = {
    "Street Flooding (SJ)": "street flooding",
    "Flooding on Street": "street flooding",
    "Sewer Backup (Use Comments) (SA)": "sewer backup",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)": "catch basin",
    "Highway Flooding (SH)": "highway flooding",
    "Manhole Overflow (Use Comments) (SA1)": "manhole overflow",
    "RAIN GARDEN FLOODING (SRGFLD)": "rain garden flooding",
}


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
    where = f"{_DESC_CLAUSE} AND within_circle(location, {lat}, {lon}, {radius_m})"
    if since:
        # Socrata floating-timestamp: drop tz suffix
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = http.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, "
                   "status, latitude, longitude",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=30)
    r.raise_for_status()
    out = []
    for row in r.json():
        lat = row.get("latitude")
        lon = row.get("longitude")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except Exception:
            lat, lon = None, None
        out.append(Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
            lat=lat, lon=lon,
        ))
    return out


def summary_for_point(lat: float, lon: float, radius_m: float = 200,
                      years: int = 5) -> dict:
    since = datetime.now(UTC) - timedelta(days=365 * years)
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
    wkt = geom.wkt
    where = f"{_DESC_CLAUSE} AND within_polygon(location, '{wkt}')"
    if since:
        ts = since.replace(tzinfo=None).isoformat(timespec="seconds")
        where += f" AND created_date >= '{ts}'"
    r = http.get(URL, params={
        "$select": "unique_key, descriptor, created_date, incident_address, status",
        "$where": where,
        "$order": "created_date desc",
        "$limit": str(limit),
    }, timeout=60)
    r.raise_for_status()
    return [
        Complaint(
            unique_key=row.get("unique_key", ""),
            descriptor=row.get("descriptor", ""),
            created_date=row.get("created_date", ""),
            address=row.get("incident_address"),
            status=row.get("status"),
        )
        for row in r.json()
    ]


def summary_for_polygon(polygon, polygon_crs: str = "EPSG:4326",
                        years: int = 5) -> dict:
    """Polygon-mode aggregation: counts of flood-related 311 complaints
    inside the polygon over the trailing window."""
    since = datetime.now(UTC) - timedelta(days=365 * years)
    cs = complaints_in_polygon(polygon, polygon_crs=polygon_crs, since=since, limit=5000)
    return _summarize(cs, years=years, radius_m=None, limit=5000)


def _summarize(cs: list[Complaint], years: int, radius_m: float | None, limit: int | None = None) -> dict:
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
    where = f"within {radius_m:.0f} m of this location" if radius_m else "inside this area"
    # The source answered: 0 here is a true zero, and the sentence says so.
    # At the fetch limit the count is a floor, not the total.
    capped = limit is not None and n >= limit
    narrative = (f"{'At least ' if capped else ''}{n} NYC 311 flood-related complaint{'s' if n != 1 else ''} filed {where} "
                 f"in the last {years} years")
    narrative += (": " + ", ".join(f"{k} {kind}" for kind, k in kinds.items()) + "." if n
                  else " (the 311 service answered and none matched).")
    return {
        "n": n,
        "capped": capped,
        "radius_m": radius_m,
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
        "headline_value": f"{n} call{'s' if n != 1 else ''}",
        "subhead_text": ", ".join(f"{k} {kind}" for kind, k in kinds.items()) or "no flood-related calls",
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
    district over the last `days`: exact counts by descriptor and by month
    (grouped server-side, so no row cap) and the ten most recent."""
    since = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None)
    where = f"{_DESC_CLAUSE} AND created_date >= '{since.isoformat(timespec='seconds')}'"
    if community_district:
        board = community_board(community_district)
        if board is None:
            return {"error": f"not a community district code like QN12: {community_district!r}"}
        where += f" AND community_board = '{board}'"
        area = {"community_district": community_district.upper().replace(" ", ""),
                "community_board": board}
    elif lat is not None and lon is not None:
        where += f" AND within_circle(location, {lat}, {lon}, {radius_m})"
        area = {"lat": lat, "lon": lon, "radius_m": radius_m}
    else:
        return {"error": "give lat and lon, or a community district"}
    def query(**params) -> list:
        r = http.get(URL, params={"$where": where, **params}, timeout=60)
        r.raise_for_status()
        return r.json()

    by_desc = query(**{"$select": "descriptor, count(*) AS n", "$group": "descriptor",
                       "$order": "n DESC"})
    by_month = query(**{"$select": "date_trunc_ym(created_date) AS month, count(*) AS n",
                        "$group": "month", "$order": "month"})
    recent = query(**{"$select": "descriptor, created_date, incident_address, status",
                      "$order": "created_date DESC", "$limit": "10"})
    return {
        **area,
        "days": days,
        "n": sum(int(row["n"]) for row in by_desc),
        "by_descriptor": {row.get("descriptor"): int(row["n"]) for row in by_desc},
        "by_kind": dict(sum((Counter({KIND.get(row.get("descriptor"), row.get("descriptor")): int(row["n"])})
                             for row in by_desc), Counter()).most_common()),
        "by_month": {row["month"][:7]: int(row["n"]) for row in by_month},
        "most_recent": [{"date": (row.get("created_date") or "")[:10],
                         "descriptor": row.get("descriptor"),
                         "address": row.get("incident_address"),
                         "status": row.get("status")} for row in recent],
        "source": CITATION,
        "source_url": "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
    }
