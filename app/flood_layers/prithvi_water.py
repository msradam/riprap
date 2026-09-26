"""Satellite-detected surface water after Hurricane Ida (experimental).

The 300M-parameter Prithvi-EO foundation model (NASA/IBM, Apache-2.0)
was run twice offline on Hurricane Ida 2021 pre/post HLS Sentinel-2
scenes over central NYC:

    pre :  HLS.S30.T18TWK.2021237T153809  (2021-08-25,  3% cloud)
    post:  HLS.S30.T18TWK.2021245T154911  (2021-09-02,  1% cloud,
                                           ~14 hours after the heaviest rain)

The diff (post-water minus pre-water, filtered to ≥3-cell polygons)
isolates surface water present about 14 hours after the heaviest rain
that wasn't present the prior week. Per query we report how many of
those polygons sit near the address, never an inside/outside verdict.
The layer is unvalidated (no comparison with Ida HWMs or 311).

Honest scope:
- Sub-surface flooding (subway entrances, basement apartments — the
  dominant Ida damage mode in NYC) is not visible to optical satellites.
- Pluvial street water had largely drained by the Sep 2 16:02Z pass,
  so the residual Prithvi signal mostly captures marsh ponding,
  riverside spillover, and low-lying park inundation.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DOC_ID = "prithvi_water"
CITATION = ("Prithvi-EO-2.0-300M-TL-Sen1Floods11 (NASA/IBM, Apache-2.0, via "
            "TerraTorch). Hurricane Ida pre/post diff: pre HLS T18TWK "
            "2021-08-25 (3% cloud), post HLS T18TWK 2021-09-02 (1% cloud, "
            "~14 h after the heaviest rain).")


@dataclass
class PrithviSummary:
    nearest_distance_m: float | None
    n_polygons_within_500m: int
    scene_id: str
    scene_date: str
    # Normalized rendering fields the type-keyed raster card reads.
    headline_value: str = ""
    subhead_text: str = ""
    narrative: str = ""
    raster_kind: str = "prithvi"
    illustrative: bool = False


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _load():
    """Load the merged Prithvi water mask (combined across NYC MGRS tiles)
    as a GeoDataFrame in NYC state plane (EPSG:2263) for fast metric
    distance queries."""
    import geopandas as gpd
    # Prefer the Ida flood-event diff (real flood-attribution signal);
    # fall back to clear-day permanent-water masks if the Ida file is absent.
    candidates = [
        DATA_DIR / "prithvi_ida_2021.geojson",
        DATA_DIR / "prithvi_flood_nyc.geojson",
    ]
    candidates += sorted(DATA_DIR.glob("prithvi_flood_*.geojson"), reverse=True)
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None, None
    with open(path) as f:
        meta = json.load(f)
    g = gpd.read_file(path)
    if g.crs is None:
        g.set_crs("EPSG:4326", inplace=True)
    g = g.to_crs("EPSG:2263")
    return g, meta


def warm() -> None:
    _load()


def summary_for_point(lat: float, lon: float) -> PrithviSummary | None:
    import geopandas as gpd
    from shapely.geometry import Point
    g, meta = _load()
    if g is None:
        return None
    pt_wgs = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    pt_2263 = pt_wgs.to_crs("EPSG:2263").iloc[0]
    # nearest distance (feet -> metres)
    distances_ft = g.geometry.distance(pt_2263)
    nearest_ft = float(distances_ft.min()) if len(distances_ft) else None
    nearest_m = round(nearest_ft / 3.281, 1) if nearest_ft is not None else None

    within_500m = int((distances_ft <= 500 * 3.281).sum())

    # The Ida pre/post artifact carries pre_/post_ scene info; the clear-day
    # artifact carries scene_ids[]. Format compactly for either case.
    if "post_scene_id" in meta:
        sid = f"pre {meta['pre_scene_id']} | post {meta['post_scene_id']}"
        sdate = f"pre {meta['pre_scene_date']}, post {meta['post_scene_date']}"
    else:
        sid = meta.get("scene_id") or ", ".join(meta.get("scene_ids", []) or ["unknown"])
        sdate = meta.get("scene_date") or ", ".join(meta.get("scene_dates", []) or ["unknown"])

    # ponytail: no inside/outside verdict on purpose. The polygons are
    # residual surface water from one pass ~14 h after the rain (mostly
    # marsh, shoreline and park water), so "outside" would falsely
    # reassure basement-flood areas. Validate against Ida HWMs and 311
    # before this layer says anything about a specific address.
    headline = f"{within_500m} within 500 m"
    narrative = (
        "Experimental: satellite-detected surface water about 14 hours after "
        f"Hurricane Ida (Sentinel-2, 2021-09-02): {within_500m} water polygons "
        "within 500 m of this address"
    )
    if nearest_m is not None:
        narrative += f", nearest {nearest_m} m away"
    narrative += (
        ". Most are marsh, shoreline and park water; street and basement "
        "flooding had drained by then and is not visible in this layer."
    )
    return PrithviSummary(
        nearest_distance_m=nearest_m,
        n_polygons_within_500m=within_500m,
        scene_id=sid,
        scene_date=sdate,
        headline_value=headline,
        subhead_text="surface water after Ida, experimental",
        narrative=narrative,
        raster_kind="prithvi",
        illustrative=False,
    )
