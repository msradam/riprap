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


def test_bare_places_and_questions():
    from app.planner import is_bare_place

    for q in ("heat QN12", "extreme heat at 350 5th Ave, Manhattan", "heat risk 80 Pioneer Street, Brooklyn"):
        assert is_bare_place(q, heuristic_plan(q)["targets"]), q
    for q in ("QN12 heat vulnerability index", "heat forecast this week 350 5th Ave, Manhattan", "cooling centers BK05"):
        assert not is_bare_place(q, heuristic_plan(q)["targets"]), q


def test_intents_follow_the_place_and_the_time():
    assert heuristic_plan("heat QN12")["intent"] == "neighborhood"
    assert heuristic_plan("extreme heat at 350 5th Ave, Manhattan")["intent"] == "single_address"
    now = heuristic_plan("How hot is it right now in Hunts Point?")
    assert now["intent"] == "live_now" and now["focus"]["time_frame"] == "now"
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
    live = set(select_pebbles(heuristic_plan("How hot is it right now at 350 5th Ave, Manhattan?"), NYC))
    assert live == {"heat_obs", "heat_station", "nws_heat_forecast", "nws_heat_alerts"}


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
    (f"Where is the nearest cooling center to {A}?", "facts", ["cool_features"]),
    # Canopy: the city's map, then the model's estimate, as in a flood answer.
    (f"How much tree canopy shades {A} in the heat?", "count", ["city_landcover", "landcover"]),
    # From the unseen set: an apartment by number, a calendar date, "the next 30 years", deaths, a pool's hours.
    (f"How hot will apartment 6C at {A} get on Saturday afternoon", "no_prediction_heat",
     ["nws_heat_forecast", "nws_heat_alerts", "heat_surface"]),
    (f"Will the playground near {A} be too hot to use on the afternoon of July 15?", "no_prediction_heat",
     ["nws_heat_forecast", "nws_heat_alerts", "heat_surface"]),
    (f"Is it going to keep getting hotter near {A} over the next 30 years", "facts", ["npcc4_heat"]),
    (f"How many heat-related deaths near {A} per year?", "cannot_answer", ["heat_visits"]),
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


def test_time_frames():
    assert ha.time_frame("How hot is it right now?") == "now" and ha.time_frame("Is it hot today in QN12?") == "now"
    assert ha.time_frame("Will it be hot this week?") == "future" and ha.time_frame("heat by the 2050s") == "future"
    assert ha.time_frame("How hot was last summer in BK05?") == "past" and ha.time_frame("heat in BK05") == "any"


def test_code_set_leads_are_exempt_from_the_word_checks_and_have_phrases():
    from riprap.core.burr import answer_checks as ac
    from riprap.core.burr.synthesis import LEAD_PHRASES

    for lead in ("heat_forecast", "no_prediction_heat", "no_score", "surface_yes", "surface_no"):
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
    assert "for the city as a whole, not for a neighbourhood" in n


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
    assert "reached 90°F on 12 days in 2026 through 2026-10-01 and on 14 in 2025; the 1991 to 2020 average is 17 a year" in n
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
