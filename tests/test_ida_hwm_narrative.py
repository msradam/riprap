"""Ida high-water marks give height above ground, and a water surface
elevation only when no mark in range has one."""

from riprap.core.pebbles.shapers.ida_hwm import shape


def _value(datum="NAVD88", above=2.05):
    props = {"site_description": "Barrett Ave.", "elev_ft": 25.3, "height_above_gnd": above,
             "vertical_datum": datum}
    return {"n_within_radius": 2, "radius_m": 800,
            "aggregations": {"max_elev_ft": 48.2, "max_height_above_gnd_ft": above},
            "nearest": {"distance_m": 120, "properties": props},
            "features": [{"lat": 40.6, "lon": -74.1, "distance_m": 120, "properties": props}]}


def test_height_above_ground_replaces_the_water_surface_elevation():
    n = shape(_value())["narrative"]
    assert "the highest stood 2.05 ft above ground" in n and "48.2" not in n and "NAVD88" not in n
    assert n.endswith("Nearest mark: Barrett Ave. (120 m away, 2.05 ft above ground).")


def test_elevation_only_without_a_ground_height_and_said_to_be_no_depth():
    n = shape(_value(above=None))["narrative"]
    assert "48.2 ft NAVD88 (an elevation above the survey datum, not a depth of water)" in n
    assert n.endswith("Nearest mark: Barrett Ave. (120 m away).")


def test_no_datum_means_no_elevation():
    assert "48.2" not in shape(_value(datum=None, above=None))["narrative"]
