"""New surface water after Hurricane Ida from the Prithvi-EO batch (experimental).

Reads the precomputed outputs of scripts/run_eo_batch.py for the Ida event
(rain ending 2021-09-01): a 10 m Cloud Optimized GeoTIFF of new water
(1 = water after the storm that was not water before, 0 = no new water,
255 = no cloud-free scene pair observed the pixel) and a per-NTA
GeoParquet summary. The model is `msradam/Prithvi-EO-2.0-NYC-Pluvial` run
on Sentinel-2 L2A scenes from 2021-09-02, with same-tile pre scenes from
2021-08-13 masking permanent water.

Per query nothing is inferred: for a point, the new-water area within
500 m and the share of the surrounding NTA; for an area, the new-water
share of the polygon. Street and basement flooding drains within hours
and is not visible at 10 to 20 m, so no water is not evidence of no
flooding. The model has no flood-detection score on held-out events.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

EO_DIR = Path(os.environ.get("RIPRAP_EO_DIR", Path(__file__).resolve().parents[2] / "data" / "eo"))
EVENT = "2021-09-01"
MODEL = "msradam/Prithvi-EO-2.0-NYC-Pluvial"
CAVEAT = ("Street and basement flooding drains within hours and is not visible at 10 to 20 m, so no "
          "water here is not evidence of no flooding.")


def _paths(event: str = EVENT) -> tuple[Path, Path]:
    stem = EO_DIR / f"prithvi_new_water_{event}"
    return stem.with_suffix(".tif"), Path(f"{stem}_by_nta.parquet")


@lru_cache(maxsize=2)
def _tags(event: str = EVENT) -> dict:
    import rasterio

    tif, _ = _paths(event)
    with rasterio.open(tif) as src:
        return src.tags()


def _dates(ids: str) -> str:
    """'S2A_MSIL2A_20210902T154911_R054_T18TWL_...;...' -> '2021-09-02'."""
    days = sorted({i.split("_")[2][:8] for i in ids.split(";") if i.count("_") >= 2})
    return ", ".join(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in days)


def _count(geom_4326) -> tuple[float, float, float]:
    """(new-water m2, observed m2, total m2) inside a WGS84 geometry."""
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.mask import mask

    tif, _ = _paths()
    with rasterio.open(tif) as src:
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        arr, _ = mask(src, [g], crop=True, nodata=254, filled=True)
        px = abs(src.transform.a * src.transform.e)
    a = arr[0]
    inside = a != 254
    return (float(np.sum(a == 1)) * px, float(np.sum(inside & (a != 255))) * px, float(np.sum(inside)) * px)


def _scene_sentence(tags: dict) -> str:
    return (f"{MODEL} on Sentinel-2 scenes from {_dates(tags.get('post_scene', ''))}, compared with "
            f"{_dates(tags.get('pre_scene', ''))}")


def summary_for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    """New water within `radius_m` of a point and the share of its NTA."""
    import geopandas as gpd
    from shapely.geometry import Point

    tif, _ = _paths()
    if not tif.exists():
        return None
    tags = _tags()
    circle = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32618").buffer(radius_m) \
        .to_crs("EPSG:4326").iloc[0]
    new_m2, obs_m2, total_m2 = _count(circle)
    out = {"new_water_m2_within_radius": round(new_m2), "radius_m": radius_m,
           "frac_observed_within_radius": round(obs_m2 / total_m2, 3) if total_m2 else 0.0,
           "post_scene": tags.get("post_scene"), "pre_scene": tags.get("pre_scene"), "model": MODEL,
           "rain_date": tags.get("rain_date", EVENT), "batch_run": tags.get("batch_run")}
    # The NTA share comes from the raster itself, the same count as the circle.
    from app.areas import nta

    g = nta.load()
    hit = g[g.contains(Point(lon, lat))]
    if len(hit):
        n_new, n_obs, n_total = _count(hit.geometry.iloc[0])
        out.update(nta_name=hit.iloc[0]["ntaname"], nta_frac_new_water=round(n_new / n_obs, 5) if n_obs else 0.0,
                   nta_frac_observed=round(n_obs / n_total, 3) if n_total else 0.0)
    if not out["frac_observed_within_radius"]:
        where = "No cloud-free scene pair covered the area within 500 m of this address, so the model saw nothing here."
    else:
        where = (f"{out['new_water_m2_within_radius']:,} m² of new surface water within {radius_m:.0f} m of this "
                 f"address ({out['frac_observed_within_radius']:.0%} of that circle observed)")
        if "nta_name" in out:
            where += (f"; {out['nta_frac_new_water']:.2%} of {out['nta_name']} showed new water "
                      f"({out['nta_frac_observed']:.0%} of it observed)")
        where += "."
    out["narrative"] = f"Experimental: {_scene_sentence(tags)}: {where} {CAVEAT}"
    out["headline_value"] = f"{out['new_water_m2_within_radius']:,} m² new water within {radius_m:.0f} m"
    return out


def summary_for_polygon(polygon) -> dict | None:
    """The new-water share of an area (an NTA or a community district)."""
    tif, _ = _paths()
    if not tif.exists():
        return None
    tags = _tags()
    new_m2, obs_m2, total_m2 = _count(polygon)
    frac = new_m2 / obs_m2 if obs_m2 else 0.0
    out = {"new_water_m2": round(new_m2), "frac_new_water": round(frac, 5),
           "frac_observed": round(obs_m2 / total_m2, 3) if total_m2 else 0.0,
           "post_scene": tags.get("post_scene"), "pre_scene": tags.get("pre_scene"), "model": MODEL,
           "rain_date": tags.get("rain_date", EVENT), "batch_run": tags.get("batch_run")}
    if not obs_m2:
        where = "no cloud-free scene pair covered this area, so the model saw nothing here."
    else:
        where = (f"{out['new_water_m2']:,} m² of new surface water, {frac:.2%} of the observed part of this area "
                 f"({out['frac_observed']:.0%} of it observed).")
    out["narrative"] = f"Experimental: {_scene_sentence(tags)}: {where} {CAVEAT}"
    out["headline_value"] = f"{frac:.2%} new water (observed part)"
    return out


def layer_geojson(lat: float, lon: float, r: float = 1500) -> dict:
    """New-water pixels within `r` m of a point as GeoJSON polygons, for the map."""
    import geopandas as gpd
    import rasterio
    from rasterio.features import shapes
    from rasterio.windows import from_bounds
    from shapely.geometry import Point, shape

    tif, _ = _paths()
    if not tif.exists():
        return {"type": "FeatureCollection", "features": []}
    with rasterio.open(tif) as src:
        c = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        win = from_bounds(c.x - r, c.y - r, c.x + r, c.y + r, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win, boundless=True, fill_value=255)
        tr = src.window_transform(win)
        geoms = [shape(g) for g, v in shapes(a, mask=a == 1, transform=tr) if v == 1]
        crs = src.crs
    if not geoms:
        return {"type": "FeatureCollection", "features": []}
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs).to_crs("EPSG:4326")
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": g.__geo_interface__} for g in gdf.geometry]}
