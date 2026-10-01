"""Experimental: land cover by year, from the TerraMind batch.

Reads the saved outputs of scripts/run_landcover_batch.py in data/eo/: one
10 m raster per year with five classes (app.eo.terramind.CLASSES; 255 = no
clear view). No model runs here and the app needs no extra to read them.

What it answers, through `app.experimental.hedge`:
  * how much of a place is paved or built over and how much is green;
  * how that compares with the first year mapped, held against the
    model's own noise (two images of one year,
    data/experimental/landcover.json): a difference inside the noise is
    reported as no measurable change.

It claims no trend. Differences beyond the noise turned up in 3 of 59
districts, which is what the noise alone produces (docs/MODELS.md), so a
larger difference is stated with that caution and nothing about runoff
follows from it.

The labels are a proxy from 10 m satellite pixels. The city's own land
cover map (2017, 6 inch) is the survey.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app import experimental

EO_DIR = Path(os.environ.get("RIPRAP_EO_DIR", Path(__file__).resolve().parents[2] / "data" / "eo"))
WATER, BUILT, TREES, GRASS, BARE = range(5)


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


MIN_PX = 500  # 5 ha: fewer labelled pixels than this say nothing about a place
# ponytail: one threshold between the two scales the noise was measured at
# (districts and neighbourhoods); a noise curve by area is the upgrade.
SMALL_AREA_PX = 30_000  # 3 km2


def _labels(year: int, geom_4326):
    """The year's labels inside a WGS84 geometry; 255 where there is no
    label (cloud, the harbour) or the pixel is outside it."""
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask

    with rasterio.open(EO_DIR / f"landcover_{year}.tif") as src:
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        a, _ = mask(src, [g], crop=True, nodata=255, filled=True, indexes=1)
    return a


def _shares(a, where) -> dict:
    """Percent of the pixels in `where` in each group."""
    import numpy as np

    n = int(where.sum())
    pct = lambda *cls: round(100 * float(np.isin(a[where], cls).sum()) / n, 1)  # noqa: E731
    return {"built_pct": pct(BUILT), "green_pct": pct(TREES, GRASS), "water_pct": pct(WATER), "bare_pct": pct(BARE)}


def _summary(geom, where: str) -> dict | None:
    maps = {y: _labels(y, geom) for y in years()}
    seen = {y: a != 255 for y, a in maps.items() if (a != 255).sum() >= MIN_PX}
    if not seen:
        return None
    last, first = max(seen), min(seen)
    # The two years are compared on the pixels both labelled, so a cloud gap
    # in one year is not read as change; with too few in common, no comparison.
    both = seen[last] & seen[first] if maps[last].shape == maps[first].shape else seen[last] & False
    compared = last != first and both.sum() >= 0.8 * max(seen[last].sum(), seen[first].sum())
    now = _shares(maps[last], both if compared else seen[last])
    ev = experimental.evaluation("landcover") or {}
    noise = ev.get("noise_points_small" if seen[last].sum() < SMALL_AREA_PX else "noise_points")
    out = {"year": last, **now, "by_year": {y: _shares(maps[y], seen[y]) for y in seen},
           "dates": _dates(last), "model": experimental.MODELS["landcover"].repo}
    statement = (f"a satellite land-cover model labels {now['built_pct']}% of {where} as paved or built over and "
                 f"{now['green_pct']}% as trees or grass, on Sentinel-2 scenes from {last}")
    if now["water_pct"] >= 1:
        statement += f" ({now['water_pct']}% water)"
    if compared:
        then = _shares(maps[first], both)["built_pct"]
        change = round(now["built_pct"] - then, 1)
        out.update(first_year=first, built_pct_first=then, built_change_points=change, noise_points=noise)
        statement += f"; in {first} the paved or built share was {then}%"
        if noise is None:
            statement += ", and no noise estimate is saved to judge that difference by"
        elif abs(change) <= noise:
            statement += (f", a difference of {abs(change)} points, inside the {noise} points by which two images of "
                          "one year can differ, so no change is measurable and no trend in runoff follows from it")
        else:
            # No trend is read from it: across the 59 districts, differences this
            # size appear as often as the noise alone produces them (docs/MODELS.md).
            statement += (f", a difference of {abs(change)} points, more than the {noise} points by which two images "
                          "of one year usually differ; differences that size appear in about 1 place in 20 from the "
                          "model's noise alone, so no trend in paving or runoff is read from it")
    out["narrative"] = experimental.hedge("landcover", statement)
    out["headline_value"] = f"{now['built_pct']}% paved or built, {now['green_pct']}% green ({last})"
    return out


def for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    import geopandas as gpd
    from shapely.geometry import Point

    circle = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32618").buffer(radius_m).to_crs("EPSG:4326").iloc[0]
    out = _summary(circle, f"the ground within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def for_polygon(polygon) -> dict | None:
    return _summary(polygon, "this area")
