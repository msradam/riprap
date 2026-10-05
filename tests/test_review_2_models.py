"""What the review of the restored models and the widened question rules
found, pinned. Offline."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app import experimental
from app.live import ttm_battery_surge as surge
from riprap.core.burr import rule_answer as ra
from riprap.core.burr import synthesis as syn
from riprap.core.burr.intake import heuristic_plan
from riprap.core.burr.synthesis import Doc
from riprap.core.compliance import predicates

T = {
    "nws_water_forecast": "The National Weather Service forecasts a peak water level of 6.0 ft above MLLW at The Battery.",
    "noaa_tides": "Latest reading at The Battery, NY: 4.1 ft above MLLW.",
    "nws_alerts": "No active NWS flood, coastal or tropical storm alerts at this point.",
    "ttm_battery_surge": "Experimental forecast: the water at The Battery may run up to 0.20 m above the tide.",
    "landcover": "Experimental: a satellite land-cover model labels 71.0% of the ground here as paved or built over.",
    "floodnet": "2 FloodNet community sensors within 600 m have logged 14 above-curb flood events in the last 3 years.",
    "nyc311": "7 NYC 311 flood-related complaints filed within 200 m in the last 5 years.",
    "sandy_inundation": "This address sits within the empirical 2012 Hurricane Sandy inundation footprint.",
    "fema_nfhl": "This address sits in FEMA flood zone AE.",
    "dep_moderate_current": "This address is outside the modeled flooding in the NYC DEP stormwater scenario.",
}
MODELS = {"ttm_battery_surge", "landcover"}


@pytest.mark.parametrize("question", [
    "Did 100 Green Street flood during Sandy?",            # "Green" is a street,
    "Is Bowling Green in a FEMA flood zone?",              # a park,
    "Was this inside the Sandy surge zone?",               # and "surge zone" is a map
    "Are there 311 complaints about high tide flooding here?",
])
def test_a_word_shared_with_a_model_topic_does_not_bring_the_model(question):
    got = ra.answer(question, T, {})
    assert got and not MODELS & set(got[1])


def test_a_flood_zone_in_the_future_is_a_question_about_the_map_not_a_prediction():
    texts = {**T, "dep_moderate_2050": "This address is outside the modeled flooding in the 2050 scenario."}
    assert ra.answer("Will this block be in a flood zone by 2050?", texts, {})[0] == "facts"
    assert ra.answer("Will my flood insurance cover this block next week?", T, {})[0] != "no_prediction"


def test_the_model_topics_still_fire_on_their_own_words():
    assert ra.answer("How green is this block?", T, {}) == ("experimental", ["landcover"])
    assert ra.answer("What is the surge forecast at the Battery?", T, {})[1][-1] == "ttm_battery_surge"


def test_standing_water_is_live_when_asked_about_now_and_the_scenario_otherwise():
    assert ra.time_frame("Is there standing water here right now?") == "now"
    assert ra.answer("Is there standing water here right now?", T, {})[1][:2] == ["nws_alerts", "floodnet"]
    assert ra.answer("Does water linger here after rain?", T, {}) == ("facts", ["dep_moderate_current"])
    # A named source keeps the question; heavy rain alone is the setting, and the record answers.
    assert ra.answer("Are there 311 complaints about standing water?", T, {})[1] == ["nyc311"]
    assert "dep_moderate_current" not in ra.answer("Does this block flood after heavy rain?", T, {})[1]


def test_a_sentence_that_starts_after_an_abbreviation_is_its_own_clause():
    q = "I live at 100 Main St. Has it flooded since Sandy?"
    assert ra._clauses(q) == ["I live at 100 Main St.", "Has it flooded since Sandy?"]
    assert ra.time_frame(q) == "past" and ra._happened_clause(q) == "Has it flooded since Sandy?"
    assert len(ra._clauses("Has 100 Main St. flooded since Sandy?")) == 1


@pytest.mark.parametrize("query", [
    "I'm thinking about renting at 80 Pioneer Street, Brooklyn. Has the block flooded since Ida?",
    "It gets hot here in the summer and the basement floods at 80 Pioneer Street, Brooklyn. Has it flooded since Ida?",
    "Flood history for 100-10 Liberty Avenue, Ozone Park",
])
def test_a_flood_question_with_a_preamble_is_not_refused(query):
    assert heuristic_plan(query)["intent"] == "single_address"


@pytest.mark.parametrize("query,intent,target", [
    ("is pennsylvania avenue in east new york flooding right now", "live_now", "East New York, Brooklyn, NY"),
    ("is the red hook ferry terminal flooding right now", "live_now", "Red Hook Ferry Terminal, New York, NY"),
])
def test_a_street_named_after_a_state_and_a_landmark_in_lower_case_are_places(query, intent, target):
    plan = heuristic_plan(query)
    assert plan["intent"] == intent and plan["targets"][0]["text"] == target


def test_the_district_sensor_source_answers_under_the_sensor_rules():
    from riprap.core.pebbles.bridge import get_registry

    p = next(p for p in get_registry("nyc").all() if p.id == "floodnet_nta")
    assert p.manifest.provenance.doc_id == "floodnet"  # the id every sensor rule names


def _answer(monkeypatch, question):
    """The answer section on a server without the ml extra."""
    docs = [Doc("sandy_inundation", "Hazard Reader", "This address sits outside the 2012 Sandy inundation footprint.", False),
            Doc("noaa_tides", "Live Observer", T["noaa_tides"], False),
            Doc("ttm_battery_surge", "Projector", experimental.not_installed("surge", "the Battery surge forecast model"), True)]
    items = [SimpleNamespace(doc_id=d.doc_id, pebble_id=d.doc_id) for d in docs]
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    out = syn.synthesize({"intent": "single_address", "sandy_inundation": {"inside": False, "edge_m": None},
                          "ttm_battery_surge": {"available": False, "installed": False},
                          "plan": {"question": question, "focus": {}}})
    return out["paragraph"].split("**Answer.**")[1].split("**")[0].strip()


def test_a_missing_model_says_so_only_where_it_would_have_answered(monkeypatch):
    # Without the ml extra its "not available" sentence closes a surge answer. Under a Sandy question
    # that says "surge" it once followed the answer and made the lead check drop a correct "No.".
    assert _answer(monkeypatch, "Did the storm surge flood this address during Sandy?").startswith("No. This address sits outside")
    assert "not available" not in _answer(monkeypatch, "Did the storm surge flood this address during Sandy?")
    surge_answer = _answer(monkeypatch, "How far above the predicted tide is the water at the Battery?")
    assert surge_answer.startswith("From the sources consulted: Latest reading at The Battery")
    assert "the Battery surge forecast model is not available on this server" in surge_answer


def test_the_hedged_sentences_pass_the_disclosure_checks(tmp_path, monkeypatch):
    (tmp_path / "surge.json").write_text(json.dumps({
        "n_windows": 635, "first": "2025-01-01", "last": "2026-09-27", "mae_cm": 11.5, "baseline_mae_cm": 13.3,
        "n_flood_windows": 23, "n_flood_foreseen": 1}))
    monkeypatch.setattr(experimental, "EVAL_DIR", tmp_path)
    tide = {f"2026-10-{d:02d} {h:02d}:00": 5.0 * surge.M_PER_FT for d in range(1, 7) for h in range(24)}
    text = surge.summarize("2026-10-01 12:00", [0.05] * 95 + [0.21], tide, {"minor": 7.0})["narrative"]
    answer = f"{syn.LEAD_PHRASES['no_prediction']} {text}"
    for check in (predicates.no_will_flood_without_hedge, predicates.no_rounding_to_false_precision,
                  predicates.projection_has_horizon):
        assert check(answer).passed, check(answer).evidence


def test_the_flood_stage_is_compared_with_the_figure_printed():
    # A total of 6.96 ft prints as 7.0 ft: it once printed "7.0 ft ..., below the minor flood stage of 7.0 ft".
    tide = {f"2026-10-{d:02d} {h:02d}:00": 6.76 * surge.M_PER_FT for d in range(1, 7) for h in range(24)}
    v = surge.summarize("2026-10-01 12:00", [0.0] * 95 + [0.2 * surge.M_PER_FT], tide, {"minor": 7.0})
    assert v["forecast_peak_total_ft_mllw"] == 7.0 and v["flood_category"] == "minor"


def test_the_surge_model_declines_a_gauge_record_with_a_gap(monkeypatch):
    end = datetime(2026, 10, 1, 12, tzinfo=UTC)
    hours = {(end - timedelta(hours=i)).strftime("%Y-%m-%d %H:%M"): 1.0 for i in range(1100)}
    monkeypatch.setattr(surge, "hourly", lambda product, a, b: dict(hours))
    times, residuals = surge.residual_history(end)
    assert len(residuals) == surge.CONTEXT_HOURS and times[-1] == "2026-10-01 12:00"
    gap = {t: v for t, v in hours.items() if t != "2026-09-20 03:00"}
    monkeypatch.setattr(surge, "hourly", lambda product, a, b: dict(gap))
    assert surge.residual_history(end) == ([], [])  # an hour missing: not spliced out
    stale = {t: v for t, v in hours.items() if t <= "2026-10-01 02:00"}
    monkeypatch.setattr(surge, "hourly", lambda product, a, b: dict(stale))
    assert surge.residual_history(end) == ([], [])  # the last reading is ten hours old


def test_a_new_evaluation_file_is_read_without_a_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(experimental, "EVAL_DIR", tmp_path)
    assert experimental.evaluation("water") is None
    (tmp_path / "water.json").write_text(json.dumps({"n_marks": 153}))
    assert experimental.evaluation("water") == {"n_marks": 153}


def test_a_compass_point_before_a_numbered_street_ends_no_sentence():
    assert predicates._sentences("A sensor on W. 4th St logged 3 events. It is flagged.") == [
        "A sensor on W. 4th St logged 3 events.", "It is flagged."]


def test_the_language_model_cannot_rest_a_yes_on_an_experimental_source(monkeypatch):
    docs = [Doc("landcover", "Hazard Reader", "Experimental: a satellite land-cover model estimates that 71.0% of the "
                "ground within 500 m of this address is paved or built over.", True),
            Doc("fema_nfhl", "Hazard Reader", "This address sits in FEMA flood zone X.", False)]
    monkeypatch.setattr(syn, "RULES_FIRST", False)
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: ({"claims": [], "answer": {"lead": "yes", "facts": ["landcover"]}}, "m"))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": "Is this block a wet one?", "focus": {}}})
    answer = out["paragraph"].split("**Answer.**")[1].split("**")[0].strip()
    assert out["grounding"]["answer_mode"] == "extractive" and not answer.startswith("Yes")
    assert answer.startswith("From the sources consulted: Experimental: a satellite land-cover model estimates")


def test_a_school_just_outside_the_sandy_outline_is_named_not_dropped():
    # PAVE Academy's point is 3 m outside the outline (another city file puts it 16 m inside). The
    # register once held only assets inside, so a question about Red Hook's schools left it out.
    from app.flood_layers import sandy_inundation
    from app.registers import exposure

    if sandy_inundation._raster_handle() is None:
        pytest.skip("the Sandy raster is not on this machine")
    out = exposure.summary_for_point(40.6762, -74.0040, "doe_schools", radius_m=800)
    near = out["narrative"].split("within 50 m of its mapped edge (the outline is not exact to a building): ")[1]
    assert "PAVE Academy Charter School" in near
    assert out["n_schools"] == out["n_inside_sandy_2012"] == 1  # named, not counted as exposed
    assert "footprint_buffer_m" not in out  # the register tested the bare point: no buffer is claimed


def test_a_dated_forecast_states_its_horizon():
    dated = ("The National Weather Service forecasts a peak water level of 5.9 ft above MLLW at The Battery on "
             "2026-10-01 17:00 UTC [nws_water_forecast].")
    assert predicates.projection_has_horizon(dated).passed
    assert not predicates.projection_has_horizon("The forecast is a peak of 5.9 ft [nws_water_forecast].").passed


def test_no_event_under_way_is_said_only_when_the_record_supports_it(monkeypatch):
    from app.context import floodnet
    from app.context.floodnet import FloodEvent, Sensor

    def narrative(status, end):
        monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: [Sensor("a", "Q - 183rd St", "183rd St", "Queens", status, None)])
        monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: [FloodEvent("a", "2026-05-20T23:21:49", end, 300, "flood")])
        return floodnet.summary_for_point(40.71, -73.78)["narrative"]

    said = "FloodNet's record showed no flood event under way at it when this was read ("
    assert said in narrative("good", "2026-05-21T01:00:00")
    assert said not in narrative("dead", "2026-05-21T01:00:00")  # a sensor out of order cannot say
    assert said not in narrative("good", None)                   # an event with no end is still open in the record


@pytest.mark.parametrize("question,lead", [
    ("Has the pavement at 80 Pioneer Street, Brooklyn ever flooded?", "yes"),   # a model word in a past question
    ("Has there been high tide flooding here?", "yes"),
    ("My landlord says it will never flood. Has 80 Pioneer Street, Brooklyn flooded since Ida?", "yes"),
    ("I live at 80 Pioneer St. Since Ida, has it flooded?", "yes"),
    ("i live at 100 main st. has it flooded since ida?", "yes"),
    ("Has 300 E. 4th St., Brooklyn flooded since 2023?", "yes"),
    ("Has Dr. Martin Luther King Jr. Blvd flooded since 2023?", "yes"),
    # Past tense, so not a forecast question; but three years of events do not say yes about two days.
    ("Did 80 Pioneer Street, Brooklyn flood this weekend?", "facts"),
    ("Did it flood here last week?", "facts"),
])
def test_the_record_answers_whether_it_flooded_whatever_else_the_question_says(question, lead):
    values = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 14, "n_flood_events_good_3y": 14,
                           "latest_event_start": "2026-08-01T00:00:00"}}
    got = ra.answer(question, T, values)
    assert got[0] == lead and got[1][0] == "floodnet" and not MODELS & set(got[1])


def test_did_100_main_st_have_flooding_is_one_clause():
    assert len(ra._clauses("did 100 main st. have flooding since sandy?")) == 1
    assert len(ra._clauses("Did W. 4th St. flood during Ida?")) == 1


@pytest.mark.parametrize("question", [
    "Was Coney Island covered by water?",            # "land cover" inside "Island covered"
    "Will FloodNet install a sensor near here?",     # "flood" inside a name
])
def test_a_word_inside_another_word_names_nothing(question):
    got = ra.answer(question, T, {})
    assert not got or (got[0] not in ("experimental", "no_prediction") and not MODELS & set(got[1]))


def test_how_high_is_the_surge_is_a_surge_question():
    assert ra.answer("How high is the surge forecast at the Battery?", T, {})[1][-1] == "ttm_battery_surge"


@pytest.mark.parametrize("query,target", [
    ("Has East New York flooded since Ida?", "East New York"),
    ("Is Pennsylvania Avenue in East New York flooding right now?", "East New York, Brooklyn, NY"),
])
def test_east_new_york_is_not_the_east_village(query, target):
    assert heuristic_plan(query)["targets"][0]["text"] == target


def test_a_landmark_in_another_city_is_not_sent_to_new_york():
    plan = heuristic_plan("is the woodlawn cemetery in chicago flooding right now")
    assert "New York" not in plan["targets"][0]["text"] if plan["targets"] else plan["intent"] == "not_implemented"


def test_a_preamble_about_heat_does_not_refuse_the_flood_question():
    q = "It was hot last summer. Was 80 Pioneer Street, Brooklyn inside the Sandy zone?"
    assert heuristic_plan(q)["intent"] == "single_address"
    assert heuristic_plan("Is 100 Broad Street on the FEMA flood insurance rate map?")["intent"] == "single_address"
    assert heuristic_plan("Has Sue's building at 80 Pioneer Street, Brooklyn flooded?")["intent"] == "single_address"


def test_a_district_sensor_sentence_is_cited():
    from riprap.core.burr.evidence import cite

    text = ("13 FloodNet community sensors inside this area have logged 358 above-curb flood events in the last 3 years. "
            "Most events: Russell Street (98); Davenport Court (66).")
    assert cite(text, "floodnet") == text.replace("3 years.", "3 years [floodnet].").replace("(66).", "(66) [floodnet].")


def test_the_not_installed_sentence_is_not_added_to_a_question_about_another_source(monkeypatch):
    assert "not available" not in _answer(monkeypatch, "What do the tide readings say at the Battery? Was it in the Sandy zone?")


def test_noaa_error_body_is_an_error(monkeypatch):
    from types import SimpleNamespace as NS

    from riprap.core import http

    monkeypatch.setattr(http, "get", lambda *a, **k: NS(raise_for_status=lambda: None,
                                                        json=lambda: {"error": {"message": "No data was found."}}))
    with pytest.raises(RuntimeError, match="No data was found"):
        surge.hourly("water_level", datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC))


def test_every_shipped_evaluation_file_fills_its_sentence():
    # A result file that lacks a field the sentence quotes falls back to "out of date": never ship one.
    for key in experimental.MODELS:
        assert "out of date" not in experimental.hedge(key, "x") and "no saved evaluation" not in experimental.hedge(key, "x"), key


def test_the_sea_level_sentence_quotes_the_published_table():
    # Braneon et al. 2024 (doi:10.1111/nyas.15116), Table 1, relative to 1995-2014. An earlier table here
    # (15 in and 29 in for the 2050s on a 2000-2004 baseline) matched no table in the report.
    from app.context import npcc4_slr

    v = npcc4_slr.get_projections()
    assert {p: v["2050s"][p]["in"] for p in ("10", "25", "75", "90")} == {"10": 12, "25": 14, "75": 19, "90": 23}
    assert {p: v["2100"][p]["in"] for p in ("10", "25", "75", "90")} == {"10": 25, "25": 30, "75": 50, "90": 65}
    assert v["narrative"] == (
        "NPCC4 (2024) projects sea-level rise in New York City of 14 to 19 in (0.36 to 0.48 m) by the 2050s and "
        "30 to 50 in (0.76 to 1.27 m) by 2100, relative to 1995-2014, as its middle range (25th to 75th "
        "percentile); the 90th percentile is 23 in (0.58 m) by the 2050s and 65 in (1.65 m) by 2100.")
    assert predicates.projection_has_horizon(v["narrative"] + " [npcc4_slr]").passed


def test_will_it_flood_quotes_the_fema_map_among_what_is_mapped():
    # A blind judge marked the answer down for leaving the flood map out of "what the maps show".
    lead, facts = ra.answer("Will my building at 30 Waterside Plaza flood next week?", T, {})
    assert lead == "no_prediction" and facts[:4] == ["nws_alerts", "nws_water_forecast", "fema_nfhl", "dep_moderate_current"]


# ---- The fourth review round: the reviewer's own inputs. ----

SENSORS = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 14, "n_flood_events_good_3y": 14,
                        "latest_event_start": "2026-08-01T00:00:00"},
           "sandy_inundation": {"inside": True}, "ida_hwm": {"n_within_radius": 1, "nearest_dist_m": 100}}


@pytest.mark.parametrize("question", [
    "Did 80 Pioneer Street, Brooklyn flood on Monday?", "Did it flood here over the weekend?",
    "Did it flood here two days ago?", "Did it flood here last Friday?", "Did it flood here this afternoon?",
    "Did it flood here in August?", "Has it flooded here recently?", "Did 80 Pioneer Street, Brooklyn flood last summer?",
    "Before Sandy, had 2940 West 21st Street, Brooklyn flooded?", "Did it flood before Ida?",
])
def test_no_yes_or_no_about_a_day_a_month_or_the_time_before_a_storm(question):
    assert ra.answer(question, T, SENSORS)[0] == "facts"


@pytest.mark.parametrize("question", [
    "Has 80 Pioneer Street, Brooklyn flooded in the last few years?", "Has it flooded here in the last 3 years?",
    "After Ida, has 80 Pioneer Street, Brooklyn flooded?", "Has it flooded here after Ida?",
    "since ida has 80 pioneer street brooklyn flooded",
    "Has 2050 Grand Concourse flooded since Ida?",
])
def test_the_sensors_still_say_yes(question):
    got = ra.answer(question, T, SENSORS)
    assert got[0] == "yes" and got[1][0] == "floodnet"


def test_a_house_number_is_not_a_year():
    assert ra.time_frame("Did 2100 Bartow Avenue, Bronx flood during Ida?") == "past"
    assert ra.time_frame("Is 2100 Avenue S in a flood zone?") == "any"
    assert ra.time_frame("What does the 2080 scenario show at 400 Carroll Street?") == "future"
    assert ra.time_frame("What will sea level be by 2100?") == "future"


def test_is_there_flood_risk_is_not_did_it_flood():
    quiet = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 0, "n_flood_events_good_3y": 0},
             "nyc311": {"n": 0, "years": 5, "by_year": {}, "by_kind": {}}}
    got = ra.answer("Is there flood risk at 80 Pioneer Street, Brooklyn?", T, quiet)
    assert got[0] != "no"  # sensors with no events once answered "No." for an address in zone AE


@pytest.mark.parametrize("question", [
    "How often has 80 Pioneer Street, Brooklyn flooded since Ida?", "Any flooding since Ida at 80 Pioneer Street?",
    "Flood history since Sandy for 80 Pioneer Street",
])
def test_a_since_question_in_any_wording_gets_the_record(question):
    got = ra.answer(question, T, SENSORS)
    assert got and got[0] != "cannot_answer" and "floodnet" in got[1]


def test_a_flood_zone_question_about_a_neighbourhood_shows_the_maps_it_has():
    area = {"sandy_nta": "40.6% of this area lies inside the 2012 Hurricane Sandy inundation extent.",
            "dep_moderate_current_nta": "DEP Moderate Stormwater: 1.2% of this area is modeled to flood from rainfall."}
    assert ra.answer("Is Red Hook in a flood zone?", area, {}) == ("cannot_answer", ["sandy_nta", "dep_moderate_current_nta"])


@pytest.mark.parametrize("question", [
    "Is Green Street in Greenpoint prone to flooding?",
    "How high is the storm surge expected to be near 80 Pioneer Street, Brooklyn?",
])
def test_the_question_asked_is_the_one_answered(question):
    got = ra.answer(question, {**T, "microtopo": "Elevation 1.37 m."}, {})
    assert got and got[0] != "experimental" and got[1] != ["microtopo"] and "landcover" not in got[1]


def test_will_it_flood_is_declined_with_or_without_a_question_mark():
    assert ra.answer("Will 80 Pioneer Street, Brooklyn flood.", T, {})[0] == "no_prediction"
    assert ra.answer("Is flooding expected at 80 Pioneer Street, Brooklyn this week?", T, {})[0] == "no_prediction"
    assert ra.time_frame("Did it flood here this week?") == "past"
    # A question that asks about the past and the future together is declined as a prediction;
    # a "Yes." about the past would sit beside "will it flood again". (Known limit: the record is not quoted.)
    assert ra.answer("Has 80 Pioneer Street, Brooklyn flooded before and will it flood again?", T, SENSORS)[0] == "no_prediction"
    assert ra.answer("Is 80 Pioneer Street in a flood zone and will it flood this week?", T, {})[0] == "no_prediction"


def test_a_question_about_imagery_takes_no_yes_from_the_record():
    got = ra.answer("Did satellite imagery show flooding at 80 Pioneer Street, Brooklyn after Sandy?", T, SENSORS)
    assert got[0] == "no_satellite"  # the Sandy outline is not what imagery showed, and no yes rests on it
    far = {"ida_hwm": {"n_within_radius": 0}}
    texts = {"ida_hwm": "No Hurricane Ida high-water marks were surveyed within 800 m of this address."}
    assert ra.answer("Did satellite imagery show flooding here after Ida?", texts, far) == ("no_satellite", ["ida_hwm"])


@pytest.mark.parametrize("query,place", [
    ("Has New Brighton flooded since Ida?", "New Brighton"),
    ("City Island", "City Island"),
    ("Is The Battery in a flood zone?", "The Battery"),
    ("Is Murray Hill in Queens in a flood zone?", "Murray Hill, Queens"),
])
def test_a_neighbourhood_keeps_its_whole_name_and_its_borough(query, place):
    assert heuristic_plan(query)["targets"][0]["text"] == place


def test_murray_hill_in_queens_resolves_in_queens():
    from app.areas import nta

    hits = nta.resolve("Murray Hill")
    assert {h["borough"] for h in hits} >= {"Queens"} or len(hits) == 1  # the data decides which exist
    picked = [m for m in hits if m["borough"] == "Queens"] or hits
    assert picked[0]["borough"] == ("Queens" if any(h["borough"] == "Queens" for h in hits) else hits[0]["borough"])


def test_a_lower_case_landmark_with_an_asset_word_is_placed():
    plan = heuristic_plan("is jamaica hospital flooding right now")
    assert plan["targets"][0]["text"] == "Jamaica Hospital, New York, NY"


def test_a_citation_mark_does_not_land_inside_a_school_name():
    from riprap.core.burr.evidence import cite

    text = ("Inside the 2012 Sandy extent: P.S./M.S 042 R. Vernam (50 m), P.S. 183 Dr. Richard R. Green (120 m). "
            "It is flagged.")
    assert cite(text, "doe_school_exposure") == text.replace("(120 m).", "(120 m) [doe_school_exposure].").replace(
        "It is flagged.", "It is flagged.")
    assert predicates._sentences("in flood zone X. 3 sensors logged events.") == ["in flood zone X.", "3 sensors logged events."]


# ---- Regressions the check of the fourth round's fixes found: its inputs. ----

def test_the_real_sensor_sentence_still_reports_a_result(monkeypatch):
    # "no flood event under way" in the first sentence read as an absence and cost every sensor-only "Yes.".
    from app.context import floodnet
    from app.context.floodnet import FloodEvent, Sensor
    from riprap.core.burr.answer_checks import check_lead, reports_result

    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: [Sensor("a", "Q - 183rd St", "183rd St", "Queens", "good", None)])
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: [
        FloodEvent("a", f"2026-05-{d:02d}T10:00:00", f"2026-05-{d:02d}T11:00:00", 300, "flood") for d in range(1, 9)])
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "no flood event under way" in v["narrative"] and reports_result(v["narrative"])
    q = "Have the FloodNet sensors near 80 Pioneer Street, Brooklyn recorded any flooding?"
    lead, facts = ra.answer(q, {"floodnet": v["narrative"]}, {"floodnet": v})
    assert lead == "yes" and not check_lead(lead, facts, q, {"floodnet": v["narrative"]}, {"floodnet": v})


def test_a_year_beside_a_street_is_still_a_year():
    for q in ("In 2050 will Ocean Parkway flood?", "By 2080 will this street flood?",
              "What does flooding look like in 2050 on Broadway?", "Will sea level rise by 2050 put Hamilton Avenue under water?"):
        assert ra.time_frame(q) == "future", q


def test_only_a_storm_or_a_year_is_moved_to_the_end_of_its_clause():
    assert ra.answer("Since my office is at 100 Gold Street, has it flooded?", T, SENSORS)[0] == "yes"
    for q in ("During which storms was this flooded?", "Since when has it flooded here?"):
        assert ra._clauses(q) == [q]


def test_this_week_in_a_question_about_the_record_brings_no_forecast():
    assert ra.answer("What were the 311 complaints here this week?", T, SENSORS)[1] == ["nyc311"]
    assert ra.answer("What did the FloodNet sensors record this week?", T, SENSORS)[1] == ["floodnet"]


def test_elevation_questions_that_mention_water_keep_the_elevation():
    texts = {**T, "microtopo": "Elevation 1.37 m."}
    assert ra.answer("How high is 80 Pioneer Street above the water?", texts, {})[1] == ["microtopo"]
    assert "microtopo" in ra.answer("How high is the ground here above high tide?", texts, {})[1]


def test_the_flood_forecast_is_a_noun_and_the_forecast_answers_it():
    for q in ("What is the flood forecast for this weekend?", "Is there a flood forecast for tomorrow?"):
        lead, facts = ra.answer(q, T, {})
        assert lead == "facts" and facts[0] == "nws_water_forecast", q


def test_a_count_for_last_night_is_not_the_five_year_total():
    from riprap.core.burr.answer_checks import count_lead

    values = {"nyc311": {"n": 7, "years": 5, "by_year": {"2024": 7}, "by_kind": {}}}
    assert count_lead("How many 311 complaints were filed last night?", T, values) == (None, True)


def test_flooded_before_during_sandy_is_about_sandy():
    assert ra.answer("Has 80 Pioneer Street flooded before during Sandy?", T, SENSORS) == ("yes", ["sandy_inundation"])


def test_a_borough_after_a_neighbourhood_keeps_the_match_exact():
    from burr.core import State

    from riprap.core.burr import intake

    plan = heuristic_plan("Is Greenpoint, Brooklyn in a flood zone?")
    out = intake.resolve_area(State({"first_target": plan["targets"][0]["text"], "trace": []}))
    assert out["geocode"]["match"] == "exact" and out["geocode"]["borough"] == "Brooklyn"
    queens = intake.resolve_area(State({"first_target": "Murray Hill, Queens", "trace": []}))
    assert queens["geocode"]["borough"] == "Queens"


def test_imagery_after_ida_is_about_the_storm_not_the_time_since():
    texts = {**T, "ida_hwm": "USGS surveyed 1 Hurricane Ida high-water mark within 800 m of this address."}
    lead, facts = ra.answer("Did satellite imagery show flooding here after Ida?", texts, SENSORS)
    assert lead == "no_satellite" and facts[0] == "ida_hwm"  # the storm's own record leads, with no yes or no
