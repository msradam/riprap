"""NYC Stormwater Flood Maps (DEP): rainfall scenarios with future high tides.

Four scenarios, all in EPSG:2263, named as NYC Open Data (9i7c-xyvv) names
them. Each is a design storm paired with a sea level, not a forecast. Each
polygon carries a
`Flooding_Category` code from the files' coded-value domain:
    1 = Nuisance Flooding (greater or equal to 4 in. and less than 1 ft.)
    2 = Deep and Contiguous Flooding (1 ft. and greater)
    3 = Future High Tides 2050 / 2080 (only in the 2050 and 2080 files)
Classes 1 and 2 are rainfall flooding from DEP's hydraulic model. Class 3
is not deeper rainfall flooding: it is coastal tidal inundation from
sea-level rise (NPCC 90th percentile), taken from the NYC Flood Hazard
Mapper. `class_label` is the one place these meanings are worded.

Two query paths exist:
    join_raster(point) — fast path. Samples the baked GeoTIFFs in
        data/baked/. ~3 ms per scenario, ~70 ms cold-open. at_point
        adds the distance to the mapped edge and is what a briefing reads.
    join(assets)       — legacy GDB path via gpd.sjoin. Retained as
        a fallback when baked rasters are absent (local dev) and as
        the polygon-overlap path used by coverage_for_polygon for
        neighborhood mode.
"""
from __future__ import annotations

import logging
import threading
from functools import lru_cache

import geopandas as gpd

from app.spatial import DATA, NYC_CRS

log = logging.getLogger(__name__)
BAKED = DATA / "baked"
_TLOCAL = threading.local()
_FALLBACK_WARNED = False

ROOT = DATA / "dep"

# `name` is the city's own name for each map, word for word from the NYC Open
# Data collection (data.cityofnewyork.us/api/views/9i7c-xyvv.json). The
# Limited map's file there is a compressed geodatabase GDAL cannot read, so
# its polygons come from DEP's own map viewer (scripts/fetch_dep_limited.py).
SCENARIOS = {
    "dep_extreme_2080": {
        "gdb": "dep_extreme_2080.gdb",
        "name": "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise",
        "year": 2080,
    },
    "dep_moderate_2050": {
        "gdb": "dep_moderate_2050.gdb",
        "name": "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise",
        "year": 2050,
    },
    "dep_moderate_current": {
        "gdb": "dep_moderate_current.gdb",
        "name": "Moderate Flood (2.13 inches/hr) with Current Sea Levels",
        "year": None,
    },
    "dep_limited_current": {
        "gdb": "dep_limited_current.gdb",
        "name": "Limited Flood (1.77 inches/hr) with Current Sea Levels",
        "year": None,
    },
}

# What "outside" does not mean, in NYC Emergency Management's words (Hazard
# Mitigation Plan, flooding profile). It travels with every outside reading.
OUTSIDE_CAVEAT = (
    "Outside a mapped extent does not mean safe: NYC Emergency Management reports that during Hurricane Ida in "
    "2021 \"The most heavily impacted areas, representing over half of all damaged buildings, were also outside of "
    "any flood risk scenario, including FEMA floodplain maps\" (NYC Hazard Mitigation Plan, flooding profile, "
    "nychazardmitigation.com).")

# Flooding_Category as each file's domain spells it (read from data/dep/*.gdb).
_DOMAIN = {1: "Nuisance Flooding (greater or equal to 4 in. and less than 1 ft.)",
           2: "Deep and Contiguous Flooding (1 ft. and greater)"}
RAIN_LABEL = {1: "nuisance flooding (4 in to under 1 ft)",
              2: "deep and contiguous flooding (1 ft or more)"}
TIDE_CLASS = 3


def domain(scenario: str) -> dict[int, str]:
    """The file's raw Flooding_Category domain text. The current-sea-level
    file has no class 3."""
    year = SCENARIOS[scenario]["year"]
    return {**_DOMAIN, TIDE_CLASS: f"Future High Tides {year}"} if year else dict(_DOMAIN)


def tide_words(scenario: str) -> str:
    """What class 3 maps, in plain words, for this scenario's year."""
    year = SCENARIOS.get(scenario, {}).get("year")
    return f"coastal tidal inundation projected for {year}" if year else "coastal tidal inundation"


def named(scenario: str) -> str:
    """The city's name for a map, in quotes. A current-sea-level map names
    no year, so "the near term" follows it: the disclosure check asks every
    scenario sentence for a time horizon."""
    s = SCENARIOS[scenario]
    return f'"{s["name"]}"' + ("" if s["year"] else " (the near term)")


def limits(scenario: str) -> str:
    """What the map is and is not, in the words of the city's disclaimer
    (the licence text of DEP's own map items, arcgis.com item
    5b82c08be55d4f30bf28d265ab8e4a49). The second sentence of every
    stormwater statement: a "not" in the first would read as an absence."""
    year = SCENARIOS[scenario]["year"]
    sea = f"{year} sea level rise" if year else "current sea levels, the near term"
    return (f"This map is a modelled scenario (a design storm paired with {sea}), not a forecast: its rainfall "
            "flooding categories cover public areas and rain only, it \"does not provide the exact depth of flooding "
            "at any location\", and it is not a flood plain determination.")


def share_sentence(fraction_class: dict, scenario: str) -> str:
    """The share of an area in each of the map's categories, by the city's
    category names, then what the map is and is not."""
    c, names = fraction_class, domain(scenario)

    def pct(x) -> float:
        return round(float(x) * 100, 1)

    out = (f"On the city's stormwater flood map {named(scenario)}, {pct(c.get(1, 0) + c.get(2, 0))}% of this area is "
           f"in a rainfall flooding category: {pct(c.get(1, 0))}% in \"{names[1]}\" and {pct(c.get(2, 0))}% in "
           f"\"{names[2]}\"")
    if TIDE_CLASS in names:
        out += (f"; {pct(c.get(TIDE_CLASS, 0))}% is in its \"{names[TIDE_CLASS]}\" category, which is "
                f"{tide_words(scenario)}")
    return f"{out}. {limits(scenario)}"


def class_label(cls: int, scenario: str) -> str:
    """The plain-words label for a Flooding_Category code; 0 is "outside"."""
    if cls == TIDE_CLASS:
        return f"future high tides: {tide_words(scenario)}"
    return RAIN_LABEL.get(cls, "outside")


@lru_cache(maxsize=4)
def load(scenario: str) -> gpd.GeoDataFrame:
    s = SCENARIOS[scenario]
    path = ROOT / s["gdb"]
    g = gpd.read_file(str(path))
    if g.crs.to_string() != NYC_CRS:
        g = g.to_crs(NYC_CRS)
    return g


def join(assets: gpd.GeoDataFrame, scenario: str) -> gpd.GeoDataFrame:
    """Per-asset Flooding_Category, or 0 if outside scenario.

    Returns a frame indexed like assets with columns: depth_class, depth_label.
    The classes do not overlap in area (class 3 only touches 1 and 2 at
    edges), so the max below only settles edge and buffered hits. It is a
    tie-break that matches the baked rasters' burn order, not a depth
    order: class 3 is tidal, not deeper.
    """
    z = load(scenario)
    a = assets[["geometry"]].copy()
    a["_aid"] = range(len(a))
    j = gpd.sjoin(a, z[["Flooding_Category", "geometry"]],
                  how="left", predicate="intersects")
    cat = (j.groupby("_aid")["Flooding_Category"].max()
              .reindex(range(len(a)))
              .fillna(0).astype(int))
    out = a[["_aid"]].copy()
    out["depth_class"] = cat.values
    out["depth_label"] = out["depth_class"].map(lambda c: class_label(c, scenario))
    return out[["depth_class", "depth_label"]].reset_index(drop=True)


def label(scenario: str) -> str:
    return f"NYC Stormwater Flood Map - {SCENARIOS[scenario]['name']}"


def _raster_handles():
    """Per-thread rasterio handle cache. rasterio.DatasetReader is not
    safe to share across threads for concurrent .sample() calls; the
    FSM runs each request on its own executor thread, so we keep one
    handle set per thread."""
    h = getattr(_TLOCAL, "handles", None)
    if h is not None:
        return h
    import rasterio
    h = {}
    for s in SCENARIOS:
        p = BAKED / f"{s}.tif"
        if not p.exists():
            return None
        h[s] = rasterio.open(str(p))
    _TLOCAL.handles = h
    return h


def join_raster(pt_geom_2263, scenario: str) -> int:
    """Fast path. Returns the Flooding_Category (0=outside, 1/2/3) for a
    single shapely Point in EPSG:2263. Falls back to the GDB join() path
    if baked rasters are missing — emits a one-time warning so local dev
    still works without the bake artifacts."""
    global _FALLBACK_WARNED
    h = _raster_handles()
    if h is None:
        if not _FALLBACK_WARNED:
            log.warning(
                "data/baked/dep_*.tif not found — falling back to GDB sjoin. "
                "Run: uv run python scripts/bake_cornerstone_rasters.py"
            )
            _FALLBACK_WARNED = True
        # legacy fallback — wrap point in a one-row GeoDataFrame
        a = gpd.GeoDataFrame(geometry=[pt_geom_2263], crs=NYC_CRS)
        return int(join(a, scenario).iloc[0]["depth_class"])
    ds = h[scenario]
    v = next(ds.sample([(pt_geom_2263.x, pt_geom_2263.y)]))
    return int(v[0])


EDGE_M = 50  # as sandy_inundation.EDGE_M: how near the mapped edge a point must be for the sentence to say so


def at_point(pt_geom_2263, scenario: str) -> dict:
    """The Flooding_Category under a point and how near the point is to the
    mapped edge, by the approach of sandy_inundation.at_point.

    The reading is one 10 ft pixel. 80 Pioneer Street reads outside with
    mapped flooding about 4 m away, and 400 Carroll Street reads inside a
    pixel or so from the edge, so a point within EDGE_M of where the map
    changes between flooding and none gets that distance stated."""
    import math

    cls = join_raster(pt_geom_2263, scenario)
    out = {"depth_class": cls, "edge_m": None}
    h = _raster_handles()
    if h is None:
        return out
    import numpy as np
    from rasterio.windows import Window

    ds = h[scenario]
    px = ds.res[0]  # feet: the raster is in EPSG:2263
    n = math.ceil(EDGE_M / 0.3048 / px)
    row, col = ds.index(pt_geom_2263.x, pt_geom_2263.y)
    a = ds.read(1, window=Window(col - n, row - n, 2 * n + 1, 2 * n + 1), boundless=True, fill_value=0) > 0
    other = np.argwhere(a != (cls > 0))
    if len(other):
        d = float(np.hypot(other[:, 0] - n, other[:, 1] - n).min() * px * 0.3048)
        if d <= EDGE_M:
            out["edge_m"] = max(round(d), 1)
    return out


def coverage_for_polygon(polygon, scenario: str,
                         polygon_crs: str = "EPSG:4326") -> dict:
    """Polygon-level summary: what fraction of the input polygon falls into
    each Flooding_Category for a given DEP scenario? Used in neighborhood mode.

    Returns:
      {
        'scenario':        scenario id,
        'label':           human-readable scenario name,
        'fraction_any':    fraction inside any class (rainfall or tidal),
        'fraction_class':  {1: f, 2: f, 3: f} fraction in each class,
        'polygon_area_m2': total polygon area,
      }
    """
    z = load(scenario)
    poly_gdf = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs(NYC_CRS)
    poly_geom = poly_gdf.iloc[0].geometry
    poly_ft2 = float(poly_geom.area)
    sqft_to_m2 = 0.092903
    fraction_class = {1: 0.0, 2: 0.0, 3: 0.0}
    if poly_ft2:
        for cat in (1, 2, 3):
            sub = z[z["Flooding_Category"] == cat]
            if sub.empty:
                continue
            inter = sub.geometry.intersection(poly_geom)
            inter = inter[~inter.is_empty]
            ft2 = float(inter.area.sum()) if len(inter) else 0.0
            fraction_class[cat] = round(ft2 / poly_ft2, 4)
    fraction_any = round(sum(fraction_class.values()), 4)
    return {
        "scenario":        scenario,
        "label":           label(scenario),
        "fraction_any":    fraction_any,
        "fraction_class":  fraction_class,
        "polygon_area_m2": round(poly_ft2 * sqft_to_m2, 1),
    }
