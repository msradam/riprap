"""Review round 2: the defects nine audience reviewers found in the answer
rules, most of them brought in by the fixes of round 1.

The reviewers' questions are here word for word, by finding number. Nothing
here reaches the network: the rules read the question and a fixed set of
source sentences and values."""

import datetime
import re
from pathlib import Path

import pytest
from test_review_round_1_answers import ADDRESS, OUTSIDE, T, _synthesize

from riprap.core.burr import answer_checks as ac
from riprap.core.burr import rule_answer as ra
from riprap.core.burr import synthesis
from riprap.core.burr.intake import heuristic_plan

TODAY = datetime.date(2026, 10, 5)
A = "90-01 183rd Street, Queens"


def _events(*days):
    return [{"date": d, "local_date": d, "max_depth_mm": 300} for d in days]


# Two sensors, 22 m and 413 m away, installed 2023-10-26: no event in 2024, one day in 2025, two in 2026.
ROWS = [{"distance_m": 22.0, "status": "good", "events": _events("2025-10-30", "2026-05-20", "2026-08-20")},
        {"distance_m": 413.0, "status": "noisy", "events": _events("2025-10-30", "2026-05-20", "2026-08-20")}]
FLOODNET = {"n_sensors": 2, "n_flood_events_3y": 6, "period_start": "2023-10-26", "by_year": {"2025": 2, "2026": 4},
            "highest_event": {"max_depth_mm": 1172, "date": "2026-05-20"}, "_rows": ROWS}
N311 = {"n": 88, "years": 5, "since": "2021-10-06", "radius_m": 200,
        "by_year": {"2021": 4, "2022": 10, "2023": 10, "2024": 21, "2025": 28, "2026": 15}}
V = {"floodnet": FLOODNET, "nyc311": N311}
AREA_T = {"floodnet": "21 FloodNet sensors inside this area have recorded 40 flood events in the last 3 years.",
          "nyc311_nta": "4499 NYC 311 complaints about flooding and sewer backups filed in Community District QN12.",
          "sandy_nta": "0.8% of this area lies inside the 2012 Hurricane Sandy inundation extent.",
          "dep_moderate_current_nta": 'On the city\'s stormwater flood map "Moderate Flood", 1.2% of this area is in a rainfall flooding category.',
          "dep_extreme_2080_nta": 'On the city\'s stormwater flood map "Extreme Flood", 4.0% of this area is in a rainfall flooding category.'}
AREA_V = {"floodnet": {"n_sensors": 21, "n_flood_events_3y": 40, "period_start": "2023-10-06",
                       "_rows": [{"distance_m": None, "status": "good", "events": _events("2024-08-06", "2026-05-20")}]},
          "nyc311_nta": {"n": 4499, "years": 3, "since": "2023-10-06", "by_year": {"2023": 300, "2024": 1500, "2025": 1500, "2026": 1199}}}
HEAT_T = {"heat_visits_nta": "Residents of the Bronx community district 1 made 36 emergency department visits for heat illness.",
          "hvi_nta": "The Heat Vulnerability Index scores this area 5 of 5. The department's file gives 86.3% of households with "
                     "air conditioning.",
          "heat_surface_nta": "Landsat measured the surface of this area at 3.0°F warmer than the city's land average.",
          "heat_station_nta": "At JFK Airport the air temperature reached 90°F on 10 days in 2026."}


def _answer(out: dict) -> str:
    return out["paragraph"].split("**Answer.**\n", 1)[1].split("\n\n", 1)[0]


# --- 1: a yes or no about a named year rests only on the records dated in that year ---

def test_a_year_with_no_event_is_a_no_for_the_sensors_record_only(monkeypatch):
    q = f"Did the block around {A} flood in 2024?"
    assert ra.answer(q, ADDRESS, V) == ("period", ["floodnet", "nyc311"])
    lead, sentence, _ = ac.period_lead(q, ADDRESS, V, TODAY)
    assert lead == "period" and sentence.startswith("No, not in the sensors' record for 2024: FloodNet's verified record "
                                                     "has no flood event in that period")
    assert "a no for those sensors only, not for the place" in sentence
    assert "21 complaints to 311 about flooding and sewer backups were filed in 2024" in sentence
    out = _synthesize(monkeypatch, q, values=V)
    assert _answer(out).startswith("No, not in the sensors' record for 2024") and not _answer(out).startswith("Yes")
    assert out["grounding"]["answer_lead"] == "period" and out["grounding"]["answered"] is True


@pytest.mark.parametrize("question,texts,values,facts", [
    (f"Did the FloodNet sensors near {A} record flooding in 2022?", ADDRESS, V, ["floodnet"]),
    ("Did QN12 flood in 2022?", AREA_T, AREA_V, ["floodnet", "nyc311_nta"]),
    ("Did this block flood in 2022?", ADDRESS, V, ["floodnet", "nyc311"]),  # the MCP tool's question
])
def test_a_year_before_the_record_gets_the_period_covered_and_no_yes_or_no(monkeypatch, question, texts, values, facts):
    assert ra.answer(question, texts, values) == ("cannot_answer", facts)
    sentence = ac.period_lead(question, texts, values, TODAY)[1]
    assert re.search(r"The FloodNet record quoted here starts on 2023-10-\d\d, after 2022, so it holds nothing", sentence)
    assert not re.search(r"\bYes\b|\bNo,", sentence)
    out = _synthesize(monkeypatch, question, texts=texts, values=values)
    assert out["grounding"]["answered"] is False and _answer(out).startswith("The FloodNet record quoted here starts on")


@pytest.mark.parametrize("question,opens", [
    (f"Did the block around {A} flood in 2025?", "Yes, in 2025: FloodNet's verified record has 2 flood events on 1 day"),
    (f"Did the block around {A} flood last year?", "Yes, in 2025:"),
    (f"Did the block around {A} flood in the summer of 2025?", "No, not in the sensors' record for the summer of 2025 (June to August)"),
    (f"Did the block around {A} flood in October 2025?", "Yes, in October 2025:"),
    (f"Has {A} flooded in the last year?", "Yes, in the last year (since 2025-10-05): FloodNet's verified record has 6 flood events on 3 days"),
    (f"Did {A} flood between 2024 and 2025?", "Yes, in 2024 to 2025:"),
])
def test_a_season_a_month_and_last_year_are_read_from_their_own_dates(question, opens):
    lead, sentence, facts = ac.period_lead(question, ADDRESS, V, TODAY)
    assert lead == "period" and sentence.startswith(opens) and facts[0] == "floodnet"
    if opens.startswith("Yes"):
        assert "the nearest of them 22 m from this address [floodnet]" in sentence


def test_a_period_no_rule_dates_gets_no_yes_or_no_and_the_since_paths_keep_theirs():
    # "Two years ago" is a period, and not one the rules turn into dates: the record with no lead.
    assert ra.answer(f"Did {A} flood two years ago?", ADDRESS, V)[0] == "facts"
    # "Since Ida", "since 2022": every event of the record is dated after the start, so its yes stands.
    for q in (f"Has {A} flooded since Ida?", f"Has {A} flooded since 2022?"):
        assert ra.answer(q, ADDRESS, V)[0] == "yes"
    # "Since 2026" starts inside the record: only the events dated from then count.
    focus = {"time_frame": "past"}
    assert ac.past_event_lead(f"Has {A} flooded since 2026?", focus, [], ADDRESS, V, 2026)[0] == "yes"
    old = {**V, "floodnet": {**FLOODNET, "_rows": [{**ROWS[0], "events": _events("2025-10-30")}]}}
    assert ac.past_event_lead(f"Has {A} flooded since 2026?", focus, [], ADDRESS, old, 2026)[0] != "yes"
    # A house number is not a year, and a named storm keeps its own record.
    assert ac.asked_period("Has 2024 Grand Concourse, Bronx flooded?", TODAY) is None
    assert ac.asked_period(f"Has {A} flooded since 2022?", TODAY) is None


def test_an_evening_event_on_new_years_eve_counts_in_the_year_people_lived_it():
    from app.context.floodnet import _local_date

    assert _local_date("2026-06-12T01:59:00") == "2026-06-11" and _local_date("2026-01-01T03:00:00") == "2025-12-31"
    nye = {"floodnet": {**FLOODNET, "_rows": [{"distance_m": 22.0, "status": "good", "events": [
        {"date": "2026-01-01", "local_date": "2025-12-31", "max_depth_mm": 200}]}]}}
    assert ac.period_lead(f"Did {A} flood in 2025?", ADDRESS, nye, TODAY)[1].startswith("Yes, in 2025:")
    assert ac.period_lead(f"Did {A} flood in 2026?", ADDRESS, nye, TODAY)[1].startswith("No, not in the sensors' record")


# --- 2: the people rule fires for what is not held, not for the bare nouns ---

@pytest.mark.parametrize("question,lead,first", [
    ("How many people went to the emergency room for heat in BX01?", "count", "heat_visits_nta"),
    ("How many residents visited the emergency department for heat illness in MN11?", "count", "heat_visits_nta"),
    ("How many households in East Harlem have air conditioning?", "count", "hvi_nta"),
    ("How many households in Brighton Beach have air conditioning?", "count", "hvi_nta"),
    ("What share of households in Brownsville have air conditioning?", "count", "hvi_nta"),
    ("How many people died of heat in East Harlem?", "no_deaths", "heat_visits_nta"),  # finding 20
])
def test_a_count_of_people_a_source_publishes_is_answered(question, lead, first):
    assert ra.not_held(question) is None
    got = ra.answer(question, HEAT_T, {})
    assert got[0] == lead and got[1][0] == first


def test_an_air_conditioning_question_leads_with_the_share(monkeypatch):
    out = _synthesize(monkeypatch, "How many households in East Harlem have air conditioning?", texts=HEAT_T,
                      values={"hvi_nta": {"hvi": 5, "ac_pct": 86.3, "area": "East Harlem (North)"}})
    assert _answer(out).startswith("The Health Department's file gives 86.3% of households with air conditioning in East "
                                   "Harlem (North), a survey estimate and a share, not a count of households [hvi_nta].")
    assert out["grounding"]["answered"] is True


def test_people_who_complained_are_counted_as_complaints_and_demographics_stay_not_held():
    q = "How many people have complained to 311 about flooding in MN11?"
    assert ra.not_held(q) is None and ra.answer(q, AREA_T, AREA_V) == ("count", ["nyc311_nta"])
    for q in ("How many older adults live alone without air conditioning in QN12?", "How many people live in Hunts Point?",
              "How many residents of BX01 went to the emergency room for heat, by age?"):
        assert ra.not_held(q)[0] == "people", q
    statement = ra.not_held("How many people live in Hunts Point?")[1]
    assert "emergency visits for heat illness" in statement and "households with air conditioning" in statement
    assert "The one count of residents" not in statement


def test_the_heat_value_serves_no_income_figure():
    from app.heat import dohmh

    source = Path(dohmh.__file__).read_text()
    assert '"median_income": a[' not in source  # the department's model input; Riprap quotes no income


# --- 3: a trend asked in other words ---

@pytest.mark.parametrize("question", [
    "Are 311 flooding complaints in QN12 rising?", "Is flooding in Hollis increasing?", "Has flooding in QN12 gone up?",
    "Does Hollis flood more than before?", "Is flooding in Red Hook getting wetter and deeper?",
    "Has flooding in QN12 changed over time?", "Is the flooding in QN12 better now?",
])
def test_a_flood_trend_question_is_told_no_record_shows_a_trend(question):
    assert ra.not_held(question)[0] == "trend"
    assert ra.answer(question, AREA_T, AREA_V) == ("not_held", [])


def test_a_heat_trend_leads_with_the_stations_yearly_record_and_land_cover_keeps_its_lead():
    assert ra.answer("Is Brownsville getting hotter?", HEAT_T, {}) == ("facts", ["heat_station_nta", "heat_surface_nta"])
    station = {"heat_station_nta": {"station": "JFK Airport", "year": 2026, "by_year": {y: 10 for y in range(1991, 2027)}}}
    assert synthesis.heat_answer.trend_sentence("Is Brownsville getting hotter?", ["heat_station_nta"], station).startswith(
        "At JFK Airport the yearly count of days at or above 90°F averaged")
    assert ra.not_held("Has QN12 become more paved over the years?") is None  # no_change_record's question
    assert ra.not_held("Is sea level rising at the Battery?") is None  # a projection answers


# --- 4, 19: a name matched to one building, or not matched at all ---

def test_el_barrio_is_east_harlem_and_the_note_names_both_tabulation_areas():
    from app.areas import nta

    hit = nta.resolve("El Barrio")[0]
    assert hit["nta_name"] == "East Harlem (North)"
    note = nta.resolution_note("El Barrio", hit)
    assert "East Harlem (South)" in note and "matches 2 of City Planning's" in note
    assert heuristic_plan("Has El Barrio flooded?")["intent"] == "neighborhood"


def test_a_name_the_geocoder_matched_to_one_building_says_so(monkeypatch):
    from burr.core import State

    from app.geocode import GeocodeHit
    from riprap.core.burr.intake import geocode_target

    hit = GeocodeHit("El Museo Del Barrio, 1230, 5th Avenue, Manhattan", "Manhattan", 40.79, -73.95, None, None, {})
    monkeypatch.setattr("app.geocode.geocode_one", lambda text, scope_hint=None: hit)
    out = geocode_target(State({"query": "Has Barrio Museum flooded?", "first_target": "Barrio Museum, New York, NY", "trace": []}))
    g = (out if hasattr(out, "get") else out[-1])["geocode"]
    assert g["match"] == "closest" and g["note"].startswith("The name typed, Barrio Museum, was matched by the geocoder to one "
                                                            "building or point, El Museo Del Barrio")
    assert "not to a neighbourhood" in g["note"] and "community district" in g["note"] and "street address" in g["note"]
    # A street address that matched keeps no such note.
    street = GeocodeHit("80 PIONEER STREET, Brooklyn, NY, USA", "Brooklyn", 40.68, -74.0, None, None, {})
    monkeypatch.setattr("app.geocode.geocode_one", lambda text, scope_hint=None: street)
    out = geocode_target(State({"query": "80 Pioneer Street, Brooklyn", "first_target": "80 Pioneer Street, Brooklyn", "trace": []}))
    assert (out if hasattr(out, "get") else out[-1])["geocode"]["note"] is None


def test_a_named_spot_that_was_not_located_gets_no_yes_or_no_about_it(monkeypatch):
    from riprap.core.burr.place import unplaced_name

    q = "Has the block around La Marqueta, East Harlem flooded?"
    assert unplaced_name(q, "East Harlem") == "La Marqueta"
    for other in ("Has the area near Hollis flooded since Ida?", "Did the blocks around Coney Island flood during Sandy?",
                  "Was there flooding at Sandy in Red Hook?", "Did it flood near FEMA's office in Hollis?"):
        assert unplaced_name(other, "Hollis") is None, other
    area = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 2, "period_start": "2023-10-06",
                         "_rows": [{"distance_m": None, "status": "good", "events": _events("2025-10-30")}]}}
    assert ra.answer(q, AREA_T, area)[0] == "yes"  # the rule's lead for the area, before the place is considered
    out = _synthesize(monkeypatch, q, texts=AREA_T, values=area, intent="neighborhood", nta={"nta_name": "East Harlem (North)"},
                      geocode={"address": "East Harlem (North), Manhattan", "unplaced": "La Marqueta"})
    assert _answer(out).startswith('Riprap could not locate "La Marqueta", so it gives no yes or no about that spot: what '
                                   "follows is the record for the wider area, East Harlem (North).")
    assert out["grounding"]["answer_lead"] == "facts" and "Yes" not in _answer(out)[:200]


# --- 5: small routes ---

def test_legally_in_a_flood_zone_is_a_flood_zone_question(monkeypatch):
    q = "Is 80 Pioneer Street, Brooklyn legally in a flood zone?"
    assert ra.not_held(q) is None and ra.answer(q, ADDRESS, {})[1][0] == "fema_nfhl"
    out = _synthesize(monkeypatch, q, values={"fema_nfhl": {"fld_zone": "X", "sfha": False}})
    assert "not a flood zone determination" in _answer(out)
    assert ra.not_held("Is it legal for my landlord to rent this flood zone basement?")[0] in ("basements", "law")


def test_environmental_justice_is_not_held_and_points_to_the_citys_tool():
    topic, statement = ra.not_held("Is Hunts Point an environmental justice area?")
    assert topic == "environmental_justice" and "holds no environmental justice designation" in statement
    assert "https://experience.arcgis.com/experience/6a3da7b920f248af961554bdf01d668b" in statement


def test_a_priorities_question_gets_the_no_advice_statement_before_the_borough_note():
    plan = heuristic_plan("Should Community Board 11 prioritize East 108th Street for drainage?")
    assert plan["intent"] == "not_implemented"
    assert plan["rationale"].startswith("Riprap gives no advice and sets no priorities")
    assert plan["rationale"].index("sets no priorities") < plan["rationale"].index("exists in more than one borough")


@pytest.mark.parametrize("question", [
    "Eske 80 Pioneer Street, Brooklyn te inonde?", "Èske katye mwen an konn inonde?",  # Haitian Creole
    "Est-ce que 80 Pioneer Street, Brooklyn a été inondé?", "Combien de fois la rue a-t-elle été inondée?",  # French
    "Czy 80 Pioneer Street, Brooklyn zostało zalane?", "Gdzie była powódź na Greenpoincie?",  # Polish
])
def test_a_question_in_another_designated_language_takes_the_not_english_lead(question):
    assert ra.not_english(question) and ra.answer(question, ADDRESS, {}) == ("not_english", [])


@pytest.mark.parametrize("text", [
    "has 80 pioneer st bklyn floded b4", "Is 80 Pioneer Street, Brooklyn flooded?", "wut abt flodding in holis",
    "Combine Street flood history", "Is the Pulaski Bridge flooded?", "100 Kosciuszko Street, Brooklyn", "Has El Barrio flooded?",
])
def test_english_and_its_misspellings_are_not_taken_for_another_language(text):
    assert not ra.not_english(text)


# --- 6: a flood word one letter off ---

def test_a_flood_word_one_edit_off_is_read_and_nothing_else_is_corrected(monkeypatch):
    q = "has 80 pioneer st bklyn floded b4"
    assert ra.spelled(q) == "has 80 pioneer st bklyn flooded b4"
    assert ra.spelled("is there blood on the first floor near floyd bennett field") == "is there blood on the first floor near floyd bennett field"
    assert ra.spelled("Floded Street") == "Floded Street"  # a capitalised word is a name
    out = _synthesize(monkeypatch, q, values=V)
    assert out["grounding"]["answer_lead"] in ("yes", "near") and out["grounding"]["answered"] is True


# --- 8: a basement, and "will" ---

def test_will_my_basement_flood_gets_the_prediction_sentence_and_the_basement_alerts(monkeypatch):
    out = _synthesize(monkeypatch, f"Will my basement flood at {A}?")
    assert out["grounding"]["not_held"] == "basements" and out["grounding"]["answered"] is False
    assert synthesis.NO_PREDICTION in _answer(out)
    turn = out["paragraph"].split("**Where to turn.**\n", 1)[1].split("\n\n", 1)[0]
    assert turn == synthesis.SAFETY_POINTER and "Basement Alerts" in turn
    # An answered question that mentions a basement carries it too, under its own heading and not "Out of scope".
    out = _synthesize(monkeypatch, f"I rent a basement at {A}. Has the block flooded?", values=V)
    assert f"**Where to turn.**\n{synthesis.SAFETY_POINTER}" in out["paragraph"]
    assert "Basement Alerts" not in out["paragraph"].split("**Out of scope.**", 1)[1]


# --- 9: a cause or a threshold no record gives ---

@pytest.mark.parametrize("question,texts", [
    ("How much rain would flood 153-10 Peck Avenue, Flushing?", {**ADDRESS, "nws_obs": "Latest METAR at LaGuardia: no precipitation reported."}),
    ("Is the flooding in Broad Channel from the tide?", {**AREA_T, "noaa_tides": "Latest reading at Sandy Hook: 3.28 ft above MLLW."}),
])
def test_a_cause_question_is_unanswered_and_gets_the_maps_the_sensors_and_the_note(monkeypatch, question, texts):
    lead, facts = ra.answer(question, texts, {})
    assert lead == "cannot_answer" and facts[-1] == "floodnet" and all(f.startswith("dep_") for f in facts[:-1]) and len(facts) > 1
    out = _synthesize(monkeypatch, question, texts=texts)
    assert out["grounding"]["answered"] is False and _answer(out).startswith(synthesis.CANNOT_ANSWER)
    assert ra.CAUSE_NOTE in _answer(out) and "METAR" not in _answer(out) and "Sandy Hook" not in _answer(out)


def test_a_question_that_names_the_stormwater_maps_is_not_a_cause_question():
    # (The question evaluation's q15 and f03: answered from the maps, and marked answered.)
    q = "Is 2017 East 17th Street, Brooklyn in any of the DEP stormwater flood scenarios?"
    lead, facts = ra.answer(q, ADDRESS, {})
    assert not ra.asks_cause(q) and lead == "facts" and facts == ["dep_moderate_current", "dep_extreme_2080"]


# --- 10: a depth, and the "100-year storm" ---

def test_how_deep_will_the_water_get_is_told_no_depth_is_given(monkeypatch):
    q = "How deep will the water get at 153-10 Peck Avenue, Flushing in a 100-year storm?"
    lead, facts = ra.answer(q, ADDRESS, {})
    assert lead == "no_depth" and facts[0] == "dep_extreme_2080" and facts[-2:] == ["fema_nfhl", "fema_pfirm"]
    out = _synthesize(monkeypatch, q)
    assert out["grounding"]["answered"] is False
    assert _answer(out).startswith('Riprap gives no flood depth for a place: no source here predicts one, and the city says '
                                   'its stormwater flood map "does not provide the exact depth of flooding at any location".')


def test_the_100_year_storm_is_the_extreme_stormwater_map_with_fema_after():
    lead, facts = ra.answer("What does the 100-year storm scenario show at 400 Carroll Street, Brooklyn?", ADDRESS, {})
    assert lead == "facts" and facts == ["dep_extreme_2080", "fema_nfhl", "fema_pfirm"]
    assert ra.answer("Is 400 Carroll Street, Brooklyn in the 100-year floodplain?", ADDRESS, {})[1][0] == "fema_nfhl"


def test_the_plans_chance_wording_is_quoted_from_the_manifests_citations():
    from app.flood_layers.dep_stormwater import PLAN_CHANCE

    manifests = Path(__file__).resolve().parent.parent / "deployments" / "nyc" / "manifests"
    cited = " ".join((manifests / f"{m}.yaml").read_text() for m in ("dep_moderate_2050", "dep_extreme_2080"))
    cited = " ".join(cited.split())
    quotes = re.findall(r'"([^"]+)"', PLAN_CHANCE)
    assert len(quotes) == 2 and all(q in cited for q in quotes), quotes


# --- 11: an area's flood zone, "high risk", a register at the Sandy edge, "at the edge" ---

def test_an_area_flood_zone_question_gets_every_map_and_the_floodplain_counts_where_held():
    lead, facts = ra.answer("Is Rockaway Park in a flood zone?", AREA_T, {})
    assert lead == "no_area_zone" and facts == ["sandy_nta", "dep_moderate_current_nta", "dep_extreme_2080_nta"]
    district = {**AREA_T, "dcp_floodplain_nta": T["dcp_floodplain_nta"]}
    lead, facts = ra.answer("Is QN14 in a flood zone?", district, {})
    assert lead == "area_zone" and facts[0] == "dcp_floodplain_nta" and "dep_extreme_2080_nta" in facts
    for k in ("area_zone", "no_area_zone"):
        assert synthesis.LEAD_PHRASES[k].startswith("FEMA flood zones are read at a street address, not for an area as a whole")
    # A count of residents in the floodplain is still City Planning's count alone.
    assert ra.answer("How many residents of QN14 live in the floodplain?", district, {})[1][0] == "dcp_floodplain_nta"


def test_high_risk_gets_the_record_the_maps_and_fema_with_the_outside_caveat_and_no_label(monkeypatch):
    q = "Is 61-20 Grand Central Parkway, Forest Hills at high risk of flooding?"
    lead, facts = ra.answer(q, ADDRESS, {})
    assert lead == "facts" and facts[:2] == ["floodnet", "nyc311"] and facts[-2:] == ["fema_nfhl", "fema_pfirm"]
    assert "dep_moderate_current" in facts
    answer = _answer(_synthesize(monkeypatch, q, values={"fema_nfhl": {"fld_zone": "X", "sfha": False}}))
    assert answer.count(OUTSIDE) == 1 and not re.search(r"high[- ]risk|low[- ]risk", answer)


def test_a_register_says_in_its_count_clause_which_assets_are_at_the_sandy_edge():
    from app.registers._loader import narrative

    text = narrative("hospital", "hospitals", 3, None, 0, 2, 0, n_near=2)
    assert ("0 inside the 2012 Sandy inundation extent at their mapped points, 2 more within 50 m of the extent's mapped "
            "edge, and 2 inside the DEP stormwater map") in text
    assert ac._register_counts(text) == (3, 0, 2)
    assert "mapped edge" not in narrative("hospital", "hospitals", 3, None, 0, 2, 0)


def test_at_the_edge_is_said_only_within_ten_metres():
    from riprap.core.pebbles.shapers.dep_scenario import _edge

    assert _edge(6, "flooding mapped on it") == "at the edge of flooding mapped on it (within about 6 m)"
    assert _edge(44, "flooding mapped on it") == "about 44 m from the edge of flooding mapped on it"


# --- 12, 17: a year's count leads with days, and a lead that states a figure carries its source's mark ---

def test_a_floodnet_count_for_a_year_leads_with_days_not_sensor_events():
    q = f"How many times did FloodNet sensors near {A} record flooding in 2026?"
    assert ac.count_lead(q, ADDRESS, V, TODAY) == (
        "Flooding was recorded on 2 separate days in 2026 so far (4 sensor events), by the New York day each event "
        "started [floodnet].", False)
    assert ac.count_lead(q.replace("2026", "2025"), ADDRESS, V, TODAY)[0].startswith("Flooding was recorded on 1 day in 2025 (2 sensor events)")


def test_every_lead_that_states_a_sources_figure_ends_with_its_mark():
    q = f"Did {A} flood on May 20, 2026?"
    assert ac.day_lead(q, ADDRESS, V)[1].endswith("the deepest 300 mm [floodnet].")
    assert ac.day_lead(q.replace("May 20", "May 21"), ADDRESS, V)[1].startswith(
        "FloodNet's verified record has no flood event dated 2026-05-21 (New York time) at the 2 sensors read for this place [floodnet].")
    far = {"floodnet": {**FLOODNET, "_rows": ROWS[1:]}}
    assert "is 413 m away [floodnet]." in ac.near_lead(["floodnet"], far)
    assert ac.yes_lead("floodnet", V) == ("The record this rests on is a FloodNet sensor with a verified flood event 22 m from "
                                          "this address [floodnet].")
    n311 = {"nyc311": {**N311, "by_kind": {"sewer backup": 48}}}
    assert ac.count_lead(f"How many 311 flood complaints near {A} in 2024?", ADDRESS, n311, TODAY)[0].endswith("[nyc311].")


# --- 13, 20: sensors are not named or placed; a citywide superlative is not held; the depth on a named day is ---

@pytest.mark.parametrize("question,topic", [
    (f"Which FloodNet sensor near {A} recorded the deepest flood?", "sensor_identity"),
    (f"Where exactly are the FloodNet sensors near {A}?", "sensor_identity"),
    (f"Was the May 20 2026 flood at {A} the deepest FloodNet has ever recorded?", "citywide_record"),
    (f"Which houses on 183rd Street near {A} complained about sewer backups?", "houses"),
    ("How many sewer complaints has BX02 had?", "sewer_311"),  # finding 18
])
def test_these_questions_are_told_what_riprap_does_not_hold(monkeypatch, question, topic):
    assert ra.not_held(question)[0] == topic
    out = _synthesize(monkeypatch, question, values=V)
    assert out["grounding"]["answered"] is False and out["grounding"]["not_held"] == topic


def test_the_sensor_statement_says_where_each_event_can_be_looked_up():
    assert "FloodNet's licence forbids reposting its records" in ra.SENSORS_NOT_NAMED
    assert '"FloodNet: Street Flooding Events Measured by FloodNet Sensors" (https://data.cityofnewyork.us/d/aq7i-eu5q)' in ra.SENSORS_NOT_NAMED
    manifests = Path(__file__).resolve().parent.parent / "deployments" / "nyc" / "manifests"
    for m in ("floodnet", "floodnet_nta"):
        citation = " ".join((manifests / f"{m}.yaml").read_text().split())
        assert "Riprap names no sensor, because FloodNet's licence forbids reposting its records" in citation
        assert "https://data.cityofnewyork.us/d/aq7i-eu5q" in citation


def test_how_deep_was_the_water_on_a_named_day_is_the_day_rules_question():
    assert ra.answer(f"How deep was the water at {A} on May 20, 2026?", ADDRESS, V) == ("day", ["floodnet"])


def test_sewer_backup_complaints_and_the_old_label_are_still_counted():
    for q in ("How many sewer backup complaints has BX02 had?", "How many flood and sewer complaints has QN12 had?"):
        assert ra.not_held(q) is None, q


# --- 14: "since Ida" names the nearest record of any kind and quotes the Ida mark ---

def test_since_ida_names_the_ida_mark_when_it_is_the_nearest_record(monkeypatch):
    q = "Has 80 Pioneer Street, Brooklyn flooded since Hurricane Ida?"
    texts = {**ADDRESS, "ida_hwm": "USGS surveyed 3 Hurricane Ida high-water marks within 800 m of this address."}
    values = {"floodnet": {**FLOODNET, "_rows": [{**ROWS[0], "distance_m": 211.0}]}, "nyc311": N311,
              "ida_hwm": {"n_within_radius": 3, "nearest_dist_m": 130.0}}
    lead, facts = ra.answer(q, texts, values)
    assert lead == "near" and facts[0] == "floodnet" and "ida_hwm" in facts
    answer = _answer(_synthesize(monkeypatch, q, texts=texts, values=values))
    assert answer.startswith("Flooding was recorded near this address, not at it: the nearest USGS high-water mark from "
                             "Hurricane Ida is 130 m away [ida_hwm].")
    assert "USGS surveyed 3 Hurricane Ida high-water marks" in answer
    # A plain yes says how far the record it rests on is.
    on_block = {**values, "floodnet": FLOODNET}
    assert _answer(_synthesize(monkeypatch, q, texts=texts, values=on_block)).startswith(
        "Yes. The record this rests on is a FloodNet sensor with a verified flood event 22 m from this address [floodnet].")


# --- 15: a named day is matched on the New York date ---

def test_an_evening_flood_is_found_on_the_day_it_happened_in_new_york():
    q = "Did 145 Rivington Street, Manhattan flood on June {}, 2026?"
    v = {"floodnet": {"n_sensors": 1, "n_flood_events_3y": 1, "period_start": "2024-07-24", "_rows": [
        {"distance_m": 57.0, "status": "good", "events": [{"date": "2026-06-12", "local_date": "2026-06-11", "max_depth_mm": 470}]}]}}
    assert ac.day_lead(q.format(11), ADDRESS, v)[1].startswith(
        "FloodNet's verified record has 1 flood event dated 2026-06-11 (New York time) at sensors within 600 m")
    assert "no flood event dated 2026-06-12 (New York time)" in ac.day_lead(q.format(12), ADDRESS, v)[1]


# --- 16: the deepest reading at one place is not a ranking of places ---

def test_the_worst_flood_measured_at_one_place_is_answered_with_its_depth(monkeypatch):
    q = "How deep was the worst flood FloodNet measured in Hollis?"
    assert ra.not_held(q) is None and ra.answer(q, AREA_T, AREA_V) == ("facts", ["floodnet"])
    answer = _answer(_synthesize(monkeypatch, q, texts=AREA_T, values={**AREA_V, "floodnet": {**AREA_V["floodnet"], "highest_event": {
        "max_depth_mm": 954, "date": "2026-05-20"}}}))
    assert answer.startswith("The highest depth in FloodNet's verified record for the sensors read here is 954 mm (37.6 in), on "
                             "2026-05-20 (UTC) [floodnet].")
    assert ra.not_held("Which block in Hollis floods the worst?")[0] == "ranking"


# --- 20: the rest of the wrong or missing refusals ---

def test_a_question_with_no_place_is_not_sent_to_the_geocoder():
    law = heuristic_plan("What does Local Law 188 of 2025 say?")
    assert law["intent"] == "not_implemented" and law["targets"] == [] and law["rationale"].startswith("Riprap holds no legal records")
    about = heuristic_plan("Who made Riprap and who pays for it?")
    assert about["intent"] == "not_implemented" and about["targets"] == [] and "about page (/about)" in about["rationale"]
    # A place beside the word Riprap is still a place.
    assert heuristic_plan("What does Riprap say about 80 Pioneer Street, Brooklyn?")["intent"] == "single_address"


def test_a_dangerous_place_in_the_heat_gets_the_heat_wording_and_a_homes_worth_the_no_advice_lead():
    assert ra.answer("Is East Harlem a dangerous place in a heat wave?", HEAT_T, {})[0] == "no_rating_heat"
    phrase = synthesis.LEAD_PHRASES["no_rating_heat"]
    assert "insurance" not in phrase and "a rank among neighbourhoods" in phrase and "All neighborhoods have residents at risk" in phrase
    address = {k.removesuffix("_nta"): v for k, v in HEAT_T.items()}
    assert ra.answer("Is my apartment at 80 Pioneer Street, Brooklyn dangerous in a heat wave?", address, {})[0] == "no_advice_heat"
    q = f"What is my home worth after the flooding at {A}?"
    assert ra.asks_advice(q) and ra.answer(q, ADDRESS, {})[0] == "no_advice"


# --- 21: 311 on the days of Ida, which the address window no longer reaches ---

def test_the_days_of_ida_are_counted_apart_with_the_same_filter_and_no_house_number(monkeypatch):
    from app.context import nyc311

    seen = {}

    def fake(clause, since, limit, timeout=60):
        seen.update(clause=clause, since=since)
        return [nyc311.Complaint("1", "Street Flooding (SJ)", "2021-09-01T22:10:00", "153-10 PECK AVENUE", "Closed", 40.74, -73.81),
                nyc311.Complaint("2", "Sewer Backup (Use Comments) (SA)", "2021-09-02T09:00:00", "153-12 PECK AVENUE", "Closed", 40.74, -73.81)]

    monkeypatch.setattr(nyc311, "_complaints_where", fake)
    text = nyc311.days_sentence(40.74, -73.81, 200, *nyc311.IDA_DAYS, "the days of Hurricane Ida")
    assert seen["clause"].endswith("created_date < '2021-09-04T00:00:00'") and seen["since"] == datetime.datetime(2021, 9, 1)
    assert "2 NYC 311 complaints about flooding and sewer backups were filed within 200 m of this location from 2021-09-01 to 2021-09-03" in text
    assert "1 street flooding, 1 sewer backup" in text and "PECK" not in text and "a low count can mean under-reporting" in text


@pytest.mark.parametrize("question", [
    "Did 153-10 Peck Avenue, Flushing flood on September 1, 2021?", "Has 153-10 Peck Avenue, Flushing flooded since Ida?",
    "Did 153-10 Peck Avenue, Flushing flood during Hurricane Ida?",
])
def test_an_ida_question_gets_the_311_sentence_for_the_storms_days(monkeypatch, question):
    from app.context import nyc311

    monkeypatch.setattr(nyc311, "days_sentence", lambda lat, lon, r, first, last, what: f"For {what}: 12 complaints {first} to {last}.")
    values = {**V, "_point": (40.74, -73.81)}
    assert synthesis._days_311(question, ADDRESS, values) == "For the days of Hurricane Ida: 12 complaints 2021-09-01 to 2021-09-03 [nyc311]."
    # The real sentence is a count and its caveat: each is cited, so the count is never an uncited number.
    monkeypatch.setattr(nyc311, "days_sentence", lambda *a: "For the days: 5 complaints were filed: 4 sewer backup. A count is of reports.")
    assert synthesis._days_311(question, ADDRESS, values) == (
        "For the days: 5 complaints were filed: 4 sewer backup [nyc311]. A count is of reports [nyc311].")
    # The fetch failed, or the place is an area: the count quoted is said to start after the storm.
    monkeypatch.setattr(nyc311, "days_sentence", lambda *a: (_ for _ in ()).throw(OSError("timed out")))
    assert synthesis._days_311(question, ADDRESS, values) == (
        "The 311 count quoted here starts on 2021-10-06, after the days of Hurricane Ida (2021-09-01 to 2021-09-03), so it "
        "holds no complaint from then [nyc311].")
    assert "starts on 2023-10-06, after the days of Hurricane Ida" in synthesis._days_311("Has QN12 flooded since Ida?", AREA_T, AREA_V)
    # No other question gets it, and a window that reaches the days asked needs no second count.
    assert synthesis._days_311(f"Has {A} flooded?", ADDRESS, values) == ""
    assert synthesis._days_311(question, ADDRESS, {**values, "nyc311": {**N311, "since": "2020-10-06"}}) == ""


def test_no_ida_mark_nearby_is_not_called_a_dry_street():
    import json

    from riprap.core.pebbles.shapers.ida_hwm import FEW_MARKS, shape

    baked = json.loads((Path(__file__).resolve().parent.parent / "data" / "ida_2021_hwms_ny.geojson").read_text())
    assert f"holds {len(baked['features'])} Ida high-water marks for all of New York State" in FEW_MARKS
    text = shape({"n_within_radius": 0, "radius_m": 800, "features": [], "nearest": None})["narrative"]
    assert text == f"No Hurricane Ida (Sept 2021) high-water marks were surveyed within 800 m of this address. {FEW_MARKS}"
    assert "not a record that the place stayed dry" in text


def test_the_311_windows_own_period_is_answered_from_its_total():
    """"Have people near 355 Food Center Drive reported flooding to 311 in the last five years?" was told the
    count "gives no count for the last 5 years (since 2021-10-06)", the very window it covers."""
    q = f"Have people near {A} reported flooding to 311 in the last five years?"
    assert ac.asked_period(q, TODAY)[0] == datetime.date(2021, 10, 6)
    assert ac.period_lead(q, ADDRESS, V, TODAY) is None  # the general rule reads the window's total
    # Beside a sensor's verdict, the count is stated for its window, not withheld.
    sentence = ac.period_lead(f"Did {A} flood in the last five years?", ADDRESS, V, TODAY)[1]
    assert "88 complaints to 311 about flooding and sewer backups were filed in the last 5 years (since 2021-10-06)" in sentence
    assert "gives no count" not in sentence
    # A shorter period is still not the window.
    assert "gives no count for the last 2 years" in ac.period_lead(f"Did {A} flood in the last two years?", ADDRESS, V, TODAY)[1]
