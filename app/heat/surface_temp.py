"""Summer land surface temperature at a place, from Landsat.

Reads data/heat/surface_temp.tif, baked by scripts/bake_surface_temperature.py:
one band per clear summer image, each cell's surface temperature as a
difference from the city's land average in the same image (tenths of a
degree Fahrenheit, 90 m cells). The images and their city averages are in
data/heat/surface_temp.json.

Two traps the sentence carries:

  * surface temperature is not air temperature. A black roof reads 140 F
    while the air above it is 90 F, and a tree canopy reads near air
    temperature. The sentence says what was measured;
  * one image is one late morning. The value is the mean over every clear
    image, with the range image by image beside it, so a reader sees how
    steady the place's standing is.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "data" / "heat"
RADIUS_M = 150  # the thermal sensor samples at 100 m; a 150 m circle is the area of about nine 90 m cells
MIN_CELLS = 3  # cells' worth of ground an image must have seen (by area inside the shape)
MIN_IMAGES = 5
TRAP = ("This is the temperature of roofs, pavement and treetops seen from orbit on clear late mornings, "
        "not the air temperature a person feels.")


@lru_cache(maxsize=1)
def meta() -> dict | None:
    path = DIR / "surface_temp.json"
    return json.loads(path.read_text()) if path.exists() else None


def _diff(x: float) -> str:
    """'at 6.2°F warmer than', 'at 1.4°F cooler than', 'within half a degree of'."""
    return "within half a degree of" if abs(x) < 0.5 else f"at {abs(x):.1f}°F {'warmer' if x > 0 else 'cooler'} than"


FINE = 9  # sub-cells per side when weighing a cell by its share inside a shape (10 m for 90 m cells)


def _coverage(geom, transform, shape):
    """(H, W) share of each cell inside the shape. A 150 m circle touches
    cells whose far edge is 240 m out; counting those whole once made the
    reading cover a wider patch than its sentence states. A large area is
    read by cell centres, where the edge does not matter."""
    from rasterio.features import rasterize
    from rasterio.transform import Affine

    h, w = shape
    if h * w > 2500:
        return rasterize([(geom, 1)], out_shape=shape, transform=transform, fill=0, dtype="uint8").astype("float32")
    fine = rasterize([(geom, 1)], out_shape=(h * FINE, w * FINE), transform=transform @ Affine.scale(1 / FINE), fill=0,
                     dtype="uint8")
    return fine.reshape(h, FINE, w, FINE).mean(axis=(1, 3)).astype("float32")


def _summary(geom_4326, where: str) -> dict | None:
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.mask import raster_geometry_mask

    m = meta()
    if m is None:
        return None
    with rasterio.open(DIR / "surface_temp.tif") as src:
        g = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(src.crs).iloc[0]
        try:
            _, _, window = raster_geometry_mask(src, [g], crop=True, all_touched=True)
        except ValueError:  # the shape does not touch the raster
            return None
        a = src.read(window=window).astype("float32")
        a[a == src.nodata] = np.nan
        weight = _coverage(g, src.window_transform(window), a.shape[1:])
    # Per image: the mean over the place, each cell weighted by the share of it
    # inside the shape, when the image saw enough of the place.
    valid = ~np.isnan(a)
    seen = (valid * weight).sum(axis=(1, 2))
    most = float(seen.max()) if seen.size else 0.0
    if most < MIN_CELLS:
        return None
    ok = seen >= max(MIN_CELLS, 0.8 * most)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_image = (np.nan_to_num(a) * weight).sum(axis=(1, 2)) / seen / 10
    diffs = [(img, float(d)) for img, d, k in zip(m["images"], per_image, ok, strict=True) if k]
    if len(diffs) < MIN_IMAGES:
        return None
    values = [d for _, d in diffs]
    mean, lo, hi = round(sum(values) / len(values), 1), round(min(values), 1), round(max(values), 1)
    last_img, last_d = diffs[-1]
    first, last = diffs[0][0]["time_utc"][:10], last_img["time_utc"][:10]
    latest_f = round(last_img["city_land_mean_f"] + last_d, 1)
    if lo >= 0 or hi <= 0:  # a rounded 0.0 reads "from 0.0 to 4.7°F warmer", not "0.0°F cooler"
        spread = f"image by image it ran from {abs(lo if hi > 0 else hi):.1f} to {abs(hi if hi > 0 else lo):.1f}°F " \
                 f"{'warmer' if hi > 0 else 'cooler'}"
    else:
        spread = f"image by image it ran from {abs(lo):.1f}°F cooler to {hi:.1f}°F warmer"
    narrative = (f"Landsat measured the surface of {where} {_diff(mean)} the city's land average, over "
                 f"{len(diffs)} clear summer images from {first} to {last}, each taken at {m['local_time']}; {spread}. "
                 f"In the latest image, on {last}, the surface here read {latest_f}°F against a city average of "
                 f"{last_img['city_land_mean_f']}°F. {TRAP}")
    return {"mean_diff_f": mean, "min_diff_f": lo, "max_diff_f": hi, "n_images": len(diffs), "first": first, "last": last,
            "latest_surface_f": latest_f, "latest_city_mean_f": last_img["city_land_mean_f"],
            "warmer_in_every_image": lo > 0, "cooler_in_every_image": hi < 0,
            "narrative": narrative, "headline_value": f"{mean:+.1f}°F against the city's land average"}


def for_point(lat: float, lon: float, radius_m: float = RADIUS_M) -> dict | None:
    from app.eo.landcover import _circle

    out = _summary(_circle(lat, lon, radius_m), f"the ground within {radius_m:.0f} m of this address")
    return out and {**out, "radius_m": radius_m}


def for_polygon(polygon) -> dict | None:
    return _summary(polygon, "this area")
