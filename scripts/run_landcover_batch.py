"""Batch earth-observation run: NYC land cover by year (experimental).

Runs offline, never per request. For each year it writes a 30 m raster of
the city's land (data/eo/landcover_<year>.tif) with five bands, the share of
each cell in tree canopy, grass and shrub, bare soil, water, and paved or built
over (building, road, other paved, railroad), in percent, 255 where there is
no clear view, for the app to read. It scores the model so every sentence about it can state its
accuracy (data/experimental/landcover.json).

    uv sync --extra eo
    uv run python scripts/run_landcover_batch.py --years 2018 2021 2024 2026

The model (app/eo/cover.py) was trained by scripts/train_cover.py on the
city's 2017 six-inch land cover map aggregated to the Sentinel-2 grid.
Method:
  * scenes: for each year, the clearest Sentinel-2 L2A dates between 15
    June and 30 September (full leaf) that cover the whole city, up to
    --dates of them (Microsoft Planetary Computer, no key). Scenes from
    before January 2022 get the 1000 added that later scenes carry, so
    every year is on one scale;
  * one map per date; cloud, shadow and missing pixels (the scene
    classification layer) get no value;
  * the year's map is the clearest date's map, with its gaps filled from
    the next date. The gap between two dates' maps of one year is the
    model's own noise. Every pair of years is compared the same way: when
    maps of different summers differ by more than that, which they do, no
    change between years is read from them;
  * accuracy: the 2021 map against the city's 2021 six-inch land cover
    (The Nature Conservancy and UVM, CC BY-NC-SA 4.0), on the 2 km test
    squares the model never trained on, when that map is on this machine
    (outputs/terramind_nyc/labels_2021_10m.tif, from
    scripts/prepare_landcover_labels.py). The map is a local test key: only
    scores are written, never the map or anything drawn from it.

The fractions are a model's estimate from 10 m pixels, not a survey: the
city's own land cover maps and building footprints are the surveys.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The bands saved, in order; the reader checks them.
from app.eo.landcover import GROUPS  # noqa: E402

NYC_BBOX = [-74.26, 40.49, -73.69, 40.92]
# ESA WorldCover classes -> the old adapter's five, for scripts/check_tim.py.
WORLDCOVER = {80: 0, 90: 0, 95: 0, 50: 1, 10: 2, 20: 2, 30: 3, 40: 3, 60: 4, 70: 4, 100: 4}
CITY_2021 = ROOT / "outputs" / "terramind_nyc" / "labels_2021_10m.tif"


def scene_dates(year: int, bbox: list[float], max_cloud: float = 15.0) -> list[tuple[str, list]]:
    """(date, items) for every day from 15 June to 30 September whose
    Sentinel-2 scenes under `max_cloud` include every tile the box touches,
    clearest first."""
    from app.eo import prithvi

    by_day = defaultdict(list)
    for it in prithvi.search_scenes(bbox, f"{year}-06-15T00:00:00Z", f"{year}-09-30T23:59:59Z", max_cloud):
        by_day[it.datetime.date().isoformat()].append(it)

    def tiles(items) -> set:
        return {i.properties["s2:mgrs_tile"] for i in items}

    def cloud(items) -> float:
        return sum(i.properties.get("eo:cloud_cover", 100) for i in items) / len(items)

    every = set().union(*(tiles(v) for v in by_day.values())) if by_day else set()
    return sorted(((d, v) for d, v in by_day.items() if tiles(v) == every), key=lambda kv: cloud(kv[1]))


def read_s2(items: list, ref, lift_old: bool):
    """The twelve bands of one date's scenes mosaicked on the grid as
    digital numbers, and the clear-view mask. `lift_old` adds 1000 to
    scenes from before processing baseline 04.00, which lack the offset
    that later scenes (and the model's statistics) carry."""
    import numpy as np

    from app.eo import cover, prithvi

    s2 = np.zeros((len(cover.S2_BANDS), *ref.shape), dtype="float32")
    clear = np.zeros(ref.shape, dtype=bool)
    for it in items:
        lift = 1000 if lift_old and not prithvi.boa_offset(it) else 0
        for b, band in enumerate(cover.S2_BANDS):
            dn = prithvi.read_band(it, band, ref, resampling="nearest").astype("float32")
            s2[b] = np.where((s2[b] == 0) & (dn > 0), dn + lift, s2[b])
        clear |= prithvi.clear_mask(it, ref)
    return s2, clear & (s2[1] > 0)




def write_map(path: Path, frac, ref, **tags) -> None:
    """(8, H, W) fractions at 10 m (NaN where unseen) saved as five group
    bands of percent at 30 m (3 by 3 pixels averaged, the scale the model is
    scored at), 255 where fewer than five of the nine pixels were seen."""
    import numpy as np
    import rasterio
    from rasterio.transform import Affine

    from app.eo import cover

    groups = np.stack([frac[0], frac[1], frac[2], frac[3], np.sum([frac[c] for c in cover.PAVED], 0)]).astype("float32")
    h, w = groups.shape[1] // 3 * 3, groups.shape[2] // 3 * 3
    blocks = groups[:, :h, :w].reshape(5, h // 3, 3, w // 3, 3)
    seen = (~np.isnan(blocks[0])).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(blocks, axis=(2, 4))
    a = np.where(seen[None] >= 5, np.clip(np.round(100 * np.nan_to_num(mean)), 0, 100), 255).astype("uint8")
    t = ref.rio.transform()
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="COG", dtype="uint8", count=len(GROUPS), height=a.shape[1], width=a.shape[2],
                       crs=ref.rio.crs, transform=t * Affine.scale(3), compress="deflate", nodata=255) as dst:
        dst.write(a)
        dst.descriptions = GROUPS
        dst.update_tags(**{"maturity": "experimental", "batch_run": str(date.today()), "units": "percent of the cell", **tags})


def land_mask(ref):
    """True on the city's land: inside a 2020 neighborhood tabulation area."""
    from rasterio.features import rasterize

    from app.areas import nta

    shapes = [(g, 1) for g in nta.load().to_crs(ref.rio.crs).geometry]
    return rasterize(shapes, out_shape=ref.shape, transform=ref.rio.transform(), fill=0, dtype="uint8") == 1


def run_year(year: int, bbox: list[float], out: Path, n_dates: int, ref, land, net) -> dict | None:
    """Write the year's map; return its dates and the per-date maps."""
    import numpy as np

    from app.eo import cover

    maps, used = [], []
    for day, items in scene_dates(year, bbox):
        if len(used) == n_dates:
            break
        s2, clear = read_s2(items, ref, lift_old=True)
        if (s2[1][land] > 0).mean() < 0.98:
            continue  # this pass covers only part of the city
        if clear[land].mean() < 0.8:
            continue
        frac = cover.predict(net, cover.normalise(s2)).astype("float16")
        frac[:, ~clear | ~land] = np.nan  # no value without a clear view, and none for the harbour
        maps.append(frac)
        used.append(day)
        print(f"{year}: {day}, {len(items)} scenes, {clear[land].mean():.1%} of the land clear", flush=True)
    if not maps:
        print(f"{year}: no clear date covering the city; skipped", flush=True)
        return None
    year_map = maps[0].copy()
    for later in maps[1:]:
        year_map = np.where(np.isnan(year_map), later, year_map)
    write_map(out / f"landcover_{year}.tif", year_map, ref, year=str(year), dates=";".join(used),
              model=cover.ARCH, weights_sha256=cover.SHA256, trained_on="NYC land cover 2017, 6 inch (NYC Open Data)")
    return {"year": year, "dates": used, "maps": maps, "map": year_map}


def zones(ref, column: str):
    """(codes, raster) of the city's community districts (`cdta2020`) or
    neighborhood tabulation areas (`nta2020`); 0 is outside all of them."""
    from rasterio.features import rasterize

    from app.areas import nta

    g = nta.load().to_crs(ref.rio.crs)
    codes = sorted(c for c in g[column].dropna().unique()
                   if column != "cdta2020" or (c[2:].isdigit() and int(c[2:]) <= 18))
    raster = rasterize([(geom, i + 1) for i, c in enumerate(codes) for geom in g[g[column] == c].geometry],
                       out_shape=ref.shape, transform=ref.rio.transform(), fill=0, dtype="uint16")
    return codes, raster


def paved_shares(frac, zone, where) -> dict[str, float]:
    """Each zone's paved or built share (mean over its pixels in `where`)."""
    import numpy as np

    from app.eo import cover

    paved = np.nansum(np.stack([frac[c].astype("float32") for c in cover.PAVED]), 0)
    codes, raster = zone
    out = {}
    for i, c in enumerate(codes):
        inside = (raster == i + 1) & where
        if inside.sum() >= 500:
            out[c] = float(paved[inside].mean())
    return out


def worldcover(bbox: list[float], ref):
    """ESA WorldCover 2021 on the grid, collapsed to the adapter's classes."""
    import numpy as np
    import planetary_computer as pc
    from pystac_client import Client

    from app.eo import prithvi

    client = Client.open(prithvi.STAC_URL, modifier=pc.sign_inplace)
    raw = np.zeros(ref.shape, dtype="uint8")
    for it in client.search(collections=["esa-worldcover"], bbox=bbox, datetime="2021-01-01/2021-12-31").items():
        tile = prithvi.read_band(it, "map", ref, resampling="nearest")
        raw = np.where(tile != 0, tile, raw)
    out = np.full(ref.shape, 255, dtype="uint8")
    for code, cls in WORLDCOVER.items():
        out[raw == code] = cls
    return out


def evaluate(results: dict[int, dict], ref, out_dir: Path, land) -> dict:
    """The model's noise (two dates of one year) and its accuracy against the
    city's 2021 map on the test squares, at the scales the app answers at."""
    import numpy as np
    import rasterio

    from app.eo import cover

    years = {}
    for tif in sorted(out_dir.glob("landcover_*.tif")):  # every saved year, also ones this run did not make
        with rasterio.open(tif) as src:
            years[src.tags().get("year", tif.stem[-4:])] = src.tags().get("dates", "").split(";")
    out: dict = {"model": cover.ARCH, "weights_sha256": cover.SHA256, "run_date": str(date.today()), "years": years}
    districts, areas = zones(ref, "cdta2020"), zones(ref, "nta2020")
    # Noise: the gap in paved share between two dates of one year, on the pixels
    # both dates saw, for a district and for a neighbourhood (the nearest thing
    # to the 500 m circle an address gets). The 95th percentile is quoted.
    for name, zone in (("noise_points", districts), ("noise_points_small", areas)):
        gaps = []
        for r in results.values():
            if len(r["maps"]) < 2:
                continue
            a, b = r["maps"][0], r["maps"][1]
            both = ~np.isnan(a[0]) & ~np.isnan(b[0])
            sa, sb = paved_shares(a, zone, both), paved_shares(b, zone, both)
            gaps += [abs(sa[c] - sb[c]) for c in sa if c in sb]
        if gaps:
            out[name] = round(100 * float(np.percentile(gaps, 95)), 1)
            out[f"{name}_median"] = round(100 * float(np.median(gaps)), 1)
    # Between years: the same district comparison for every pair of years
    # mapped in this run. When images of different summers differ by more than
    # two images of one summer, no change between years can be read.
    import itertools

    pairs = []
    for y1, y2 in itertools.combinations(sorted(results), 2):
        a, b = results[y1]["map"], results[y2]["map"]
        both = ~np.isnan(a[0]) & ~np.isnan(b[0])
        sa, sb = paved_shares(a, districts, both), paved_shares(b, districts, both)
        d = [100 * abs(sb[c] - sa[c]) for c in sa if c in sb]
        pairs.append({"years": [y1, y2], "districts": len(d),
                      "beyond_noise": int(sum(x > out.get("noise_points", 0) for x in d))})
    out["between_years"] = pairs
    if pairs:  # the pair that disagrees most, for the sentence
        worst = max(pairs, key=lambda p: p["beyond_noise"] / max(p["districts"], 1))
        out["between_years_worst"] = f"{worst['years'][0]} and {worst['years'][1]}"
        out["between_years_beyond_noise"] = worst["beyond_noise"]
        out["between_years_districts"] = worst["districts"]
    if 2021 not in results or not CITY_2021.exists():
        print("no 2021 map in this run or no city 2021 map on this machine: accuracy not rescored", flush=True)
        return out
    with rasterio.open(CITY_2021) as src:
        truth, covered = src.read(list(range(1, 9))).astype("float32"), src.read(9)
    pred = results[2021]["map"].astype("float32")
    test = (cover.split_map(ref.shape) == 2) & land & (covered >= 0.95) & ~np.isnan(pred[0])
    out["eval_year"] = 2021
    out["key"] = "NYC land cover 2021, 6 inch (The Nature Conservancy and UVM), on the 2 km test squares"
    ours, theirs = paved_shares(pred, districts, test), paved_shares(truth, districts, test)
    diffs = np.array([100 * (ours[c] - theirs[c]) for c in ours if c in theirs])
    out["n_districts"] = len(diffs)
    out["district_paved_minus_city_map_points_median"] = round(float(np.median(diffs)), 1)
    out["district_paved_gap_points_median_abs"] = round(float(np.median(np.abs(diffs))), 1)
    out["district_paved_gap_points_max"] = round(float(np.abs(diffs).max()), 1)
    # 30 m cells (3 by 3 pixels, all nine valid): mean absolute error of the
    # paved and the canopy share, in points.
    def block(a):
        h, w = a.shape[-2] // 3 * 3, a.shape[-1] // 3 * 3
        return a[..., :h, :w].reshape(*a.shape[:-2], h // 3, 3, w // 3, 3).mean(axis=(-3, -1))
    ok = block(test.astype("float32")) == 1
    for name, idx in (("paved", list(cover.PAVED)), ("tree_canopy", [0])):
        p = block(np.nan_to_num(pred[idx]).sum(0))[ok]
        t = block(truth[idx].sum(0))[ok]
        out[f"{name}_mae_points_30m"] = round(100 * float(np.abs(p - t).mean()), 1)
        out[f"{name}_r2_30m"] = round(float(1 - ((p - t) ** 2).sum() / ((t - t.mean()) ** 2).sum()), 2)
    bias = out["district_paved_minus_city_map_points_median"]
    out["district_paved_vs_city_map"] = f"{abs(bias)} points {'above' if bias > 0 else 'below'}"  # for the hedge
    return {**out, **test_scores()}


TEST_SCORES = ROOT / "data" / "experimental" / "landcover_nyc_eval.json"  # written by scripts/eval_cover.py


def test_scores() -> dict:
    """For the hedge, from the test on the 2021 squares (eval_cover.py): this
    model's mean error per group on the better of the two 2021 images, and
    the error of the city's 2017 map read as if it were 2021, on the worse.
    The map wins even so."""
    from app.eo import cover

    methods = json.loads(TEST_SCORES.read_text())["methods"]

    def mae(name: str) -> list[float]:
        return [v["test_squares"]["mean_mae_pts"] for v in methods[name].values()
                if "mean_mae_pts" in v.get("test_squares", {})]

    return {"model_test_mae_points": round(min(mae(cover.ARCH)), 1),
            "city_map_2017_as_2021_mae_points": round(max(mae("persistence_2017_map")), 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="NYC land cover by year (experimental).")
    ap.add_argument("--years", nargs="+", type=int, default=[])
    ap.add_argument("--dates", type=int, default=2, help="clear dates per year")
    ap.add_argument("--bbox", nargs=4, type=float, default=NYC_BBOX)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "eo")
    ap.add_argument("--eval-out", type=Path, default=ROOT / "data" / "experimental" / "landcover.json")
    ap.add_argument("--merge-test-scores", action="store_true",
                    help="only copy the test scores of eval_cover.py into the saved evaluation; no model runs")
    args = ap.parse_args()
    if args.merge_test_scores:
        args.eval_out.write_text(json.dumps({**json.loads(args.eval_out.read_text()), **test_scores()}, indent=1) + "\n")
        return 0

    from app.eo import cover, prithvi

    bbox = list(args.bbox)
    ref = prithvi.grid(bbox)
    land = land_mask(ref)
    net = cover.load()
    results = {}
    for year in args.years:
        r = run_year(year, bbox, args.out, args.dates, ref, land, net)
        if r:
            results[year] = r
    if not results:
        return 1
    if bbox == NYC_BBOX:
        report = evaluate(results, ref, args.out, land)
        print(json.dumps(report, indent=1))
        if "eval_year" in report or not args.eval_out.exists():
            args.eval_out.parent.mkdir(parents=True, exist_ok=True)
            args.eval_out.write_text(json.dumps(report, indent=1) + "\n")
        else:
            # A run without 2021 or without the 2021 key rescored no accuracy: the
            # saved evaluation, which every land-cover sentence quotes, stays.
            print(f"{args.eval_out} left as it was: this run did not rescore accuracy", flush=True)
        if args.out.resolve() == (ROOT / "data" / "eo").resolve():
            # The canopy comparison with the city's 2017 map is measured from the yearly maps just written, and a
            # rewritten evaluation has lost it: measure it again, so the caveat every canopy sentence quotes
            # is never stale or missing.
            import check_landcover_canopy

            check_landcover_canopy.main(args.eval_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
