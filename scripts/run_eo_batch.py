"""Batch earth-observation run: Prithvi-EO surface water after rain (experimental).

Runs offline, never per request. For each rain event it writes a Cloud
Optimized GeoTIFF of new surface water over the city's land for the app
to read, and it scores the result (data/experimental/water.json).

    uv sync --extra eo
    uv run python scripts/run_eo_batch.py --rain-date 2021-09-01
    uv run python scripts/run_eo_batch.py --heavy-rain-since 2017 --min-inches 1.5
    uv run python scripts/run_eo_batch.py --evaluate-only

Method:
  * post scene: the least cloudy Sentinel-2 L2A scene on one of the two
    days after the rain day; an event with none is skipped;
  * pre scene: the least cloudy scene of the same tile in the 30 days
    before, read on the same grid, whose water is treated as permanent
    (rivers, harbour, ponds);
  * new water = water after and not water before, on land, only where both
    scenes have a clear view in the Sentinel-2 scene classification (SCL)
    layer: cloud, cloud shadow, cirrus and saturated pixels count as
    unobserved.

Street and basement flooding usually drains within hours and cannot be
seen at 10 to 20 m, so an empty result is not evidence of no flooding.
Shadow moves between the two scenes and can read as new water. The
model's labels were its base model's own output for Hurricane Ida.
Outputs are experimental (docs/MODELS.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NYC_BBOX = [-74.26, 40.49, -73.69, 40.92]
RAIN_URL = "https://www.ncei.noaa.gov/access/services/data/v1"  # NOAA daily summaries, Central Park


def heavy_rain_days(since: int, min_inches: float) -> list[tuple[date, float]]:
    """Days at Central Park (GHCN USW00094728) with at least `min_inches`
    of rain. Consecutive days are one event, dated by its last day, with
    the event's total."""
    import httpx

    r = httpx.get(RAIN_URL, params={"dataset": "daily-summaries", "stations": "USW00094728", "dataTypes": "PRCP",
                                    "startDate": f"{since}-01-01", "endDate": str(date.today()), "units": "standard",
                                    "format": "json"}, timeout=60)
    r.raise_for_status()
    wet = sorted((date.fromisoformat(d["DATE"]), float(d["PRCP"])) for d in r.json()
                 if d.get("PRCP") not in (None, "") and float(d["PRCP"]) >= min_inches)
    events: list[tuple[date, float]] = []
    for day, inches in wet:
        if events and (day - events[-1][0]).days <= 1:
            events[-1] = (day, round(events[-1][1] + inches, 2))
        else:
            events.append((day, inches))
    return events


def land_mask(ref):
    """True on the city's land: inside a 2020 neighborhood tabulation area."""
    from rasterio.features import rasterize

    from app.areas import nta

    shapes = [(g, 1) for g in nta.load().to_crs(ref.rio.crs).geometry]
    return rasterize(shapes, out_shape=ref.shape, transform=ref.rio.transform(), fill=0, dtype="uint8") == 1


def run_event(rain_date: date, bbox: list[float], out: Path, max_cloud: float) -> dict | None:
    """One event: write its new-water raster and return a summary, or None
    when no scene pair observed it."""
    import numpy as np
    import rasterio

    from app.eo import prithvi

    day = datetime.combine(rain_date, datetime.min.time())
    post_all = prithvi.search_scenes(bbox, (day + timedelta(days=1)).isoformat() + "Z",
                                     (day + timedelta(days=3)).isoformat() + "Z", max_cloud)
    if not post_all:
        print(f"{rain_date}: no Sentinel-2 scene under {max_cloud}% cloud in the two days after; skipped", flush=True)
        return None
    pre_all = prithvi.search_scenes(bbox, (day - timedelta(days=30)).isoformat() + "Z", day.isoformat() + "Z", max_cloud)
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
        print(f"{rain_date}: no clear scene of the same tile in the 30 days before; skipped", flush=True)
        return None
    ref = prithvi.grid(bbox)
    new_water = np.zeros(ref.shape, dtype="uint8")
    observed = np.zeros(ref.shape, dtype=bool)
    for post_item, pre_item in pairs:
        print(f"{rain_date} tile {post_item.properties['s2:mgrs_tile']}: post {post_item.id} "
              f"({post_item.properties.get('eo:cloud_cover'):.1f}% cloud), pre {pre_item.id}", flush=True)
        post_img, pre_img = prithvi.read_bands(post_item, ref), prithvi.read_bands(pre_item, ref)
        # Observed = both scenes have data and a clear view (no cloud, shadow or
        # saturation in the scene classification layer).
        valid = ((post_img.sum(0) > 0) & (pre_img.sum(0) > 0) & ~observed
                 & prithvi.clear_mask(post_item, ref) & prithvi.clear_mask(pre_item, ref))
        if not valid.any():
            continue
        new = (prithvi.water_mask(post_img) == 1) & (prithvi.water_mask(pre_img) == 0) & valid
        new_water[new] = 1
        observed |= valid
    # Land only: "new water" over the harbour is the tide or a missed pixel
    # of the earlier scene, and no place Riprap briefs is out there.
    observed &= land_mask(ref)
    if not observed.any():
        print(f"{rain_date}: every land pixel was cloud or shadow in one scene or the other; skipped", flush=True)
        return None
    new_water[~observed] = 255
    out.mkdir(parents=True, exist_ok=True)
    tif = out / f"prithvi_new_water_{rain_date.isoformat()}.tif"
    profile = {"driver": "COG", "dtype": "uint8", "count": 1, "height": new_water.shape[0],
               "width": new_water.shape[1], "crs": ref.rio.crs, "transform": ref.rio.transform(),
               "compress": "deflate", "nodata": 255}
    with rasterio.open(tif, "w", **profile) as dst:
        dst.write(new_water, 1)
        dst.update_tags(rain_date=str(rain_date), batch_run=str(date.today()), model=prithvi.REPO,
                        revision=prithvi.MODEL.revision, maturity="experimental",
                        post_scene=";".join(p.id for p, _ in pairs), pre_scene=";".join(q.id for _, q in pairs))
    return {"rain_date": str(rain_date), "cog": str(tif), "new_water_pixels": int((new_water == 1).sum()),
            "land_seen_share": round(float(observed.sum() / land_mask(ref).sum()), 3), "pairs": len(pairs)}


def ida_marks_score(a, transform, crs, radius_m: float = 500) -> dict:
    """Hold a water raster for Ida (1 water, 0 none, 255 unobserved) against
    the high-water marks USGS surveyed after the storm, and against chance:
    how many observed marks have water within `radius_m`, and what share of
    all the observed land lies that close to water."""
    import geopandas as gpd
    import rasterio
    from scipy.ndimage import distance_transform_edt

    marks = gpd.read_file(ROOT / "data" / "ida_2021_hwms_ny.geojson").to_crs(crs)
    rows, cols = rasterio.transform.rowcol(transform, marks.geometry.x.values, marks.geometry.y.values)
    res = transform.a
    seen = a != 255
    near = distance_transform_edt(a != 1) * res <= radius_m
    at = [(r, c) for r, c in zip(rows, cols, strict=True) if 0 <= r < a.shape[0] and 0 <= c < a.shape[1] and seen[r, c]]
    hit = sum(bool(near[r, c]) for r, c in at)
    out = {"n_marks": len(at), "n_marks_with_water": hit, "marks_pct": round(100 * hit / max(len(at), 1)),
           "chance_pct": round(100 * float(near[seen].mean())),
           "new_water_km2": round(float((a == 1).sum()) * res * res / 1e6, 2)}
    out["against_chance"] = "more than chance gives" if out["marks_pct"] > out["chance_pct"] else "no better than chance"
    return out


def evaluate(out: Path, report: Path) -> dict | None:
    """Hold the Ida layer against the high-water marks USGS surveyed after
    the storm, and against chance: how many marks have new water within
    500 m, and what share of all the land the model saw lies that close to
    new water. Then ask whether new water that recurs across storms marks
    flood-prone ground. Written to data/experimental/water.json, which the
    hedge on every satellite sentence quotes."""
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, reproject

    tif = out / "prithvi_new_water_2021-09-01.tif"
    if not tif.exists():
        return None
    with rasterio.open(tif) as src:
        a, tags, transform, crs = src.read(1), src.tags(), src.transform, src.crs
    res = transform.a
    from app.eo import prithvi

    n_land = int(land_mask(prithvi.grid(NYC_BBOX)).sum())
    seen = a != 255
    result = {"model": tags.get("model"), "revision": tags.get("revision"), "run_date": str(date.today()),
              "event": "2021-09-01", "post_scene": tags.get("post_scene"),
              # The fields the hedge sentence reads.
              **ida_marks_score(a, transform, crs),
              "land_seen_share": round(float(seen.sum() / n_land), 3)}
    events = {}
    n_new, n_seen = np.zeros(a.shape, "uint8"), np.zeros(a.shape, "uint8")
    for e in sorted(out.glob("prithvi_new_water_*.tif")):
        with rasterio.open(e) as src:
            b = src.read(1)
        events[e.stem[-10:]] = {"land_seen_share": round(float((b != 255).sum() / n_land), 3),
                                "new_water_share_of_seen": round(float((b == 1).sum() / max((b != 255).sum(), 1)), 5)}
        n_new += b == 1
        n_seen += b != 255
    result["events"] = events
    # Does new water that recurs mark flood-prone ground? Land with new water
    # after two or more storms (of at least three that saw it), held against
    # the city's own stormwater flood map (DEP moderate scenario, current sea level).
    often, twice = n_seen >= 3, (n_seen >= 3) & (n_new >= 2)
    with rasterio.open(ROOT / "data" / "baked" / "dep_moderate_current.tif") as src:
        dep = np.zeros(a.shape, "uint8")
        reproject(rasterio.band(src, 1), dep, dst_transform=transform, dst_crs=crs, resampling=Resampling.nearest)
    result["recurrence_check"] = {
        "recurrent_km2": round(float(twice.sum()) * res * res / 1e6, 2),
        "share_of_land_in_dep_flood_map_pct": round(100 * float((dep[often] > 0).mean()), 1),
        "share_of_recurrent_land_in_dep_flood_map_pct": round(100 * float((dep[twice] > 0).mean()), 1) if twice.any() else None,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=1) + "\n")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Prithvi-EO new surface water after rain events (experimental).")
    ap.add_argument("--rain-date", action="append", type=date.fromisoformat, default=[],
                    help="day the rain fell (repeatable)")
    ap.add_argument("--heavy-rain-since", type=int, help="run every heavy rain day at Central Park since this year")
    ap.add_argument("--min-inches", type=float, default=1.5)
    ap.add_argument("--evaluate-only", action="store_true", help="rescore the saved events, run none")
    ap.add_argument("--bbox", nargs=4, type=float, default=NYC_BBOX,
                    metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--max-cloud", type=float, default=30.0)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "eo")
    args = ap.parse_args()

    days = [(d, None) for d in args.rain_date]
    if args.heavy_rain_since:
        days += heavy_rain_days(args.heavy_rain_since, args.min_inches)
    results = []
    for day, inches in days:
        try:
            r = run_event(day, list(args.bbox), args.out, args.max_cloud)
        except Exception as e:  # noqa: BLE001 - one event's network failure must not stop the batch
            print(f"{day}: failed ({type(e).__name__}: {e}); skipped", flush=True)
            r = None
        if r:
            results.append({**r, "rain_inches": inches})
            print(json.dumps(results[-1]), flush=True)
    if list(args.bbox) == NYC_BBOX:
        print(json.dumps(evaluate(args.out, ROOT / "data" / "experimental" / "water.json"), indent=1))
    return 0 if results or args.evaluate_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
