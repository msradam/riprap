"""NYCHA Developments (NYC OpenData phvi-damg).

326 public-housing developments across NYC. Used as an asset class for
the bulk-mode register; the parent rationale for surfacing this layer
is that NYCHA was hit hard by Sandy and remains a published Tier-1
flood-resilience priority in the city's Hazard Mitigation Plan.
"""
from __future__ import annotations

import geopandas as gpd

from app.spatial import DATA, load_layer

# A development is inside the 2012 Sandy extent when this share or more of
# its mapped outline is. Its centre point alone found 20 developments and
# missed Hammel (94% inside); the threshold keeps out a sliver at the edge
# of an outline that is not exact to a building.
SANDY_MIN_SHARE = 0.10


def footprint_share(footprints: gpd.GeoDataFrame, layer: gpd.GeoDataFrame) -> list[float]:
    """The fraction of each footprint's area inside the layer (same CRS).
    The layer's overlapping pieces are unioned, so no area counts twice."""
    index = layer.sindex
    out = []
    for geom in footprints.geometry:
        hits = layer.geometry.iloc[index.query(geom, predicate="intersects")]
        out.append(float(hits.intersection(geom).union_all().area / geom.area) if len(hits) else 0.0)
    return out


def load() -> gpd.GeoDataFrame:
    from app.flood_layers import sandy_inundation

    g = load_layer(DATA / "nycha.geojson").copy()
    # Measured on the outline, before it becomes a point.
    g["sandy_share"] = [round(s, 4) for s in footprint_share(g, sandy_inundation.load().to_crs(g.crs))]
    g["sandy"] = (g["sandy_share"] >= SANDY_MIN_SHARE).astype(int)
    # The stormwater joins and the distance from an address still use the
    # centre point, and the register sentence says so.
    g["geometry"] = g.geometry.centroid

    # NYCHA Developments has only `developmen` (truncated label), tds_num, borough.
    g = g.rename(columns={"developmen": "name"})
    g["address"] = g["name"]  # the field doubles as both
    g["borough"] = g["borough"].str.title()  # "BRONX" -> "Bronx" to match Riprap convention

    keep = [c for c in ["name", "address", "borough", "tds_num", "sandy_share", "sandy", "geometry"] if c in g.columns]
    return g[keep].copy()
