"""A plain place briefing says less: the terrain sentence keeps the two
figures a reader can use, and a live reading is quoted only when notable.
The values stay in the evidence table."""

from riprap.core.burr import templated_reconciler as tr
from riprap.core.burr.intake import heuristic_plan


class E:
    def __init__(self, pebble_id):
        self.pebble_id = pebble_id


def test_unremarkable_live_readings_are_not_quoted_in_a_plain_briefing():
    state = {"nws_obs": {"raining": False}, "usgs_gauges": {"n_gauges_in_area": 0},
             "noaa_tides": {"residual_ft": 0.2}, "nws_water_forecast": {"flood_category": None},
             "nws_alerts": {"n_active": 0}}
    assert all(tr._quiet(state, E(p)) for p in ("nws_obs", "usgs_gauges", "noaa_tides", "nws_water_forecast"))
    assert not tr._quiet(state, E("nws_alerts"))  # "no active alerts" is always said
    loud = {"nws_obs": {"raining": True}, "usgs_gauges": {"n_gauges_in_area": 1},
            "noaa_tides": {"residual_ft": 1.4}, "nws_water_forecast": {"flood_category": "minor"}}
    assert not any(tr._quiet(loud, E(p)) for p in loud)


def test_terrain_sentence_keeps_elevation_and_the_low_spot_percentile():
    from app.context.microtopo import microtopo_at

    m = microtopo_at(40.7106, -73.7785)
    if m is None:  # the DEM is not in this checkout (no LFS)
        return
    assert m.narrative.startswith("Elevation ") and "percentile" in m.narrative
    assert "HAND" not in m.narrative and "TWI" not in m.narrative and "basin relief" not in m.narrative
    assert m.hand_m is not None  # still in the value


def test_nycha_developments_are_not_a_construction_question():
    assert heuristic_plan("Which NYCHA developments in BK06 are in the Sandy flood area?")["intent"] == "neighborhood"
    assert heuristic_plan("How many buildings in QN12 are in the floodplain?")["intent"] == "neighborhood"
    assert heuristic_plan("What construction is underway in Gowanus?")["intent"] == "development_check"
