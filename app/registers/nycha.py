"""nycha_development_exposure — flood-exposure briefing per NYCHA development.

Same pattern as the MTA-entrance specialist, but NYCHA developments are
*polygons* not points, so the metrics shift to overlap fractions:

  - % of footprint inside the 2012 Sandy Inundation Zone (empirical)
  - % of footprint inside DEP Extreme-2080 / Moderate-2050 scenarios
    (modeled; Flooding_Category 1 and 2 are rainfall depths, 3 the
    future high tide area)
  - Representative-point elevation, HAND, TWI (proxy)
  - Footprint area (km²)
  - Distance from query point to development boundary

Joins:
  - data/nycha.geojson  (NYC Open Data, 218 NYCHA developments)
  - data/sandy_inundation.geojson
  - DEP Stormwater Flood Map polygons (3 scenarios)
  - data/nyc_dem_30m.tif, data/hand.tif

Per queried (lat, lon), returns developments whose centroid is within
the radius (default 2000 m — NYCHA developments are sparser than
subway entrances, so the radius is wider).

Honest scope:
  - This is exposure, not damage forecast. We say "85% of this
    development's footprint is inside the 2012 Sandy zone" — not
    "this development will flood next storm".
  - All overlap fractions are computed in EPSG:2263 (NYC State Plane,
    feet) for accurate area arithmetic in the city.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

log = logging.getLogger("riprap.nycha")

DATA = _ROOT / "data"
NYCHA = DATA / "nycha.geojson"

DEFAULT_RADIUS_M = 2000
DEFAULT_MAX_PER_QUERY = 5


@dataclass
class DevelopmentFinding:
    development: str
    tds_num: str
    borough: str
    centroid_lat: float
    centroid_lon: float
    distance_m: float
    rep_elevation_m: float | None
    rep_hand_m: float | None
    inside_sandy_2012: bool
    dep_extreme_2080_class: int          # 0=outside, 1/2/3 = Flooding_Category
    dep_extreme_2080_label: str
    dep_moderate_2050_class: int
    dep_moderate_2050_label: str
    dep_moderate_current_class: int
    dep_moderate_current_label: str


@lru_cache(maxsize=1)
def _load_nycha():
    import geopandas as gpd
    gdf = gpd.read_file(NYCHA).to_crs("EPSG:2263")  # feet, accurate areas
    gdf["centroid_2263"] = gdf.geometry.centroid
    return gdf.reset_index(drop=True)


@lru_cache(maxsize=1)
def _load_sandy_2263():
    """Load the Sandy zone in EPSG:2263 once. Already used by
    app.flood_layers.sandy_inundation but we want the geometry directly
    for overlap-fraction math."""
    import geopandas as gpd
    g = gpd.read_file(DATA / "sandy_inundation.geojson").to_crs("EPSG:2263")
    # Some NYC OEM Sandy polygons have hole-orientation issues that
    # blow up unary_union. buffer(0) fixes self-intersections without
    # changing the footprint at sub-foot precision.
    g["geometry"] = g.geometry.buffer(0)
    return g.geometry.union_all()


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _sample_raster(raster_path: Path, lat: float, lon: float) -> float | None:
    if not raster_path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            v = next(src.sample([(lon, lat)]))[0]
            v = float(v)
            if math.isnan(v) or v == src.nodata:
                return None
            return v
    except Exception:
        log.exception("raster sample failed for %s", raster_path)
        return None


def _developments_near(lat: float, lon: float, radius_m: float):
    """Return developments whose centroid is within `radius_m` of
    (lat, lon). Uses haversine on centroids re-projected back to
    EPSG:4326 — the bbox prefilter gets us close, then exact distance."""
    import geopandas as gpd
    gdf = _load_nycha()
    # Re-project centroids to 4326 for haversine
    cents_4326 = gpd.GeoSeries(gdf["centroid_2263"], crs="EPSG:2263").to_crs("EPSG:4326")
    deg = radius_m / 90_000
    cent_lat = cents_4326.y
    cent_lon = cents_4326.x
    mask = ((cent_lat >= lat - deg) & (cent_lat <= lat + deg)
            & (cent_lon >= lon - deg) & (cent_lon <= lon + deg))
    sub = gdf[mask].copy()
    if sub.empty:
        return sub, []
    sub["clat"] = cent_lat[mask].values
    sub["clon"] = cent_lon[mask].values
    sub["distance_m"] = sub.apply(
        lambda r: _haversine_m(lat, lon, r["clat"], r["clon"]),
        axis=1,
    )
    sub = sub[sub["distance_m"] <= radius_m].sort_values("distance_m")
    return sub, sub.index.tolist()


def summary_for_point(lat: float, lon: float,
                       radius_m: float = DEFAULT_RADIUS_M,
                       max_developments: int = DEFAULT_MAX_PER_QUERY) -> dict:
    """Return the tier-1-3 NYCHA developments near (lat, lon)
    within radius_m, with their pre-computed exposure flags from the
    register catalog at data/registers/nycha.json.

    The catalog is the source of truth for which developments are
    flood-exposed (the bake script ran the polygon-overlap math once,
    citywide). Per-query work is haversine + dict lookup — sub-ms even
    on the HF Space CPU. Developments outside the tier-1-3 catalog
    (truly unexposed inland sites) are intentionally not surfaced;
    "no NYCHA developments at risk within 1 mi" is the honest answer
    for low-exposure queries.
    """
    from app.flood_layers.dep_stormwater import class_label
    from app.registers._loader import narrative, nearest_n
    # Every register row in range counts; only the nearest
    # max_developments are listed. None in range is a true zero: the
    # register was read and nothing is near. A register that cannot be
    # read raises instead, and the step is reported as failed.
    hits = nearest_n("nycha", lat, lon, radius_m, None)

    findings: list[DevelopmentFinding] = []
    for distance_m, row in hits:
        snap = row.get("snap") or {}
        dep = snap.get("dep") or {}
        microtopo = snap.get("microtopo") or {}

        def _dep_class(scen: str) -> int:
            d = dep.get(scen) or {}
            return int(d.get("depth_class") or 0)

        c2080 = _dep_class("dep_extreme_2080")
        c2050 = _dep_class("dep_moderate_2050")
        ccur  = _dep_class("dep_moderate_current")

        elev = microtopo.get("point_elev_m")
        hand = microtopo.get("aoi_hand_m") or microtopo.get("hand_m")

        findings.append(DevelopmentFinding(
            development=str(row.get("name", "")),
            tds_num=str(row.get("tds_num", "")),
            borough=str(row.get("borough", "")),
            centroid_lat=round(float(row["lat"]), 5),
            centroid_lon=round(float(row["lon"]), 5),
            distance_m=round(distance_m, 1),
            rep_elevation_m=round(float(elev), 2) if elev is not None else None,
            rep_hand_m=round(float(hand), 2) if hand is not None else None,
            inside_sandy_2012=bool(snap.get("sandy")),
            dep_extreme_2080_class=c2080,
            dep_extreme_2080_label=class_label(c2080, "dep_extreme_2080"),
            dep_moderate_2050_class=c2050,
            dep_moderate_2050_label=class_label(c2050, "dep_moderate_2050"),
            dep_moderate_current_class=ccur,
            dep_moderate_current_label=class_label(ccur, "dep_moderate_current"),
        ))

    n_in_sandy = sum(1 for f in findings if f.inside_sandy_2012)
    n_in_2080 = sum(1 for f in findings if f.dep_extreme_2080_class > 0)
    return {
        "available": True,
        "n_developments": len(findings),
        "radius_m": radius_m,
        "n_inside_sandy_2012": n_in_sandy,
        "n_in_dep_extreme_2080": n_in_2080,
        # The register holds only exposed developments, so the count says so.
        "narrative": narrative(
            "flood-exposed NYCHA development", "flood-exposed NYCHA developments",
            len(findings), radius_m, n_in_sandy, n_in_2080,
            scope=" (the register lists only developments found inside the 2012 Sandy "
                  "extent or a DEP stormwater scenario, not every development)"),
        "developments": [vars(f) for f in findings[:max_developments]],
        "citation": ("Pre-computed from NYC Open Data NYCHA Developments "
                     "(phvi-damg) joined to Sandy 2012 Inundation Zone "
                     "(5xsi-dfpx) + NYC DEP Stormwater Flood Maps + "
                     "USGS 3DEP DEM. See data/registers/nycha.json."),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS_M)
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_PER_QUERY)
    args = ap.parse_args()
    s = summary_for_point(args.lat, args.lon, args.radius, args.max)
    print(json.dumps(s, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
