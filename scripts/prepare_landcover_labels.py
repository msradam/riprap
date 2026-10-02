"""Training and test data for a NYC land-cover model at Sentinel-2 10 m.

Data only, no model. Everything lands in outputs/terramind_nyc/ (git-ignored)
and downloads are cached, so a rerun only redoes what is missing.

    uv sync --extra eo
    uv run python scripts/prepare_landcover_labels.py

Labels: the city's 6 inch land cover maps turned into class fractions on the
10 m grid (prithvi.grid over NYC_BBOX, EPSG:32618):

  * 2017, NYC Open Data he6d-2qns (OTI, UVM Spatial Analysis Lab), the
    training labels;
  * 2021, The Nature Conservancy and UVM, Zenodo 14053441, CC BY-NC-SA 4.0.
    A local test key only: nothing made from it may leave outputs/.

Both maps use the same eight codes (1 tree canopy ... 8 railroad), so the
harmonised classes are the source codes in order. Fractions are computed in
two steps: the 6 inch pixels are counted per class into 10 x 10 pixel cells
(5 ft, exact, in the source CRS EPSG:2263), and those counts are averaged
into the 10 m UTM cells with area weighted average resampling. Each output
has one band per class (share of the cell's area in that class) and a last
band with the share of the cell that is labelled at all.

Imagery: for summer 2017 and 2021 (15 June to 30 September) the two clearest
Sentinel-2 L2A dates covering the whole city, read as run_landcover_batch.py
reads them (twelve bands, digital numbers, +1000 before baseline 04.00),
plus the SCL clear-view mask as a 13th band.

Sanity numbers go to outputs/terramind_nyc/prep_report.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "outputs" / "terramind_nyc"
RAW = OUT / "raw"
CLASSES = ("tree_canopy", "grass_shrub", "bare_soil", "water", "building", "road", "other_paved", "railroad")
PAVED = ("building", "road", "other_paved", "railroad")
CELL = 10  # 6 inch pixels per side of a counting cell (5 ft)
LABELS = {
    2017: {
        "url": "https://data.cityofnewyork.us/api/views/he6d-2qns/files/64c49dc7-c17f-43db-a4e3-669a28f73234?filename=Land_Cover.zip",
        "file": "Land_Cover_2017.zip",
        "size": 1334211225,
        # source code -> index in CLASSES (both years: 1 tree canopy, 2 grass/shrubs,
        # 3 bare soil, 4 water, 5 buildings, 6 roads, 7 other impervious, 8 railroads)
        "codes": {c: c - 1 for c in range(1, 9)},
    },
    2021: {
        "url": "https://zenodo.org/api/records/14053441/files/landcover_nyc_2021_6in.tif/content",
        "file": "landcover_nyc_2021_6in.tif",
        "size": 1739874194,
        "codes": {c: c - 1 for c in range(1, 9)},
    },
}
S2_YEARS = {2017: [], 2021: ["2021-06-16", "2021-09-29"]}  # preferred dates (the existing adapter's 2021 map)


def download(url: str, path: Path, size: int) -> Path:
    """Fetch `url` to `path` with curl, resuming a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == size:
        return path
    print(f"downloading {path.name}", flush=True)
    subprocess.run(["curl", "-sS", "-L", "-C", "-", "--retry", "5", "-o", str(path), url], check=True)
    if path.stat().st_size != size:
        raise RuntimeError(f"{path.name}: {path.stat().st_size} bytes, expected {size}")
    return path


def source_raster(year: int) -> str:
    """The map's raster as a GDAL path. The 2017 zip holds a 98 GB ERDAS
    Imagine file; it is read through /vsizip/ rather than unpacked (each
    worker reads its rows in order, which /vsizip/ streams quickly)."""
    spec = LABELS[year]
    path = download(spec["url"], RAW / spec["file"], spec["size"])
    if path.suffix != ".zip":
        return str(path)
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith((".tif", ".img"))]
    if len(names) != 1:
        raise RuntimeError(f"{path.name}: expected one raster, found {names}")
    return f"/vsizip/{path}/{names[0]}"


def _count_rows(args):
    """Per-class counts of a band of 6 inch pixel rows in CELL x CELL cells,
    read top to bottom in strips. Returns (first source row, uint8 array
    (9, rows, cols)): 8 classes, then the labelled count."""
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    src_path, col0, row0, width, height, codes = args
    h, w = height // CELL, width // CELL
    out = np.zeros((len(CLASSES) + 1, h, w), dtype="uint8")
    step = 100 * CELL
    with rasterio.open(src_path) as src:
        for top in range(row0, row0 + height, step):
            n = min(step, row0 + height - top)
            blk = np.zeros((n, width), dtype="uint8")  # outside the map: no code, so unlabelled
            c0, r0 = max(col0, 0), max(top, 0)
            c1, r1 = min(col0 + width, src.width), min(top + n, src.height)
            if c1 > c0 and r1 > r0:
                blk[r0 - top:r1 - top, c0 - col0:c1 - col0] = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
            o = out[:, (top - row0) // CELL:(top - row0 + n) // CELL]
            for code, idx in codes.items():
                o[idx] = (blk == code).reshape(n // CELL, CELL, w, CELL).sum((1, 3), dtype="uint16")
    out[-1] = out[:-1].sum(0, dtype="uint16")  # at most CELL * CELL = 100, so it fits
    return row0, out


def native_counts(year: int, src_path: str, ref) -> Path:
    """Class counts in CELL x CELL cells of the source grid, covering the
    whole 10 m grid (outside the map: zero counts), as uint8 GeoTIFF."""
    import numpy as np
    import rasterio
    from rasterio.transform import Affine
    from rasterio.warp import transform_bounds

    path = OUT / f"counts_{year}_5ft.tif"
    if path.exists():
        return path
    with rasterio.open(src_path) as src:
        st, crs = src.transform, src.crs
        print(f"{year}: {src_path} {src.width} x {src.height}, {crs.to_string()}, res {st.a}, "
              f"dtype {src.dtypes[0]}, nodata {src.nodata}", flush=True)
    left, bottom, right, top = transform_bounds(ref.rio.crs, crs, *ref.rio.bounds(), densify_pts=101)
    # snap to the source pixel grid, a whole number of cells, with a cell of margin
    col0 = int(np.floor((left - st.c) / st.a)) // CELL * CELL - CELL
    row0 = int(np.floor((top - st.f) / st.e)) // CELL * CELL - CELL
    cols = (int(np.ceil((right - st.c) / st.a)) - col0) // CELL + 2
    rows = (int(np.ceil((bottom - st.f) / st.e)) - row0) // CELL + 2
    tf = Affine(st.a * CELL, 0, st.c + col0 * st.a, 0, st.e * CELL, st.f + row0 * st.e)
    chunk = -(-rows // 24)  # cells per job: 24 bands of rows, each read in order
    codes = LABELS[year]["codes"]
    jobs = [(src_path, col0, row0 + r * CELL, cols * CELL, min(chunk, rows - r) * CELL, codes)
            for r in range(0, rows, chunk)]
    tmp = path.with_suffix(".part.tif")
    t0 = time.time()
    with rasterio.open(tmp, "w", driver="GTiff", dtype="uint8", count=len(CLASSES) + 1, width=cols, height=rows,
                       crs=crs, transform=tf, tiled=True, compress="deflate", predictor=2, BIGTIFF="YES") as dst, \
            ProcessPoolExecutor(max_workers=6) as pool:
        for n, (r0, counts) in enumerate(pool.map(_count_rows, jobs), 1):
            dst.write(counts, window=(((r0 - row0) // CELL, (r0 - row0) // CELL + counts.shape[1]), (0, cols)))
            print(f"{year}: counted {n}/{len(jobs)} bands of rows, {time.time() - t0:.0f}s", flush=True)
        dst.descriptions = (*CLASSES, "labelled")
    tmp.rename(path)
    return path


def fractions(year: int, counts_path: Path, ref) -> Path:
    """Average the 5 ft counts into the 10 m grid: per class share of the
    cell, then the labelled share. float32, 9 bands."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    path = OUT / f"labels_{year}_10m.tif"
    if path.exists():
        return path
    h, w = ref.shape
    out = np.zeros((len(CLASSES) + 1, h, w), dtype="float32")
    with rasterio.open(counts_path) as src:
        for b in range(src.count):
            t0 = time.time()
            reproject(rasterio.band(src, b + 1), out[b], dst_transform=ref.rio.transform(), dst_crs=ref.rio.crs,
                      resampling=Resampling.average, num_threads=4, warp_mem_limit=2048)
            print(f"{year}: band {src.descriptions[b]} on the 10 m grid, {time.time() - t0:.0f}s", flush=True)
    out /= CELL * CELL
    with rasterio.open(path, "w", driver="GTiff", dtype="float32", count=out.shape[0], width=w, height=h,
                       crs=ref.rio.crs, transform=ref.rio.transform(), tiled=True, compress="deflate",
                       predictor=3) as dst:
        dst.write(out)
        dst.descriptions = (*CLASSES, "labelled")
        dst.update_tags(year=str(year), source=LABELS[year]["url"], method="6in counts in 5 ft cells, "
                        "area weighted average into the 10 m grid; class bands are shares of the whole cell")
    return path


def imagery(year: int, ref, land, n: int = 2) -> list[dict]:
    """Save the year's n clearest full-coverage dates (preferred dates first)."""
    import numpy as np
    import rasterio

    from app.eo import cover
    from scripts.run_landcover_batch import NYC_BBOX, read_s2, scene_dates

    saved = sorted(OUT.glob(f"s2_{year}-*.tif"))
    if len(saved) >= n:  # cached: skip the search (rejected dates would be read again)
        out = []
        for path in saved[:n]:
            with rasterio.open(path) as src:
                out.append(json.loads(src.tags()["info"]))
        return out
    days = scene_dates(year, NYC_BBOX)
    prefer = S2_YEARS[year]
    days.sort(key=lambda kv: (kv[0] not in prefer, prefer.index(kv[0]) if kv[0] in prefer else 0))
    used = []
    for day, items in days:
        if len(used) == n:
            break
        path = OUT / f"s2_{day}.tif"
        info = {"date": day, "file": path.name, "scenes": sorted(i.id for i in items),
                "baselines": sorted({i.properties.get("s2:processing_baseline") for i in items})}
        if path.exists():
            with rasterio.open(path) as src:
                used.append(json.loads(src.tags()["info"]))
            continue
        t0 = time.time()
        s2, clear = read_s2(items, ref, lift_old=True)
        coverage, clear_share = float((s2[1][land] > 0).mean()), float(clear[land].mean())
        print(f"{year}: {day} covers {coverage:.1%} of the land, {clear_share:.1%} clear, "
              f"{time.time() - t0:.0f}s", flush=True)
        if coverage < 0.98 or clear_share < 0.8:
            continue
        info.update(land_coverage=round(coverage, 4), land_clear=round(clear_share, 4))
        h, w = ref.shape
        with rasterio.open(path, "w", driver="GTiff", dtype="uint16", count=13, width=w, height=h,
                           crs=ref.rio.crs, transform=ref.rio.transform(), tiled=True, compress="deflate",
                           predictor=2, nodata=0) as dst:
            dst.write(np.clip(s2, 0, 65535).astype("uint16"), list(range(1, 13)))
            dst.write(clear.astype("uint16"), 13)
            dst.descriptions = (*cover.S2_BANDS, "clear")
            dst.update_tags(source="Microsoft Planetary Computer sentinel-2-l2a", info=json.dumps(info),
                            scale="digital numbers; +1000 added to scenes before processing baseline 04.00")
        used.append(info)
    return used


def corr(a, b) -> float:
    import numpy as np

    return round(float(np.corrcoef(a, b)[0, 1]), 3)


def block3(x):
    """3 x 3 block means (30 m), trimming the edges."""
    h, w = (x.shape[0] // 3) * 3, (x.shape[1] // 3) * 3
    return x[:h, :w].reshape(h // 3, 3, w // 3, 3).mean((1, 3))


def sanity(ref, land, s2_2017: Path) -> dict:
    import numpy as np
    import rasterio

    rep: dict = {}
    lab = {}
    for year in LABELS:
        with rasterio.open(OUT / f"labels_{year}_10m.tif") as src:
            lab[year] = src.read()
        f, labelled = lab[year][:-1], lab[year][-1]
        full = land & (labelled > 0.999)
        # land shares on fully labelled land cells, normalised by labelled area
        tot = f[:, full].sum()
        rep[str(year)] = {
            "land_share_pct": {c: round(100 * float(f[i, full].sum() / tot), 2) for i, c in enumerate(CLASSES)},
            "land_cells_fully_labelled_pct": round(100 * float(full.sum() / land.sum()), 2),
            "land_cells_any_label_pct": round(100 * float((labelled[land] > 0).mean()), 2),
            "land_labelled_area_pct": round(100 * float(labelled[land].mean()), 2),
        }
    both = land & (lab[2017][-1] > 0.999) & (lab[2021][-1] > 0.999)
    paved = [CLASSES.index(c) for c in PAVED]

    def share(y, idx):
        return 100 * float(lab[y][idx][:, both].sum() / lab[y][:-1][:, both].sum())
    rep["change_2017_2021_points"] = {
        "cells": int(both.sum()),
        "tree_canopy": round(share(2021, [0]) - share(2017, [0]), 2),
        "paved": round(share(2021, paved) - share(2017, paved), 2),
        "tree_canopy_2017_2021_pct": [round(share(2017, [0]), 2), round(share(2021, [0]), 2)],
        "paved_2017_2021_pct": [round(share(2017, paved), 2), round(share(2021, paved), 2)],
    }
    with rasterio.open(s2_2017) as src:
        b = src.read().astype("float32")
    g, r, nir, clear = b[2], b[3], b[7], b[12] > 0  # B03, B04, B08
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi, ndvi = (g - nir) / (g + nir), (nir - r) / (nir + r)
    f17 = lab[2017]
    ok = clear & (f17[-1] > 0.999) & np.isfinite(ndwi) & np.isfinite(ndvi)
    geo = {"image": s2_2017.name, "cells_10m": int(ok.sum())}
    for name, frac, idx in (("water_vs_ndwi", f17[3], ndwi), ("canopy_vs_ndvi", f17[0], ndvi)):
        geo[f"{name}_10m"] = corr(frac[ok], idx[ok])
        okb = block3(ok.astype("float32")) == 1
        geo[f"{name}_30m"] = corr(block3(np.where(ok, frac, 0))[okb], block3(np.where(ok, idx, 0))[okb])
    rep["geolocation_2017"] = geo
    # Registration of every saved date against its year's labels: a date that
    # is off by a pixel correlates better with the labels rolled by that pixel.
    rep["registration"] = {}
    for tif in sorted(OUT.glob("s2_*.tif")):
        with rasterio.open(tif) as src:
            r, nir, clear = (src.read(i).astype("float32") for i in (4, 8, 13))
        with np.errstate(divide="ignore", invalid="ignore"):
            v = (nir - r) / (nir + r)
        f = lab[int(tif.stem[3:7])]
        ok = (clear > 0) & (f[-1] > 0.999) & np.isfinite(v)
        rs = {}
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                m = ok & np.roll(ok, (dy, dx), (0, 1))
                rs[(dy, dx)] = corr(np.roll(f[0], (dy, dx), (0, 1))[m], v[m])
        best = max(rs, key=rs.get)
        rep["registration"][tif.name] = {"canopy_vs_ndvi_r_unshifted": rs[(0, 0)], "best_label_shift_rows_cols": best,
                                         "r_at_best": rs[best]}
    return rep


def fix_registration(registration: dict) -> dict:
    """Move a date's image by the shift that best matches the labels, when it
    gains at least 0.02 in canopy against NDVI correlation (2017-08-26 is one
    row off). The labels stay put; the published file goes to raw/. Returns
    {file: [rows, cols]} for every date moved."""
    import numpy as np
    import rasterio

    moved = {}
    for name, r in registration.items():
        dy, dx = r["best_label_shift_rows_cols"]
        path = OUT / name
        with rasterio.open(path) as src:
            done = "registration_fix" in src.tags()
        if done or (dy, dx) == (0, 0) or r["r_at_best"] - r["canopy_vs_ndvi_r_unshifted"] < 0.02:
            continue
        raw = OUT / "raw" / f"{path.stem}_as_published.tif"
        path.replace(raw)
        with rasterio.open(raw) as src:
            a, prof, desc, tags = src.read(), src.profile, src.descriptions, src.tags()
        a = np.roll(a, (-dy, -dx), (1, 2))  # labels rolled by (dy, dx) fit, so the image moves the other way
        # Blank the rows and columns that wrapped round.
        if dy > 0:
            a[:, -dy:] = 0
        elif dy < 0:
            a[:, :-dy] = 0
        if dx > 0:
            a[:, :, -dx:] = 0
        elif dx < 0:
            a[:, :, :-dx] = 0
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(a)
            dst.descriptions = desc
            dst.update_tags(**tags, registration_fix=f"moved by {-dy} rows and {-dx} columns to match the labels")
        moved[name] = [-dy, -dx]
    return moved


CITY_MAP = ROOT / "data" / "landcover_nyc_2017.tif"


def bake_city_map(ref) -> Path:
    """The city's 2017 map as the app reads it (app/eo/landcover.py): the
    same five group bands of percent at 30 m as the model's yearly maps, so
    one reader serves both. A 10 m cell counts where at least half of it is
    labelled, and its shares are of the labelled part."""
    import numpy as np
    import rasterio

    from scripts.run_landcover_batch import write_map

    with rasterio.open(OUT / "labels_2017_10m.tif") as src:
        a = src.read()
    labelled = a[-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(labelled >= 0.5, a[:-1] / labelled, np.nan)
    write_map(CITY_MAP, frac, ref, maturity="production", year="2017", source=LABELS[2017]["url"],
              method="6 inch classes counted into 10 m cells, then averaged to 30 m")
    return CITY_MAP


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-imagery", action="store_true")
    ap.add_argument("--bake-city-map", action="store_true",
                    help="only write data/landcover_nyc_2017.tif from the saved 2017 labels")
    args = ap.parse_args()

    from app.eo import prithvi
    from scripts.run_landcover_batch import NYC_BBOX, land_mask

    OUT.mkdir(parents=True, exist_ok=True)
    ref = prithvi.grid(NYC_BBOX)
    if args.bake_city_map:
        print(bake_city_map(ref))
        return 0
    land = land_mask(ref)
    timings = {}
    for year in LABELS:
        t0 = time.time()
        src = source_raster(year)
        fractions(year, native_counts(year, src, ref), ref)
        timings[f"labels_{year}_s"] = round(time.time() - t0)
    report: dict = {"grid": {"crs": "EPSG:32618", "shape": list(ref.shape), "transform": list(ref.rio.transform())[:6]},
                    "classes": list(CLASSES), "label_codes": {y: LABELS[y]["codes"] for y in LABELS}}
    if not args.skip_imagery:
        report["imagery"] = {}
        for year in S2_YEARS:
            t0 = time.time()
            report["imagery"][year] = imagery(year, ref, land)
            timings[f"imagery_{year}_s"] = round(time.time() - t0)
    s2_2017 = OUT / report["imagery"][2017][0]["file"] if "imagery" in report else next(OUT.glob("s2_2017-*.tif"))
    t0 = time.time()
    report.update(sanity(ref, land, s2_2017))
    report["registration_fixed"] = fix_registration(report["registration"])
    if report["registration_fixed"]:  # score the corrected files
        report["registration"] = sanity(ref, land, s2_2017)["registration"]
    timings["sanity_s"] = round(time.time() - t0)
    report["timings_this_run"] = timings
    (OUT / "prep_report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
