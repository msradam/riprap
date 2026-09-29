"""NYC DEP Stormwater Flood Maps: rainfall scenarios with future high tides.

Three scenarios, all in EPSG:2263. Each polygon carries a
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
        data/baked/. ~3 ms per scenario, ~70 ms cold-open. Used by
        step_dep in the FSM.
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

SCENARIOS = {
    "dep_extreme_2080": {
        "gdb": "dep_extreme_2080.gdb",
        "label": "DEP Extreme Stormwater (3.66 in/hr, 2080 SLR)",
        "year": 2080,
    },
    "dep_moderate_2050": {
        "gdb": "dep_moderate_2050.gdb",
        "label": "DEP Moderate Stormwater (2.13 in/hr, 2050 SLR)",
        "year": 2050,
    },
    "dep_moderate_current": {
        "gdb": "dep_moderate_current.gdb",
        "label": "DEP Moderate Stormwater (2.13 in/hr, current SLR)",
        "year": None,
    },
}

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
    return SCENARIOS[scenario]["label"]


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
