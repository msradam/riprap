"""Review round 1, Section B: how questions are answered and places resolved.

Nine audience reviewers put their own questions to Riprap. The questions
are here word for word, one test per finding. Nothing here reaches the
network: the rules read the question and a fixed set of source sentences."""

import datetime

import pytest

from app.planner import is_bare_place
from riprap.core.burr import answer_checks as ac
from riprap.core.burr import rule_answer as ra
from riprap.core.burr.intake import heuristic_plan

OUTSIDE = "Outside a mapped extent does not mean safe"
T = {
    "floodnet": "2 FloodNet sensors within 600 m have recorded 10 flood events in the last 3 years.",
    "nyc311": "81 NYC 311 flood and sewer complaints filed within 200 m of this location in the last 5 years.",
    "ida_hwm": "No Hurricane Ida (Sept 2021) high-water marks were surveyed within 800 m of this address.",
    "sandy_inundation": "This address sits outside the empirical 2012 Hurricane Sandy inundation footprint.",
    "dep_moderate_current": f"The city's stormwater flood map shows no flooding category at the point mapped. {OUTSIDE}: NYC "
                            "Emergency Management reports that damaged buildings were outside any scenario.",
    "dep_extreme_2080": "The city's stormwater flood map shows the category \"Future High Tides 2080\" at the point mapped.",
    "fema_nfhl": "This address sits in FEMA flood zone X (an area of minimal flood hazard) on FEMA's effective flood map.",
    "fema_pfirm": "FEMA's preliminary flood map places this address in zone X.",
    "nws_alerts": "No active NWS flood, coastal or tropical storm alerts at this point, checked 2026-10-05 16:00 UTC.",
    "noaa_tides": "Latest reading at The Battery: 1.87 ft above MLLW.",
    "nws_water_forecast": "The National Weather Service forecasts a peak water level of 5.4 ft above MLLW at The Battery.",
    "doe_school_exposure": "8 public schools in this area: 7 inside the 2012 Sandy inundation extent and 2 inside the DEP "
                           "extreme stormwater scenario.",
    "dcp_floodplain_nta": "NYC Planning counts 12,000 residents in this district's 1% annual chance floodplain.",
}
ADDRESS = {k: v for k, v in T.items() if not k.endswith("_nta")}  # what an address returns
# FloodNet's value as the rules read it: the private rows (one per sensor with verified events, nearest first).
ROWS = [{"distance_m": 413.0, "status": "noisy", "events": [{"date": "2026-05-20", "max_depth_mm": 1172},
                                                             {"date": "2026-08-20", "max_depth_mm": 300}]},
        {"distance_m": 520.0, "status": "good", "events": [{"date": "2026-05-20", "max_depth_mm": 954}]}]
FLOODNET = {"n_sensors": 2, "n_flood_events_3y": 3, "n_flood_events_good_3y": 1, "period_start": "2023-10-26", "_rows": ROWS}


def _synthesize(monkeypatch, question, texts=T, values=None, **state):
    """synthesize() over fixed sentences, with no source read and no model."""
    from types import SimpleNamespace

    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import Doc

    docs = [Doc(d, "Evidence", t, False) for d, t in texts.items()]
    items = [SimpleNamespace(doc_id=d.doc_id, pebble_id=d.doc_id) for d in docs]
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn, "compose_briefing", lambda s: (f"{syn._scope_header(s)}\n\n**Evidence.**\nThe records.", {}))
    return syn.synthesize({"intent": "single_address", **(values or {}), **state, "plan": {"question": question}},
                          use_llm=False)


# --- B4: what Riprap does not hold is said first, and the question is not marked answered ---

@pytest.mark.parametrize("question,topic", [
    ("What should Community Board 12 ask DEP to fix first in QN12?", "advice"),
    ("Which neighborhood should the city prioritize for cooling centers?", "advice"),
    ("Should the city relocate residents of Edgemere, Queens?", "advice"),
    ("Is flooding in QN12 getting worse?", "trend"),
    ("Who is most at risk from flooding in East Harlem?", "people"),
    ("How many older adults live alone without air conditioning in QN12?", "people"),
    ("How many Black residents live in Hunts Point?", "people"),
    ("What is the median income in Hunts Point?", "income"),
    ("How many basement apartments are in QN04?", "basements"),
    ("Are there illegal basement apartments near 90-01 183rd Street, Queens?", "basements"),
    ("Who lives at 90-12 183rd Street, Queens and have they complained to 311?", "people"),
    ("What is the flood risk score for 80 Pioneer Street, Brooklyn?", "score"),
    ("How many noise complaints did BK06 get from 311?", "other_311"),
    ("Can my landlord evict me after a flood at 80 Pioneer Street, Brooklyn?", "law"),
    ("Is my house at 90-01 183rd Street, Queens eligible for a city buyout?", "benefits"),
    ("Where can I get help after flooding at 90-01 183rd Street, Queens?", "benefits"),
    ("Did the May 20 2026 storm match the city's extreme stormwater scenario in Hollis?", "rain_on_a_day"),
    ("Which block in Hollis floods the worst?", "ranking"),  # B14
])
def test_a_question_about_something_riprap_does_not_hold_is_told_so_and_not_answered(monkeypatch, question, topic):
    assert ra.not_held(question)[0] == topic
    assert ra.answer(question, T, {}) == ("not_held", [])
    out = _synthesize(monkeypatch, question)
    g, sentence = out["grounding"], ra.not_held(question)[1]
    assert (g["answered"], g["answer_lead"], g["not_held"]) == (False, "not_held", topic)
    # B5: the text itself says so, where the answer would be, before any record.
    assert f"**Answer.**\n{sentence}" in out["paragraph"]
    assert out["paragraph"].index(sentence) < out["paragraph"].index("**Evidence.**")


def test_help_and_law_questions_get_plain_links_and_no_advice():
    for q in ("Can my landlord evict me after a flood at 80 Pioneer Street, Brooklyn?",
              "Where can I get help after flooding at 90-01 183rd Street, Queens?"):
        sentence = ra.not_held(q)[1]
        for link in ("https://portal.311.nyc.gov", "https://a858-nycnotify.nyc.gov", "https://www.floodhelpny.org"):
            assert link in sentence
        assert "should" not in sentence and "recommend" not in sentence


def test_an_ask_no_rule_recognises_is_unanswered_and_never_given_the_neutral_lead(monkeypatch):
    # "Does NYU CUSP endorse Riprap?" geocoded to a building and was once shown its briefing as an answer.
    for q in ("Does NYU CUSP endorse Riprap?", "Does NYU CUSP endorse Riprap's flood model at 370 Jay Street, Brooklyn?",
              "Whose fault is the flooding at 80 Pioneer Street, Brooklyn?"):
        assert ra.answer(q, T, {}) is None, q
    out = _synthesize(monkeypatch, "Does NYU CUSP endorse Riprap?")
    g = out["grounding"]
    assert (g["answered"], g["answer_lead"], g["answer_mode"]) == (False, "not_recognised", None)
    assert "**Answer.**\nRiprap's rules did not recognise what this question asks, so it is not answered." in out["paragraph"]


@pytest.mark.parametrize("question", [
    "Does Hollis flood?", "does hollis flood a lot", "How bad is the flooding near 80 Pioneer Street, Brooklyn?",
    "Has 80 Pioneer Street, Brooklyn flooded since Ida?", "Flood history since Sandy for 80 Pioneer Street",
    "I rent a basement on Pioneer Street. Has the block flooded?",  # a preamble names nothing
    "My landlord says it never floods. Does 80 Pioneer Street, Brooklyn flood?",
    "How many people in Brooklyn Community District 6 live in the floodplain?",  # City Planning counts them
    "How many 311 complaints about street flooding near 80 Pioneer Street, Brooklyn?",
    "How many flooding complaints have people near 2017 East 17th Street, Brooklyn made to 311?",  # complaints, not people
    "What flood events have been recorded near 400 Carroll Street, Brooklyn?",
    "Which schools in BK18 are in the flood zone?",
])
def test_questions_the_rules_do_recognise_stay_answered(question):
    got = ra.answer(question, T, {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 10}})
    assert got and got[1] and got[0] not in (*ac.UNANSWERED_LEADS, "not_recognised"), (question, got)


def test_a_ranking_with_no_place_says_riprap_does_not_rank():
    plan = heuristic_plan("Which community district has the most flooding?")
    assert plan["intent"] == "not_implemented"
    assert plan["rationale"].startswith("Riprap does not rank places against each other")


def test_every_result_says_whether_the_question_was_answered():
    # B5: `answer_path` is "rules" for an unanswered question too, so the result carries `answered` beside it.
    from riprap.core.burr import app

    out = app._final({"query": "q", "paragraph": "", "grounding": {"tier": "no_llm", "answered": False}})
    assert (out["answer_path"], out["answered"]) == ("rules", False)
    assert app._final({"query": "q", "paragraph": "", "grounding": {"tier": "no_llm"}})["answered"] is None


# --- B1, B2: safety, basements, insurance and flood zones ---

@pytest.mark.parametrize("question", [
    "Is 153-10 Peck Avenue, Flushing safe from flooding?",
    "Is the basement apartment at 153-10 Peck Avenue, Flushing safe?",
    "Is 90-11 183rd Street, Queens safe from flooding?",
    "Is Riverdale safe from flooding?",
])
def test_a_safety_question_gets_the_observed_record_before_the_maps_and_never_fema_alone(monkeypatch, question):
    lead, facts = ra.answer(question, ADDRESS, {})
    assert lead == "no_advice"
    assert facts[:3] == ["floodnet", "nyc311", "ida_hwm"] and facts[-2:] == ["fema_nfhl", "fema_pfirm"]
    assert facts.index("dep_moderate_current") < facts.index("fema_nfhl")
    out = _synthesize(monkeypatch, question, values={"fema_nfhl": {"fld_zone": "X", "sfha": False}})
    answer = out["paragraph"].split("**Answer.**\n", 1)[1].split("\n\n", 1)[0]
    assert answer.startswith("Riprap reports public records about a place.") and "the observed record first:" in answer
    assert answer.count(OUTSIDE) == 1 and "not a flood zone determination" in answer
    # Review round 2: the pointers have their own heading, before the "Out of scope" note.
    turn, footer = out["paragraph"].split("**Where to turn.**\n", 1)[1].split("\n\n**Out of scope.** ", 1)
    assert "https://a858-nycnotify.nyc.gov" in turn and "Basement Alerts" in turn and "https://www.floodhelpny.org" in turn
    assert "nycnotify" not in footer


def test_an_insurance_question_keeps_fema_first_and_says_outside_is_not_safe(monkeypatch):
    q = "How much is flood insurance at 153-10 Peck Avenue, Flushing?"
    assert ra.answer(q, ADDRESS, {}) == ("no_advice", ["fema_nfhl", "fema_pfirm"])
    answer = _synthesize(monkeypatch, q, values={"fema_nfhl": {"fld_zone": "X", "sfha": False}})["paragraph"]
    assert "The FEMA flood zone here" in answer and OUTSIDE in answer
    inside = _synthesize(monkeypatch, q, values={"fema_nfhl": {"fld_zone": "AE", "sfha": True}})["paragraph"]
    assert OUTSIDE not in inside.split("**Answer.**\n", 1)[1].split("\n\n", 1)[0]


@pytest.mark.parametrize("question", [
    "Is 153-10 Peck Avenue, Flushing in a flood zone?", "Is 2940 Brighton 3rd St, Brooklyn in the 100-year floodplain?",
])
def test_a_flood_zone_answer_is_no_determination_and_points_to_femas_map_service_center(monkeypatch, question):
    zone_x = _synthesize(monkeypatch, question, values={"fema_nfhl": {"fld_zone": "X", "sfha": False}})["paragraph"]
    assert "not a flood zone determination" in zone_x and "https://msc.fema.gov" in zone_x and OUTSIDE in zone_x
    zone_ae = _synthesize(monkeypatch, question, values={"fema_nfhl": {"fld_zone": "AE", "sfha": True}})["paragraph"]
    assert "not a flood zone determination" in zone_ae and OUTSIDE not in zone_ae


def test_a_heat_safety_question_gets_the_same_opening_decline():
    from riprap.core.burr.synthesis import LEAD_PHRASES, NO_ADVICE

    heat = {"heat_surface": "Landsat measured the surface here at 3.1°F warmer than the city's land average.",
            "hvi": "The Heat Vulnerability Index scores Longwood at 5 out of 5."}
    lead, facts = ra.answer("Is my apartment at 1150 Intervale Avenue, Bronx too hot to be safe?", heat, {})
    assert (lead, facts) == ("no_advice_heat", ["heat_surface", "hvi"]) and LEAD_PHRASES[lead].startswith(NO_ADVICE)


# --- B3, A5: a plain yes about an address needs a record on its block ---

def test_a_yes_about_an_address_needs_a_record_within_the_block_distance():
    focus, q = {"time_frame": "past"}, "Has 187-10 Jamaica Avenue, Queens flooded since Ida?"
    texts = {"floodnet": T["floodnet"]}
    assert ac.BLOCK_M == 100
    far = ac.past_event_lead(q, focus, ["floodnet"], texts, {"floodnet": FLOODNET})
    assert far == ("near", ["floodnet"])
    assert ac.near_lead("floodnet", {"floodnet": FLOODNET}).startswith(
        "Flooding was recorded near this address, not at it: the nearest FloodNet sensor with a verified flood event is "
        "413 m away [floodnet].")
    on_block = {**FLOODNET, "_rows": [{**ROWS[0], "distance_m": 60.0}]}
    assert ac.past_event_lead(q, focus, ["floodnet"], texts, {"floodnet": on_block})[0] == "yes"
    # The same distance for an Ida mark: 174 m is near, not at.
    ida = {"ida_hwm": "USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address."}
    q = "Did 90-01 183rd Street, Queens flood during Hurricane Ida?"
    assert ra.answer(q, ida, {"ida_hwm": {"n_within_radius": 2, "nearest_dist_m": 174}}) == ("near", ["ida_hwm"])
    assert "USGS high-water mark from Hurricane Ida is 174 m away" in ac.near_lead("ida_hwm", {"ida_hwm": {"nearest_dist_m": 174}})


def test_the_block_test_reads_the_public_sensor_fields_when_the_private_rows_are_absent():
    # Before FloodNet's value carried `_rows`: each sensor's lat, lon and n_events, measured from the queried point.
    point = (40.7127, -73.7700)
    sensors = [{"deployment_id": "a", "lat": 40.7127, "lon": -73.7650, "status": "good", "n_events": 2},  # about 420 m east
               {"deployment_id": "b", "lat": 40.7128, "lon": -73.7700, "status": "good", "n_events": 0}]  # beside it, no events
    v = {"n_sensors": 2, "n_flood_events_3y": 2, "sensors": sensors,
         "highest_event": {"deployment_id": "a", "start_time": "2026-03-12T10:58:00", "max_depth_mm": 18}}
    rows, complete = ac.floodnet_rows(v, point)
    assert not complete and len(rows) == 1 and 400 < rows[0]["distance_m"] < 440
    assert rows[0]["events"] == [{"date": "2026-03-12", "max_depth_mm": 18}]
    lead = ac.past_event_lead("Has 4 South Street, Manhattan flooded?", {"time_frame": "past"}, ["floodnet"],
                              {"floodnet": T["floodnet"]}, {"floodnet": v, "_point": point})
    assert lead[0] == "near"
    assert ac.floodnet_rows({**v, "_rows": ROWS}, point) == (ROWS, True)  # the private rows are preferred


def test_a_yes_about_an_area_names_the_area_in_the_lead(monkeypatch):
    area = {"n_sensors": 13, "n_flood_events_3y": 41, "_rows": [{"distance_m": None, "status": "good", "events": []}]}
    out = _synthesize(monkeypatch, "Has Gowanus flooded?", texts={"floodnet": T["floodnet"]}, values={"floodnet": area},
                      intent="neighborhood", nta={"nta_name": "Carroll Gardens-Cobble Hill-Gowanus-Red Hook"})
    assert out["grounding"]["answer_lead"] == "yes"
    assert "**Answer.**\nYes, in Carroll Gardens-Cobble Hill-Gowanus-Red Hook: 2 FloodNet sensors" in out["paragraph"]


# --- B6: a question in another language ---

@pytest.mark.parametrize("question", [
    "¿Se ha inundado 4302 4th Avenue, Brooklyn desde el huracán Ida?",
    "inundaciones en 80 Pioneer Street, Brooklyn",
    "80 Pioneer Street, Brooklyn 淹过水吗",
    "80 Pioneer Street, Brooklyn এ কি বন্যা হয়েছে",
])
def test_a_question_in_another_language_is_not_read_as_a_bare_address_or_answered(question):
    assert ra.not_english(question)
    assert not is_bare_place(question, heuristic_plan(question)["targets"])
    assert ra.answer(question, T, {}) == ("not_english", [])
    for line in ("Riprap reads questions in English only", "Español: Riprap solo lee preguntas en inglés",
                 "中文：Riprap 只能阅读英文问题", "বাংলা: Riprap শুধু ইংরেজি প্রশ্ন পড়ে"):
        assert line in ra.ENGLISH_ONLY


def test_english_and_plain_addresses_are_not_taken_for_another_language():
    for text in ("Has 4302 4th Avenue, Brooklyn flooded since Hurricane Ida?", "123 SE Main St, Detroit, MI",
                 "El Barrio flooding", "La Guardia Airport", "80 Pioneer Street, Brooklyn"):
        assert not ra.not_english(text), text


# --- B7: a named past day, and "right now" ---

@pytest.mark.parametrize("question", [
    "Did 90-01 183rd Street, Queens flood on September 1, 2021?", "Did 90-01 183rd Street, Queens flood on May 20, 2026?",
])
def test_a_question_about_a_named_past_day_is_not_refused_as_a_retrospective(question):
    from app.planner import _not_implemented_message

    assert _not_implemented_message(question) is None
    assert heuristic_plan(question)["intent"] == "single_address"
    # What Riprap would have said on an earlier date is still declined.
    assert _not_implemented_message("What would Riprap have said about 80 Pioneer Street, Brooklyn in 2019?")


def test_a_named_day_is_answered_from_the_sensor_events_dated_that_day():
    texts, values = {"floodnet": T["floodnet"]}, {"floodnet": FLOODNET}
    q = "Did 90-01 183rd Street, Queens flood on {}?"
    assert ac.named_day(q.format("May 20, 2026")) == datetime.date(2026, 5, 20)
    lead, sentence, facts = ac.day_lead(q.format("May 20, 2026"), texts, values)
    assert (lead, facts) == ("day", ["floodnet"])
    assert sentence == ("Flooding was recorded near this address on 2026-05-20 (UTC), not at it: FloodNet's verified record "
                        "has 2 flood events that day, at sensors the nearest of which is 413 m away, the deepest 1172 mm "
                        "[floodnet].")
    assert ra.answer(q.format("May 20, 2026"), texts, values) == ("day", ["floodnet"])
    assert "no flood event dated 2026-05-21" in ac.day_lead(q.format("May 21, 2026"), texts, values)[1]
    # Before the sensors' record starts: said so, never a no.
    before = ac.day_lead(q.format("June 3, 2022"), texts, values)[1]
    assert before == ("The FloodNet record quoted here starts on 2023-10-26, after 2022-06-03, so the sensors say nothing "
                      "about that day [floodnet].")
    # A value that does not date every event cannot say "none that day".
    undated = {"floodnet": {k: v for k, v in FLOODNET.items() if k != "_rows"}}
    assert ac.day_lead(q.format("May 21, 2026"), texts, undated)[0] == "cannot_answer"


def test_a_day_of_ida_is_answered_from_the_storms_own_record(monkeypatch):
    q = "Did 90-01 183rd Street, Queens flood on September 1, 2021?"
    ida = {"ida_hwm": "USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address."}
    values = {"ida_hwm": {"n_within_radius": 2, "nearest_dist_m": 174}}
    assert ac.storm_of_day(q) == "ida" and ra.answer(q, ida, values) == ("near", ["ida_hwm"])
    out = _synthesize(monkeypatch, q, texts=ida, values=values)
    assert "2021-09-01 is a day of Hurricane Ida's flooding in the city" in out["paragraph"]


def test_a_right_now_question_gets_the_live_readings_whatever_else_it_asks():
    q = "Is the street passable right now at 20 West 12th Road, Queens, or should I move my car?"
    assert ra.asks_now(q) and heuristic_plan(q)["intent"] == "live_now"
    lead, facts = ra.answer(q, T, {})
    assert lead == "facts" and facts[:2] == ["nws_alerts", "floodnet"] and "fema_nfhl" not in facts
    q = "Can I get to the Howard Beach subway stop, is the street flooded?"
    assert ra.asks_now(q) and heuristic_plan(q)["intent"] == "live_now"
    assert not ra.asks_now("Can I get flood insurance at 80 Pioneer Street, Brooklyn?")
    assert not ra.asks_now("Was the street flooded during Ida?")


# --- B8: a forecast asked of a register, and a cause asked of the sensors ---

def test_which_schools_will_flood_gets_the_forecast_refusal_before_the_register():
    from riprap.core.burr.synthesis import LEAD_PHRASES

    lead, facts = ra.answer("Which schools in BK18 will flood?", T, {})
    assert (lead, facts) == ("no_prediction_register", ["doe_school_exposure"])
    assert LEAD_PHRASES[lead].startswith("Riprap cannot predict which places will flood")
    assert ra.answer("Which schools in BK18 are inside the Sandy zone?", T, {})[0] == "facts"


def test_a_question_that_names_rain_or_tide_gets_the_stormwater_maps_and_the_note_on_cause(monkeypatch):
    q = "Does rain flood 20 West 12th Road, Broad Channel?"
    lead, facts = ra.answer(q, T, {})
    # Review round 2: no record gives a cause, so the question is not answered; the maps, then the sensors.
    assert lead == "cannot_answer" and facts[-1] == "floodnet" and facts[:2] == ["dep_moderate_current", "dep_extreme_2080"]
    out = _synthesize(monkeypatch, q)
    assert ra.CAUSE_NOTE in out["paragraph"] and "does not label a flood event by its cause" in ra.CAUSE_NOTE
    assert "Future High Tides 2080" in out["paragraph"]


# --- B9, B10: places ---

def test_the_mcp_district_tool_refuses_a_district_that_does_not_exist():
    from riprap.mcp.server import get_district_summary

    out = get_district_summary("QN99")
    assert out == {"error": "Queens has community districts QN01 to QN14, so QN99 is not one of them. Did you mean QN14?"}
    assert "error" in get_district_summary("Astoria")


def test_a_park_tabulation_area_says_it_is_one_and_names_the_areas_beside_it():
    from app.areas import nta

    note = nta.type_note("QN0791")  # Kissena Park
    assert note.startswith("City Planning classes Kissena Park as a park")
    assert "Auburndale; East Flushing; Queensboro Hill" in note and "street address" in note
    assert nta.type_note(nta.resolve("Hollis")[0]["nta_code"]) is None


# --- B11, B12: the Heat Vulnerability Index in the department's words ---

def test_the_heat_index_sentence_lists_the_departments_four_factors_and_its_account_of_race():
    from app.heat import dohmh

    high = dohmh.hvi_for_point(40.7128, -73.778)["narrative"]  # Jamaica, scored 5
    assert ("\"uses a statistical model to summarize the most important factors of neighborhood heat risk: surface "
            "temperature, green space, home air conditioning, and income\"") in high
    assert "share of Black residents" not in high
    assert ("\"These disparities stem from structural racism, which includes neighborhood disinvestment, racist housing "
            "policies, fewer job opportunities and lower pay, and less access to high-quality education and health "
            "care\" (NYC Health Department, Interactive Heat Vulnerability Index).") in high
    # B12: the neighbourhood named is the index's own area, which the address line may name differently.
    assert "can carry another name than the neighbourhood in the address above" in high
    low = dohmh.hvi_for_point(40.6790, -74.0110)  # Carroll Gardens-Cobble Hill-Gowanus-Red Hook, scored 2
    assert low["hvi"] < 4 and "structural racism" not in low["narrative"]
    assert "no one of the neighbourhoods in its name has a score of its own" in low["narrative"]
    district = dohmh.hvi_for_area(type("Q", (), {"extras": {"area_code": "QN12"}})())["narrative"]
    assert "structural racism" in district


def test_an_address_at_a_public_housing_development_is_told_the_figures_are_the_neighbourhoods():
    from app.heat import dohmh

    g = dohmh._developments()
    inside = g.to_crs(4326).iloc[0].geometry.representative_point()
    v = dohmh.hvi_for_point(inside.y, inside.x)
    assert v["public_housing"] and "its air conditioning share especially, are not the development's" in v["narrative"]
    assert "public housing" not in dohmh.hvi_for_point(40.7128, -73.778)["narrative"]


def test_air_temperature_at_an_address_opens_by_saying_riprap_has_none():
    from riprap.core.burr.synthesis import LEAD_PHRASES

    heat = {"heat_obs": "The air at JFK Airport, the nearest weather station, was 66°F.",
            "heat_surface": "Landsat measured the surface here at 3.0°F warmer than the city's land average."}
    lead, facts = ra.answer("What is the air temperature at 2940 Brighton 3rd St, Brooklyn?", heat, {})
    assert (lead, facts) == ("no_air_temp", ["heat_obs", "heat_surface"])
    assert LEAD_PHRASES[lead].startswith("Riprap has no air temperature at an address")


def test_does_one_place_flood_more_than_another_is_a_side_by_side_comparison():
    plan = heuristic_plan("Does Hollis flood more than Forest Hills?")
    assert plan["intent"] == "compare"
    assert [(t["type"], t["text"]) for t in plan["targets"]] == [("nta", "Hollis"), ("nta", "Forest Hills")]
    assert heuristic_plan("Has 80 Pioneer Street, Brooklyn had more flooding than usual?")["intent"] == "single_address"


def test_a_question_about_a_place_outside_coverage_says_so_in_its_answer(monkeypatch):
    out = _synthesize(monkeypatch, "Has 1 Washington Street, Hoboken, NJ flooded?",
                      texts={"fema_nfhl": T["fema_nfhl"]}, deployment="__none__")
    assert "**Answer.**\nThis place is outside the cities Riprap covers, so Riprap holds no local record" in out["paragraph"]
    assert out["grounding"]["answered"] is False


# --- C10 and the heat briefing's out-of-scope line ---

def test_the_fixed_disclaimers_say_what_the_briefing_is_not_in_plain_words():
    from riprap.core.burr.templated_reconciler import HEAT_NON_SCOPE_FOOTER, NON_SCOPE_FOOTER

    assert NON_SCOPE_FOOTER.startswith("**Out of scope.** This briefing is not a flood zone determination, an engineering "
                                       "assessment or advice.")
    for word in ("title", "zoning", "structural condition"):  # real-estate framing
        assert word not in NON_SCOPE_FOOTER
    # The disclaimer cites no FEMA map, so the map-vintage disclosure check does not ask it for a year.
    from riprap.core.compliance.predicates import firm_citation_has_vintage

    assert firm_citation_has_vintage(NON_SCOPE_FOOTER).passed and firm_citation_has_vintage(ra.FEMA_POINTER).passed
    assert not firm_citation_has_vintage("This address sits in FEMA flood zone X.").passed
    assert ("Air temperature and an outdoor heat exposure index are mapped on the NYC Urban Heat Portal "
            "(https://urbanheat.nyc), by BetaNYC.") in HEAT_NON_SCOPE_FOOTER


def test_no_sentence_these_rules_write_ranks_or_judges_a_place():
    import re

    from riprap.core.burr import synthesis

    written = [s for _, _, s, _ in ra.NOT_HELD] + [ra.ENGLISH_ONLY, ra.CAUSE_NOTE, ra.FEMA_POINTER, synthesis.NOT_RECOGNISED,
                                                    synthesis.SAFETY_POINTER, ac.near_lead("floodnet", {"floodnet": FLOODNET}),
                                                    *synthesis.LEAD_PHRASES.values()]
    for text in written:
        assert not re.search(r"high[- ]risk|flood[- ]prone|\bdangerous|\bworst\b", text, re.I), text
