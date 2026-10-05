"""Fetch a DEP stormwater scenario from the city's vector tile service.

NYC Open Data (9i7c-xyvv) ships the "Limited Flood (1.77 inches/hr) with
Current Sea Levels" map as a compressed file geodatabase (.cdf), which
GDAL's open driver cannot read. DEP's own map viewer (nyc.gov/stormwater-map)
draws the same map from a public vector tile service, so this script reads
that: it walks the service's tile index, reads every leaf tile with GDAL's
MVT driver, and writes the polygons to data/dep/<scenario>.gdb with the
same Flooding_Category codes the other three files use.

`--check` fetches the Moderate (current sea levels) tiles the same way and
compares them with the geodatabase from Open Data, which is how the tile
route was validated before the Limited map was trusted. On 2026-10-05 the
deep and contiguous category matched to 0.5% of its area once SHIFT_FT was
applied; the nuisance category did not (the viewer's Moderate tiles hold
about 10% more nuisance area than the Open Data file, so the two are
different versions of that map). The Limited tiles sit 99.3% inside the
Open Data Moderate map for the same sea level, as a smaller storm should.

Run:
    uv run python scripts/fetch_dep_limited.py [--check]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from riprap.core import http  # noqa: E402

TILES = "https://tiles.arcgis.com/tiles/at3rDjch5X7i9Bag/arcgis/rest/services/{service}/VectorTileServer"
# The viewer's "Limited Flood (1.77 in/hr) with Current Sea Levels" view draws
# the first service; the second is its "Moderate Flood (2.13 in/hr) with
# Current Sea Levels" view, used only by --check.
LIMITED = "Moderate_5yearMHHW_updateOB_VTile1_61424"
MODERATE_CURRENT = "TenYear_MHHW_updatedOB_61424_Tile1"
# Tile layer name prefix -> Flooding_Category code (dep_stormwater._DOMAIN).
CATEGORY = {"Nuisance Flooding": 1, "Deep and Contiguous Flooding": 2}
# Feet east and north to add after projecting the tiles (Web Mercator) to
# EPSG:2263. The tile service and the geodatabases differ by a constant
# datum offset of about 0.9 m; this is the offset that best lays the
# Moderate tiles' deep category over the geodatabase (--check, five windows
# across the boroughs, all agreeing to the half foot).
SHIFT_FT = (0.5, -3.0)


def leaves(node, z=0, x=0, y=0):
    """(z, x, y) of every tile the index marks as present with no children.
    A node is 0 (empty), 1 (a leaf tile) or its four children [NW, NE, SW, SE];
    the index itself is the zoom 0 tile."""
    if node == 1:
        yield z, x, y
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from leaves(child, z + 1, 2 * x + i % 2, 2 * y + i // 2)


def fetch(service: str) -> gpd.GeoDataFrame:
    base = TILES.format(service=service)
    index = http.get(f"{base}/tilemap", timeout=60).json()["index"]
    parts = []
    with tempfile.TemporaryDirectory() as tmp:
        for z, x, y in leaves(index):
            r = http.get(f"{base}/tile/{z}/{y}/{x}.pbf", timeout=60)
            r.raise_for_status()
            if not r.content:
                continue  # the index lists a few tiles the service serves empty
            p = Path(tmp) / f"{z}-{x}-{y}.pbf"
            p.write_bytes(r.content)
            for name, _ in pyogrio.list_layers(p):
                cat = next((c for k, c in CATEGORY.items() if name.startswith(k)), None)
                if cat is None:
                    continue  # "Area not included in analysis", "Wetland and Waterbodies"
                # CLIP (the driver's default) trims each tile's buffer, so pieces do not overlap.
                g = pyogrio.read_dataframe(p, layer=name, X=x, Y=y, Z=z, columns=[])
                parts.append(g.assign(Flooding_Category=cat)[["Flooding_Category", "geometry"]])
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:3857").to_crs("EPSG:2263")
    g["geometry"] = g.geometry.translate(*SHIFT_FT).make_valid()
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
    return g.dissolve("Flooding_Category").reset_index()


def main():
    if "--check" in sys.argv:
        import shapely

        from app.flood_layers import dep_stormwater

        tiles, gdb = fetch(MODERATE_CURRENT), dep_stormwater.load("dep_moderate_current")
        for cat in CATEGORY.values():
            a = tiles[tiles.Flooding_Category == cat].geometry.union_all()
            b = shapely.force_2d(gdb[gdb.Flooding_Category == cat].geometry.union_all())
            print(f"moderate current, category {cat}: tiles {a.area:,.0f} sq ft, geodatabase {b.area:,.0f} sq ft, "
                  f"ratio {a.area / b.area:.4f}, symmetric difference {a.symmetric_difference(b).area / b.area:.4%}")
        return
    g = fetch(LIMITED)
    out = REPO / "data" / "dep" / "dep_limited_current.gdb"
    pyogrio.write_dataframe(g, out, layer="dep_limited_current", driver="OpenFileGDB")
    for _, row in g.iterrows():
        print(f"category {row.Flooding_Category}: {row.geometry.area:,.0f} sq ft")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
