"""Defects an independent review found in the rule answers and the sources
they read (2026-10-01). Each case is the input the reviewer gave."""

import sys
from pathlib import Path

import pytest

from app.context import nws_obs, nyc311
from app.context.nyc311 import Complaint
from riprap.core.burr import rule_answer as ra
from riprap.core.burr import templated_reconciler as tr
from riprap.core.burr.evidence import cite
from riprap.core.burr.intake import _with_borough, heuristic_plan

SCHOOLS = {"doe_school_exposure": "2 flood-exposed NYC DOE schools within 1500 m: 0 inside the 2012 Sandy inundation "
                                  "extent and 2 inside the DEP extreme stormwater scenario (2080 sea-level rise)."}
COUNTS = {"doe_school_exposure": {"n_schools": 2, "n_inside_sandy_2012": 0, "n_in_dep_extreme_2080": 2}}


@pytest.mark.parametrize("question,lead", [
    ("Did any schools near here flood during Sandy?", "no"),       # 0 inside the Sandy extent, whatever the DEP count
    ("Are any schools inside the Sandy zone?", "no"),
    ("Are any schools near here inside the 2080 stormwater scenario?", "yes"),
    ("Are any schools near here exposed to flooding?", "yes"),
    ("Has the school flooded since Ida?", "facts"),                # a register records no flooding since a date
    ("Is the school on high ground?", "facts"),                    # the opposite question
    ("Are the schools safe from flooding?", "facts"),
    ("Which schools near here are exposed?", "facts"),
])
def test_an_asset_lead_follows_the_count_the_question_names(question, lead):
    assert ra.answer(question, SCHOOLS, COUNTS) == (lead, ["doe_school_exposure"])


def test_some_of_a_full_layer_is_in_part_unless_any_is_asked():
    texts = {"doh_hospital_exposure": "3 hospitals in this area: 1 inside the 2012 Sandy inundation extent."}
    v = {"doh_hospital_exposure": {"n_hospitals": 3, "n_inside_sandy_2012": 1, "n_in_dep_extreme_2080": 0}}
    assert ra.answer("Were the hospitals in MN06 inside the Sandy extent?", texts, v)[0] == "partly"
    assert ra.answer("Were any hospitals in MN06 inside the Sandy extent?", texts, v)[0] == "yes"


@pytest.mark.parametrize("span,query,want", [
    ("350 Fifth Avenue, New York, NY", "350 Fifth Avenue, New York, NY", "350 Fifth Avenue, New York, NY"),
    ("200 Water Street, NY", "200 Water Street, NY", "200 Water Street, NY"),
    ("35-37 Bleecker Street", "In Manhattan, is 35-37 Bleecker Street in a flood zone?", "35-37 Bleecker Street, Manhattan"),
    ("200 Water Street", "Is 200 Water Street safe? I commute from Queens", "200 Water Street"),
    ("90-01 183rd St, Hollis", "Did 90-01 183rd St in Hollis flood?", "90-01 183rd St, Hollis, Queens"),
    ("90-01 183rd St", "Did 90-01 183rd St flood?", "90-01 183rd St, Queens"),
])
def test_a_borough_is_added_only_when_the_query_says_or_implies_it(span, query, want):
    assert _with_borough(span, query) == want


def test_a_neighbourhood_named_after_a_borough_keeps_its_name():
    plan = heuristic_plan("Is 123 Oriental Boulevard, Manhattan Beach in a flood zone?")
    assert "Manhattan Beach" in plan["targets"][0]["text"] and not plan["targets"][0]["text"].endswith(", Manhattan")


def test_two_neighbourhoods_are_still_a_comparison():
    assert heuristic_plan("Red Hook vs Gowanus")["intent"] == "compare"
    assert heuristic_plan("Compare Red Hook and Gowanus")["intent"] == "compare"


def test_are_there_any_counts_the_kind_the_question_names():
    texts = {"nyc311": "12 NYC 311 flood-related complaints filed within 200 m in the last 5 years: 12 street flooding."}
    v = {"nyc311": {"n": 12, "years": 5, "by_kind": {"street flooding": 12}}}
    assert ra.answer("Are there any sewer backup complaints near here?", texts, v)[0] == "no"
    assert ra.answer("Are there any street flooding complaints near here?", texts, v)[0] == "yes"
    sensors = {"floodnet": "2 FloodNet sensors within 600 m have recorded 0 flood events."}
    v = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 0}}
    assert ra.answer("Do the sensors show any flooding?", sensors, v)[0] != "yes"
    assert ra.answer("Is there a FloodNet sensor near here?", sensors, v)[0] == "yes"


@pytest.mark.parametrize("question", [
    "Is there flooding risk at 80 Pioneer Street, Brooklyn?",
    "Is there flooding history at 80 Pioneer Street, Brooklyn?",
    "Is it flooding often at 80 Pioneer Street, Brooklyn?",
    "Is 80 Pioneer Street, Brooklyn currently in a FEMA flood zone?",
])
def test_a_risk_or_zone_question_is_not_a_right_now_question(question):
    assert not ra.asks_now(question) and heuristic_plan(question)["intent"] == "single_address"


def test_is_it_flooding_right_now_still_is():
    assert ra.asks_now("Is it flooding near 80 Pioneer Street, Brooklyn right now?")
    assert ra.asks_now("Is the street flooding in the FEMA zone right now? Is it flooding?")


def test_a_point_near_the_sandy_edge_gets_no_flat_yes_or_no():
    texts = {"sandy_inundation": "This address sits outside the footprint, about 40 m from the mapped edge."}
    q = "Was this address flooded during Sandy?"
    assert ra.soften("no", ["sandy_inundation"], {"sandy_inundation": {"inside": False, "edge_m": 40}}) == "facts"
    assert ra.soften("no", ["sandy_inundation"], {"sandy_inundation": {"inside": False, "edge_m": None}}) == "no"
    assert ra.answer(q, texts, {"sandy_inundation": {"inside": False, "edge_m": None}})[0] == "no"


def test_the_lead_says_how_near_the_sandy_edge_is():
    from test_address_lead import STATE

    near = {**STATE, "sandy": {**STATE["sandy"], "edge_m": 40, "edge_note": ", about 40 m from the mapped edge"}}
    assert "footprint (about 40 m from its mapped edge) [sandy_inundation]" in tr.compose_briefing(near)[0]


def test_a_request_logged_twice_at_an_intersection_counts_once():
    coded = Complaint("1", "Street Flooding (SJ)", "2023-09-29T10:00:00", None, None, 40.7, -73.9)
    plain = Complaint("2", "Flooding on Street", "2023-09-29T10:02:00", "114 STREET", None, 40.7, -73.9)
    later = Complaint("3", "Flooding on Street", "2023-09-29T12:00:00", "114 STREET", None, 40.7, -73.9)
    assert [c.unique_key for c in nyc311.one_per_incident([coded, plain, later])] == ["1", "3"]


def test_the_keys_call_a_catch_basin_row_a_catch_basin_and_twin_by_coordinates():
    sys.path.insert(0, str(Path(__file__).parent / "golden"))
    import keys

    assert keys._kind("Catch Basin Clogged/Flooding (Use Comments) (SC)") == keys._kind("Catch Basin Clogged")
    rows = [{"descriptor": "Street Flooding (SJ)", "created_date": "2023-09-29T10:00:00", "latitude": "40.7", "longitude": "-73.9"},
            {"descriptor": "Flooding on Street", "created_date": "2023-09-29T10:02:00", "incident_address": "114 STREET",
             "latitude": "40.7", "longitude": "-73.9"}]
    assert len(keys._once(rows)) == 1


def test_a_district_with_no_published_resident_count_does_not_say_zero(monkeypatch):
    from types import SimpleNamespace

    from app.areas import nta_evidence
    from riprap.core import http

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rows": [{"fp_100_bldg": 2, "fp_100_resunits": 1, "fp_100_pop": None, "fp_100_area": 0.01}]}

    monkeypatch.setattr(http, "get", lambda *a, **k: R())
    v = nta_evidence.floodplain(None, SimpleNamespace(extras={"area_code": "BK14"}))
    assert v["n_residents_2010"] is None and "0 resident" not in v["narrative"]
    assert "counts 2 buildings and 1 residential unit in" in v["narrative"]
    assert v["narrative"].endswith("The profile gives no resident count for this district.")


def test_the_register_builder_reads_inside_from_the_sandy_value(monkeypatch):
    from app import register_builder
    from riprap.core.pebbles import bridge

    answers = {"sandy": {"inside": False, "edge_m": None}}
    monkeypatch.setattr(bridge, "fetch_pebble", lambda pid, lat, lon: (answers.get(pid, {"depth_class": 0}), None, None))
    assert register_builder._snap(40.711, -73.7777)["sandy"] is False
    answers["sandy"] = None  # the layer did not answer: no register, not "outside"
    with pytest.raises(RuntimeError):
        register_builder._snap(40.711, -73.7777)


def test_a_citation_marker_does_not_land_inside_a_school_name():
    text = ("2 schools within 1500 m: 2 inside. Inside the 2012 Sandy extent: Liberation Diploma Plus (150 m), "
            "P.S. 90 Edna Cohen School (549 m), St. Mary's (5 m).")
    out = cite(text, "doe_school_exposure")
    assert "P.S [" not in out and "P.S. 90 Edna Cohen School" in out and "St. Mary's" in out


def test_wet_weather_with_a_zero_gauge_does_not_say_no_precipitation(monkeypatch):
    class R:
        def __init__(self, props):
            self.props = props

        def raise_for_status(self):
            pass

        def json(self):
            return {"properties": {"timestamp": "2026-10-01T03:35:00+00:00", "temperature": {"value": 15.0}, **self.props}}

    for sky in ("Light Rain", "Ice Pellets"):
        monkeypatch.setattr(nws_obs.http, "get", lambda *a, sky=sky, **k: R(
            {"textDescription": sky, "precipitationLastHour": {"value": 0.0}}))
        v = nws_obs.summary_for_point(40.711, -73.778)
        assert v["raining"] is True and "no precipitation" not in v["narrative"], sky


# What the third fresh question set found (fresh_r3_unblinded.json).

def test_the_place_is_the_neighbourhood_named_not_the_first_capitalised_word():
    plan = heuristic_plan("We're drafting a capital budget request for sewer upgrades. In Hollis, how many flood "
                          "related 311 complaints have there been?")
    assert plan["intent"] == "neighborhood" and plan["targets"][0]["text"] == "Hollis"


def test_a_borough_code_with_cd_is_a_district():
    assert heuristic_plan("SI CD 2: how many hospitals are in the flood zone?")["targets"][0]["text"] == "SI02"


def test_a_live_question_about_a_neighbourhood_is_read_there_not_at_city_hall():
    plan = heuristic_plan("Is it flooding in Broad Channel right now?")
    assert plan["intent"] == "live_now" and plan["targets"][0]["text"] == "Broad Channel, Queens, NY"


def test_a_place_with_its_borough_is_the_target_not_the_whole_question():
    plan = heuristic_plan("Hamilton Beach, Queens. Two things: how often have the tide gauges nearby hit flood stage?")
    assert plan["targets"][0]["text"] == "Hamilton Beach, Queens, NY"


def test_tonight_beside_a_register_question_is_not_a_now_question():
    q = "Manhattan Community District 3: which public schools were inside the Sandy line? A list would help tonight."
    assert not ra.asks_now(q)


def test_an_ida_mark_far_from_the_block_does_not_say_the_block_flooded():
    texts = {"ida_hwm": "USGS surveyed 1 Hurricane Ida high-water mark within 800 m of this address (691 m away)."}
    q = "Did 61-20 Woodside Ave flood during Ida?"
    assert ra.answer(q, texts, {"ida_hwm": {"n_within_radius": 1, "nearest_dist_m": 691}})[0] != "yes"
    # Review round 1 (B3): 174 m is not the block either. Within answer_checks.BLOCK_M it is.
    assert ra.answer(q, texts, {"ida_hwm": {"n_within_radius": 2, "nearest_dist_m": 174}})[0] == "near"
    assert ra.answer(q, texts, {"ida_hwm": {"n_within_radius": 2, "nearest_dist_m": 60}})[0] == "yes"


def test_a_hospital_just_outside_the_sandy_outline_is_named_not_counted_as_dry():
    """Bellevue and NYU Langone were closed by Sandy; their mapped points sit
    46 m and 3 m outside the outline. The district sentence names them, and
    "were any hospitals flooded by Sandy" gets no flat No."""
    from app.areas import nta
    from app.registers import exposure

    v = exposure.summary_for_polygon(nta.by_district("MN06")["geometry"], "doh_hospitals")
    assert v["n_inside_sandy_2012"] == 0 and v["n_near_sandy_edge"] == 2
    assert ("within 50 m of its mapped edge (the outline is not exact to a building): Bellevue Hospital Center, "
            "NYU Langone Hospitals") in v["narrative"]
    lead, _ = ra.answer("Were any hospitals in MN06 flooded by Sandy?", {"doh_hospital_exposure": v["narrative"]},
                        {"doh_hospital_exposure": v})
    assert lead == "facts"


# What the fourth fresh question set found (fresh_r4_unblinded.json).

@pytest.mark.parametrize("query,intent,target", [
    ("whats going on in hunts point rn any flooding", "live_now", "Hunts Point, Bronx, NY"),
    ("gowanus stormwater flooding 2050 vs 2080 scenario, whats the difference", "neighborhood", "Gowanus"),
    ("community district 301, any hospitals with flood exposure?", "neighborhood", "BK01"),
    ("east elmhurst ida high water marks, how many and the deepest one", "neighborhood", "East Elmhurst"),
    ("A constituent at 222 Bay Street on Staten Island keeps calling. What do the records show?", "single_address",
     "222 Bay Street, Staten Island"),
    ("Did Hamilton Beach flood during Sandy and how much of the neighborhood was underwater", "single_address",
     "Hamilton Beach, New York, NY"),
    ("Ferry Building, San Francisco", "single_address", "Ferry Building, San Francisco"),  # a short place keeps its city
])
def test_places_typed_the_way_people_type_them(query, intent, target):
    plan = heuristic_plan(query)
    assert (plan["intent"], plan["targets"][0]["text"]) == (intent, target)


def test_a_district_count_carries_coordinates_so_intersection_twins_drop(monkeypatch):
    """The golden set found QN12 one over and BK06 two over: the district
    fetch did not ask for coordinates, so the same-place rule had only
    addresses to go on."""
    asked = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"unique_key": "2", "descriptor": "Flooding on Street", "created_date": "2023-10-02T21:28:17.000",
                     "incident_address": "5 AVENUE", "latitude": "40.675777", "longitude": "-73.980889"},
                    {"unique_key": "1", "descriptor": "Street Flooding (SJ)", "created_date": "2023-10-02T21:26:00.000",
                     "latitude": "40.675777", "longitude": "-73.980889"}]

    monkeypatch.setattr(nyc311.http, "get", lambda url, params=None, **k: asked.update(params) or R())
    v = nyc311.summary_for_district("BK06")
    assert "latitude" in asked["$select"] and v["n"] == 1


# What a fresh-context walkthrough of the running app found.

def test_a_count_for_one_year_comes_from_that_year_not_the_window():
    import datetime

    from riprap.core.burr import answer_checks as ac

    docs = {"nyc311_nta": "871 NYC 311 flood-related complaints filed in Community District BX10 in the last 3 years."}
    v = {"nyc311_nta": {"n": 871, "years": 3, "by_kind": {"sewer backup": 500},
                        "by_year": {"2023": 92, "2024": 360, "2025": 203, "2026": 216}}}
    day = datetime.date(2026, 10, 1)
    last, undetermined = ac.count_lead("How many flood complaints did Bronx CD 10 get last year?", docs, v, day)
    assert last == "203 complaints to 311 about flooding and sewer backups filed in 2025, by the year each was filed [nyc311_nta]." and not undetermined
    assert ac.count_lead("How many flood complaints in 2024 in BX10?", docs, v, day)[0].startswith("360 ")
    assert ac.count_lead("How many flood complaints this year in BX10?", docs, v, day)[0].startswith("216 complaints to 311 about flooding and sewer backups filed in 2026 so far")
    # The window starts in October 2023, so 2023 is partly outside it; a month is not in the value at all.
    assert ac.count_lead("How many flood complaints in 2023 in BX10?", docs, v, day) == (None, True)
    assert ac.count_lead("How many flood complaints last month in BX10?", docs, v, day) == (None, True)
    assert ac.count_lead("How many flood complaints in BX10?", docs, v, day) == (None, False)


def test_311_complaints_alone_do_not_make_has_it_flooded_a_yes():
    texts = {"nyc311": "29 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years."}
    v = {"nyc311": {"n": 29, "years": 5, "by_year": {"2022": 9, "2023": 10, "2024": 10}}}
    assert ra.answer("Has 350 Fifth Avenue, Manhattan flooded since Hurricane Ida?", texts, v) == ("facts", ["nyc311"])
    assert ra.answer("Have people near 350 Fifth Avenue reported flooding to 311 since 2022?", texts, v)[0] == "yes"
    sensors = {**texts, "floodnet": "2 FloodNet sensors within 600 m have recorded 14 flood events."}
    v2 = {**v, "floodnet": {"n_sensors": 2, "n_flood_events_3y": 14}}
    assert ra.answer("Has this block flooded since Hurricane Ida?", sensors, v2)[0] == "yes"


@pytest.mark.parametrize("query,intent", [
    # A prediction, not a past date: declined in the answer, with what is forecast there (test_experimental.py).
    ("Will 90-01 183rd Street, Queens flood on October 15?", "single_address"),
    ("Will it flood on October 15?", "out_of_scope"),
    # Advice at a place that is named: the rules say Riprap gives none and quote the FEMA zone (test_rule_answer.py).
    ("Is it safe to rent a basement apartment at 153-10 Peck Avenue, Queens?", "single_address"),
    ("Is it safe to rent a basement apartment?", "out_of_scope"),
    ("what is flooding right now", "not_implemented"),                              # no place: point to the live tools
])
def test_declines(query, intent):
    plan = heuristic_plan(query)
    assert plan["intent"] == intent
    if intent == "not_implemented":
        assert "FloodNet sensor dashboard" in plan["rationale"] and "names none" in plan["rationale"]


def test_a_numbered_street_typed_without_its_ordinal_is_read():
    assert heuristic_plan("131 beach 96 st queens")["targets"][0]["text"] == "131 beach 96th st, Queens"
    assert heuristic_plan("560 5 avenue brooklyn")["targets"][0]["text"] == "560 5th avenue, Brooklyn"
    assert "311th" not in str(heuristic_plan("How many 311 street flooding complaints near 80 Pioneer St since Ida?"))


def test_a_place_outside_every_city_says_what_was_not_read():
    out = tr.compose_briefing({"intent": "single_address", "deployment": "__none__", "plan": {"question": ""},
                               "fema_nfhl": {"fld_zone": "X", "effective_year": 2006,
                                             "narrative": "This address sits in FEMA flood zone X, effective 2006."}})[0]
    assert "outside the cities Riprap covers" in out and "no local record of past flooding" in out


def test_register_name_lists_carry_the_scenario_year():
    """The disclosure check for projections wants a horizon in every sentence
    that names a scenario; the name list is its own sentence."""
    from app.registers import exposure
    from riprap.core.compliance.predicates import projection_has_horizon

    v = exposure.summary_for_point(40.5757, -73.986, "mta_entrances")
    assert ('In a rainfall flooding category of the modelled "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise" map, '
            "by station:") in v["narrative"] or "future high tides category of the modelled" in v["narrative"]
    assert projection_has_horizon(v["narrative"]).passed


def test_floodnet_distance_is_decided_here_not_by_the_service(monkeypatch):
    """The golden set: a sensor 599 m away with nine flood events was left out
    of a 600 m search by the service's own radius function."""
    from app.context import floodnet

    asked = {}
    rows = [{"deployment_id": "near", "name": "Q - 87th St", "sensor_status": "signal",
             "location": {"type": "Point", "coordinates": [-73.88184068, 40.76466648]}},   # 599 m
            {"deployment_id": "far", "name": "Q - 77th St", "sensor_status": "good",
             "location": {"type": "Point", "coordinates": [-73.8827, 40.7648]}}]           # about 670 m
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: asked.update(v) or {"deployments_within_radius": rows})
    found = floodnet.sensors_near(40.763193, -73.874995, 600)
    assert asked["r"] == 650 and [s.deployment_id for s in found] == ["near"]
