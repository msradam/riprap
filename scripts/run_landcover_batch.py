"""Batch earth-observation run: TerraMind land cover by year (experimental).

Runs offline, never per request. For each year it writes a 10 m land-cover
raster of the city's land (data/eo/landcover_<year>.tif) for the app to
read, and it scores the model so every sentence about it can state its
accuracy (data/experimental/landcover.json).

    uv sync --extra eo
    uv run python scripts/run_landcover_batch.py --years 2018 2021 2024 2026

Method:
  * scenes: for each year, the clearest Sentinel-2 L2A dates between 15
    June and 30 September (full leaf) that cover the whole city, up to
    --dates of them (Microsoft Planetary Computer, no key). Scenes from
    before January 2022 get the 1000 added that later scenes carry, so
    every year is on one scale;
  * one map per date: the model sees one scene at a time, as in training;
    cloud, shadow and missing pixels (the scene classification layer) get
    no label;
  * the year's map is the clearest date's map, with its unlabelled pixels
    filled from the next date. (A vote between two dates is a tie wherever
    they differ, and a tie-break favours one class.) The gap between two
    dates' maps of one year is the model's own noise: a change between
    years smaller than that is not reported as change;
  * accuracy: the 2021 map against ESA WorldCover 2021 (the adapter's label
    source, collapsed to the same five classes), citywide and by borough.

The labels are a proxy from 10 m pixels, not a survey: the city's own land
cover map (2017, 6 inch) and building footprints are the surveys.
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

NYC_BBOX = [-74.26, 40.49, -73.69, 40.92]
# ESA WorldCover classes -> the adapter's five (app.eo.terramind.CLASSES), as
# its training script collapsed them.
WORLDCOVER = {80: 0, 90: 0, 95: 0, 50: 1, 10: 2, 20: 2, 30: 3, 40: 3, 60: 4, 70: 4, 100: 4}
BUILT = 1


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

    from app.eo import prithvi, terramind

    s2 = np.zeros((len(terramind.S2_BANDS), *ref.shape), dtype="float32")
    clear = np.zeros(ref.shape, dtype=bool)
    for it in items:
        lift = 1000 if lift_old and not prithvi.boa_offset(it) else 0
        for b, band in enumerate(terramind.S2_BANDS):
            dn = prithvi.read_band(it, band, ref, resampling="nearest").astype("float32")
            s2[b] = np.where((s2[b] == 0) & (dn > 0), dn + lift, s2[b])
        clear |= prithvi.clear_mask(it, ref)
    return s2, clear & (s2[1] > 0)


def write_map(path: Path, classes, ref, **tags) -> None:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="COG", dtype="uint8", count=1, height=classes.shape[0], width=classes.shape[1],
                       crs=ref.rio.crs, transform=ref.rio.transform(), compress="deflate", nodata=255) as dst:
        dst.write(classes, 1)
        dst.update_tags(maturity="experimental", batch_run=str(date.today()), **tags)


def land_mask(ref):
    """True on the city's land: inside a 2020 neighborhood tabulation area."""
    from rasterio.features import rasterize

    from app.areas import nta

    shapes = [(g, 1) for g in nta.load().to_crs(ref.rio.crs).geometry]
    return rasterize(shapes, out_shape=ref.shape, transform=ref.rio.transform(), fill=0, dtype="uint8") == 1


def run_year(year: int, bbox: list[float], out: Path, n_dates: int, ref, land) -> dict | None:
    """Write the year's map; return its dates and the per-date maps."""
    import numpy as np

    from app.eo import terramind

    maps, used = [], []
    for day, items in scene_dates(year, bbox):
        if len(used) == n_dates:
            break
        s2, clear = read_s2(items, ref, lift_old=True)
        if (s2[1][land] > 0).mean() < 0.98:
            continue  # this pass covers only part of the city
        if clear[land].mean() < 0.8:
            continue
        s2[:, ~land] = 0  # the harbour is not classified
        labels = terramind.classify(s2)
        labels[~clear | ~land] = 255  # no label without a clear view, and none for the harbour
        maps.append(labels)
        used.append(day)
        print(f"{year}: {day}, {len(items)} scenes, {clear[land].mean():.1%} of the land clear", flush=True)
    if not maps:
        print(f"{year}: no clear date covering the city; skipped", flush=True)
        return None
    year_map = maps[0].copy()
    for later in maps[1:]:
        year_map = np.where(year_map == 255, later, year_map)
    write_map(out / f"landcover_{year}.tif", year_map, ref, year=str(year), dates=";".join(used),
              model=terramind.MODEL.repo, revision=terramind.MODEL.revision, adapter=terramind.ADAPTER,
              class_names=";".join(terramind.CLASSES))
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


def built_shares(labels, zone, where) -> dict[str, float]:
    """The share of each zone's pixels (those in `where`) labelled built."""
    codes, raster = zone
    out = {}
    for i, c in enumerate(codes):
        inside = (raster == i + 1) & where
        if inside.sum():
            out[c] = float((labels[inside] == BUILT).mean())
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


def evaluate(results: dict[int, dict], bbox: list[float], ref, out_dir: Path) -> dict:
    """The model's noise (two dates of one year) and its agreement with
    WorldCover 2021, at the scales the app answers at."""
    import numpy as np
    import rasterio
    from rasterio.features import rasterize

    from app.areas import nta
    from app.eo import terramind

    years = {}
    for tif in sorted(out_dir.glob("landcover_*.tif")):  # every saved year, also ones this run did not make
        with rasterio.open(tif) as src:
            years[src.tags().get("year", tif.stem[-4:])] = src.tags().get("dates", "").split(";")
    out: dict = {"model": terramind.MODEL.repo, "revision": terramind.MODEL.revision, "adapter": terramind.ADAPTER,
                 "run_date": str(date.today()), "years": years}
    districts, areas = zones(ref, "cdta2020"), zones(ref, "nta2020")
    # Noise: the gap in built share between two dates of one year, on the pixels
    # both dates labelled, for a district and for a neighbourhood (the nearest
    # thing to the 500 m circle an address gets). The 95th percentile is quoted.
    for name, zone in (("noise_points", districts), ("noise_points_small", areas)):
        gaps = []
        for r in results.values():
            if len(r["maps"]) < 2:
                continue
            a, b = r["maps"][0], r["maps"][1]
            both = (a != 255) & (b != 255)
            sa, sb = built_shares(a, zone, both), built_shares(b, zone, both)
            gaps += [abs(sa[c] - sb[c]) for c in sa if c in sb]
        if gaps:
            out[name] = round(100 * float(np.percentile(gaps, 95)), 1)
            out[f"{name}_median"] = round(100 * float(np.median(gaps)), 1)
    year = 2021 if 2021 in results else min(results, key=lambda y: abs(y - 2021))
    truth, pred = worldcover(bbox, ref), results[year]["map"]
    both = (truth != 255) & (pred != 255)
    out["eval_year"] = year
    out["agreement_pct"] = round(100 * float((truth[both] == pred[both]).mean()), 1)
    # The app reports three groups (paved or built, green, water): trees and grass together.
    group = np.array([0, 1, 2, 2, 3, 255], dtype="uint8")
    out["group_agreement_pct"] = round(100 * float((group[np.minimum(truth[both], 5)] == group[np.minimum(pred[both], 5)]).mean()), 1)
    # How many of WorldCover's pixels of each class the model gives the same class.
    out["class_recall_pct"] = {name: round(100 * float((pred[both & (truth == c)] == c).mean()), 1)
                               for c, name in enumerate(terramind.CLASSES) if (both & (truth == c)).any()}
    green = np.isin(truth, (2, 3)) & both
    out["green_found_pct"] = round(100 * float(np.isin(pred[green], (2, 3)).mean()), 1)
    # District level: the model's built share less WorldCover's, in points.
    ours, theirs = built_shares(pred, districts, both), built_shares(truth, districts, both)
    diffs = [100 * (ours[c] - theirs[c]) for c in ours if c in theirs]
    out["district_built_minus_worldcover_points_median"] = round(float(np.median(diffs)), 1)
    out["district_built_gap_points_max"] = round(float(np.max(np.abs(diffs))), 1)
    bias = out["district_built_minus_worldcover_points_median"]
    out["district_built_vs_worldcover"] = f"{abs(bias)} points {'above' if bias > 0 else 'below'}"  # for the hedge sentence
    g = nta.load().to_crs(ref.rio.crs)
    out["by_borough_agreement_pct"] = {}
    for boro in sorted(g["boroname"].unique()):
        zone = rasterize([(geom, 1) for geom in g[g["boroname"] == boro].geometry], out_shape=pred.shape,
                         transform=ref.rio.transform(), fill=0, dtype="uint8") == 1
        m = both & zone
        out["by_borough_agreement_pct"][boro] = round(100 * float((truth[m] == pred[m]).mean()), 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="TerraMind land cover by year (experimental).")
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--dates", type=int, default=2, help="clear dates per year")
    ap.add_argument("--bbox", nargs=4, type=float, default=NYC_BBOX)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "eo")
    ap.add_argument("--eval-out", type=Path, default=ROOT / "data" / "experimental" / "landcover.json")
    args = ap.parse_args()

    from app.eo import prithvi

    bbox = list(args.bbox)
    ref = prithvi.grid(bbox)
    land = land_mask(ref)
    results = {}
    for year in args.years:
        r = run_year(year, bbox, args.out, args.dates, ref, land)
        if r:
            results[year] = r
    if not results:
        return 1
    if bbox == NYC_BBOX:
        report = evaluate(results, bbox, ref, args.out)
        args.eval_out.parent.mkdir(parents=True, exist_ok=True)
        args.eval_out.write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
