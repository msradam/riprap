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

# The 311 descriptors that record flooding. This is the one definition the
# keys share with Riprap (app/context/nyc311.py); everything else is
# computed differently (server-side counts here, client-side rows there).
FLOOD_DESCRIPTORS = [
    "Street Flooding (SJ)",
    "Sewer Backup (Use Comments) (SA)",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)",
    "Highway Flooding (SH)",
    "Manhole Overflow (Use Comments) (SA1)",
    "Flooding on Street",
    "RAIN GARDEN FLOODING (SRGFLD)",
]
_DESC = "(" + " OR ".join(f"descriptor='{d}'" for d in FLOOD_DESCRIPTORS) + ")"


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


# NYC 311 (Socrata erm2-nwe9): counts grouped on the server, no row cap.
def nyc311(lat: float, lon: float, radius_m: int = 200, years: int = 5) -> dict:
    since = (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=365 * years)).replace(tzinfo=None).isoformat(timespec="seconds")
    where = f"{_DESC} AND within_circle(location, {lat}, {lon}, {radius_m}) AND created_date >= '{since}'"
    url = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
    by_desc = _get(url, {"$select": "descriptor, count(*) AS n", "$where": where, "$group": "descriptor"})
    by_year = _get(url, {"$select": "date_extract_y(created_date) AS y, count(*) AS n",
                         "$where": where, "$group": "y"})
    return {"n": sum(int(r["n"]) for r in by_desc),
            "by_descriptor": {r["descriptor"]: int(r["n"]) for r in by_desc},
            "by_year": {str(r["y"]): int(r["n"]) for r in by_year}}


def nyc311_district(community_board: str, years: int = 3) -> int:
    """Flood-related 311 requests filed in one community board ('12 QUEENS')."""
    since = (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=365 * years)).replace(tzinfo=None).isoformat(timespec="seconds")
    where = f"{_DESC} AND community_board='{community_board}' AND created_date >= '{since}'"
    rows = _get("https://data.cityofnewyork.us/resource/erm2-nwe9.json",
                {"$select": "count(*) AS n", "$where": where})
    return int(rows[0]["n"])


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
    good = {d["deployment_id"] for d in near if (d.get("sensor_status") or "").lower().startswith("good")}
    good_depths = [e["max_depth_proc_mm"] for e in events
                   if e["deployment_id"] in good and e.get("max_depth_proc_mm") is not None]
    return {"n_sensors": len(near), "n_events": len(events),
            "peak_mm_good": max(good_depths) if good_depths else None,
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


def _nfhl_point(layer: int, lat: float, lon: float, fields: str) -> dict | None:
    d = _get(f"{_NFHL}/{layer}/query", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": fields,
        "returnGeometry": "false", "f": "json"}, timeout=90)
    feats = d.get("features") or []
    return feats[0]["attributes"] if feats else None


def fema_nfhl(lat: float, lon: float) -> dict | None:
    zone = _nfhl_point(28, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF")
    panel = _nfhl_point(3, lat, lon, "FIRM_PAN,EFF_DATE")
    if not zone:
        return None
    eff = panel.get("EFF_DATE") if panel else None
    return {"zone": zone.get("FLD_ZONE"), "subtype": zone.get("ZONE_SUBTY"),
            "sfha": zone.get("SFHA_TF") == "T",
            "panel": panel.get("FIRM_PAN") if panel else None,
            "effective_year": datetime.fromtimestamp(eff / 1000, UTC).year if eff else None}


# The Sandy inundation zone (NYC Open Data uyj8-7rv5). The dataset's
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


# MTA subway entrances (data.ny.gov i9wp-a4ja), counted on the server.
def mta_entrances_within(lat: float, lon: float, radius_m: int = 800) -> int:
    rows = _get("https://data.ny.gov/resource/i9wp-a4ja.json", {
        "$select": "count(*) AS n",
        "$where": f"within_circle(entrance_georeference, {lat}, {lon}, {radius_m})"})
    return int(rows[0]["n"])


def all_keys(lat: float, lon: float) -> dict:
    """Every key for one point, in one dict."""
    return {
        "nyc311": nyc311(lat, lon),
        "floodnet": floodnet(lat, lon),
        "ida_hwm": ida_hwm(lat, lon),
        "fema_nfhl": fema_nfhl(lat, lon),
        "sandy_inside": sandy_inside(lat, lon),
        "dep": {s: dep_class(lat, lon, s) for s in DEP_FILES},
        "mta_entrances_800m": mta_entrances_within(lat, lon),
    }


if __name__ == "__main__":
    import sys

    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    print(json.dumps(all_keys(lat, lon), indent=1))
