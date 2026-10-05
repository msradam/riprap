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
counts and exposure is checked for the nearest max_n only. Every asset is
read at its own point, with no buffer, for an address and for an area
alike: a station once had 8 of 8 entrances inside by one path (each
entrance buffered by 8 m) and 5 of 9 by the other. A layer or
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

from app.assets.nycha import SANDY_MIN_SHARE
from app.flood_layers import dep_stormwater, sandy_inundation
from app.flood_layers.dep_stormwater import category_kind
from app.registers._loader import DEP_MAP, load_register, narrative, nearest_n

log = logging.getLogger("riprap.registers")

DATA = Path(__file__).resolve().parents[2] / "data"
SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050")
# What the stormwater map is and is not, in the city's words: it travels with every list of assets
# (a briefing that prints several lists, or the maps themselves, prints it once: evidence.cite_each).
MAP_LIMITS = dep_stormwater.limits("dep_extreme_2080")
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
    scope: str = ""               # what an exposed-only register counted
    missing_class: int | None = None  # DEP class when the register has none for a scenario
    scenarios: tuple[str, ...] = SCENARIOS
    elev_key: str = "elevation_m"
    hand_key: str = "hand_m"
    rollups: dict[str, str] = field(default_factory=dict)  # extra count key: finding flag
    unique: str | None = None     # a live layer's facility key: a repeated row is one asset


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
            "managed_by": str(r.get("managed_by") or ""),
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
        rollups={"n_ada_accessible": "ada_accessible"},
        scope=" (each entrance read at its own point on the maps, with no buffer)"),
    "doh_hospitals": Spec(
        singular="hospital", plural="hospitals", radius_m=3000, max_n=5,
        count_key="n_hospitals", list_key="hospitals",
        citation="NYS DOH Health Facility Certification (vn5v-hh5r) + NYC Sandy 2012 Inundation "
                 "Zone (5xsi-dfpx) + NYC DEP Stormwater Flood Maps + USGS 3DEP DEM",
        head=_hospital, name=lambda f: f["facility_name"],
        geojson=DATA / "hospitals.geojson", unique="fac_id",
        scope=" (each read at the one point the state file gives for it, not across its campus)"),
    "doe_schools": Spec(
        singular="public school inside a mapped flood extent", plural="public schools inside a mapped flood extent",
        radius_m=1500, max_n=6,
        count_key="n_schools", list_key="schools",
        citation="Pre-computed from NYC DOE 2019 - 2020 School Point Locations (a3nt-yts4; public schools, charter "
                 "schools included) joined to Sandy 2012 Inundation Zone (5xsi-dfpx) + "
                 "NYC DEP Stormwater Flood Maps + USGS 3DEP DEM. See data/registers/schools.json.",
        head=_school, name=lambda f: f["loc_name"], register="schools",
        scope=" (from the NYC Department of Education's school locations for the 2019 to 2020 school year, charter "
              "schools included; the register lists only schools whose location point is inside the 2012 Sandy "
              "extent or one of three modeled DEP stormwater scenarios (Moderate Flood with current and with 2050 sea "
              "levels, Extreme Flood with 2080; the Limited Flood map is not tested), not every school)"),
    "nycha": Spec(
        singular="NYCHA development inside a mapped flood extent",
        plural="NYCHA developments inside a mapped flood extent", radius_m=2000, max_n=5,
        count_key="n_developments", list_key="developments",
        citation="Pre-computed from NYC Open Data NYCHA Developments (phvi-damg) joined to Sandy 2012 "
                 "Inundation Zone (5xsi-dfpx) + NYC DEP Stormwater Flood Maps + USGS 3DEP DEM. "
                 "See data/registers/nycha.json.",
        head=_development, name=lambda f: f["development"], register="nycha", missing_class=0,
        scenarios=SCENARIOS + ("dep_moderate_current",),
        elev_key="rep_elevation_m", hand_key="rep_hand_m",
        scope=f" (the register lists only developments with {SANDY_MIN_SHARE:.0%} or more of their mapped outline inside the "
              "2012 Sandy extent, or their centre point inside one of three modeled DEP stormwater scenarios (Moderate "
              "Flood with current and with 2050 sea levels, Extreme Flood with 2080; the Limited Flood map is not "
              "tested), not every development)"),
}


@lru_cache(maxsize=4)
def geojson_rows(asset_class: str) -> list[dict]:
    """The live layer's feature properties with lat and lon lifted out.
    A feature without usable coordinates is skipped."""
    spec = CLASSES[asset_class]
    with open(spec.geojson) as f:
        feats = json.load(f)["features"]
    rows, seen = [], set()
    for feat in feats:
        try:
            lat, lon = spec.lat_lon(feat)
        except (KeyError, TypeError, ValueError):
            continue
        # The state file repeats a facility (67 rows for 61 hospitals in one
        # download), which printed one hospital as two.
        key = feat["properties"].get(spec.unique) if spec.unique else None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
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


def _exposure(spec: Spec, lat: float, lon: float) -> tuple[bool, dict[str, int], int | None]:
    """Sandy flag, DEP category code per scenario and the asset's distance
    to the mapped Sandy edge when within 50 m (Bellevue's point is 46 m
    outside the outline of a flood that closed it), all read at the asset's
    own point. A failed read raises: counting the asset as outside would
    print a failure as a zero."""
    import geopandas as gpd
    from shapely.geometry import Point
    pt = (gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
          .to_crs("EPSG:2263").iloc[0].geometry)
    sandy = sandy_inundation.at_point(pt)
    return (sandy["inside"], {s: dep_stormwater.join_raster(pt, s) for s in spec.scenarios},
            None if sandy["inside"] else sandy["edge_m"])


def _sandy_edge_m(lat: float, lon: float) -> int | None:
    """Distance to the mapped Sandy edge when within 50 m of it, else None."""
    import geopandas as gpd
    from shapely.geometry import Point

    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263").iloc[0]
    return sandy_inundation.at_point(pt)["edge_m"]


def _finding(spec: Spec, distance_m: float | None, row: dict) -> dict:
    lat, lon = float(row["lat"]), float(row["lon"])
    f = spec.head(row, lat, lon, None if distance_m is None else round(distance_m, 1))
    if spec.register:
        snap = row.get("snap") or {}
        dep = snap.get("dep") or {}
        micro = snap.get("microtopo") or {}
        elev, hand = micro.get("point_elev_m"), micro.get("aoi_hand_m") or micro.get("hand_m")
        sandy = bool(snap.get("sandy"))
        if row.get("sandy_share") is not None:
            # An outline, counted by the share of its area inside the extent.
            f["sandy_share"] = round(float(row["sandy_share"]), 3)
        elif not sandy:
            # The register tested the asset's bare point. One just outside the
            # outline is named as near its edge, not left out (PAVE Academy's
            # point is 3 m outside; another city file puts it 16 m inside).
            edge = _sandy_edge_m(lat, lon)
            if edge is not None:
                f["sandy_edge_m"] = edge
        classes = {}
        for scen in spec.scenarios:
            c = (dep.get(scen) or {}).get("depth_class")
            classes[scen] = spec.missing_class if c is None else int(c)
    else:
        elev = _sample_raster(DATA / "nyc_dem_30m.tif", lat, lon)
        hand = _sample_raster(DATA / "hand.tif", lat, lon)
        sandy, classes, edge = _exposure(spec, lat, lon)
        if edge is not None:
            f["sandy_edge_m"] = edge  # outside the outline, within 50 m of it
    f[spec.elev_key] = round(float(elev), 2) if elev is not None else None
    f[spec.hand_key] = round(float(hand), 2) if hand is not None else None
    f["inside_sandy_2012"] = sandy
    for scen in spec.scenarios:
        # Inside or outside and which kind of category, never a depth: a row names a structure.
        f[f"{scen}_category"] = category_kind(classes[scen])
    return f


def _rain(f: dict, scen: str = "dep_extreme_2080") -> bool:
    return f[f"{scen}_category"] == "rainfall flooding"


def _tide(f: dict, scen: str = "dep_extreme_2080") -> bool:
    return f[f"{scen}_category"] == "future high tides"


def _mapped(f: dict, scen: str) -> bool:
    return f[f"{scen}_category"] not in (None, "outside")


def _named(spec: Spec, findings: list[dict], limit: int = 20) -> str:
    """The exposed assets by name, nearest first: a question that asks
    which schools gets the schools, not only how many."""
    out = ""
    for label, hit in (("Inside the 2012 Sandy extent", lambda f: f["inside_sandy_2012"]),
                       ("Outside the 2012 Sandy extent but within 50 m of its mapped edge (the outline is not exact to a building)",
                        lambda f: f.get("sandy_edge_m") is not None),
                       (f"Under {SANDY_MIN_SHARE:.0%} of the outline inside the 2012 Sandy extent (not counted)",
                        lambda f: not f["inside_sandy_2012"] and (f.get("sandy_share") or 0) > 0),
                       # A list of names carries its extent: the event, or the map by the city's name and the
                       # word modelled. Rainfall flooding and the tidal category are different hazards: two lists.
                       (f"In a rainfall flooding category of the modelled {DEP_MAP} map", _rain),
                       (f"In the future high tides category of the modelled {DEP_MAP} map (coastal tidal inundation "
                        "projected for 2080, not rainfall flooding)", _tide)):
        nearest: dict[str, float | None] = {}  # one station has several entrances: its nearest one
        for f in findings:
            if hit(f) and spec.name(f) not in nearest:
                nearest[spec.name(f)] = f.get("distance_m")
        names = [n if d is None else f"{n} ({d:.0f} m)" for n, d in nearest.items()]
        if names:
            more = f", and {len(names) - limit} more" if len(names) > limit else ""
            # Entrances are counted; a station has several, so the names are stations.
            out += f". {label}{', by station' if spec.plural.endswith('entrances') else ''}: {', '.join(names[:limit])}{more}"
    return out


def _n_exposed(spec: Spec, findings: list[dict]) -> int:
    """How many of a baked register's rows are exposed. The register also
    keeps assets within 50 m of the Sandy edge; those are named, not counted."""
    return sum(1 for f in findings
               if f["inside_sandy_2012"] or any(_mapped(f, s) for s in spec.scenarios))


def _near_sandy(f: dict) -> bool:
    """Named, not counted: a point within 50 m of the mapped edge, or an
    outline with some of its area inside but under the threshold."""
    return f.get("sandy_edge_m") is not None or (not f["inside_sandy_2012"] and (f.get("sandy_share") or 0) > 0)


def summary_for_polygon(polygon, asset_class: str) -> dict:
    """The assets of `asset_class` inside a WGS84 polygon (a neighbourhood,
    or the outline drawn for a community district), with their exposure.
    Schools and NYCHA come from the baked registers, which list exposed
    assets only; subway entrances and hospitals are every asset in the
    polygon, each checked against the baked rasters at its own point."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    spec = CLASSES[asset_class]
    inside = prep(polygon)
    rows = [r for r in _rows(asset_class, spec)
            if r.get("lat") is not None and inside.contains(Point(float(r["lon"]), float(r["lat"])))]
    findings = sorted((_finding(spec, None, r) for r in rows), key=spec.name)
    n_sandy = sum(1 for f in findings if f["inside_sandy_2012"])
    n_rain, n_tide = sum(map(_rain, findings)), sum(map(_tide, findings))
    n = _n_exposed(spec, findings) if spec.register else len(findings)
    return {"available": True, spec.count_key: n, "n_inside_sandy_2012": n_sandy, "n_in_dep_extreme_2080": n_rain + n_tide,
            "n_in_dep_extreme_2080_rainfall": n_rain, "n_in_dep_extreme_2080_tidal": n_tide,
            "n_near_sandy_edge": sum(1 for f in findings if _near_sandy(f)),
            "narrative": narrative(spec.singular, spec.plural, n, None, n_sandy, n_rain, n_tide, scope=spec.scope)
                         + _named(spec, findings) + f". {MAP_LIMITS}",
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
    n_rain, n_tide = sum(map(_rain, findings)), sum(map(_tide, findings))
    n = len(hits) if live else _n_exposed(spec, findings)
    out: dict = {"available": True, spec.count_key: n}
    if live:
        out["n_checked"] = len(findings)
    out["radius_m"] = radius_m
    out["n_inside_sandy_2012"] = n_sandy
    # Any category of the map, then its two kinds: rainfall flooding is not the tidal category.
    out["n_in_dep_extreme_2080"] = n_rain + n_tide
    out["n_in_dep_extreme_2080_rainfall"] = n_rain
    out["n_in_dep_extreme_2080_tidal"] = n_tide
    if any(_near_sandy(f) for f in findings):
        out["n_near_sandy_edge"] = sum(1 for f in findings if _near_sandy(f))
    out["narrative"] = narrative(spec.singular, spec.plural, n, radius_m, n_sandy, n_rain, n_tide,
                                 scope=spec.scope, n_checked=len(findings) if live else None) + _named(spec, findings) + f". {MAP_LIMITS}"
    for key, flag in spec.rollups.items():
        out[key] = sum(1 for f in findings if f[flag])
    out[spec.list_key] = findings[:max_n]
    out["citation"] = spec.citation
    return out
