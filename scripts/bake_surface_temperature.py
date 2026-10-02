"""Bake summer land surface temperature over New York City from Landsat.

Data only, no model. For every clear Landsat 8 or 9 pass of the last
summers it reads the Collection 2 Level 2 surface temperature band (USGS,
via Microsoft Planetary Computer) and saves, per 90 m cell, how much warmer
or cooler the surface was than the city's land average in the same image.

Why a difference and not a temperature: the city's average surface runs from
about 85 F on a mild June morning to over 105 F in a July heat wave, so two
images are not comparable as temperatures. Where a block sits against the
city's average in the same image is, and the app reports that, image by
image.

The rule for which images count, fixed before reading any:

  * Landsat 8 and 9, Tier 1 scenes, WRS row 032 (paths 013 and 014 each
    cover the whole city), 1 June to 10 September, scene cloud cover under
    20%. (Tier 1 was added after the first run: the one Tier 2 scene that
    passed the cloud rule, 2026-08-17, gave the city a mean surface of 67 F
    in August, which is cloud its quality band did not flag. USGS keeps
    Tier 2 for scenes that miss its geometric and radiometric standard.);
  * a pixel counts when QA_PIXEL has none of fill, dilated cloud, cirrus,
    cloud or cloud shadow;
  * an image counts when at least 95% of the city's land cells have a clear
    view (a cell needs five of its nine 30 m pixels).

Kelvin = digital number x 0.00341802 + 149.0 (the collection's scale and
offset, checked against each asset's raster:bands). The thermal sensor's
own sampling is 100 m; USGS resamples it to 30 m, and 90 m cells keep what
the sensor resolved.

    uv sync --extra eo
    uv run python scripts/bake_surface_temperature.py --years 2023 2024 2025 2026

Writes data/heat/surface_temp.tif (one band per image: tenths of a degree
Fahrenheit above the city's land mean of that image, -32768 = no clear
view) and data/heat/surface_temp.json (the images, their times and their
city means). Scenes are cached under outputs/landsat/ (git-ignored).

It also draws the map overlay the heat briefing shows: the mean difference
over all images on the city's land, as web/sveltekit/static/heat/surface.png
(Web Mercator) with its corner coordinates and colour stops in
surface.json beside it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NYC_BBOX = [-74.26, 40.49, -73.69, 40.92]
OUT = ROOT / "data" / "heat"
CACHE = ROOT / "outputs" / "landsat"
SCALE, OFFSET = 0.00341802, 149.0
UNCLEAR = 0b11111  # QA_PIXEL bits 0 to 4: fill, dilated cloud, cirrus, cloud, cloud shadow
MIN_CLEAR_LAND = 0.95
NODATA = -32768


def scenes(years: list[int], max_cloud: float = 20.0) -> list:
    import planetary_computer as pc
    from pystac_client import Client

    from app.eo.prithvi import STAC_URL

    client = Client.open(STAC_URL, modifier=pc.sign_inplace)
    out = []
    for year in years:
        out += client.search(
            collections=["landsat-c2-l2"], bbox=NYC_BBOX, datetime=f"{year}-06-01/{year}-09-10",
            query={"eo:cloud_cover": {"lt": max_cloud}, "platform": {"in": ["landsat-8", "landsat-9"]},
                   "landsat:wrs_row": {"eq": "032"}}).items()
    return sorted(out, key=lambda it: it.datetime)


def kelvin_90m(item, ref30):
    """(H/3, W/3) kelvin, NaN where fewer than five of nine pixels are clear."""
    import numpy as np

    from app.eo.prithvi import read_band

    cache = CACHE / f"{item.id}.npz"
    if cache.exists():
        z = np.load(cache)
        dn, qa = z["dn"], z["qa"]
    else:
        band = item.assets["lwir11"].extra_fields["raster:bands"][0]
        if (band["scale"], band["offset"]) != (SCALE, OFFSET):
            raise RuntimeError(f"{item.id}: scale {band['scale']} offset {band['offset']}, expected {SCALE} {OFFSET}")
        dn = read_band(item, "lwir11", ref30, resampling="nearest")
        qa = read_band(item, "qa_pixel", ref30, resampling="nearest")
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, dn=dn, qa=qa)
    k = np.where((dn > 0) & ((qa & UNCLEAR) == 0), dn * SCALE + OFFSET, np.nan).astype("float32")
    h, w = k.shape[0] // 3 * 3, k.shape[1] // 3 * 3
    blocks = k[:h, :w].reshape(h // 3, 3, w // 3, 3)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(blocks, axis=(1, 3))
    return np.where((~np.isnan(blocks)).sum(axis=(1, 3)) >= 5, mean, np.nan)


OVERLAY = ROOT / "web" / "sveltekit" / "static" / "heat"
# Degrees F against the city's land mean -> colour: the briefing's blue for
# cooler, paper for the mean, the warning amber and alert red for warmer.
STOPS = ((-12, (0, 94, 162)), (-4, (140, 184, 214)), (0, (244, 246, 249)), (4, (222, 170, 110)), (8, (146, 64, 14)),
         (14, (185, 28, 28)))


def write_overlay(a, land, crs, transform, meta: dict) -> None:
    """The mean difference over the images, coloured and warped to Web
    Mercator for the map; transparent off the city's land."""
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

    mean = np.where(a == NODATA, np.nan, a).astype("float32")
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(mean, axis=0) / 10
    mean[~land] = np.nan
    h, w = mean.shape
    bounds = rasterio.transform.array_bounds(h, w, transform)
    t2, w2, h2 = calculate_default_transform(crs, "EPSG:3857", w, h, *bounds)
    out = np.full((h2, w2), np.nan, "float32")
    reproject(mean, out, src_transform=transform, src_crs=crs, dst_transform=t2, dst_crs="EPSG:3857",
              src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    xs = [s for s, _ in STOPS]
    rgba = np.zeros((4, h2, w2), "uint8")
    for i in range(3):
        rgba[i] = np.interp(np.nan_to_num(out), xs, [c[i] for _, c in STOPS]).astype("uint8")
    rgba[3] = np.where(np.isnan(out), 0, 190)
    OVERLAY.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OVERLAY / "surface.png", "w", driver="PNG", dtype="uint8", count=4, height=h2, width=w2) as dst:
        dst.write(rgba)
    for aux in OVERLAY.glob("surface.png.aux.xml"):
        aux.unlink()
    west, south, east, north = transform_bounds("EPSG:3857", "EPSG:4326", *rasterio.transform.array_bounds(h2, w2, t2))
    (OVERLAY / "surface.json").write_text(json.dumps({
        "image": "surface.png",
        "coordinates": [[round(west, 6), round(north, 6)], [round(east, 6), round(north, 6)],
                        [round(east, 6), round(south, 6)], [round(west, 6), round(south, 6)]],
        "stops_f": [{"diff_f": s, "rgb": list(c)} for s, c in STOPS],
        "what": "Mean summer surface temperature against the city's land average, Landsat 8 and 9",
        "n_images": meta["n_images"], "first": meta["first"], "last": meta["last"]}, indent=1) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="+", type=int, required=True)
    args = ap.parse_args()

    import numpy as np
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import Affine

    from app.areas import nta
    from app.eo import prithvi

    ref30 = prithvi.grid(NYC_BBOX, res=30.0)
    h, w = ref30.shape[0] // 3, ref30.shape[1] // 3
    # Landsat's pixel centres sit on multiples of 30 m and this grid's cell edges do, so the nearest pixel to
    # each cell centre is the one half a pixel east and south of it. The transform says where the data is.
    # (Found by an independent key: every reading matched the ground 15 m east and south of its circle.)
    t90 = ref30.rio.transform() * Affine.translation(0.5, 0.5) * Affine.scale(3)
    # The city's land: inside a 2020 neighborhood tabulation area.
    land = rasterize([(g, 1) for g in nta.load().to_crs(ref30.rio.crs).geometry], out_shape=(h, w), transform=t90,
                     fill=0, dtype="uint8") == 1
    bands, kept, skipped = [], [], []
    for it in scenes(args.years):
        k = kelvin_90m(it, ref30)
        clear = float((~np.isnan(k[land])).mean())
        tier = it.properties.get("landsat:collection_category")
        row = {"id": it.id, "tier": tier, "time_utc": it.datetime.strftime("%Y-%m-%dT%H:%M:%SZ"), "platform": it.properties["platform"],
               "scene_cloud_cover_pct": round(it.properties["eo:cloud_cover"], 1), "clear_land_pct": round(100 * clear, 1)}
        if clear < MIN_CLEAR_LAND or tier != "T1":
            skipped.append(row)
            print(f"skip {it.id}: {clear:.1%} of land clear, tier {tier}", flush=True)
            continue
        city_k = float(np.nanmean(k[land]))
        dev_f = (k - city_k) * 1.8
        bands.append(np.where(np.isnan(dev_f), NODATA, np.round(dev_f * 10)).astype("int16"))
        kept.append({**row, "city_land_mean_f": round((city_k - 273.15) * 1.8 + 32, 1)})
        print(f"keep {it.id}: city land mean {kept[-1]['city_land_mean_f']} F, {clear:.1%} clear", flush=True)
    if not bands:
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    a = np.stack(bands)
    # Land only: the sentence compares "the ground" with the city's land average, and a pier's circle that took
    # in the river once read 5°F cooler than its ground.
    a[:, ~land] = NODATA
    with rasterio.open(OUT / "surface_temp.tif", "w", driver="COG", dtype="int16", count=len(a), height=h, width=w,
                       crs=ref30.rio.crs, transform=t90, compress="deflate",
                       predictor=2, nodata=NODATA) as dst:
        dst.write(a)
        dst.descriptions = tuple(s["time_utc"][:10] for s in kept)
        dst.update_tags(units="tenths of a degree Fahrenheit above the city's land mean in the same image",
                        source="Landsat Collection 2 Level 2 surface temperature (USGS), band lwir11", batch_run=str(date.today()))
    # How far a place's standing moves from image to image: for every land cell
    # seen in all images, the spread (max minus min) of its difference from the city mean.
    full = np.all(a != NODATA, axis=0) & land
    spread = (a[:, full].max(0) - a[:, full].min(0)) / 10
    report = {
        "what": __doc__.split("\n\n")[0], "run_date": str(date.today()),
        "source": "Landsat Collection 2 Level 2 Science Products, surface temperature (USGS), via Microsoft Planetary Computer",
        "rule": {"months": "1 June to 10 September", "tier": "T1", "max_scene_cloud_pct": 20, "min_clear_land_pct": 100 * MIN_CLEAR_LAND,
                 "cell_m": 90, "kelvin": f"DN x {SCALE} + {OFFSET}"},
        "years": args.years, "images": kept, "skipped": skipped,
        "first": kept[0]["time_utc"][:10], "last": kept[-1]["time_utc"][:10], "n_images": len(kept),
        "local_time": "about 11:35 am Eastern Daylight Time",
        "cell_spread_f_median": round(float(np.median(spread)), 1),
        "cell_spread_f_p90": round(float(np.percentile(spread, 90)), 1),
        "land_cells": int(land.sum()), "land_cells_clear_in_every_image": int(full.sum()),
    }
    (OUT / "surface_temp.json").write_text(json.dumps(report, indent=1) + "\n")
    write_overlay(a, land, ref30.rio.crs, t90, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("images", "skipped")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
