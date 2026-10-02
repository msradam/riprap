"""Land cover at a place: the city's own map, then the model's estimate.

Two sources in one raster format (30 m, five bands: the percent of each cell
in tree canopy, grass and shrub, bare soil, water, and paved or built over;
255 = no value), so one reader serves both:

  * `city_map_*`: NYC Land Cover 2017 (6 inch, from LiDAR and imagery),
    aggregated by scripts/prepare_landcover_labels.py --bake-city-map. A
    survey, cited as the source of its sentence;
  * `for_point` / `for_polygon`: the experimental land-cover model's saved
    yearly maps (scripts/run_landcover_batch.py, data/eo/), from the latest
    year mapped, through `app.experimental.hedge`. No model runs here and
    the app needs no extra to read them.

The model's maps are not compared between years. Two images of one summer
give a district's paved share within 2 points of each other 19 times in 20,
but maps of different summers differ by more than that in many districts
(between the 2018 and 2024 maps, 49 of 59; data/experimental/landcover.json),
which is the images, not the ground. The hedge says so.

The city's map is the more accurate source for the year it covers: read as
if it were 2021, the 2017 map is closer to the 2021 map than any model
tested (docs/MODELS.md). So a land-cover question is answered with the map
first, and the model's sentence follows as the estimate for newer imagery.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app import experimental

DATA = Path(__file__).resolve().parents[2] / "data"
EO_DIR = Path(os.environ.get("RIPRAP_EO_DIR", DATA / "eo"))
CITY_MAP = DATA / "landcover_nyc_2017.tif"
# The bands every land-cover raster carries, in order; the batch scripts import this.
GROUPS = ("tree_canopy", "grass_shrub", "bare_soil", "water", "paved")
TREES, GRASS, BARE, WATER, PAVED = range(5)


def years() -> list[int]:
    return sorted(int(p.stem.split("_")[1]) for p in EO_DIR.glob("landcover_*.tif"))


def _dates(year: int) -> str:
    path = EO_DIR / f"landcover_{year}.tif"
    return _dates_at(path, path.stat().st_mtime)


@lru_cache(maxsize=16)
def _dates_at(path: Path, mtime: float) -> str:  # a raster rewritten by the batch is read again
    import rasterio

    with rasterio.open(path) as src:
        return src.tags().get("dates", "")


MIN_M2 = 50_000  # 5 ha: less ground with a value than this says nothing about a place


def _fractions(path: Path, geom_4326):
    """The raster's (5, H, W) percent bands inside a WGS84 geometry, 255 where
    there is no value (cloud, the harbour) or the cell is outside it, and the
    area of one cell in square metres."""
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask

    with rasterio.open(path) as src:
        if src.descriptions != GROUPS:
            raise ValueError(f"{path.name} is not a five-group land-cover raster (from an older batch?)")
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        a, _ = mask(src, [g], crop=True, nodata=255, filled=True)
        return a, abs(src.transform.a * src.transform.e)


def _shares(a, where) -> dict:
    """Mean percent of the cells in `where` in each group. `built_pct` is the
    paved band (roofs, roads, other paving, rail); `tree_canopy_pct` is part
    of `green_pct`, not a further slice."""
    pct = lambda b: round(float(a[b][where].astype("float32").mean()), 1)  # noqa: E731
    return {"built_pct": pct(PAVED), "green_pct": round(pct(TREES) + pct(GRASS), 1), "tree_canopy_pct": pct(TREES),
            "water_pct": pct(WATER), "bare_pct": pct(BARE)}


def _rest(now: dict, wrap: str) -> str:
    """Water and bare ground (sand, soil) when either is 1% or more, so the
    stated shares add up: at Breezy Point 16% of the ground is bare."""
    parts = [f"{now[k]}% {name}" for k, name in (("water_pct", "water"), ("bare_pct", "bare soil or sand")) if now[k] >= 1]
    return wrap.format(" and ".join(parts)) if parts else ""


SEEN_SHARE = 0.9  # a year counts when it sees this much of the ground the best year sees


def _summary(geom, where: str) -> dict | None:
    # The latest year that sees nearly all of the place. A year with half the
    # circle under cloud once stood for the whole of it. Years are not
    # compared (see the module docstring).
    views = {}
    for year in years():
        a, cell_m2 = _fractions(EO_DIR / f"landcover_{year}.tif", geom)
        views[year] = (a, a[0] != 255, cell_m2)
    most = max((seen.sum() for _, seen, _ in views.values()), default=0)
    year = max((y for y, (_, seen, m2) in views.items()
                if seen.sum() * m2 >= MIN_M2 and seen.sum() >= SEEN_SHARE * most), default=None)
    if year is None:
        return None
    a, seen, _ = views[year]
    now = _shares(a, seen)
    out = {"year": year, **now, "dates": _dates(year), "model": experimental.MODELS["landcover"].name}
    statement = (f"a satellite land-cover model estimates that {now['built_pct']}% of {where} is paved or built over "
                 f"and {now['green_pct']}% is green ({now['tree_canopy_pct']}% tree canopy), on Sentinel-2 scenes "
                 f"from {year}")
    statement += _rest(now, " ({})")
    out["narrative"] = experimental.hedge("landcover", f"{statement}; no change between years is read from it")
    out["headline_value"] = (f"{now['built_pct']}% paved or built, {now['green_pct']}% green, "
                             f"{now['tree_canopy_pct']}% tree canopy ({year})")
    return out


def _city_map(geom, where: str) -> dict | None:
    """What the city's 2017 map shows inside a geometry, or None where the
    map has too little ground (outside the city, open water)."""
    if not CITY_MAP.exists():
        return None
    a, cell_m2 = _fractions(CITY_MAP, geom)
    seen = a[0] != 255
    if seen.sum() * cell_m2 < MIN_M2:
        return None
    now = _shares(a, seen)
    narrative = (f"New York City's 2017 land cover map (6 inch, from LiDAR and aerial imagery) shows that "
                 f"{now['built_pct']}% of {where} is paved or built over and {now['green_pct']}% is green "
                 f"({now['tree_canopy_pct']}% tree canopy)")
    narrative += _rest(now, "; the rest is {}")
    return {"year": 2017, **now, "narrative": narrative + ".",
            "headline_value": f"{now['tree_canopy_pct']}% tree canopy, {now['built_pct']}% paved or built (2017)"}


def _circle(lat: float, lon: float, radius_m: float):
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32618").buffer(radius_m).to_crs("EPSG:4326").iloc[0]


def city_map_for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    out = _city_map(_circle(lat, lon, radius_m), f"the ground within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def city_map_for_polygon(polygon) -> dict | None:
    return _city_map(polygon, "this area")


def for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    out = _summary(_circle(lat, lon, radius_m), f"the ground within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def for_polygon(polygon) -> dict | None:
    return _summary(polygon, "this area")
