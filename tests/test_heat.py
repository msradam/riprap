"""The heat briefing: which queries it takes, which sources it runs, how its
rules answer, and what each source's sentence says. Offline: the live
sources are given canned responses."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

from riprap.core.burr import heat_answer as ha
from riprap.core.burr import rule_answer as ra
from riprap.core.burr.intake import heuristic_plan
from riprap.core.burr.stones import hazard_of, select_pebbles
from riprap.core.pebbles.bridge import get_registry

NYC = get_registry("nyc")
ROOT = Path(__file__).resolve().parent.parent


# ---- which hazard a query is about -----------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "heat QN12", "extreme heat at 350 5th Ave, Manhattan", "How hot is it right now in Hunts Point?",
    "Will it be dangerously hot this week at 90-01 183rd Street, Queens?", "Is BX02 a heat island?",
    "Where is the nearest cooling center to 80 Pioneer Street, Brooklyn?", "How many 95 degree days by the 2050s in QN12?",
    "Will my apartment at 80 Pioneer Street, Brooklyn overheat this weekend?", "surface temperature in East Harlem",
    "which blocks around 104 W 136th St in Harlem get the hottest in summer?",
])
def test_heat_words_make_a_heat_query(query):
    assert ha.hazard_of(query) == "heat"
    assert heuristic_plan(query)["focus"]["hazard"] == "heat"


@pytest.mark.parametrize("query", [
    # Streets, parks and neighbourhoods that hold a heat word are places, not questions about heat.
    "135 Heath Avenue, Bronx", "100 Summer Street, Staten Island", "Coolidge Avenue, Queens", "Sunnyside", "QN12",
    "2940 Brighton 3rd St, Brooklyn", "Hot water outage at 100 Gold Street",
    # A flood question with the heat as its setting.
    "It gets hot here in the summer and the basement floods at 80 Pioneer St Brooklyn",
    "It was hot last summer. Was 80 Pioneer Street, Brooklyn inside the Sandy zone?",
    "Did 80 Pioneer Street, Brooklyn flood last summer?",
    # Heating, not heat.
    "How many heating complaints near 100 Gold Street?",
])
def test_a_heat_word_in_a_place_or_a_flood_question_is_not_a_heat_query(query):
    assert ha.hazard_of(query) == "flood"
    assert (heuristic_plan(query).get("focus") or {}).get("hazard", "flood") != "heat"


@pytest.mark.parametrize("query", [
    "no heat in my apartment at 100 Gold St", "The landlord turned off the heat at 2940 Brighton 3rd St",
    "heat and hot water complaints in BK05", "Is the boiler out at 80 Pioneer Street?",
])
def test_indoor_heating_is_named_as_such_and_sent_to_311(query):
    # The trap: 311 "HEAT/HOT WATER" is a cold apartment in winter (67,229 complaints in January 2025, 2,929 in August).
    plan = heuristic_plan(query)
    assert plan["intent"] == "not_implemented" and "indoor heating" in plan["rationale"] and "311" in plan["rationale"]


@pytest.mark.parametrize("query", [
    "Should I go running today in Astoria in this heat?", "Is it too hot to walk the dog in Hunts Point today?",
    "What are the symptoms of heat stroke? I live at 80 Pioneer Street, Brooklyn",
    "Should I buy an apartment at 350 5th Ave given the heat?",
])
def test_advice_about_heat_is_declined_in_heats_own_words(query):
    from riprap.core.burr.templated_reconciler import HEAT_REFUSAL, refusal

    plan = heuristic_plan(query)
    assert plan["intent"] == "out_of_scope" and plan["focus"]["hazard"] == "heat"
    assert refusal({"intent": "out_of_scope", "plan": plan}) == HEAT_REFUSAL


# Questions written by an agent that had seen none of the rules (tests/golden/unseen_heat.json, first run
# 2026-10-02). Each of these went wrong the first time: no heat word the pattern knew, a place the parser
# missed, or a borough where a place was wanted.
@pytest.mark.parametrize("query", [
    "will it be over 95 this weekend in Tottenville", "forecast highs next 3 days Flushing Meadows Corona Park",
    "how many days hit 90 or above in Central Park in summer 2024",
    "How hot did the surface get around Polo Grounds Towers last summer? I mean the satellite number, not air temp",
    "need a list of cool places within walking distance of Van Dyke Houses for a flyer, libraries pools senior centers",
    "cooling centers and libraries near Stapleton Houses, and what is the closest hospital",
    "what will summers be like on the south shore of staten island when my kids are my age, say the 2060s",
    "What is the record high at Central Park?",
    "current temp + any heat alerts, Brownsville Houses",
])
def test_heat_questions_nobody_here_wrote_are_heat_questions(query):
    assert ha.hazard_of(query) == "heat"


@pytest.mark.parametrize("query,place", [
    ("Thinking of renting a top floor apartment near Marcy Houses, is that a bad idea because of heat?", "Marcy Houses"),
    ("I live in Wagner Houses. Where can I cool off after the senior center on East 109th closes?", "Wagner Houses"),
    ("cooling centers near Queensbridge Houses", "Queensbridge Houses"),
    ("current temp + any heat alerts, Brownsville Houses", "Brownsville Houses"),
    ("how hot is it right now near Crotona Park", "Crotona Park"),
    ("what time is the Heat game at Barclays Center tonight", "Barclays Center"),
])
def test_a_named_building_or_park_is_the_place_not_the_sentences_first_word(query, place):
    # "Thinking" was once geocoded to a trail upstate, and "East" of "East 109th" to the East Village.
    from riprap.core.burr.place import resolve_query

    assert resolve_query(query)["text"] == place


@pytest.mark.parametrize("query,code", [
    ("Is there a heat advisory in effect for Manhattan right now?", "MN"),
    ("What was the hottest day on record in Brooklyn and when was it?", "BK"),
    ("Is the Weather Service expecting a heat advisory in the Bronx tomorrow?", "BX"),
    ("How many 90 degree days is NYC projected to have by the 2050s according to NPCC?", "NYC"),
    ("How many heat-related deaths does the city report per year, and what years does that cover?", "NYC"),
])
def test_a_borough_or_the_city_is_a_place_for_a_heat_question(query, code):
    # (The second once went to the geocoder whole and came back as a Weather Service office in Albany.)
    plan = heuristic_plan(query)
    assert plan["intent"] == "neighborhood" and plan["targets"] == [{"type": "nta", "text": code}]
    from app.areas import nta

    area = nta.by_borough(code)
    assert area["nta_code"] == code and area["geometry"].area > 0
    # A flood question still needs a place: a borough alone is not one.
    assert heuristic_plan("Queens")["targets"][0]["text"] != "QN"


def test_a_heat_question_with_no_place_says_so_in_heats_words():
    plan = heuristic_plan("How hot does it get, and is there a heat advisory?")
    assert plan["intent"] == "not_implemented" and "names none" in plan["rationale"] and "FloodNet" not in plan["rationale"]
    # The word alone names no place: it was once geocoded to a heat-treating works and briefed.
    for q in ("heat", "extreme heat", "Heat?"):
        assert heuristic_plan(q)["intent"] == "not_implemented", q
    assert heuristic_plan("gantry plaza state park heat")["targets"][0]["text"] == "gantry plaza state park"


@pytest.mark.parametrize("query,targets", [
    ("Is Mott Haven hotter than Riverdale? By how much?", [("nta", "Mott Haven"), ("nta", "Riverdale")]),
    ("compare heat vulnerability BK16 vs BK06", [("district", "BK16"), ("district", "BK06")]),
    ("Corona vs Forest Hills, surface temperature and tree canopy", [("nta", "Corona"), ("nta", "Forest Hills")]),
])
def test_two_places_in_a_heat_question_are_compared_not_merged(query, targets):
    # The first was once answered "At the surface, yes." from Mott Haven against the city, with Riverdale unread.
    plan = heuristic_plan(query)
    assert plan["intent"] == "compare" and [(t["type"], t["text"]) for t in plan["targets"]] == targets
    assert heuristic_plan("Is Hunts Point hotter than the rest of the city?")["intent"] == "neighborhood"
    assert ra.answer("Is Mott Haven hotter than Riverdale?", {"heat_surface_nta": "x"}, {"heat_surface_nta": {"warmer_in_every_image": True}}) == (
        "facts", ["heat_surface_nta"])


def test_heat_outside_the_city_is_said_not_briefed():
    from riprap.core.burr.templated_reconciler import nothing_built

    state = {"lat": 40.717, "lon": -74.04, "deployment": "__none__", "plan": {"focus": {"hazard": "heat"}},
             "geocode": {"address": "30 Montgomery Street, Jersey City, New Jersey"}}
    text = nothing_built(state)
    assert "covers New York City only" in text and "30 Montgomery Street, Jersey City" in text
    from riprap.core.compliance import check_briefing

    assert not check_briefing(text).failed  # it is shown as a briefing, so the disclosure checks run on it


def test_bare_places_and_questions():
    from app.planner import is_bare_place

    for q in ("heat QN12", "extreme heat at 350 5th Ave, Manhattan", "heat risk 80 Pioneer Street, Brooklyn"):
        assert is_bare_place(q, heuristic_plan(q)["targets"]), q
    for q in ("QN12 heat vulnerability index", "heat forecast this week 350 5th Ave, Manhattan", "cooling centers BK05"):
        assert not is_bare_place(q, heuristic_plan(q)["targets"]), q


def test_intents_follow_the_place_and_the_time():
    assert heuristic_plan("heat QN12")["intent"] == "neighborhood"
    assert heuristic_plan("extreme heat at 350 5th Ave, Manhattan")["intent"] == "single_address"
    # A heat question about now runs every heat source, not the live ones alone: "is the pool open today"
    # needs the list of pools. The rules pick the live facts from the time frame.
    now = heuristic_plan("How hot is it right now in Hunts Point?")
    assert now["intent"] == "neighborhood" and now["focus"]["time_frame"] == "now"
    assert heuristic_plan("How hot is it right now at 350 5th Ave, Manhattan?")["intent"] == "single_address"
    assert heuristic_plan("Is it flooding right now at 350 5th Ave, Manhattan?")["intent"] == "live_now"  # flood, unchanged
    week = heuristic_plan("Will it be dangerously hot this week at 90-01 183rd Street, Queens?")
    assert week["intent"] == "single_address" and week["focus"]["time_frame"] == "future"


# ---- which sources run -----------------------------------------------------------------------------------

def test_a_heat_briefing_runs_the_heat_sources_and_a_flood_briefing_none_of_them():
    heat = {p.id for p in NYC.all() if p.manifest.hazard == "heat"}
    shared = {p.id for p in NYC.all() if p.manifest.hazard == "any"}
    assert {"heat_surface", "hvi", "heat_visits", "heat_station", "heat_obs", "nws_heat_forecast", "nws_heat_alerts",
            "npcc4_heat", "cool_features"} <= heat and {"city_landcover", "landcover", "area_boundary"} <= shared
    got = set(select_pebbles(heuristic_plan("extreme heat at 350 5th Ave, Manhattan"), NYC))
    assert got == {i for i in heat | shared if not i.endswith("_nta") and i != "area_boundary"}
    area = set(select_pebbles(heuristic_plan("heat QN12"), NYC))
    assert area == {i for i in heat | shared if i.endswith("_nta") or i == "area_boundary"}
    flood = set(select_pebbles(heuristic_plan("350 5th Ave, Manhattan"), NYC))
    assert not flood & heat and "sandy" in flood and "city_landcover" in flood
    now = set(select_pebbles(heuristic_plan("How hot is it right now at 350 5th Ave, Manhattan?"), NYC))
    assert now == got  # every heat source: the rules choose the live facts


def test_a_plan_without_a_focus_is_a_flood_plan():
    assert hazard_of(None) == "flood" and hazard_of({"focus": {"hazard": "air"}}) == "flood"
    assert hazard_of({"focus": {"hazard": "heat"}}) == "heat"


def test_every_heat_manifest_is_dated_sourced_and_licensed():
    for p in NYC.all():
        m = p.manifest
        if m.hazard != "heat":
            continue
        prov = m.provenance
        assert prov.date_modified and prov.retrieved_at and prov.license and prov.source_url and prov.citation, m.id
        assert m.tier in ("empirical", "modeled") and m.maturity == "production" and m.answers, m.id
        assert (m.type == "live") == (prov.date_modified == "at_fetch"), m.id  # a baked record states its own date


# ---- the rules -------------------------------------------------------------------------------------------

T = {
    "heat_surface": "Landsat measured the surface of the ground within 150 m of this address at 7.5°F warmer than the "
                    "city's land average, over 18 clear summer images.",
    "hvi": "The NYC Health Department's Heat Vulnerability Index (2023) scores Jamaica at 5 out of 5.",
    "heat_visits": "Residents of Queens community district 12 made 79 emergency department visits for heat illness.",
    "city_landcover": "New York City's 2017 land cover map shows that 83.5% of the ground is paved (11.5% tree canopy).",
    "landcover": "Experimental: a satellite land-cover model estimates that 84.0% is paved.",
    "heat_station": "At JFK Airport the air temperature reached 90°F on 10 days in 2026 through 2026-10-01.",
    "heat_obs": "The air at JFK Airport was 72°F at 09:55 on 2026-10-02.",
    "cool_features": "NYC Parks lists spray showers at 2 parks or playgrounds within 800 m of this address.",
    "nws_heat_alerts": "No active NWS heat advisory, watch or warning at this point, checked 2026-10-02 14:29 UTC.",
    "nws_heat_forecast": "Over the next 7 days the National Weather Service expects daytime highs of 82°F today.",
    "npcc4_heat": "NPCC4 (2024) projects 38 to 62 days a year at or above 90°F in New York City by the 2050s.",
}
V = {"heat_surface": {"mean_diff_f": 7.5, "warmer_in_every_image": True, "cooler_in_every_image": False},
     "heat_station": {"station": "JFK Airport", "year": 2026, "through": "2026-10-01", "days_ge_90": 10,
                      "by_year": {2023: 5, 2025: 15, 2026: 10}}}
A = "90-01 183rd Street, Queens"


@pytest.mark.parametrize("question,lead,facts", [
    # A score: Riprap computes none, and quotes the department's index as what it is.
    (f"What is the heat score for {A}?", "no_score", ["hvi"]),
    (f"How does {A} rank for heat?", "no_score", ["hvi"]),
    (f"What is the hottest block near {A}?", "no_ranking", ["heat_surface"]),
    ("Which parts of the Bronx should worry most about heat?", "no_ranking", ["heat_surface", "hvi", "city_landcover", "heat_station"]),
    # A building or a block on a coming day: nobody predicts that.
    (f"Will my apartment at {A} overheat this weekend?", "no_prediction_heat", ["nws_heat_forecast", "nws_heat_alerts", "heat_surface"]),
    (f"How hot will it get inside my building at {A} tomorrow?", "no_prediction_heat",
     ["nws_heat_forecast", "nws_heat_alerts", "heat_surface"]),
    # Now: the reading, the alert, the forecast; no yes or no.
    (f"How hot is it right now at {A}?", "facts", ["heat_obs", "nws_heat_alerts", "nws_heat_forecast"]),
    (f"Is it dangerously hot today at {A}?", "facts", ["heat_obs", "nws_heat_alerts", "nws_heat_forecast"]),
    # The coming days: the Weather Service's forecast and alerts, named as its own.
    (f"Will it be dangerously hot this week at {A}?", "heat_forecast", ["nws_heat_forecast", "nws_heat_alerts"]),
    (f"Is a heat wave coming to {A}?", "heat_forecast", ["nws_heat_forecast", "nws_heat_alerts"]),
    (f"What is the heat forecast for {A}?", "heat_forecast", ["nws_heat_forecast", "nws_heat_alerts"]),
    # The coming decades: the projection.
    (f"How many 90 degree days will there be by the 2050s at {A}?", "facts", ["npcc4_heat", "heat_station"]),
    (f"How will climate change affect the heat at {A}?", "facts", ["npcc4_heat"]),
    # Counts of hot days: the station record.
    (f"How many days hit 90 degrees this year near {A}?", "count", ["heat_station"]),
    (f"How many days above 90 near {A} in 2023?", "count", ["heat_station"]),
    # Hotter than the city: the measurement decides, and only "at the surface".
    (f"Is {A} hotter than the rest of the city?", "surface_yes", ["heat_surface"]),
    (f"Is it cooler here than average at {A}?", "surface_no", ["heat_surface"]),
    (f"How does the heat at {A} compare to the city?", "facts", ["heat_surface"]),
    # A named source.
    (f"What is the heat vulnerability index at {A}?", "facts", ["hvi"]),
    (f"How many emergency room visits for heat illness near {A}?", "count", ["heat_visits"]),
    (f"Where can people cool off near {A}?", "facts", ["cool_features"]),
    (f"Where is the nearest cooling center to {A}?", "cooling_centers", ["cool_features"]),
    # Canopy: the city's map, then the model's estimate, as in a flood answer.
    (f"How much tree canopy shades {A} in the heat?", "facts", ["city_landcover", "landcover"]),
    # From the unseen set: an apartment by number, a calendar date, "the next 30 years", deaths, a pool's hours.
    (f"How hot will apartment 6C at {A} get on Saturday afternoon", "no_prediction_heat",
     ["nws_heat_forecast", "nws_heat_alerts", "heat_surface"]),
    (f"Is it going to keep getting hotter near {A} over the next 30 years", "facts", ["npcc4_heat"]),
    (f"How many heat-related deaths near {A} per year?", "no_deaths", ["heat_visits"]),
    (f"Is the pool near {A} open today and are there spray showers?", "facts", ["cool_features"]),
    (f"How hot does it get near {A} and where are the cooling centers and is there a heat advisory", "facts",
     ["cool_features", "nws_heat_alerts", "heat_surface", "heat_station"]),
    # Anything else about heat: the measurement, the index, the map and the station.
    (f"Tell me about extreme heat at {A}?", "facts", ["heat_surface", "hvi", "city_landcover", "heat_station"]),
])
def test_heat_questions_are_answered_by_rule(question, lead, facts):
    assert ra.answer(question, T, V) == (lead, facts)


def test_a_mixed_surface_record_gets_no_yes_or_no():
    mixed = {**V, "heat_surface": {"mean_diff_f": 0.2, "warmer_in_every_image": False, "cooler_in_every_image": False}}
    assert ra.answer(f"Is {A} hotter than the rest of the city?", T, mixed) == ("facts", ["heat_surface"])


def test_a_source_that_did_not_answer_is_not_quoted():
    texts = {k: v for k, v in T.items() if k not in ("nws_heat_forecast", "nws_heat_alerts")}
    assert ra.answer(f"Will it be dangerously hot this week at {A}?", texts, V) is None
    assert ra.answer(f"What is the heat score for {A}?", {"heat_surface": T["heat_surface"]}, V) is None


def test_the_count_of_hot_days_for_a_named_year_comes_from_the_stations_own_record():
    q = f"How many days above 90 near {A} in 2023?"
    assert ha.count_sentence(q, ["heat_station"], V) == "5 days at or above 90°F at JFK Airport in 2023."
    assert ha.count_sentence(q.replace("2023", "2026"), ["heat_station"], V) == (
        "10 days at or above 90°F at JFK Airport in 2026 through 2026-10-01.")
    assert ha.count_sentence(q.replace("2023", "1950"), ["heat_station"], V) is None  # a year the record does not hold
    assert ha.count_sentence(f"How hot was it near {A} in 2023?", ["heat_station"], V) is None


def test_the_highest_reading_of_a_named_year_comes_from_the_stations_own_record():
    v = {"heat_station": {**V["heat_station"], "max_by_year": {2025: [101, "2025-06-24"]}}}
    q = f"how hot did it get near {A} during the heat wave in late June 2025"
    assert ha.year_sentence(q, ["heat_station"], v) == "The highest reading at JFK Airport in 2025 was 101°F on 2025-06-24."
    assert ha.year_sentence(q.replace("2025", "1950"), ["heat_station"], v) is None
    assert ha.year_sentence(f"How many days above 90 near {A} in 2025?", ["heat_station"], v) is None  # a count, not a peak


def test_the_record_and_a_year_in_any_position_reach_their_leads():
    v = {"heat_station": {**V["heat_station"], "record_f": 104, "record_date": "1966-07-03", "record_since": "1948"}}
    assert ha.record_sentence("What was the hottest day on record in Brooklyn?", ["heat_station"], v) == (
        "The record at JFK Airport is 104°F, set on 1966-07-03 (records from 1948).")
    assert ha.record_sentence("How hot was last summer?", ["heat_station"], v) is None
    # "in summer 2024" names the year without "in 2024" (the unseen set's uh25, once answered with other years).
    assert ha.count_sentence("how many days hit 90 or above in summer 2023", ["heat_station"], v) == (
        "5 days at or above 90°F at JFK Airport in 2023.")
    assert ha.count_sentence("how many 90 degree days by the 2050s", ["heat_station"], v) is None  # a decade is not a year


def test_the_basketball_team_is_not_the_weather():
    plan = heuristic_plan("what time is the Heat game at Barclays Center tonight")
    assert plan["intent"] == "not_implemented" and "hot weather" in plan["rationale"]
    # "Heat score" is a question about a score for heat, not the game's (the first version of this rule caught it).
    assert heuristic_plan("What is the heat score for 2940 Brighton 3rd St, Brooklyn?")["intent"] == "single_address"
    assert heuristic_plan("how bad is the heat at Barclays Center tonight")["focus"]["hazard"] == "heat"


def test_time_frames():
    assert ha.time_frame("How hot is it right now?") == "now" and ha.time_frame("Is it hot today in QN12?") == "now"
    assert ha.time_frame("Will it be hot this week?") == "future" and ha.time_frame("heat by the 2050s") == "future"
    assert ha.time_frame("How hot was last summer in BK05?") == "past" and ha.time_frame("heat in BK05") == "any"


def test_code_set_leads_are_exempt_from_the_word_checks_and_have_phrases():
    from riprap.core.burr import answer_checks as ac
    from riprap.core.burr.synthesis import LEAD_PHRASES

    for lead in ("heat_forecast", "no_prediction_heat", "no_score", "no_ranking", "surface_yes", "surface_no"):
        assert lead in ac.CODE_LEADS and LEAD_PHRASES[lead]
        assert ac.check_lead(lead, ["heat_surface"], "Is it hotter here?", T, V) == []


# ---- the sources' sentences ------------------------------------------------------------------------------

@pytest.fixture
def surface(tmp_path, monkeypatch):
    """A 9 km square of 90 m cells, six images: the west half 8 F above the
    city mean in every image, the east half from 3 below to 2 above."""
    rasterio = pytest.importorskip("rasterio")
    from pyproj import Transformer
    from rasterio.transform import from_origin

    from app.heat import surface_temp as st

    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(-73.8, 40.7)
    a = np.zeros((6, 100, 100), "int16")
    a[:, :, :50] = 80
    for i, d in enumerate((-30, -20, -10, 0, 10, 20)):
        a[i, :, 50:] = d
    a[0, :10] = -32768  # the first image missed the top rows
    with rasterio.open(tmp_path / "surface_temp.tif", "w", driver="GTiff", dtype="int16", count=6, height=100, width=100,
                       crs="EPSG:32618", transform=from_origin(x - 4500, y + 4500, 90, 90), nodata=-32768) as dst:
        dst.write(a)
    images = [{"time_utc": f"2026-07-{d:02d}T15:33:00Z", "city_land_mean_f": 100.0 + d} for d in range(1, 7)]
    (tmp_path / "surface_temp.json").write_text(json.dumps({"images": images, "local_time": "about 11:35 am Eastern Daylight Time"}))
    monkeypatch.setattr(st, "DIR", tmp_path)
    st.meta.cache_clear()
    yield st, Transformer.from_crs(32618, 4326, always_xy=True), (x, y)
    st.meta.cache_clear()


def test_surface_temperature_is_a_difference_from_the_city_with_its_range_and_its_trap(surface):
    st, to_ll, (x, y) = surface
    lon, lat = to_ll.transform(x - 2000, y)  # in the warm west half
    v = st.for_point(lat, lon)
    assert v["mean_diff_f"] == 8.0 and v["min_diff_f"] == 8.0 and v["n_images"] == 6 and v["warmer_in_every_image"]
    assert v["latest_surface_f"] == 114.0 and v["latest_city_mean_f"] == 106.0  # the last image's city mean plus 8
    n = v["narrative"]
    assert "at 8.0°F warmer than the city's land average, over 6 clear summer images from 2026-07-01 to 2026-07-06" in n
    assert "not the air temperature a person feels" in n and "the ground within 150 m of this address" in n
    lon, lat = to_ll.transform(x + 2000, y)  # the east half swings either side of the mean
    v = st.for_point(lat, lon)
    assert v["mean_diff_f"] == -0.5 and not v["warmer_in_every_image"] and not v["cooler_in_every_image"]
    assert "image by image it ran from 3.0°F cooler to 2.0°F warmer" in v["narrative"]


def test_an_image_that_missed_the_place_is_left_out_and_too_few_images_say_nothing(surface, monkeypatch):
    st, to_ll, (x, y) = surface
    lon, lat = to_ll.transform(x - 2000, y + 4200)  # under the rows the first image missed
    assert st.for_point(lat, lon)["n_images"] == 5
    monkeypatch.setattr(st, "MIN_IMAGES", 6)
    assert st.for_point(lat, lon) is None
    assert st.for_point(41.5, -72.0) is None  # outside the raster


def test_the_heat_index_sentence_says_it_is_a_rank_and_gives_no_address_level_reading():
    from app.heat import dohmh

    v = dohmh.hvi_for_point(40.7128, -73.778)  # Hollis, Queens
    assert v["hvi"] in (1, 2, 3, 4, 5) and v["year"] == 2023 and v["area_code"].startswith("QN12")
    n = v["narrative"]
    assert f"at {v['hvi']} out of 5" in n and "ranks neighbourhoods against each other" in n
    assert "not a measurement of heat at an address" in n and "every neighbourhood has residents at risk" in n
    assert "no risk" not in n  # the disclosure check reads that phrase as reassurance
    park = dohmh.hvi_for_point(40.7775, -73.9695)  # Central Park: no index
    assert park["available"] is False and "publishes no Heat Vulnerability Index for Central Park" in park["narrative"]
    d = dohmh.hvi_for_area(NS(extras={"area_code": "QN12"}))
    assert d["hvi"] == 5 and "Queens community district 12 at 5 out of 5, the highest risk group" in d["narrative"]
    assert {n["name"] for n in d["neighbourhoods"]} >= {"Jamaica", "Hollis", "St. Albans"}


def test_heat_visits_state_the_period_and_a_suppressed_count_is_not_a_zero():
    from app.heat import dohmh

    v = dohmh.visits_for_area(NS(extras={"area_code": "QN12"}))
    assert v["n"] == 79 and v["age_adjusted_rate"] == 7.6 and v["citywide_age_adjusted_rate"] == 6.0
    assert "79 emergency department visits for heat illness in May to September of 2018 to 2022" in v["narrative"]
    assert "counted by where the patient lives" in v["narrative"]
    hidden = dohmh.visits_for_area(NS(extras={"area_code": "MN01"}))
    assert hidden["suppressed"] and hidden["n"] is None and "A withheld count is not a zero." in hidden["narrative"]
    assert not re.search(r"\b0 emergency|\bno emergency", hidden["narrative"])
    assert dohmh.visits_for_point(40.7128, -73.778)["district"] == "QN12"  # an address reads its district


def test_the_health_portal_uses_two_borough_codes_and_the_bake_reads_its_lookup():
    # A borough row's id counts the boroughs alphabetically (1 is the Bronx); a district id leads with the city's
    # borough code (1 is Manhattan). Hard-coding one scheme once gave Brooklyn's visits to the Bronx.
    d = json.loads((ROOT / "data" / "heat" / "dohmh_heat.json").read_text())["ed_visits"]
    assert d["borough"]["BK"]["n"] == 749 and d["borough"]["BX"]["n"] == 498 and d["citywide"]["n"] == 2549
    assert sum(b["n"] for b in d["borough"].values()) == d["citywide"]["n"]
    assert len(d["district"]) == 59 and len([k for k in d["district"] if k.startswith("BK")]) == 18


def test_the_heat_projection_quotes_the_published_table():
    # Braneon et al. 2024 (doi:10.1111/nyas.15116), Table 4, as saved from the paper on 2026-10-02.
    from app.heat import npcc4

    text = (ROOT / "tests" / "fixtures" / "npcc4_table4.txt").read_text()
    blocks = dict(zip(("2030s", "2050s", "2080s"), re.split(r"\n\s*20[58]0s\n", text.split("2030s", 1)[1]), strict=True))
    rows = {"days_ge_90": r"Days at or above 90", "days_ge_95": r"Days at or above 95", "heat_waves": r"Number of heat waves"}
    for decade, block in blocks.items():
        flat = re.sub(r"\s*\n\s*◦\s*\n", "\n", block)  # a degree sign the PDF set on its own line
        for key, label in rows.items():
            m = re.search(label + r"\D*?F?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", flat)
            assert m, (decade, key)
            base, *pcts = (int(g) for g in m.groups())
            assert base == npcc4.BASELINE[key], (decade, key)
            assert dict(zip((10, 25, 75, 90), pcts, strict=True)) == npcc4.TABLE[decade][key], (decade, key)
    n = npcc4.get_projections()["narrative"]
    assert "38 to 62 days a year at or above 90°F in New York City by the 2050s" in n and "against 17 a year in 1981-2010" in n
    assert "heat waves from 2 a year to 5 to 8 and then 6 to 9" in n and "17 to 54 by the 2080s" in n
    assert "two emissions scenarios (SSP2-4.5 and SSP5-8.5)" in n and "for the city as a whole, not for a neighbourhood" in n


def test_parks_cooling_counts_playgrounds_and_points_to_the_citys_cooling_center_list(monkeypatch):
    from app.heat import cooling

    data = {"sources": {"spray shower": {"date_modified": "2026-09-03"}, "pool": {"date_modified": "2026-09-15"}},
            "sites": [["spray shower", "A Playground", 40.7000, -73.8000], ["spray shower", "A Playground", 40.7001, -73.8000],
                      ["outdoor pool", "B Pool", 40.7030, -73.8000], ["spray shower", "Far Park", 40.8000, -73.8000]]}
    monkeypatch.setattr(cooling, "_data", lambda: data)
    v = cooling.for_point(40.7, -73.8)
    assert v["n_spray_shower_sites"] == 1 and v["n_outdoor_pools"] == 1  # two spray features in one playground
    n = v["narrative"]
    assert "spray showers at 1 park or playground and 1 outdoor pool within 800 m" in n and "A Playground" in n
    assert "run in summer only" in n and "finder.nyc.gov/coolingcenters" in n and "only during a heat emergency" in n
    assert "nearest first: A Playground (spray shower, " in n and "B Pool (outdoor pool, " in n  # names, usable as a list
    none = cooling.for_point(40.6, -73.9)
    assert none["n_sites"] == 0 and "lists no spray shower or public pool within 800 m" in none["narrative"]


def _resp(body):
    return NS(raise_for_status=lambda: None, json=lambda: body)


def test_the_station_record_names_the_station_its_distance_and_the_normal(monkeypatch):
    from app.heat import weather

    rows = [[str(y), ["17", 0], ["95", f"{y}-07-01"]] for y in range(1991, 2025)]
    rows += [["2025", ["14", 0], ["99", "2025-06-24"]], ["2026", ["12", 91], ["100", "2026-07-02"]]]
    seen = {}

    def post(url, **kw):
        seen.update(kw["json"])
        return _resp({"meta": {"valid_daterange": [["1869-01-01", "2026-10-01"]]}, "data": rows})

    monkeypatch.setattr(weather.http, "post", post)
    v = weather.station_record(40.78, -73.97, today=date(2026, 10, 2))
    assert seen["sid"] == "NYCthr" and v["station"] == "Central Park" and v["days_ge_90"] == 12
    assert v["days_ge_90_last_year"] == 14 and v["normal_days_ge_90"] == 17 and v["by_year"][2025] == 14
    n = v["narrative"]
    assert "reached 90°F on 12 days in 2026 through 2026-10-01 and on 14 in 2025; a full year averaged 17 in 1991 to 2020" in n
    assert "100°F on 2026-07-02" in n and "the station's readings, not this address's" in n
    assert weather.station_record(40.64, -73.78, today=date(2026, 10, 2))["station"] == "JFK Airport"


def test_the_forecast_is_quoted_as_the_weather_services_with_its_thresholds(monkeypatch):
    from app.heat import weather

    grid = {"gridId": "OKX", "gridX": 34, "gridY": 45, "forecast": "F", "forecastGridData": "G"}
    periods = [{"name": "Today", "isDaytime": True, "temperature": 97, "temperatureUnit": "F", "startTime": "2026-07-02T06:00:00-04:00"},
               {"name": "Tonight", "isDaytime": False, "temperature": 80, "temperatureUnit": "F", "startTime": "2026-07-02T18:00:00-04:00"},
               {"name": "Friday", "isDaytime": True, "temperature": 91, "temperatureUnit": "F", "startTime": "2026-07-03T06:00:00-04:00"}]
    apparent = [{"validTime": "2099-07-02T19:00:00+00:00/PT1H", "value": 40.0}, {"validTime": "2099-07-03T19:00:00+00:00/PT1H", "value": 35.0}]
    bodies = {"F": {"properties": {"updateTime": "2026-07-02T08:00:00+00:00", "periods": periods}},
              "G": {"properties": {"apparentTemperature": {"values": apparent}}}}
    monkeypatch.setattr(weather.http, "get", lambda url, **kw: _resp(bodies.get(url) or {"properties": grid}))
    v = weather.forecast(40.78, -73.97)
    assert v["max_high_f"] == 97 and v["max_high_date"] == "2026-07-02" and v["max_apparent_f"] == 104
    n = v["narrative"]
    assert "the National Weather Service expects daytime highs of 97°F today, 91°F Friday" in n and "80°F" not in n
    assert "issued 2026-07-02 04:00 Eastern" in n and "is 104°F on" in n
    assert "Heat Advisory when it expects the heat index to reach 95°F for two days in a row or 100°F at any time" in n
    assert "not a prediction for a building" in n


def test_heat_alerts_read_heat_events_only(monkeypatch):
    from app.context import nws_alerts

    feats = [{"properties": {"event": e, "severity": "Moderate"}} for e in ("Heat Advisory", "Coastal Flood Advisory", "Extreme Heat Warning")]
    monkeypatch.setattr(nws_alerts.http, "get", lambda *a, **k: _resp({"features": feats}))
    heat = nws_alerts.summary_for_point(40.7, -74.0, kind="heat")
    assert [a["event"] for a in heat["alerts"]] == ["Heat Advisory", "Extreme Heat Warning"]
    flood = nws_alerts.summary_for_point(40.7, -74.0)
    assert [a["event"] for a in flood["alerts"]] == ["Coastal Flood Advisory"]
    monkeypatch.setattr(nws_alerts.http, "get", lambda *a, **k: _resp({"features": []}))
    assert nws_alerts.summary_for_point(40.7, -74.0, kind="heat")["narrative"].startswith(
        "No active NWS heat advisory, watch or warning at this point, checked ")


# ---- the briefing ----------------------------------------------------------------------------------------

def test_a_heat_briefing_reads_like_a_flood_one_and_passes_the_disclosure_checks(monkeypatch):
    """End to end without a server: the district briefing from the baked
    records, with the live sources switched off."""
    from app.heat import weather
    from riprap.core.burr.app import run

    for name in ("station_record", "forecast", "alerts", "observation"):
        monkeypatch.setattr(weather, f"{name}_area", lambda polygon: None)
    out = run("heat QN12", no_llm=True)
    p = out["paragraph"]
    assert out["intent"] == "neighborhood" and out["plan"]["focus"]["hazard"] == "heat"
    assert "**In brief.**" in p and "[heat_surface_nta]" in p and "[hvi_nta]" in p and "[city_landcover_nta]" in p
    assert "surface temperature, not air temperature" in p and "a rank among neighbourhoods and not a measurement" in p
    assert "Sandy" not in p and "FEMA" not in p and "311 flood" not in p  # no flood source in a heat briefing
    assert "Experimental" not in p  # the land-cover model stays quiet unless asked
    assert not out["compliance"]["failed"], out["compliance"]["failed"]
    cites = out["citations"]
    assert cites["heat_surface_nta"]["vintage"] and cites["hvi_nta"]["vintage"] == "2023-10-21"


def test_quiet_rules_for_live_heat_readings():
    from riprap.core.burr.templated_reconciler import _QUIET_UNLESS_HEAT as Q

    assert not Q["heat_obs"]({"temp_f": 72}) and Q["heat_obs"]({"temp_f": 91})
    assert not Q["nws_heat_forecast"]({"max_high_f": 82, "max_apparent_f": 85})
    assert Q["nws_heat_forecast"]({"max_high_f": 93}) and Q["nws_heat_forecast"]({"max_high_f": 88, "max_apparent_f": 97})
    assert "city_landcover" not in Q  # canopy is a ground condition of heat: quoted in a plain heat briefing


def test_station_coordinates_are_the_weather_services_own():
    # An independent key found the JFK distance 1.2 km out: the table held the airport's reference point, not
    # the instruments'. Both station tables are pinned to api.weather.gov/stations/{id}, saved 2026-10-02.
    from app.context import nws_obs
    from app.heat import weather

    official = json.loads((ROOT / "tests" / "fixtures" / "nws_station_coordinates.json").read_text())
    for sid, _, lat, lon in nws_obs.STATIONS:
        assert [lat, lon] == official[sid][:2], sid
    for acis, icao in (("NYCthr", "KNYC"), ("LGAthr", "KLGA"), ("JFKthr", "KJFK")):
        row = next(s for s in weather.STATIONS if s[0] == acis)
        assert list(row[2:]) == official[icao][:2], acis


def test_the_second_unseen_set():
    """Inputs from tests/golden/unseen_heat2.json that the first run got wrong."""
    # An acronym is not a place: "ER" once matched Gramercy by substring, for a question about the city.
    assert heuristic_plan("which parts of the city have the most heat related ER visits")["targets"][0]["text"] == "NYC"
    # "Oval" is a street word: Stuyvesant Oval once went to Bedford-Stuyvesant.
    plan = heuristic_plan("will my apartment at 14 Stuyvesant Oval go over 90 inside next August? top floor, faces west")
    assert plan["place"]["kind"] == "address" and plan["targets"][0]["text"].startswith("14 Stuyvesant Oval")
    # The coming decades are the projection, even when the asker mentions a house.
    q = "My kids will inherit our house in Port Richmond. How many more heat waves is the city expecting there in the coming decades?"
    assert ha.answer(q, T)[0] == "facts" and ha.answer(q, T)[1][0] == "npcc4_heat"
    assert ha.answer(f"Will my apartment at {A} overheat on July 4 2035?", T)[0].startswith("no_prediction")
    # A rating by any wording is a score.
    q = "rate jackson heights heat risk on a scale of 1 to 10"
    assert ha.asks_something(q) and ha.answer(q, T) == ("no_score", ["hvi"])
    assert ha.answer("What is the rate of heat ER visits here?", T)[0] != "no_score"
    # Basketball and fashion are not the weather; hot spots can be.
    for q in ("heat knicks friday at the garden, who you got", "hottest new restaurants in williamsburg right now"):
        assert heuristic_plan(q)["intent"] == "not_implemented", q
    assert heuristic_plan("where are the heat hot spots in Hunts Point")["focus"]["hazard"] == "heat"
    # A scorcher is a hot day.
    assert ha.hazard_of("Ive lived in Parkchester since 1984 and I swear there are more scorchers now. Do the records back that up?") == "heat"
    assert ha.answer("I swear there are more scorchers now than in 1984. Do the records back that up?", T)[1][0] == "heat_station"
    # Who is at risk: the department's index first.
    assert ha.answer("who is most at risk from heat in brownsville", T)[1][0] == "hvi"


def test_a_flood_answer_to_a_question_that_also_names_heat_says_so():
    from riprap.core.burr.synthesis import BOTH_HAZARDS, _render

    both = _render([], [], [], question="Which is the bigger problem at 80 Pioneer Street, flooding or heat?")
    assert BOTH_HAZARDS in both
    assert BOTH_HAZARDS not in _render([], [], [], question="Has 80 Pioneer Street flooded?")
    assert BOTH_HAZARDS not in _render([], [], [], question="Did Sandy hit 89-11 Merrick Boulevard, Queens?")
    assert BOTH_HAZARDS not in _render([], [], [], question="Is 80 Pioneer Street hotter than the city?")


def test_what_a_fresh_reviewer_broke():
    """Each input here gave a wrong or misleading answer before it was fixed."""
    hot = {"heat_surface": {"mean_diff_f": 5.7, "warmer_in_every_image": True, "cooler_in_every_image": False}}
    # Polarity: "hot compared to the city" and "higher than the city average" ask "hotter", and were answered "no".
    for q in ("Is Hunts Point hot compared to the rest of the city?", "Is the surface temperature here higher than the city average?"):
        assert ha.answer(q, T, hot)[0] == "surface_yes", q
    assert ha.answer("Is Hunts Point cooler than the rest of the city?", T, hot)[0] == "surface_no"
    # Only the city is the baseline: another borough, another time and no direction at all get no yes or no.
    for q in ("Is Bayside hotter than the rest of Queens?", "Is it hotter than usual in Hunts Point this summer?",
              "Is Mott Haven hotter than Riverdale?", "Is it hotter or cooler than the city here?"):
        assert ha.answer(q, T, hot)[0] == "facts", q
    # A house number is not a temperature or a year.
    for q in ("Did Sandy hit 89-11 Merrick Boulevard, Queens?", "Is Red Hook a hot spot for sewer backups?",
              "Does the street outside 80 Pioneer Street, Brooklyn take on water most summers?",
              "What is the record high tide at the Battery?"):
        assert ha.hazard_of(q) == "flood", q
    assert ha.hazard_of("Where can kids cool off near Mariners Harbor Houses?") == "heat"
    assert ha.count_sentence("How many days hit 90 last year near 2020 Grand Concourse, Bronx?", ["heat_station"], V) == (
        "15 days at or above 90°F at JFK Airport in 2025.")  # last year, not the house number's year
    assert ha.count_sentence("How many days hit 90 this year near here?", ["heat_station"], V) == (
        "10 days at or above 90°F at JFK Airport in 2026 through 2026-10-01.")
    assert ha.year_sentence("How hot did it get at 2025 Broadway, Manhattan?", ["heat_station"], {"heat_station": {
        "station": "Central Park", "max_by_year": {2025: [99, "2025-06-24"]}}}) is None
    assert ha.time_frame("How hot does it get at 2050 Bartow Avenue, Bronx?") != "future"
    # The count is of days at 90°F: another threshold, a span of years or a calendar day is not answered by it.
    assert ha.count_sentence("How many days above 95 in 2025 in QN12?", ["heat_station"], V) is None
    assert ha.count_sentence("How many days above 90 since 2023 in QN12?", ["heat_station"], V) is None
    assert ha.count_sentence("How many days above 90 in 2025 in QN12?", ["heat_station"], V) == "15 days at or above 90°F at JFK Airport in 2025."
    peaks = {"heat_station": {"station": "JFK Airport", "max_by_year": {2025: [102, "2025-06-25"]}, "record_f": 104,
                              "record_date": "1966-07-03", "record_since": "1948"}}
    assert ha.year_sentence("How hot was it on July 15, 2025 in QN12?", ["heat_station"], peaks) is None
    assert ha.record_sentence("What is the record low temperature in QN12?", ["heat_station"], peaks) is None
    assert ha.record_sentence("What is the record high in QN12?", ["heat_station"], peaks)
    # The heat index is the weather's, not the Health Department's index.
    assert ha.answer("Is the heat index above 100 in QN12?", T)[1][0] == "heat_obs"
    # Past advisories are in no source, and an alert source that did not answer is not "no advisory".
    assert ha.answer("How many heat advisories were issued in 2025 for QN12?", T)[0] == "cannot_answer"
    assert ha.answer("Is there a heat advisory right now?", {k: v for k, v in T.items() if k != "nws_heat_alerts"})[0] == "cannot_answer"
    assert ha.answer("Is there a heat advisory right now?", T)[0] == "facts"
    # Advice, asked without "should I".
    for q in ("Is it too hot for my kids to play outside in Hunts Point today?", "What precautions should residents of QN12 take in a heat wave?",
              "Would you recommend moving to Hunts Point given the heat?", "Do I need an air conditioner at 80 Pioneer Street, Brooklyn?"):
        assert heuristic_plan(q)["intent"] == "out_of_scope", q
    assert heuristic_plan("Will the playground at Tompkins Square Park be too hot to use on the afternoon of July 15?")["intent"] != "out_of_scope"
    # A named day by ordinal or by holiday is still a named day.
    for q in (f"Will it reach 100 on July 4th at {A}?", f"Will it be hot on Labor Day at {A}?"):
        assert ha.answer(q, T)[0].startswith("no_prediction"), q
    # A landmark with a borough in its name is the landmark, not the borough.
    for q, name in (("Is the Staten Island Mall a heat island?", "Staten Island Mall"), ("How hot is the Bronx Zoo?", "Bronx Zoo")):
        plan = heuristic_plan(q)
        assert plan["intent"] == "single_address" and plan["targets"][0]["text"].startswith(name), plan
    assert heuristic_plan("heat on the Staten Island North Shore")["targets"][0]["text"] == "SI01"


def test_the_station_record_stands_on_new_years_day(monkeypatch):
    from datetime import date
    from types import SimpleNamespace

    from app.heat import weather

    rows = [[str(y), ["M" if y == 2027 else 10 + y % 7, 0], ["M" if y == 2027 else 95, f"{y}-07-10"]] for y in range(1991, 2028)]
    monkeypatch.setattr(weather.http, "post", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"data": rows, "meta": {"valid_daterange": [["1869-01-01", "2026-12-31"]]},
                                                      "smry": [[106, "1936-07-09"]]}))
    v = weather.station_record(40.78, -73.97, today=date(2027, 1, 1))
    assert v["year"] == 2026 and "in 2026 through 2026-12-31" in v["narrative"]


def test_the_surface_reading_is_of_land():
    from app.heat import surface_temp as st

    # 89 South Street, Manhattan, on the East River: the river once pulled this to -9.3.
    v = st.for_point(40.7056, -74.0018)
    assert v and -5 < v["mean_diff_f"] < -2


def test_what_a_blind_judge_found_in_the_second_round(monkeypatch):
    from datetime import date

    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import _render

    # A named day months away is refused with what was measured, not with this week's forecast.
    q = f"Will the playground near {A} be too hot to use on the afternoon of July 15?"
    assert ha._beyond_forecast(q, today=date(2026, 10, 2)) and not ha._beyond_forecast(q, today=date(2026, 7, 10))
    assert ha._beyond_forecast("will my apartment go over 90 inside next summer", today=date(2026, 7, 10))
    assert not ha._beyond_forecast("will my apartment overheat this weekend", today=date(2026, 10, 2))
    assert not ha._beyond_forecast("it may get hot in my apartment tomorrow", today=date(2026, 10, 2))
    monkeypatch.setattr(ha, "_beyond_forecast", lambda q, today=None: True)
    assert ha.answer(q, T) == ("no_prediction_far", ["heat_surface", "heat_station"])
    assert "7 days ahead" in syn.LEAD_PHRASES["no_prediction_far"]
    # A question that names two neighbourhoods is answered for one, and says so; a comparison and an address do not.
    assert ha.places_named("who is most at risk from heat in Corona and Elmhurst. seniors living alone?") == ["Corona", "Elmhurst"]
    assert ha.places_named("which parts of Washington Heights and Inwood run hottest") == ["Washington Heights", "Inwood"]
    assert ha.places_named("Is Mott Haven hotter than Riverdale?") == []
    assert ha.places_named("How hot is it in Red Hook and Carroll Gardens?") == []  # one tabulation area
    assert ha.places_named(f"heat at {A} in Hollis near Jamaica") == []
    assert "names more than one place (Corona and Elmhurst)" in _render([], [], [], question="who is most at risk from heat in Corona and Elmhurst?")
    # A heat answer's footer is about heat.
    out = _render([], [], [], question="How hot is Hunts Point?")
    assert "temperature inside a building" in out and "zoning" not in out
    assert "zoning" in _render([], [], [], question="Has Hunts Point flooded?")
    # Words beside a borough that ask nothing name something in it; a question about the borough does not.
    plan = heuristic_plan("heat briefing for around curtis high school staten island")
    assert plan["intent"] == "single_address" and plan["targets"][0]["text"] == "curtis high school, Staten Island, NY"
    for q in ("heat in the bronx", "queens heat", "bronx heat vulnerability", "extreme heat risk staten island north shore",
              "Which parts of the Bronx should worry most about heat?"):
        assert heuristic_plan(q)["intent"] == "neighborhood", q


def test_a_capped_list_of_cooling_places_says_it_is_capped():
    from app.heat import cooling

    d = {"sources": {"spray shower": {"date_modified": "2026-09-03"}, "pool": {"date_modified": "2026-09-15"}}}
    many = cooling._summary([("spray shower", f"Park {i}", 100.0 + i) for i in range(8)], "within 800 m of this address", d)
    few = cooling._summary([("spray shower", f"Park {i}", 100.0 + i) for i in range(3)], "within 800 m of this address", d)
    assert "at 8 parks or playgrounds" in many["narrative"] and "the six nearest: Park 0" in many["narrative"]
    assert "nearest first: Park 0" in few["narrative"]


def test_what_three_personas_found():
    """A council staffer, a reporter and a public health researcher used the running app; each input here went wrong."""
    from riprap.core.burr.intake import _heat_compare

    # A ZIP after the word heat was geocoded whole and came back as a heat-treating works in Brooklyn.
    for q in ("heat 10474", "10474 heat"):
        plan = heuristic_plan(q)
        assert plan["intent"] == "not_implemented" and "ZIP code" in plan["rationale"], q
    # A part of a borough got the whole borough's figures under its own name.
    for q in ("south bronx heat", "isn't the South Bronx the hottest part of the city?"):
        plan = heuristic_plan(q)
        assert plan["intent"] == "not_implemented" and "no official boundary" in plan["rationale"], q
    for q in ("north shore staten island heat", "heat Staten Island North Shore"):
        assert heuristic_plan(q)["targets"] == [{"type": "district", "text": "SI01"}], q
    assert heuristic_plan("heat in the Bronx")["targets"][0]["text"] == "BX"
    # A comparison in other words was answered for the first place only.
    assert [t["text"] for t in _heat_compare("compare Hunts Point and Riverdale heat")] == ["Hunts Point", "Riverdale"]
    assert [t["text"] for t in _heat_compare("how does heat in BX02 compare with MN08")] == ["BX02", "MN08"]
    assert [t["text"] for t in _heat_compare("Why is Port Richmond rated more heat vulnerable than Todt Hill?")] == ["Port Richmond", "Todt Hill"]
    assert _heat_compare("how does Hunts Point compare with the city") is None
    # Questions no source answers were given the nearest figure with no word that it was not the answer.
    visits = {"heat_visits": {"period": "2018 to 2022", "n": 21}}
    for q in ("How many heat stress hospitalizations were there here in 2023?", "How many heat emergency visits here in 2024?",
              "Is the heat illness visit rate here significantly higher than the city's?", "How many days above 95 degrees were there in 2025 near here?"):
        assert ha.answer(q, T, visits)[0] == "cannot_answer", q
    assert ha.answer("how many heat emergency visits here", T, visits) == ("count", ["heat_visits"])
    assert ha.answer("How many people died from heat here?", T)[0] == "no_deaths"
    # A ranking asked of the city, where no index row exists, is still told that Riprap ranks nothing.
    no_index = {k: v for k, v in T.items() if k != "hvi"}
    assert ha.answer("Which community district is the hottest in the city? Rank them by heat vulnerability.", no_index)[0] == "no_ranking"
    # Cooling centers are answered about first; the parks list follows.
    assert ha.answer("how many cooling centers are near here", T)[0] == "cooling_centers"
    # A trend question gets the station's decades, not this year and last.
    by_year = {y: 10 + (y - 1991) // 10 for y in range(1991, 2027)}
    trend = ha.trend_sentence("Has the number of 90 degree days gone up over the years?", ["heat_station"],
                              {"heat_station": {"station": "JFK Airport", "year": 2026, "by_year": by_year}})
    assert trend == ("At JFK Airport the yearly count of days at or above 90°F averaged 10.0 in 1991 to 2000, 11.0 in 2001 to "
                     "2010, 12.0 in 2011 to 2020 and 13.0 in 2021 to 2025 [heat_station].")
    # A trend in visits is not a trend in hot days: the visits file is one five-year total.
    q = "heat-related emergency department visits here 2019 to 2024 trend"
    assert ha.answer(q, T, visits)[0] == "cannot_answer"
    assert ha.trend_sentence(q, ["heat_visits", "heat_station"], {"heat_station": {"station": "JFK Airport", "year": 2026, "by_year": by_year}}) is None
    assert ha.trend_sentence("How many days hit 90 this year?", ["heat_station"], {"heat_station": {"station": "x", "by_year": by_year}}) is None
    # "How hot does East Harlem get" is about the place's surface as well as the station.
    assert "heat_surface" in ha.answer("how hot does East Harlem get", T)[1]


def test_the_named_half_of_a_neighbourhood_is_the_one_briefed():
    from burr.core import State

    from riprap.core.burr.intake import resolve_area

    for q, name in (("heat in East Harlem (South)", "East Harlem (South)"), ("heat East Harlem south", "East Harlem (South)"),
                    ("heat in East Harlem", "East Harlem (North)")):
        out = resolve_area(State({"first_target": "East Harlem", "query": q, "trace": []}))
        assert out["nta"]["nta_name"] == name, q


def test_what_a_blind_verifier_found_after_the_personas():
    """77 fresh queries in the same ten areas; each input here still went wrong."""
    from riprap.core.burr.intake import _heat_compare
    from riprap.core.burr.place import geocode_matches

    # A geocoder result with another house number is not the address asked for ("1/2" holds a 1).
    assert not geocode_matches("1 Bay Street, Staten Island", "400 1/2, Bay Street, Staten Island, Richmond County, New York, 10301")
    assert geocode_matches("1 Bay Street, Staten Island", "1 BAY STREET, Staten Island, NY, USA")
    assert geocode_matches("233 S Wacker Drive, Chicago", "Willis Tower, 233, South Wacker Drive, Chicago")
    # A part of a borough inside a question, and a ZIP inside a question.
    for q in ("whats the heat vulnerability index for the south bronx", "is eastern queens hot in summer"):
        plan = heuristic_plan(q)
        assert plan["intent"] == "not_implemented" and "no official boundary" in plan["rationale"], q
    assert heuristic_plan("heat on staten island's north shore")["targets"][0]["text"] == "SI01"
    for q in ("heat in zip 10035", "is 11212 hot"):
        assert "ZIP code" in heuristic_plan(q)["rationale"], q
    assert heuristic_plan("How hot did it get in 2025 near JFK Airport?")["intent"] == "single_address"  # a year is not a ZIP
    # Two places set side by side in other words; three places are not a pair.
    for q, pair in (("which is hotter, mott haven or riverdale", ["Mott Haven", "Riverdale"]),
                    ("hunts point compared to park slope for heat", ["Hunts Point", "Park Slope"]),
                    ("difference in heat between QN12 and jamaica", ["QN12", "Jamaica"]),
                    ("brownsville or the upper east side, where is heat worse", ["Brownsville", "Upper East Side"])):
        assert [t["text"] for t in _heat_compare(q)] == pair, q
    q = "compare heat in brownsville, jackson heights and tottenville"
    assert _heat_compare(q) is None and ha.places_named(q) == ["Brownsville", "Jackson Heights", "Tottenville"]
    # A ranking of a borough is the borough with the no-ranking lead, not a landmark for the geocoder.
    assert heuristic_plan("top 5 worst neighborhoods for heat in brooklyn")["targets"][0]["text"] == "BK"
    # A nickname is the neighbourhood, not a point called an address.
    assert heuristic_plan("bed stuy heat")["intent"] == "neighborhood"
    # Sprinklers and pools are asked about for heat.
    assert ha.hazard_of("pools and sprinklers near 108-25 62nd dr forest hills") == "heat"
    assert ha.hazard_of("water pools in the street outside 80 Pioneer Street when it rains") == "flood"
    # Night and indoor readings exist in no source here; a worsening trend is the station's decades.
    assert ha.answer("how hot does it get at night in corona queens", T)[0] == "cannot_answer"
    assert ha.answer("has heat gotten worse here since 2000", T)[1][0] == "heat_station"
    # The city as a whole has no reading against itself.
    from app.areas import nta
    from app.heat import surface_temp as st

    v = st.for_polygon(nta.by_borough("NYC")["geometry"])
    assert v and "mean_diff_f" not in v and "no reading of its own" in v["narrative"]
