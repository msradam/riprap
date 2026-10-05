"""The four NYC stormwater flood map pebbles: what each reads at a point,
how the sentence words it, and how near the mapped edge the point is.

Verifies that:
  - all four pebbles load and agree with dep_stormwater.join_raster() on the same point,
  - the sentence uses the city's own map and category names and says no more than the city's disclaimer allows,
  - a point near the mapped edge states the distance (as the Sandy sentence does),
  - an outside reading carries NYC Emergency Management's caveat,
  - the baked rasters cover the same area as the polygons they were baked from.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from riprap.core.pebbles import SpatialQuery, load_registry

TEST_LAT = 40.7100
TEST_LON = -73.9800

SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current", "dep_limited_current")
# The map names as NYC Open Data lists them (data.cityofnewyork.us/api/views/9i7c-xyvv.json, read 2026-10-05).
CITY_NAMES = {
    "dep_extreme_2080": "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise",
    "dep_moderate_2050": "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise",
    "dep_moderate_current": "Moderate Flood (2.13 inches/hr) with Current Sea Levels",
    "dep_limited_current": "Limited Flood (1.77 inches/hr) with Current Sea Levels",
}


@pytest.fixture(scope="module")
def registry():
    return load_registry("deployments/nyc")


def _pt(lat, lon):
    import geopandas as gpd  # noqa: PLC0415
    from shapely.geometry import Point  # noqa: PLC0415

    return gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263").iloc[0]


def _manifest(sid):
    return SimpleNamespace(id=sid, title="t", provenance=SimpleNamespace(citation="c"))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_dep_pebble_matches_legacy(registry, scenario):
    from app.flood_layers.dep_stormwater import join_raster  # noqa: PLC0415

    legacy_cls = int(join_raster(_pt(TEST_LAT, TEST_LON), scenario))

    result = registry.get(scenario).fetch(SpatialQuery(lat=TEST_LAT, lon=TEST_LON))
    assert result.error is None, result.error
    # Class 0 (outside the scenario) is reported as an "outside" record.
    assert isinstance(result.value, dict)
    assert result.value["depth_class"] == legacy_cls
    assert "depth_label" in result.value
    assert "narrative" in result.value
    if legacy_cls == 0:
        assert result.value["depth_label"] == "outside"
        assert "shows no flooding category" in result.value["narrative"]
    assert result.value["citation"].startswith("NYC Stormwater Flood Maps (NYC Open Data 9i7c-xyvv")


def test_the_maps_carry_the_citys_own_names(registry):
    from app.flood_layers import dep_stormwater  # noqa: PLC0415

    assert {s: v["name"] for s, v in dep_stormwater.SCENARIOS.items()} == CITY_NAMES
    for sid, name in CITY_NAMES.items():
        assert registry.get(sid).manifest.title == f"NYC Stormwater Flood Map - {name}"


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("cls", [0, 1, 2, 3])
def test_every_sentence_is_a_scenario_at_the_mapped_point_and_no_determination(scenario, cls):
    from app.flood_layers import dep_stormwater  # noqa: PLC0415
    from riprap.core.pebbles.shapers.dep_scenario import shape  # noqa: PLC0415

    if cls == 3 and not dep_stormwater.SCENARIOS[scenario]["year"]:
        return  # the current-sea-level files have no future high tide category
    v = shape({"depth_class": cls, "edge_m": None}, _manifest(scenario))
    text = v["narrative"]
    assert f'"{CITY_NAMES[scenario]}"' in text
    assert "is a modelled scenario (a design storm paired with " in text and "not a forecast" in text
    assert "at the point mapped for this address" in text and "This address is" not in text
    assert "public areas and rain only" in text
    assert '"does not provide the exact depth of flooding at any location"' in text
    assert "not a flood plain determination" in text
    # The category is the city's own name for it, never a depth worded for a building.
    assert v["category"] == dep_stormwater.domain(scenario).get(cls)
    if cls:
        assert f'shows the category "{v["category"]}"' in text
    assert "in/hr" not in text and "DEP " not in text


def test_tidal_inundation_is_never_called_rainfall_flooding():
    from riprap.core.pebbles.shapers.dep_scenario import shape  # noqa: PLC0415

    tide = shape({"depth_class": 3, "edge_m": None}, _manifest("dep_extreme_2080"))["narrative"]
    assert 'the category "Future High Tides 2080" (coastal tidal inundation, not rainfall flooding)' in tide
    rain = shape({"depth_class": 2, "edge_m": None}, _manifest("dep_extreme_2080"))["narrative"]
    assert 'the category "Deep and Contiguous Flooding (1 ft. and greater)"' in rain and "tidal" not in rain


def test_an_outside_reading_carries_the_emergency_management_caveat():
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT  # noqa: PLC0415
    from riprap.core.pebbles.shapers.dep_scenario import shape  # noqa: PLC0415

    # NYC Emergency Management's words (nychazardmitigation.com/documentation/hazard-profiles/flooding/, read 2026-10-05).
    assert ('"The most heavily impacted areas, representing over half of all damaged buildings, were also outside of '
            'any flood risk scenario, including FEMA floodplain maps"') in OUTSIDE_CAVEAT
    assert "nychazardmitigation.com" in OUTSIDE_CAVEAT and "does not mean safe" in OUTSIDE_CAVEAT
    outside = shape({"depth_class": 0, "edge_m": None}, _manifest("dep_moderate_2050"))["narrative"]
    inside = shape({"depth_class": 1, "edge_m": None}, _manifest("dep_moderate_2050"))["narrative"]
    assert outside.endswith(OUTSIDE_CAVEAT) and OUTSIDE_CAVEAT not in inside


def test_a_point_near_the_mapped_edge_states_the_distance(registry):
    """80 Pioneer Street reads outside the Extreme map with mapped flooding
    about 4 m away (an independent overlay gave 4.3 m), and 400 Carroll
    Street reads inside a pixel from the edge. One pixel with no margin
    read the same as a point a mile from any mapped flooding."""
    from app.flood_layers import dep_stormwater  # noqa: PLC0415

    pioneer = dep_stormwater.at_point(_pt(40.678113, -74.009514), "dep_extreme_2080")
    assert pioneer["depth_class"] == 0 and 3 <= pioneer["edge_m"] <= 6
    carroll = dep_stormwater.at_point(_pt(40.678299, -73.989605), "dep_extreme_2080")
    assert carroll["depth_class"] == 3 and 1 <= carroll["edge_m"] <= 4
    v = registry.get("dep_extreme_2080").fetch(SpatialQuery(lat=40.678113, lon=-74.009514)).value
    assert v["edge_m"] == pioneer["edge_m"]
    assert f"(about {v['edge_m']} m from the nearest flooding mapped on it)" in v["narrative"]
    v = registry.get("dep_extreme_2080").fetch(SpatialQuery(lat=40.678299, lon=-73.989605)).value
    assert f"about {v['edge_m']} m from the edge of the mapped flooding" in v["narrative"]


def test_a_point_far_from_any_mapped_flooding_says_nothing_more():
    from app.flood_layers import dep_stormwater  # noqa: PLC0415

    # Central Park's Great Lawn: no flooding mapped within 50 m on the Limited map.
    assert dep_stormwater.at_point(_pt(40.7812, -73.9665), "dep_limited_current") == {"depth_class": 0, "edge_m": None}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_baked_raster_covers_the_area_of_its_polygons(scenario):
    """The raster-to-vector area ratio, as the sanity check ran it for the
    first three maps: within half a percent for each."""
    import rasterio  # noqa: PLC0415

    from app.flood_layers import dep_stormwater  # noqa: PLC0415

    with rasterio.open(dep_stormwater.BAKED / f"{scenario}.tif") as ds:
        raster = float((ds.read(1) > 0).sum()) * ds.res[0] * ds.res[1]
    vector = float(dep_stormwater.load(scenario).geometry.area.sum())
    assert abs(raster / vector - 1) < 0.005


def test_the_limited_map_sits_inside_the_moderate_map_for_the_same_sea_level():
    """A smaller storm on the same sea level floods less. The Limited map
    comes from DEP's tile service and the Moderate from NYC Open Data, so
    this is also the check that the two line up."""
    import rasterio  # noqa: PLC0415

    from app.flood_layers import dep_stormwater  # noqa: PLC0415

    with rasterio.open(dep_stormwater.BAKED / "dep_limited_current.tif") as a, \
            rasterio.open(dep_stormwater.BAKED / "dep_moderate_current.tif") as b:
        limited, moderate = a.read(1) > 0, b.read(1) > 0
    assert limited.sum() < moderate.sum()
    assert (limited & ~moderate).sum() / limited.sum() < 0.03
