"""Independent answer keys for the golden set.

Each function reads one public dataset directly: Socrata (311, MTA
entrances), the FloodNet GraphQL API, the USGS STN web service, FEMA's
NFHL ArcGIS REST service and NYC GeoSearch over HTTP with urllib, and the
two file datasets (the Sandy inundation zone exported from NYC Open Data,
the DEP stormwater geodatabases as NYC DEP publishes them) with geopandas.
Nothing here imports riprap or app: this is a second opinion, written to
be short and obvious rather than fast.
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "Mozilla/5.0 (compatible; Riprap golden keys; +https://github.com/msradam/riprap)"

# Which 311 requests record flooding: a pattern over the two sewer complaint
# types, read from the live descriptor column, not a list. Until 2026-10-01
# this was a list shared with app/context/nyc311.py; NYC renamed the
# descriptors that July and the shared list hid the app's undercount.
_FLOOD = ("(complaint_type='Sewer' OR complaint_type='Sewer Maintenance') AND ("
          "upper(descriptor) like '%FLOOD%' OR upper(descriptor) like '%BACKUP%' OR "
          "upper(descriptor) like '%CATCH BASIN CLOGGED%' OR upper(descriptor) like '%MANHOLE OVERFLOW%')")
# "Catch Basin Clogged/Flooding" is a catch basin row: that word is looked for before FLOOD.
_KIND_WORDS = ("HIGHWAY", "RAIN GARDEN", "CATCH BASIN", "BACKUP", "MANHOLE", "FLOOD")


def _kind(descriptor: str) -> str:
    d = descriptor.upper()
    return next(w for w in _KIND_WORDS if w in d)


def _once(rows: list[dict]) -> list[dict]:
    """A request logged under both descriptor names counts once: the
    plain-name row ("Backup") is dropped when a coded-name row ("Sewer
    Backup (Use Comments) (SA)") of the same kind at the same address or at
    the same coordinates (an intersection has no address on its coded row)
    was created within ten minutes of it. Written apart from the app's rule."""
    def secs(r):
        return datetime.fromisoformat(r["created_date"]).timestamp()

    def same_place(a, b):
        if a.get("incident_address") and a.get("incident_address") == b.get("incident_address"):
            return True
        return bool(a.get("latitude")) and all(
            abs(float(a[k]) - float(b[k])) < 1e-5 for k in ("latitude", "longitude") if b.get(k)) and bool(b.get("latitude"))

    coded = [r for r in rows if "(" in r["descriptor"]]
    keep = []
    for r in rows:
        if "(" not in r["descriptor"] and any(
                same_place(c, r) and _kind(c["descriptor"]) == _kind(r["descriptor"])
                and abs(secs(c) - secs(r)) <= 600 for c in coded):
            continue
        keep.append(r)
    return keep


def _flood_rows(where: str, years: int) -> list[dict]:
    since = (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=365 * years)).replace(tzinfo=None).isoformat(timespec="seconds")
    rows = _get("https://data.cityofnewyork.us/resource/erm2-nwe9.json",
                {"$select": "descriptor, created_date, incident_address, latitude, longitude",
                 "$where": f"{_FLOOD} AND {where} AND created_date >= '{since}'", "$limit": 50000})
    return _once(rows)


def _get(url: str, params: dict | None = None, timeout: int = 60):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(6):  # FEMA's firewall resets some connections at random
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, ConnectionResetError, TimeoutError):
            if attempt == 5:
                raise
            time.sleep(3 * 2 ** attempt)


def _post_json(url: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


# NYC GeoSearch (NYC Department of City Planning), the city's own geocoder.
def geocode(address: str) -> dict | None:
    d = _get("https://geosearch.planninglabs.nyc/v2/search", {"text": address, "size": 1})
    feats = d.get("features") or []
    if not feats:
        return None
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    return {"lat": lat, "lon": lon, "label": f["properties"].get("label"),
            "match_type": f["properties"].get("match_type"),
            "accuracy": f["properties"].get("accuracy")}


# NYC 311 (Socrata erm2-nwe9): every matching row, no cap in practice.
def nyc311(lat: float, lon: float, radius_m: int = 200, years: int = 5) -> dict:
    rows = _flood_rows(f"within_circle(location, {lat}, {lon}, {radius_m})", years)
    by_desc: dict[str, int] = {}
    by_year: dict[str, int] = {}
    for r in rows:
        by_desc[r["descriptor"]] = by_desc.get(r["descriptor"], 0) + 1
        by_year[r["created_date"][:4]] = by_year.get(r["created_date"][:4], 0) + 1
    return {"n": len(rows), "by_descriptor": by_desc, "by_year": by_year}


def nyc311_district(community_board: str, years: int = 3) -> int:
    """Flood-related 311 requests filed in one community board ('12 QUEENS')."""
    return len(_flood_rows(f"community_board='{community_board}'", years))


# FloodNet (Hasura GraphQL): every deployment, filtered here by distance.
_FLOODNET = "https://api.floodnet.nyc/v1/graphql"


@lru_cache(maxsize=1)
def _floodnet_deployments() -> list[dict]:
    q = "{ deployments(limit: 5000) { deployment_id sensor_status location } }"
    return _post_json(_FLOODNET, {"query": q})["data"]["deployments"]


def floodnet(lat: float, lon: float, radius_m: int = 600, years: int = 3) -> dict:
    near = []
    for d in _floodnet_deployments():
        loc = d.get("location") or {}
        coords = loc.get("coordinates") or []
        if len(coords) == 2 and haversine_m(lat, lon, coords[1], coords[0]) <= radius_m:
            near.append(d)
    ids = [d["deployment_id"] for d in near]
    since = (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=365 * years)).replace(tzinfo=None).isoformat(timespec="seconds")
    events: list[dict] = []
    if ids:
        q = ("query($ids:[String!],$since:timestamp!){ sensor_events(where:{deployment_id:{_in:$ids},"
             "start_time:{_gte:$since},label:{_eq:\"flood\"}}, limit: 10000)"
             "{ deployment_id start_time max_depth_proc_mm } }")
        events = _post_json(_FLOODNET, {"query": q, "variables": {"ids": ids, "since": since}})["data"]["sensor_events"]
        # The table holds events stamped 2080 (a sensor clock fault): none of those is in "the last 3 years".
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        events = [e for e in events if e["start_time"] <= now]
    good = {d["deployment_id"] for d in near if (d.get("sensor_status") or "").lower().startswith("good")}
    good_depths = [e["max_depth_proc_mm"] for e in events
                   if e["deployment_id"] in good and e.get("max_depth_proc_mm") is not None]
    flagged_depths = [e["max_depth_proc_mm"] for e in events
                      if e["deployment_id"] not in good and e.get("max_depth_proc_mm") is not None]
    return {"n_sensors": len(near), "n_events": len(events),
            "peak_mm_good": max(good_depths) if good_depths else None,
            "peak_mm_flagged": max(flagged_depths) if flagged_depths else None,
            "statuses": sorted(d.get("sensor_status") or "" for d in near)}


# USGS STN high-water marks for Hurricane Ida (event 312), read live.
@lru_cache(maxsize=1)
def _ida_marks() -> list[dict]:
    return _get("https://stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json?Event=312&States=NY", timeout=120)


def ida_hwm(lat: float, lon: float, radius_m: int = 800) -> dict:
    marks = []
    for m in _ida_marks():
        if m.get("latitude") is None or m.get("longitude") is None:
            continue
        d = haversine_m(lat, lon, m["latitude"], m["longitude"])
        marks.append((d, m))
    marks.sort(key=lambda t: t[0])
    within = [m for d, m in marks if d <= radius_m]
    above = [m["height_above_gnd"] for m in within if m.get("height_above_gnd") is not None]
    elev = [m["elev_ft"] for m in within if m.get("elev_ft") is not None]
    return {"n": len(within),
            "max_height_above_gnd_ft": max(above) if above else None,
            "max_elev_ft": max(elev) if elev else None,
            "nearest_m": round(marks[0][0]) if marks else None,
            "nearest_site": marks[0][1].get("siteDescription") if marks else None,
            "n_total": len(marks)}


# FEMA NFHL ArcGIS REST: the flood zone polygon and the FIRM panel at the point.
_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"


def _nfhl_query(layer: int, lat: float, lon: float, fields: str, base: str = _NFHL) -> list[dict]:
    d = _get(f"{base}/{layer}/query", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": fields,
        "returnGeometry": "false", "f": "json"}, timeout=90)
    return [f["attributes"] for f in d.get("features") or []]


def _nfhl_point(layer: int, lat: float, lon: float, fields: str, base: str = _NFHL) -> dict | None:
    feats = _nfhl_query(layer, lat, lon, fields, base)
    return feats[0] if feats else None


def fema_nfhl(lat: float, lon: float) -> dict | None:
    zone = _nfhl_point(28, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF,DFIRM_ID")
    if not zone:
        return None
    # Panel polygons overlap along the water: at Staten Island's shore two
    # New Jersey countywide panels cover the point as well as NYC's. The
    # panel is the one from the study the zone belongs to (DFIRM_ID).
    panels = _nfhl_query(3, lat, lon, "FIRM_PAN,EFF_DATE,DFIRM_ID")
    panel = next((p for p in panels if p.get("DFIRM_ID") == zone.get("DFIRM_ID")), panels[0] if panels else None)
    eff = panel.get("EFF_DATE") if panel else None
    return {"zone": zone.get("FLD_ZONE"), "subtype": zone.get("ZONE_SUBTY"),
            "sfha": zone.get("SFHA_TF") == "T",
            "panel": panel.get("FIRM_PAN") if panel else None,
            "effective_year": datetime.fromtimestamp(eff / 1000, UTC).year if eff else None}


# FEMA's preliminary NFHL: the same layers one service over, plus the
# availability layer that carries the preliminary study's issue date.
_PRELIM = "https://hazards.fema.gov/arcgis/rest/services/PrelimPending/Prelim_NFHL/MapServer"


def fema_pfirm(lat: float, lon: float) -> dict | None:
    zone = _nfhl_point(28, lat, lon, "FLD_ZONE,SFHA_TF,STATIC_BFE", base=_PRELIM)
    study = _nfhl_point(0, lat, lon, "DFIRM_ID,PRELM_ISSUE_DATE", base=_PRELIM)
    if not zone or not study:
        return None
    issued = study.get("PRELM_ISSUE_DATE")
    bfe = zone.get("STATIC_BFE")
    return {"zone": zone.get("FLD_ZONE"), "sfha": zone.get("SFHA_TF") == "T",
            "bfe_ft": float(bfe) if bfe is not None and bfe > -9000 else None,
            "issue_date": datetime.fromtimestamp(issued / 1000, UTC).date().isoformat() if issued else None}


# The Sandy inundation zone (NYC Open Data 5xsi-dfpx; uyj8-7rv5 is its map view). The dataset's
# export endpoint returned an empty feature collection on 2026-09-30, so
# the key reads the public file as downloaded on 2026-07-11 and checks the
# point against the polygons themselves, not Riprap's rasterised copy.
@lru_cache(maxsize=1)
def _sandy():
    import geopandas as gpd

    return gpd.read_file(ROOT / "data" / "sandy_inundation.geojson").to_crs("EPSG:4326")


def sandy_inside(lat: float, lon: float) -> bool:
    from shapely.geometry import Point

    g = _sandy()
    hits = g.sindex.query(Point(lon, lat), predicate="within")
    return len(hits) > 0


@lru_cache(maxsize=1)
def _sandy_edge():
    return _sandy().to_crs("EPSG:2263").geometry.boundary.union_all()


def sandy_edge_m(lat: float, lon: float) -> float:
    """Metres from the point to the nearest mapped edge of the Sandy zone,
    measured on the published polygons (the app measures on its raster)."""
    import geopandas as gpd
    from shapely.geometry import Point

    p = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263").iloc[0]
    return round(p.distance(_sandy_edge()) * 0.3048, 1)


# NYC DEP stormwater flood maps: the geodatabases as DEP publishes them.
DEP_FILES = {
    "dep_extreme_2080": "dep_extreme_2080.gdb",
    "dep_moderate_2050": "dep_moderate_2050.gdb",
    "dep_moderate_current": "dep_moderate_current.gdb",
}


@lru_cache(maxsize=3)
def _dep(scenario: str):
    import geopandas as gpd

    return gpd.read_file(ROOT / "data" / "dep" / DEP_FILES[scenario])


def dep_class(lat: float, lon: float, scenario: str) -> int:
    """0 outside, 1 nuisance, 2 deep and contiguous, 3 future high tide."""
    import geopandas as gpd
    from shapely.geometry import Point

    g = _dep(scenario)
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(g.crs).iloc[0]
    hits = g.iloc[g.sindex.query(pt, predicate="within")]
    return int(hits["Flooding_Category"].max()) if len(hits) else 0


# MTA subway entrances (data.ny.gov i9wp-a4ja), every entrance read live
# and filtered by distance here, on the same sphere as the FloodNet and
# Ida keys. Socrata's within_circle measures about 0.3% longer at NYC, so
# an entrance 797 m out by haversine falls outside its 800 m circle; the
# count at 200 Water Street is 116 one way and 114 the other.
@lru_cache(maxsize=1)
def _mta_entrances() -> list[tuple[float, float]]:
    rows = _get("https://data.ny.gov/resource/i9wp-a4ja.json",
                {"$select": "entrance_latitude, entrance_longitude", "$limit": 10000})
    return [(float(r["entrance_latitude"]), float(r["entrance_longitude"])) for r in rows
            if r.get("entrance_latitude") and r.get("entrance_longitude")]


def mta_entrances_within(lat: float, lon: float, radius_m: int = 800) -> int:
    return sum(1 for la, lo in _mta_entrances() if haversine_m(lat, lon, la, lo) <= radius_m)


def all_keys(lat: float, lon: float) -> dict:
    """Every key for one point, in one dict."""
    return {
        "nyc311": nyc311(lat, lon),
        "floodnet": floodnet(lat, lon),
        "ida_hwm": ida_hwm(lat, lon),
        "fema_nfhl": fema_nfhl(lat, lon),
        "fema_pfirm": fema_pfirm(lat, lon),
        "sandy_inside": sandy_inside(lat, lon),
        "sandy_edge_m": sandy_edge_m(lat, lon),
        "dep": {s: dep_class(lat, lon, s) for s in DEP_FILES},
        "mta_entrances_800m": mta_entrances_within(lat, lon),
    }


if __name__ == "__main__":
    import sys

    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    print(json.dumps(all_keys(lat, lon), indent=1))
