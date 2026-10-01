"""Answers picked from the question's own words, with no model, and the
place parsing they depend on. The cases are questions a fresh reader wrote
that the first version got wrong (research_notes: fresh_r1_unblinded.json)."""

import pytest

from app.planner import is_bare_place
from riprap.core.burr import rule_answer as ra
from riprap.core.burr.intake import heuristic_plan

SANDY = "This address is inside the 2012 Sandy inundation footprint (NYC Open Data)."
T = {
    "sandy_inundation": SANDY,
    "nyc311": "7 flood-related 311 service requests within 200 m in the last 5 years.",
    "fema_nfhl": "This address sits in FEMA flood zone AE.",
    "floodnet": "2 FloodNet community sensors within 600 m have logged 14 flood events in the last 3 years.",
    "nws_alerts": "No active NWS flood, coastal or wind alerts at this point, checked 2026-10-01 03:40 UTC.",
    "noaa_tides": "The Battery tide gauge reads 4.1 ft above MLLW.",
    "usgs_gauges": "The nearest stream gauge reads 1.2 ft.",
    "nws_obs": "JFK: clear, 18.0°C, no precipitation reported.",
    "nws_water_forecast": "The National Weather Service forecasts a peak water level of 6.0 ft above MLLW at The Battery.",
    "npcc4_slr": "NPCC4 projects 0.38 m of sea-level rise by the 2050s.",
    "dep_moderate_2050": "The DEP 2050 scenario models nuisance flooding here.",
    "dep_extreme_2080": "The DEP 2080 scenario models deep and contiguous flooding here.",
    "mta_entrance_exposure": "3 of 5 subway entrances within 800 m are inside the Sandy extent: Smith St.",
}


@pytest.mark.parametrize("query,intent,target", [
    ("200 Water Street Manhattan FEMA flood zone", "single_address", "200 Water Street, Manhattan"),
    ("How many 311 street flooding complaints have there been near 80 Pioneer St since Ida?", "single_address",
     "80 Pioneer St"),  # "311 street" is not an address
    ("Compare the current and 2080 stormwater flood maps at 89-11 Merrick Boulevard", "single_address",
     "89-11 Merrick Boulevard, Queens"),  # one place, and a Queens house number
    ("Is 1310 Surf Ave, Bklyn in a flood zone?", "single_address", "1310 Surf Ave, Brooklyn"),
    ("Did 90-01 183rd St in Hollis flood during Ida?", "single_address", "90-01 183rd St, Hollis, Queens"),
])
def test_the_place_is_read_from_the_question(query, intent, target):
    plan = heuristic_plan(query)
    assert (plan["intent"], plan["targets"][0]["text"]) == (intent, target)
    assert not is_bare_place(query, plan["targets"])


def test_two_addresses_still_compare_and_a_bare_place_has_no_question():
    plan = heuristic_plan("Compare 80 Pioneer Street, Brooklyn to 200 Water Street, Manhattan")
    assert plan["intent"] == "compare" and len(plan["targets"]) == 2
    for bare in ("80 Pioneer Street, Brooklyn", "flood risk 442 East Houston Street", "Hollis flooding"):
        assert is_bare_place(bare, heuristic_plan(bare)["targets"])


def test_a_now_question_reads_the_live_sources_and_never_says_yes_or_no():
    lead, facts = ra.answer("Is it flooding near 80 Pioneer Street right now?", T, {"nws_obs": {"raining": False}})
    assert lead == "facts" and facts == ["nws_alerts", "floodnet", "noaa_tides", "nws_water_forecast"]
    lead, facts = ra.answer("What is the tide right now near 80 Pioneer Street?", T, {})
    assert facts[0] == "noaa_tides" and "usgs_gauges" not in facts  # what was asked first, no padding
    assert "nws_obs" in ra.answer("Is it flooding right now?", T, {"nws_obs": {"raining": True}})[1]


def test_a_named_asset_is_answered_from_its_register_alone():
    assert ra.answer("Are any subway entrances near here exposed to flooding?", T) == ("yes", ["mta_entrance_exposure"])


def test_a_count_question_keeps_the_second_subject():
    lead, facts = ra.answer("Was it in the Sandy area, and how many 311 flood complaints are there?", T)
    assert facts[:2] == ["nyc311", "sandy_inundation"] or facts[:2] == ["sandy_inundation", "nyc311"]


def test_a_far_projection_leaves_out_this_weeks_tide_forecast():
    lead, facts = ra.answer("What sea level rise is projected here by the 2050s?", T)
    assert lead == "facts" and "npcc4_slr" in facts and "nws_water_forecast" not in facts
    assert ra.answer("What does the 2080 scenario show here?", T)[1][0] == "dep_extreme_2080"


def test_a_named_source_that_returned_nothing_is_not_answered_with_another():
    texts = {k: v for k, v in T.items() if k != "nyc311"}
    assert ra.answer("How many 311 flood complaints are there near here?", texts) == ("cannot_answer", [])


def test_an_area_sandy_question_says_yes_from_the_share():
    texts = {"sandy_nta": "0.8% of this area is inside the 2012 Sandy inundation footprint."}
    assert ra.answer("Did Sandy flood any of QN12?", texts, {"sandy_nta": {"fraction": 0.008}}) == ("yes", ["sandy_nta"])
    assert ra.answer("Did Sandy flood any of QN12?", texts, {"sandy_nta": {"fraction": 0.0}}) == ("no", ["sandy_nta"])


def test_no_rule_no_answer():
    assert ra.answer("Who is the council member here?", T) is None
    assert ra.asks_something("FEMA flood zone") and not ra.asks_something("flooding")
