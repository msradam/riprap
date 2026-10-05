"""LiDAR/DEM-derived micro-topography specialist.

Reads a window from a precomputed NYC-wide DEM (data/nyc_dem_30m.tif)
fetched from USGS 3DEP via py3dep. Computes per-address terrain numbers
that the static FEMA/DEP scenario maps don't expose.

Metrics (all derived from the same small AOI raster):

    point_elev_m          elevation at the address (m)
    rel_elev_pct_750m     percentile of point elev in a 750-m radius
    rel_elev_pct_200m     percentile of point elev in a 200-m radius
                          (block-scale "is this a bowl?")
    basin_relief_m        max-elev in 750-m AOI minus point elev
    aoi_min_m, aoi_max_m  for context
    resolution_m

We deliberately stop at "shape-of-the-terrain" metrics rather than full
hydrology — depression-fill / D8 flow accumulation on a flat coastal
DEM are noisy and slow. Percentile + relief is what the reconciler
actually needs to write a useful sentence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("riprap.microtopo")

DOC_ID = "microtopo"
# No resolution in the label: the cells are about 22 m east-west and 29 m north-south.
CITATION = "USGS 3DEP DEM (precomputed citywide GeoTIFF, WGS84)"

# The DEM's own tag (vertical_datum, written by py3dep from 3DEP) says NAVD88.
VERTICAL_DATUM = "NAVD88"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEM_PATH = DATA_DIR / "nyc_dem_30m.tif"
HAND_PATH = DATA_DIR / "hand.tif"


@dataclass
class Microtopo:
    point_elev_m: float
    rel_elev_pct_750m: float    # 0..100
    rel_elev_pct_200m: float    # 0..100
    basin_relief_m: float
    aoi_min_m: float
    aoi_max_m: float
    aoi_radius_m: int
    resolution_m: int
    # Height Above Nearest Drainage (m), from synthetic channels on the same DEM
    # (whitebox-workflows). Not said in a sentence or shown on the page; kept because
    # the asset registers store it per asset (app/register_builder.py).
    hand_m: float | None = None
    # Templatable narrative the manifest's narration.template renders.
    narrative: str = ""


def _percentile_in_window(arr: np.ndarray, iy: int, ix: int, point_val: float,
                          window_radius_cells: int) -> float:
    H, W = arr.shape
    y0 = max(0, iy - window_radius_cells)
    y1 = min(H, iy + window_radius_cells + 1)
    x0 = max(0, ix - window_radius_cells)
    x1 = min(W, ix + window_radius_cells + 1)
    sub = arr[y0:y1, x0:x1]
    finite = sub[np.isfinite(sub)]
    if finite.size == 0:
        return float("nan")
    return float((finite < point_val).sum()) / finite.size * 100.0


_DEM_CACHE: dict = {}


def _read_full_raster(path: Path) -> tuple[np.ndarray | None, dict | None]:
    import rasterio
    if not path.exists():
        return None, None
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype("float32")
        nodata = ds.nodata
        meta = {"H": ds.height, "W": ds.width,
                "transform": ds.transform, "crs": ds.crs, "nodata": nodata}
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr, meta


def _load_dem():
    """Read the precomputed NYC DEM and HAND rasters into memory.

    They are aligned (same grid, same transform). We hold them as
    numpy arrays so per-query slicing is safe under threading.
    """
    if "arr" in _DEM_CACHE:
        return _DEM_CACHE
    arr, meta = _read_full_raster(DEM_PATH)
    if arr is None:
        log.warning("microtopo DEM not found at %s — run scripts/fetch_nyc_dem.py", DEM_PATH)
        return None
    hand, _  = _read_full_raster(HAND_PATH)
    _DEM_CACHE.update({
        "arr": arr, "H": meta["H"], "W": meta["W"],
        "transform": meta["transform"], "crs": meta["crs"],
        "hand": hand,
    })
    note = []
    if hand is not None: note.append(f"HAND {HAND_PATH.name}")
    log.info("microtopo: loaded NYC DEM %s (%dx%d, %s); aux: %s",
             DEM_PATH.name, meta["H"], meta["W"], meta["crs"],
             ", ".join(note) if note else "(none, algorithmic only)")
    return _DEM_CACHE


def warm():
    _load_dem()


def _row_col(transform, lat: float, lon: float) -> tuple[int, int]:
    """WGS84 (lat, lon) to the (row, col) of the cell that contains it.

    rasterio's own index takes the floor. Rounding the pixel coordinate
    read the next cell for a point in the far half of its own: 400 Carroll
    Street printed the Gowanus Canal's 0.0 m, not its cell's 1.07 m."""
    from rasterio.transform import rowcol

    row, col = rowcol(transform, lon, lat)
    return int(row), int(col)


def _ordinal(n: int) -> str:
    """29 -> '29th', 1 -> '1st', 12 -> '12th'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def microtopo_at(lat: float, lon: float, radius_m: int = 750) -> Microtopo | None:
    state = _load_dem()
    if state is None:
        return None
    arr_full = state["arr"]
    transform = state["transform"]

    try:
        row, col = _row_col(transform, lat, lon)
    except Exception as e:
        log.warning("microtopo index failed: %s", e)
        return None

    res_m = abs(transform.a) * 111_000.0 * np.cos(np.radians(lat))
    cells_radius = max(2, int(np.ceil(radius_m / max(res_m, 1.0))))

    H, W = state["H"], state["W"]
    y0 = max(0, row - cells_radius); y1 = min(H, row + cells_radius + 1)
    x0 = max(0, col - cells_radius); x1 = min(W, col + cells_radius + 1)
    if y1 <= y0 or x1 <= x0:
        return None

    arr = arr_full[y0:y1, x0:x1].copy()

    iy = row - y0
    ix = col - x0
    if not (0 <= iy < arr.shape[0] and 0 <= ix < arr.shape[1]):
        return None

    point_elev = float(arr[iy, ix])
    if not np.isfinite(point_elev):
        for r in range(1, 6):
            ya, yb = max(0, iy - r), min(arr.shape[0], iy + r + 1)
            xa, xb = max(0, ix - r), min(arr.shape[1], ix + r + 1)
            sub = arr[ya:yb, xa:xb]
            if np.isfinite(sub).any():
                point_elev = float(np.nanmean(sub))
                break
        else:
            return None

    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    aoi_min = float(finite.min())
    aoi_max = float(finite.max())

    pct_750 = float((finite < point_elev).sum()) / finite.size * 100.0
    cells_200m = max(1, int(round(200 / max(res_m, 1.0))))
    pct_200 = _percentile_in_window(arr, iy, ix, point_elev, cells_200m)

    hand_arr = state.get("hand")
    hand_v: float | None = None
    if hand_arr is not None and 0 <= row < H and 0 <= col < W:
        v = float(hand_arr[row, col])
        hand_v = round(v, 2) if np.isfinite(v) else None

    elev = round(point_elev, 2)
    pct_200_r = round(pct_200, 1)
    relief = round(aoi_max - point_elev, 2)
    bits = [f"Elevation {elev} m ({VERTICAL_DATUM})"]
    pct = round(pct_200)
    bits.append(f"; this point is higher than {pct}% of the ground within 200 m (the {_ordinal(pct)} "
                f"percentile; a low percentile means a local low spot where water collects)")
    # Basin relief stays in the value (the evidence table): two decimals
    # from a 30 m raster read as precision the data lacks. The wetness index
    # is not returned at all: it rests on synthetic channels and nothing read it.
    narrative = "".join(bits) + "."
    return Microtopo(
        point_elev_m=elev,
        rel_elev_pct_750m=round(pct_750, 1),
        rel_elev_pct_200m=pct_200_r,
        basin_relief_m=relief,
        aoi_min_m=round(aoi_min, 2),
        aoi_max_m=round(aoi_max, 2),
        aoi_radius_m=radius_m,
        resolution_m=int(round(res_m)),
        hand_m=hand_v,
        narrative=narrative,
    )


def microtopo_for_polygon(polygon, polygon_crs: str = "EPSG:4326") -> dict | None:
    """Polygon-mode aggregation: the DEM clipped to the polygon, as its
    minimum, median, 10th percentile and maximum elevation. Used for
    neighborhood-mode queries."""
    state = _load_dem()
    if state is None:
        return None
    try:
        import rasterio
        from rasterio.mask import mask as rio_mask
    except Exception:
        return None
    import geopandas as gpd

    poly = gpd.GeoDataFrame(geometry=[polygon], crs=polygon_crs).to_crs("EPSG:4326")
    geom = [poly.iloc[0].geometry.__geo_interface__]

    def _stats(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with rasterio.open(path) as src:
                clipped, _ = rio_mask(src, geom, crop=True, filled=False)
                arr = clipped[0]
                vals = arr.compressed() if hasattr(arr, "compressed") else arr.flatten()
                vals = vals[np.isfinite(vals)]
                if vals.size == 0:
                    return None
                return {
                    "n_cells":   int(vals.size),
                    "min":       float(np.min(vals)),
                    "median":    float(np.median(vals)),
                    "p10":       float(np.percentile(vals, 10)),
                    "p90":       float(np.percentile(vals, 90)),
                    "max":       float(np.max(vals)),
                    "raw":       vals,
                }
        except Exception as e:
            log.warning("polygon raster mask failed for %s: %r", path.name, e)
            return None

    elev = _stats(DEM_PATH)
    if elev is None:
        return None
    # Elevation only. The area's height above nearest drainage and wetness
    # index (their medians, and the share of cells under 1 m or over 10) are
    # not returned: the channels are synthetic, on a 30 m grid that includes
    # harbour cells, and inland QN12 read 28.8% "less than 1 m above".
    return {
        "n_cells": elev["n_cells"],
        "elev_min_m":     round(elev["min"], 2),
        "elev_median_m":  round(elev["median"], 2),
        "elev_p10_m":     round(elev["p10"], 2),
        "elev_max_m":     round(elev["max"], 2),
    }
