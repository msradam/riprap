"""Batch earth-observation run: Prithvi-EO surface water after a rain event.

Runs offline, never per request. Writes a Cloud Optimized GeoTIFF of new
surface water and a small GeoParquet summary per 2020 NTA, for the app to
read as precomputed layers.

    uv sync --extra eo
    uv run python scripts/run_eo_batch.py --rain-date 2021-09-01 \\
        --bbox -73.83 40.69 -73.75 40.73 --out data/eo

Method (the constraints the per-request layer lacked):
  * post scene: the least cloudy Sentinel-2 L2A scene within 48 h after
    the rain; the run stops if there is none;
  * pre scene: the least cloudy scene in the 30 days before, read on the
    same grid, whose water is treated as permanent (rivers, harbour, ponds);
  * new water = water after and not water before.

Street and basement flooding usually drains within hours and cannot be
seen at 10 to 20 m, so an empty result is not evidence of no flooding.
Outputs are experimental: the model has no flood-detection score on
held-out events.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rain-date", required=True, type=date.fromisoformat,
                    help="day the rain event ended (UTC)")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--max-cloud", type=float, default=30.0)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "eo")
    args = ap.parse_args()

    import geopandas as gpd
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import shape

    from app.areas import nta
    from app.eo import prithvi

    rain = datetime.combine(args.rain_date, datetime.min.time())
    post = prithvi.search_scenes(args.bbox, rain.isoformat() + "Z",
                                 (rain + timedelta(hours=48)).isoformat() + "Z", args.max_cloud)
    if not post:
        print(f"No Sentinel-2 scene under {args.max_cloud}% cloud within 48 h after "
              f"{args.rain_date}; nothing written.")
        return 1
    pre = prithvi.search_scenes(args.bbox, (rain - timedelta(days=30)).isoformat() + "Z",
                                rain.isoformat() + "Z", args.max_cloud)
    if not pre:
        print("No clear pre-event scene in the 30 days before; cannot mask permanent water.")
        return 1
    post_item, pre_item = post[0], pre[0]
    print(f"post {post_item.id} ({post_item.properties.get('eo:cloud_cover')}% cloud), "
          f"pre {pre_item.id}", flush=True)

    post_img, ref = prithvi.read_bands(post_item, args.bbox)
    pre_img, _ = prithvi.read_bands(pre_item, args.bbox, match=ref)
    new_water = ((prithvi.water_mask(post_img) == 1) & (prithvi.water_mask(pre_img) == 0))
    new_water = new_water.astype("uint8")

    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"prithvi_new_water_{args.rain_date.isoformat()}"
    tif = args.out / f"{stem}.tif"
    profile = {"driver": "COG", "dtype": "uint8", "count": 1, "height": new_water.shape[0],
               "width": new_water.shape[1], "crs": ref.rio.crs, "transform": ref.rio.transform(),
               "compress": "deflate", "nodata": 255}
    with rasterio.open(tif, "w", **profile) as dst:
        dst.write(new_water, 1)
        dst.update_tags(rain_date=str(args.rain_date), post_scene=post_item.id,
                        pre_scene=pre_item.id, model=prithvi.REPO, maturity="experimental")

    water = gpd.GeoDataFrame(
        geometry=[shape(g) for g, _ in shapes(new_water, mask=new_water.astype(bool),
                                              transform=ref.rio.transform())],
        crs=ref.rio.crs)
    ntas = nta.load().to_crs(ref.rio.crs)
    box = gpd.GeoSeries.from_xy([args.bbox[0], args.bbox[2]], [args.bbox[1], args.bbox[3]],
                                crs="EPSG:4326").to_crs(ref.rio.crs).total_bounds
    ntas = ntas.cx[box[0]:box[2], box[1]:box[3]].copy()
    ntas["new_water_m2"] = [float(water.clip(g).area.sum()) if len(water) else 0.0
                            for g in ntas.geometry]
    ntas["frac_new_water"] = (ntas["new_water_m2"] / ntas.geometry.area).round(5)
    summary = ntas[["nta2020", "ntaname", "boroname", "new_water_m2", "frac_new_water", "geometry"]]
    summary = summary.assign(rain_date=str(args.rain_date), post_scene=post_item.id,
                             pre_scene=pre_item.id, model=prithvi.REPO, maturity="experimental")
    parquet = args.out / f"{stem}_by_nta.parquet"
    summary.to_crs("EPSG:4326").to_parquet(parquet)
    print(json.dumps({"cog": str(tif), "summary": str(parquet),
                      "new_water_pixels": int(new_water.sum()),
                      "ntas": int(len(summary))}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
