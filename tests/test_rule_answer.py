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
    "floodnet": "2 FloodNet sensors within 600 m have recorded 14 flood events in the last 3 years.",
    "nws_alerts": "No active NWS flood, coastal or tropical storm alerts at this point, checked 2026-10-01 03:40 UTC.",
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
    counts = {"mta_entrance_exposure": {"n_entrances": 5, "n_inside_sandy_2012": 3, "n_in_dep_extreme_2080": 0}}
    q = "Are any subway entrances near here exposed to flooding?"
    assert ra.answer(q, T, counts) == ("yes", ["mta_entrance_exposure"])
    assert ra.answer(q, T) == ("facts", ["mta_entrance_exposure"])  # no counts, no yes


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


def test_a_two_part_question_is_answered_part_by_part():
    # The first part's yes or no leads; the facts follow in the order asked.
    q = ("Was 204 Van Dyke Street, Brooklyn inside the area Hurricane Sandy flooded in 2012, and how many "
         "flood-related 311 complaints were filed within 200 m of it in the last five years?")
    assert ra.answer(q, T, {"sandy_inundation": {"inside": True}}) == ("yes", ["sandy_inundation", "nyc311"])
    # A district's Sandy share and its schools: both parts, the share first.
    area = {"sandy_nta": "14.2% of this area lies inside the 2012 Hurricane Sandy inundation extent.",
            "doe_school_exposure": "3 public schools in this area: 2 inside the 2012 Sandy inundation extent: P.S. 5."}
    lead, facts = ra.answer("Queens CD 14: how much of the district did Sandy flood, and which public schools are "
                            "inside that area?", area, {"sandy_nta": {"fraction": 0.142}})
    assert facts == ["sandy_nta", "doe_school_exposure"] and lead == "facts"
    # A preamble that names nothing adds nothing.
    lead, facts = ra.answer("We keep hearing about flooding. Is 80 Pioneer Street in a FEMA flood zone?", T)
    assert facts == ["fema_nfhl"]


def test_district_floodplain_counts_and_flood_history():
    area = {"dcp_floodplain_nta": "NYC Planning's Community District Profile counts 1,204 buildings in the floodplain.",
            "nyc311_nta": "4,530 NYC 311 flood-related complaints filed in this district in the last 3 years.",
            "sandy_nta": "0.8% of this area lies inside the 2012 Hurricane Sandy inundation extent."}
    # ("facts" and "count" print the same neutral opening.)
    assert ra.answer("How many people in Brooklyn Community District 6 live in the floodplain?", area) == (
        "facts", ["dcp_floodplain_nta"])
    # An area has no storm record of its own: the observed record it has, with no yes or no.
    # The district's 311 record is quoted for "since Ida", misspelt or not, with
    # no Yes: complaints are reports, not a measurement of flooding.
    assert ra.answer("Has Manhattan Community District 12 had any flooding since Hurricaine Ida?", area,
                     {"nyc311_nta": {"n": 4530, "years": 3, "by_year": {"2024": 1500, "2025": 1600}}}) == (
        "facts", ["nyc311_nta"])
    assert ra.answer("Was any part of Queens CD 12 inside the 2012 Sandy inundation zone?", area,
                     {"sandy_nta": {"fraction": 0.008}}) == ("yes", ["sandy_nta"])
    assert ra.asks_something("flooding history") and not ra.asks_something("flooding")


def test_a_source_s_own_count_answers_were_there_any():
    texts = {"ida_hwm": "USGS surveyed 0 Hurricane Ida high-water marks within 800 m of this address."}
    q = "Were any high-water marks surveyed after Ida near 1040 Grand Concourse?"
    assert ra.answer(q, texts, {"ida_hwm": {"n_within_radius": 0}}) == ("no", ["ida_hwm"])
    assert ra.answer(q, texts, {"ida_hwm": {"n_within_radius": 2}}) == ("yes", ["ida_hwm"])
    assert ra.answer(q, texts, {})[0] == "facts"  # no count, no yes or no


def test_what_a_scenario_map_shows_is_a_fact_and_a_prediction_is_not():
    v = {"dep_extreme_2080": {"depth_class": 2}}
    shows = "Does the city's stormwater map show water at 515 Malcolm X Boulevard in an extreme rainstorm?"
    assert ra.answer(shows, T, v) == ("yes", ["dep_extreme_2080"])
    assert ra.answer(shows, T, {"dep_extreme_2080": {"depth_class": 0}}) == ("no", ["dep_extreme_2080"])
    lead, facts = ra.answer("Will 515 Malcolm X Boulevard flood by 2080 under the stormwater scenario?", T, v)
    assert lead == "facts" and facts[0] == "dep_extreme_2080"


def test_weather_words_bring_the_observation_into_a_now_answer():
    dry = {"nws_obs": {"raining": False}}
    assert "nws_obs" in ra.answer("Its pouring. Is the street flooding near 79-01 Broadway right now?", T, dry)[1]
    assert "nws_obs" not in ra.answer("Is the street flooding near 79-01 Broadway right now?", T, dry)[1]


def test_a_follow_on_part_about_an_asset_does_not_quote_the_address_layer():
    q = ("Is the NYCHA development next to 80 Pioneer Street in the Sandy flood area, and does it also show up in "
         "the 2050 stormwater flood map?")
    texts = {**T, "nycha_development_exposure": "2 flood-exposed NYCHA developments within 2000 m: Red Hook East."}
    assert ra.answer(q, texts, {})[1] == ["nycha_development_exposure"]
