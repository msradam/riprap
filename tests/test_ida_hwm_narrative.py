"""Ida high-water marks lead with height above ground and give the
elevation only with its datum."""

from riprap.core.pebbles.shapers.ida_hwm import shape


def _value(datum="NAVD88", above=2.05):
    props = {"site_description": "Barrett Ave.", "elev_ft": 25.3, "height_above_gnd": above,
             "vertical_datum": datum}
    return {"n_within_radius": 2, "radius_m": 800,
            "aggregations": {"max_elev_ft": 48.2, "max_height_above_gnd_ft": above},
            "nearest": {"distance_m": 120, "properties": props},
            "features": [{"lat": 40.6, "lon": -74.1, "distance_m": 120, "properties": props}]}


def test_height_above_ground_first_then_elevation_with_datum():
    n = shape(_value())["narrative"]
    assert n.index("2.05 ft above ground") < n.index("48.2 ft NAVD88")


def test_no_datum_means_no_elevation():
    n = shape(_value(datum=None))["narrative"]
    assert "48.2" not in n and "2.05 ft above ground" in n
