"""Experimental: new surface water after rain, from the Prithvi-EO batch.

Reads the saved outputs of scripts/run_eo_batch.py in data/eo/: one 10 m
raster per rain event (1 = water after the storm that was not water
before, 0 = no new water, 255 = sea, or no cloud-free scene pair saw the
pixel). Nothing is inferred per request and no model runs here.

One thing is answered, through `app.experimental.hedge`: what the
satellite model showed near a place after Hurricane Ida, and after which
of the other saved storms it showed any new water there.

It does not say a place is prone to standing water. That was tried: land
that showed new water after two or more storms was less likely than
average land to lie in the city's own stormwater flood map, and it
clustered on wooded hills (shadow, not water). docs/MODELS.md has the
numbers.

Street and basement flooding drains within hours and is not visible at
10 to 20 m a day later, so no water here is not evidence of no flooding.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app import experimental

EO_DIR = Path(os.environ.get("RIPRAP_EO_DIR", Path(__file__).resolve().parents[2] / "data" / "eo"))
IDA = "2021-09-01"
MODEL = experimental.MODELS["water"].repo


def _event_tif(event: str) -> Path:
    return EO_DIR / f"prithvi_new_water_{event}.tif"


def events() -> list[str]:
    """The rain dates with a saved raster, oldest first."""
    return sorted(p.stem[-10:] for p in EO_DIR.glob("prithvi_new_water_*.tif"))


def _tags(path: Path) -> dict:
    return _tags_at(path, path.stat().st_mtime)


@lru_cache(maxsize=32)
def _tags_at(path: Path, mtime: float) -> dict:  # a raster rewritten by the batch is read again
    import rasterio

    with rasterio.open(path) as src:
        return src.tags()


def _dates(ids: str) -> str:
    """'S2A_MSIL2A_20210902T154911_R054_T18TWL_...;...' -> '2021-09-02'."""
    days = sorted({i.split("_")[2][:8] for i in ids.split(";") if i.count("_") >= 2})
    return ", ".join(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in days)


def _read(path: Path, geom_4326, band: int = 1):
    """(array, pixel area m2) for one band inside a WGS84 geometry; pixels
    outside the geometry are 254."""
    import geopandas as gpd
    import rasterio
    from rasterio.mask import raster_geometry_mask

    with rasterio.open(path) as src:
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        outside, _, window = raster_geometry_mask(src, [g], crop=True)
        arr = src.read(band, window=window)  # raw: 255 (not observed) must stay apart from 254
        arr[outside] = 254
        return arr, abs(src.transform.a * src.transform.e)


def _circle(lat: float, lon: float, radius_m: float):
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32618").buffer(radius_m) \
        .to_crs("EPSG:4326").iloc[0]


def _summary(geom, where: str) -> dict | None:
    """New water after Ida inside a geometry, and the other saved storms
    that showed any. `where` names the place in the sentence."""
    import numpy as np

    tif = _event_tif(IDA)
    if not tif.exists():
        return None
    a, px = _read(tif, geom)
    inside = a != 254
    new_m2, obs_m2, total_m2 = float(np.sum(a == 1)) * px, float(np.sum(inside & (a != 255))) * px, float(np.sum(inside)) * px
    tags = _tags(tif)
    others = []
    for e in events():
        if e == IDA:
            continue
        b, _ = _read(_event_tif(e), geom)
        if np.any((b != 254) & (b != 255)):  # the storm's scenes saw this place
            others.append({"rain_date": e, "new_water_m2": round(float(np.sum(b == 1)) * px)})
    wet = [o["rain_date"] for o in others if o["new_water_m2"]]
    out = {"new_water_m2": round(new_m2), "frac_observed": round(obs_m2 / total_m2, 3) if total_m2 else 0.0,
           "frac_new_water": round(new_m2 / obs_m2, 5) if obs_m2 else 0.0,
           "post_scene": tags.get("post_scene"), "pre_scene": tags.get("pre_scene"), "model": MODEL,
           "rain_date": tags.get("rain_date", IDA), "batch_run": tags.get("batch_run"), "other_events": others}
    if not obs_m2:
        statement = f"no cloud-free scene pair covered {where} after Hurricane Ida, so the satellite model saw nothing here"
    else:
        statement = (f"a satellite model on Sentinel-2 scenes from {_dates(tags.get('post_scene', ''))}, the day after "
                     f"Hurricane Ida, compared with {_dates(tags.get('pre_scene', ''))}, showed {out['new_water_m2']:,} m² "
                     f"of new surface water {where} ({out['frac_observed']:.0%} of it observed)")
    if others:
        statement += (f"; of {len(others)} other heavy-rain events since 2017 with a clear pass over this place, it "
                      f"showed new water after {len(wet)}" + (f" ({', '.join(wet)})" if wet else ""))
    out["narrative"] = experimental.hedge("water", statement)
    out["headline_value"] = f"{out['new_water_m2']:,} m² new water after Ida"
    return out


def summary_for_point(lat: float, lon: float, radius_m: float = 500) -> dict | None:
    out = _summary(_circle(lat, lon, radius_m), f"within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def summary_for_polygon(polygon) -> dict | None:
    return _summary(polygon, "in this area")
