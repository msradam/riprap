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
  * new water = water after and not water before, only where both scenes
    have a clear view in the Sentinel-2 scene classification (SCL) layer:
    cloud, cloud shadow, cirrus and saturated pixels count as unobserved.

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
    import numpy as np
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import shape

    from app.areas import nta
    from app.eo import prithvi

    rain = datetime.combine(args.rain_date, datetime.min.time())
    post_all = prithvi.search_scenes(args.bbox, rain.isoformat() + "Z",
                                     (rain + timedelta(hours=48)).isoformat() + "Z", args.max_cloud)
    if not post_all:
        print(f"No Sentinel-2 scene under {args.max_cloud}% cloud within 48 h after "
              f"{args.rain_date}; nothing written.")
        return 1
    pre_all = prithvi.search_scenes(args.bbox, (rain - timedelta(days=30)).isoformat() + "Z",
                                    rain.isoformat() + "Z", args.max_cloud)
    # NYC spans several Sentinel-2 tiles. Pair each tile's least cloudy post
    # scene with the same tile's least cloudy pre scene (the same relative
    # orbit first, for an identical footprint), and read every pair onto one
    # 10 m grid over the box. A pixel no pair observed is nodata (255).
    pairs = []
    for tile in dict.fromkeys(it.properties["s2:mgrs_tile"] for it in post_all):
        post = next(it for it in post_all if it.properties["s2:mgrs_tile"] == tile)
        same = [it for it in pre_all if it.properties["s2:mgrs_tile"] == tile]
        orbit = [it for it in same if it.properties.get("sat:relative_orbit") == post.properties.get("sat:relative_orbit")]
        if orbit or same:
            pairs.append((post, (orbit or same)[0]))
    if not pairs:
        print("No clear pre-event scene of the same tile in the 30 days before; cannot mask permanent water.")
        return 1
    ref = prithvi.grid(args.bbox)
    new_water = np.zeros(ref.shape, dtype="uint8")
    observed = np.zeros(ref.shape, dtype=bool)
    for post_item, pre_item in pairs:
        print(f"tile {post_item.properties['s2:mgrs_tile']}: post {post_item.id} "
              f"({post_item.properties.get('eo:cloud_cover'):.1f}% cloud), pre {pre_item.id}", flush=True)
        post_img, _ = prithvi.read_bands(post_item, args.bbox, match=ref)
        pre_img, _ = prithvi.read_bands(pre_item, args.bbox, match=ref)
        # Observed = both scenes have data and a clear view (no cloud, shadow or
        # saturation in the scene classification layer).
        valid = ((post_img.sum(0) > 0) & (pre_img.sum(0) > 0) & ~observed
                 & prithvi.clear_mask(post_item, args.bbox, ref) & prithvi.clear_mask(pre_item, args.bbox, ref))
        new = (prithvi.water_mask(post_img) == 1) & (prithvi.water_mask(pre_img) == 0) & valid
        new_water[new] = 1
        observed |= valid
    new_water[~observed] = 255
    post_ids = ";".join(p.id for p, _ in pairs)
    pre_ids = ";".join(q.id for _, q in pairs)
    print(f"observed {observed.mean():.1%} of the box", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"prithvi_new_water_{args.rain_date.isoformat()}"
    tif = args.out / f"{stem}.tif"
    profile = {"driver": "COG", "dtype": "uint8", "count": 1, "height": new_water.shape[0],
               "width": new_water.shape[1], "crs": ref.rio.crs, "transform": ref.rio.transform(),
               "compress": "deflate", "nodata": 255}
    with rasterio.open(tif, "w", **profile) as dst:
        dst.write(new_water, 1)
        dst.update_tags(rain_date=str(args.rain_date), batch_run=str(date.today()), post_scene=post_ids,
                        pre_scene=pre_ids, model=prithvi.REPO, maturity="experimental")

    water = gpd.GeoDataFrame(
        geometry=[shape(g) for g, _ in shapes(new_water, mask=new_water == 1,
                                              transform=ref.rio.transform())],
        crs=ref.rio.crs)
    ntas = nta.load().to_crs(ref.rio.crs)
    box = gpd.GeoSeries.from_xy([args.bbox[0], args.bbox[2]], [args.bbox[1], args.bbox[3]],
                                crs="EPSG:4326").to_crs(ref.rio.crs).total_bounds
    ntas = ntas.cx[box[0]:box[2], box[1]:box[3]].copy()
    ntas["new_water_m2"] = [float(water.clip(g).area.sum()) if len(water) else 0.0
                            for g in ntas.geometry]
    ntas["frac_new_water"] = (ntas["new_water_m2"] / ntas.geometry.area).round(5)
    # The share of each NTA that a scene pair observed: 0 means no evidence either way.
    obs = gpd.GeoDataFrame(
        geometry=[shape(g) for g, _ in shapes(observed.astype("uint8"), mask=observed,
                                              transform=ref.rio.transform())], crs=ref.rio.crs)
    ntas["frac_observed"] = [round(float(obs.clip(g).area.sum()) / g.area, 3) if len(obs) else 0.0
                             for g in ntas.geometry]
    summary = ntas[["nta2020", "ntaname", "boroname", "new_water_m2", "frac_new_water", "frac_observed",
                    "geometry"]]
    summary = summary.assign(rain_date=str(args.rain_date), post_scene=post_ids,
                             pre_scene=pre_ids, model=prithvi.REPO, maturity="experimental")
    parquet = args.out / f"{stem}_by_nta.parquet"
    summary.to_crs("EPSG:4326").to_parquet(parquet)
    print(json.dumps({"cog": str(tif), "summary": str(parquet),
                      "new_water_pixels": int((new_water == 1).sum()),
                      "observed_share": round(float(observed.mean()), 3), "pairs": len(pairs),
                      "ntas": int(len(summary))}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
