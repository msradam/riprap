"""Experimental: land cover by year, from the land-cover batch.

Reads the saved outputs of scripts/run_landcover_batch.py in data/eo/: one
30 m raster per year with five bands, the percent of each cell in tree
canopy, grass and shrub, bare soil, water, and paved or built over (255 = no
clear view). No model runs here and the app needs no extra to read them.

What it answers, through `app.experimental.hedge`: how much of a place is
paved or built over, how much is green, and how much is tree canopy, from
the latest year mapped.

It does not compare years. Two images of one summer give a district's paved
share within 2 points of each other 19 times in 20, but maps of different
summers differ by more than that in many districts (between the 2018 and
2024 maps, 49 of 59; data/experimental/landcover.json), which is the
images, not the ground. So no change or trend is read from the maps,
and the sentence says why.

The fractions are a model's estimate from 10 m satellite pixels. The
city's own land cover maps (2017 and 2021, 6 inch) are the surveys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app import experimental

EO_DIR = Path(os.environ.get("RIPRAP_EO_DIR", Path(__file__).resolve().parents[2] / "data" / "eo"))
# Band indices (scripts/run_landcover_batch.py GROUPS), so the app need not import the model.
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


def _fractions(year: int, geom_4326):
    """The year's (5, H, W) percent bands inside a WGS84 geometry, 255 where
    there is no value (cloud, the harbour) or the cell is outside it, and the
    area of one cell in square metres."""
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask

    with rasterio.open(EO_DIR / f"landcover_{year}.tif") as src:
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        a, _ = mask(src, [g], crop=True, nodata=255, filled=True)
        return a, abs(src.transform.a * src.transform.e)


def _shares(a, where) -> dict:
    """Mean percent of the cells in `where` in each group."""
    pct = lambda b: round(float(a[b][where].astype("float32").mean()), 1)  # noqa: E731
    return {"built_pct": pct(PAVED), "green_pct": round(pct(TREES) + pct(GRASS), 1), "tree_pct": pct(TREES),
            "water_pct": pct(WATER), "bare_pct": pct(BARE)}


def _summary(geom, where: str) -> dict | None:
    # The latest year with enough ground in view; years are not compared (see the module docstring).
    for year in sorted(years(), reverse=True):
        a, cell_m2 = _fractions(year, geom)
        seen = a[0] != 255
        if seen.sum() * cell_m2 >= MIN_M2:
            break
    else:
        return None
    now = _shares(a, seen)
    out = {"year": year, **now, "dates": _dates(year), "model": experimental.MODELS["landcover"].repo}
    statement = (f"a satellite land-cover model estimates that {now['built_pct']}% of {where} is paved or built over "
                 f"and {now['green_pct']}% is green ({now['tree_pct']}% tree canopy), on Sentinel-2 scenes from {year}")
    if now["water_pct"] >= 1:
        statement += f" ({now['water_pct']}% water)"
    ev = experimental.evaluation("landcover") or {}
    if {"between_years_worst", "between_years_beyond_noise", "between_years_districts", "noise_points"} <= ev.keys():
        statement += (f"; no change between years is read from it, because its maps of different summers differ by "
                      f"more than two images of one summer do (between {ev['between_years_worst']}, "
                      f"{ev['between_years_beyond_noise']} of {ev['between_years_districts']} districts' paved shares "
                      f"differ by more than {ev['noise_points']} points)")
    else:
        statement += "; no change between years is read from it"
    out["narrative"] = experimental.hedge("landcover", statement)
    out["headline_value"] = (f"{now['built_pct']}% paved or built, {now['green_pct']}% green, "
                             f"{now['tree_pct']}% tree canopy ({year})")
    return out


def for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    import geopandas as gpd
    from shapely.geometry import Point

    circle = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32618").buffer(radius_m).to_crs("EPSG:4326").iloc[0]
    out = _summary(circle, f"the ground within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def for_polygon(polygon) -> dict | None:
    return _summary(polygon, "this area")
