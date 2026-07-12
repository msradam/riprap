"""Spatial helpers. NYC works in EPSG:2263 (NY state plane, feet)."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

NYC_CRS = "EPSG:2263"  # ft
WGS84 = "EPSG:4326"

DATA = Path(__file__).resolve().parent.parent / "data"


def to_nyc(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if g.crs is None:
        raise ValueError("layer has no CRS")
    return g.to_crs(NYC_CRS) if g.crs.to_string() != NYC_CRS else g


def load_layer(path: str | Path, layer: str | None = None) -> gpd.GeoDataFrame:
    _check_not_lfs_pointer(path)
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    return to_nyc(g)


def _check_not_lfs_pointer(path: str | Path) -> None:
    """A Git LFS pointer file (checked out when `git lfs install` was
    never run) is ~130 bytes of plain text starting with this exact
    line. geopandas fails on it with an opaque `DataSourceError: not
    recognized as being in a supported file format`, which gives no
    hint what's actually wrong — raise something actionable instead."""
    p = Path(path)
    try:
        if p.stat().st_size < 1024:
            with open(p, "rb") as f:
                head = f.read(64)
            if head.startswith(b"version https://git-lfs.github.com/spec/"):
                raise RuntimeError(
                    f"{p} is a Git LFS pointer, not the real data file. "
                    "Run `git lfs install && git lfs pull` in the repo root "
                    "(installing Git LFS first if you don't have it: "
                    "`brew install git-lfs` or your package manager's "
                    "equivalent), then restart."
                )
    except OSError:
        pass  # let gpd.read_file produce its own not-found error
