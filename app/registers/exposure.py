"""Nearest assets of one class around a point, with their flood exposure.

The four asset classes in CLASSES share one shape: the assets within a
radius, each with its 2012 Sandy and DEP stormwater exposure, ground
elevation and HAND, then a count rollup, the register sentence that
answer_checks._register_counts parses, and a citation. The table holds
what differs, and the per-class modules (mta_entrances, doh_hospitals,
doe_schools, nycha) are thin wrappers the manifests call.

Two sources. DOE schools and NYCHA read a baked register under
data/registers/ that lists exposed assets only, with the flags computed
by scripts/build_register.py, so every row in range counts and the
nearest max_n are listed. MTA entrances and hospitals read the full
GeoJSON layer and look exposure up per hit, so every asset in range
counts and exposure is checked for the nearest max_n only. A layer or
register that cannot be read raises and the step is reported as failed:
none in range is a true zero, never a failure printed as one.
"""
from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.flood_layers import dep_stormwater, sandy_inundation
from app.flood_layers.dep_stormwater import class_label
from app.registers._footprint import (
    BUFFER_DOE_SCHOOL_M,
    BUFFER_DOH_HOSPITAL_M,
    BUFFER_MTA_ENTRANCE_M,
    dep_class_buffered,
    inside_sandy_buffered,
)
from app.registers._loader import load_register, narrative, nearest_n

log = logging.getLogger("riprap.registers")

DATA = Path(__file__).resolve().parents[2] / "data"
SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050")
ADA_ACCESSIBLE_TYPES = {"Elevator", "Ramp"}
COUNTY_TO_BOROUGH = {
    "New York": "MANHATTAN", "Kings": "BROOKLYN", "Bronx": "BRONX",
    "Queens": "QUEENS", "Richmond": "STATEN ISLAND",
}


@dataclass(frozen=True)
class Spec:
    singular: str             # noun for the register sentence
    plural: str
    radius_m: int
    max_n: int
    count_key: str
    list_key: str
    citation: str
    # The row's identity fields, coordinates and distance, in output order.
    head: Callable[[dict, float, float, float], dict]
    name: Callable[[dict], str] = lambda f: ""  # what the sentence calls one asset
    register: str | None = None   # baked register name under data/registers/
    geojson: Path | None = None   # live layer; exposure is looked up per hit
    lat_lon: Callable[[dict], tuple[float, float]] = (
        lambda f: (f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]))
    buffer_m: int | None = None   # reported; the buffered join also buffers the point by it
    raster: bool = False          # live exposure from the baked rasters, not the buffered GDB join
    scope: str = ""               # what an exposed-only register counted
    missing_class: int | None = None  # DEP class when the register has none for a scenario
    scenarios: tuple[str, ...] = SCENARIOS
    elev_key: str = "elevation_m"
    hand_key: str = "hand_m"
    rollups: dict[str, str] = field(default_factory=dict)  # extra count key: finding flag


def _entrance(r: dict, lat: float, lon: float, distance_m: float) -> dict:
    return {"station_id": str(r["station_id"]), "station_name": str(r["stop_name"]),
            "daytime_routes": str(r["daytime_routes"]), "borough": str(r["borough"]),
            "entrance_type": str(r["entrance_type"]), "entrance_lat": lat, "entrance_lon": lon,
            "distance_m": distance_m,
            "ada_accessible": str(r["entrance_type"]) in ADA_ACCESSIBLE_TYPES}


def _hospital(r: dict, lat: float, lon: float, distance_m: float) -> dict:
    return {"fac_id": str(r["fac_id"]), "facility_name": str(r["facility_name"]),
            "address": f"{r['address1']}, {r['city']}".strip(", "),
            "borough": COUNTY_TO_BOROUGH.get(str(r["county"]), str(r["county"])),
            "operator_name": str(r["operator_name"]), "ownership_type": str(r["ownership_type"]),
            "hospital_lat": round(lat, 5), "hospital_lon": round(lon, 5), "distance_m": distance_m}


def _school(r: dict, lat: float, lon: float, distance_m: float) -> dict:
    return {"loc_code": str(r.get("loc_code", "")), "loc_name": str(r.get("name", "")),
            "address": str(r.get("address", "")).strip(), "borough": str(r.get("borough", "")),
            "bin": str(r.get("bin", "")), "bbl": str(r.get("bbl", "")), "managed_by": "DOE-managed",
            "school_lat": round(lat, 5), "school_lon": round(lon, 5), "distance_m": distance_m}


def _development(r: dict, lat: float, lon: float, distance_m: float) -> dict:
    return {"development": str(r.get("name", "")), "tds_num": str(r.get("tds_num", "")),
            "borough": str(r.get("borough", "")), "centroid_lat": round(lat, 5),
            "centroid_lon": round(lon, 5), "distance_m": distance_m}


def _mta_lat_lon(f: dict) -> tuple[float, float]:
    p = f["properties"]  # the coordinates are strings in this GeoJSON
    return float(p["entrance_latitude"]), float(p["entrance_longitude"])


CLASSES: dict[str, Spec] = {
    "mta_entrances": Spec(
        singular="MTA subway entrance", plural="MTA subway entrances", radius_m=800, max_n=8,
        count_key="n_entrances", list_key="entrances",
        citation="MTA Open Data subway entrances + NYC Sandy 2012 Inundation Zone (5xsi-dfpx) + "
                 "NYC DEP Stormwater Flood Maps + USGS 3DEP DEM",
        head=_entrance, name=lambda f: f"{f['station_name']} ({f['daytime_routes']})",
        geojson=DATA / "mta_entrances.geojson", lat_lon=_mta_lat_lon,
        buffer_m=BUFFER_MTA_ENTRANCE_M, rollups={"n_ada_accessible": "ada_accessible"}),
    "doh_hospitals": Spec(
        singular="hospital", plural="hospitals", radius_m=3000, max_n=5,
        count_key="n_hospitals", list_key="hospitals",
        citation="NYS DOH Health Facility Certification (vn5v-hh5r) + NYC Sandy 2012 Inundation "
                 "Zone (5xsi-dfpx) + NYC DEP Stormwater Flood Maps + USGS 3DEP DEM",
        head=_hospital, name=lambda f: f["facility_name"],
        geojson=DATA / "hospitals.geojson", buffer_m=BUFFER_DOH_HOSPITAL_M, raster=True),
    "doe_schools": Spec(
        singular="flood-exposed NYC DOE school", plural="flood-exposed NYC DOE schools", radius_m=1500, max_n=6,
        count_key="n_schools", list_key="schools",
        citation="Pre-computed from NYC DOE Locations Points joined to Sandy 2012 Inundation Zone (5xsi-dfpx) + "
                 "NYC DEP Stormwater Flood Maps + USGS 3DEP DEM. See data/registers/schools.json.",
        head=_school, name=lambda f: f["loc_name"], register="schools", buffer_m=BUFFER_DOE_SCHOOL_M,
        scope=" (the register lists only schools found inside the 2012 Sandy extent or a DEP "
              "stormwater scenario, not every school)"),
    "nycha": Spec(
        singular="flood-exposed NYCHA development", plural="flood-exposed NYCHA developments", radius_m=2000, max_n=5,
        count_key="n_developments", list_key="developments",
        citation="Pre-computed from NYC Open Data NYCHA Developments (phvi-damg) joined to Sandy 2012 "
                 "Inundation Zone (5xsi-dfpx) + NYC DEP Stormwater Flood Maps + USGS 3DEP DEM. "
                 "See data/registers/nycha.json.",
        head=_development, name=lambda f: f["development"], register="nycha", missing_class=0,
        scenarios=SCENARIOS + ("dep_moderate_current",),
        elev_key="rep_elevation_m", hand_key="rep_hand_m",
        scope=" (the register lists only developments found inside the 2012 Sandy extent or a DEP "
              "stormwater scenario, not every development)"),
}


@lru_cache(maxsize=4)
def geojson_rows(asset_class: str) -> list[dict]:
    """The live layer's feature properties with lat and lon lifted out.
    A feature without usable coordinates is skipped."""
    spec = CLASSES[asset_class]
    with open(spec.geojson) as f:
        feats = json.load(f)["features"]
    rows = []
    for feat in feats:
        try:
            lat, lon = spec.lat_lon(feat)
        except (KeyError, TypeError, ValueError):
            continue
        rows.append({**feat["properties"], "lat": lat, "lon": lon})
    return rows


def _rows(asset_class: str, spec: Spec) -> list[dict]:
    return load_register(spec.register) if spec.register else geojson_rows(asset_class)


def _sample_raster(raster_path: Path, lat: float, lon: float) -> float | None:
    """One pixel of an EPSG:4326 raster at (lat, lon); None outside it,
    at nodata, or when the raster is missing or unreadable."""
    if not raster_path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            v = float(next(src.sample([(lon, lat)]))[0])
            return None if math.isnan(v) or v == src.nodata else v
    except Exception:
        log.exception("raster sample failed for %s", raster_path)
        return None


def _exposure(spec: Spec, lat: float, lon: float) -> tuple[bool, dict[str, int]]:
    """Sandy flag and DEP class per scenario for one live asset. A failed
    join raises: counting the asset as outside would print a failure as
    a zero."""
    if spec.raster:
        import geopandas as gpd
        from shapely.geometry import Point
        pt = (gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
              .to_crs("EPSG:2263").iloc[0].geometry)
        return (sandy_inundation.inside_raster(pt),
                {s: dep_stormwater.join_raster(pt, s) for s in spec.scenarios})
    return (inside_sandy_buffered(lat, lon, spec.buffer_m),
            {s: dep_class_buffered(lat, lon, spec.buffer_m, s)[0] for s in spec.scenarios})


def _finding(spec: Spec, distance_m: float | None, row: dict) -> dict:
    lat, lon = float(row["lat"]), float(row["lon"])
    f = spec.head(row, lat, lon, None if distance_m is None else round(distance_m, 1))
    if spec.register:
        snap = row.get("snap") or {}
        dep = snap.get("dep") or {}
        micro = snap.get("microtopo") or {}
        elev, hand = micro.get("point_elev_m"), micro.get("aoi_hand_m") or micro.get("hand_m")
        sandy = bool(snap.get("sandy"))
        classes = {}
        for scen in spec.scenarios:
            c = (dep.get(scen) or {}).get("depth_class")
            classes[scen] = spec.missing_class if c is None else int(c)
    else:
        elev = _sample_raster(DATA / "nyc_dem_30m.tif", lat, lon)
        hand = _sample_raster(DATA / "hand.tif", lat, lon)
        sandy, classes = _exposure(spec, lat, lon)
    f[spec.elev_key] = round(float(elev), 2) if elev is not None else None
    f[spec.hand_key] = round(float(hand), 2) if hand is not None else None
    f["inside_sandy_2012"] = sandy
    for scen in spec.scenarios:
        c = classes[scen]
        f[f"{scen}_class"] = c
        f[f"{scen}_label"] = None if c is None else class_label(c, scen)
    return f


def _named(spec: Spec, findings: list[dict], limit: int = 6) -> str:
    """The exposed assets by name, nearest first: a question that asks
    which schools gets the schools, not only how many."""
    out = ""
    for label, hit in (("Inside the 2012 Sandy extent", lambda f: f["inside_sandy_2012"]),
                       ("Inside the DEP extreme scenario", lambda f: (f["dep_extreme_2080_class"] or 0) > 0)):
        nearest: dict[str, float | None] = {}  # one station has several entrances: its nearest one
        for f in findings:
            if hit(f) and spec.name(f) not in nearest:
                nearest[spec.name(f)] = f.get("distance_m")
        names = [n if d is None else f"{n} ({d:.0f} m)" for n, d in nearest.items()]
        if names:
            more = f", and {len(names) - limit} more" if len(names) > limit else ""
            out += f". {label}: {', '.join(names[:limit])}{more}"
    return out


def summary_for_polygon(polygon, asset_class: str) -> dict:
    """The assets of `asset_class` inside a WGS84 polygon (a neighbourhood,
    or the outline drawn for a community district), with their exposure.
    Schools and NYCHA come from the baked registers, which list exposed
    assets only; subway entrances and hospitals are every asset in the
    polygon, each checked against the baked rasters at its own point."""
    from dataclasses import replace

    from shapely.geometry import Point
    from shapely.prepared import prep

    spec = CLASSES[asset_class]
    inside = prep(polygon)
    rows = [r for r in _rows(asset_class, spec)
            if r.get("lat") is not None and inside.contains(Point(float(r["lon"]), float(r["lat"])))]
    at_point = spec if spec.register else replace(spec, raster=True)
    findings = sorted((_finding(at_point, None, r) for r in rows), key=spec.name)
    n_sandy = sum(1 for f in findings if f["inside_sandy_2012"])
    n_dep = sum(1 for f in findings if (f["dep_extreme_2080_class"] or 0) > 0)
    n = len(findings)
    return {"available": True, spec.count_key: n, "n_inside_sandy_2012": n_sandy, "n_in_dep_extreme_2080": n_dep,
            "narrative": (f"{n} {spec.singular if n == 1 else spec.plural} in this area{spec.scope}: {n_sandy} inside "
                          f"the 2012 Sandy inundation extent and {n_dep} inside the DEP extreme stormwater "
                          f"scenario (2080 sea-level rise)" + _named(spec, findings)),
            spec.list_key: findings, "citation": spec.citation}


def summary_for_point(lat: float, lon: float, asset_class: str,
                      radius_m: float | None = None, max_n: int | None = None) -> dict:
    """The assets of `asset_class` within radius_m of (lat, lon), nearest
    first, with exposure per asset and the counts the sentence states."""
    spec = CLASSES[asset_class]
    radius_m = spec.radius_m if radius_m is None else radius_m
    max_n = spec.max_n if max_n is None else max_n
    hits = nearest_n(_rows(asset_class, spec), lat, lon, radius_m, None)
    live = spec.register is None
    findings = [_finding(spec, d, r) for d, r in (hits[:max_n] if live else hits)]
    n_sandy = sum(1 for f in findings if f["inside_sandy_2012"])
    n_dep = sum(1 for f in findings if (f["dep_extreme_2080_class"] or 0) > 0)
    out: dict = {"available": True, spec.count_key: len(hits)}
    if live:
        out["n_checked"] = len(findings)
    out["radius_m"] = radius_m
    if spec.buffer_m is not None:
        out["footprint_buffer_m"] = spec.buffer_m
    out["n_inside_sandy_2012"] = n_sandy
    out["n_in_dep_extreme_2080"] = n_dep
    out["narrative"] = narrative(spec.singular, spec.plural, len(hits), radius_m, n_sandy, n_dep,
                                 scope=spec.scope, n_checked=len(findings) if live else None) + _named(spec, findings)
    for key, flag in spec.rollups.items():
        out[key] = sum(1 for f in findings if f[flag])
    out[spec.list_key] = findings[:max_n]
    out["citation"] = spec.citation
    return out
