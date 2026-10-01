"""A point near the mapped edge of the 2012 Sandy zone says so. The
outline was drawn in 2013 and is not exact to a building: 204 Van Dyke
Street, Red Hook sits in a dry pocket about 38 m from mapped flooding (an
independent overlay on the published polygons gives 37.7 m), and "outside"
alone read like "outside" a mile inland."""

import geopandas as gpd
from shapely.geometry import Point

from app.flood_layers import sandy_inundation


def _pt(lat, lon):
    return gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263").iloc[0]


def test_a_point_near_the_mapped_edge_states_the_distance():
    v = sandy_inundation.at_point(_pt(40.677684, -74.016841))  # 204 Van Dyke Street
    assert v["inside"] is False and 33 <= v["edge_m"] <= 43
    assert v["edge_note"].startswith(", about ") and "from the mapped edge" in v["edge_note"]


def test_a_point_far_from_the_edge_says_nothing_more():
    inland = sandy_inundation.at_point(_pt(40.711001, -73.777712))  # Hollis
    deep = sandy_inundation.at_point(_pt(40.575285, -73.981469))    # 1310 Surf Avenue, 200 m inside
    assert inland == {"inside": False, "edge_m": None, "edge_note": ""}
    assert deep == {"inside": True, "edge_m": None, "edge_note": ""}
