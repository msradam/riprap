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


# The fix pass of 5 October 2026 (riprap_sanity_check_report.md, rows 6, 7, 8, 19, 29).

def _synthesize(monkeypatch, docs, question, values=None, **state):
    from types import SimpleNamespace

    from riprap.core.burr import synthesis as syn

    items = [SimpleNamespace(doc_id=d.doc_id, pebble_id=d.doc_id) for d in docs]
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    return syn.synthesize({"intent": "single_address", **(values or {}), **state, "plan": {"question": question}},
                          use_llm=False)


def test_two_named_areas_are_set_side_by_side_and_neither_is_dropped():
    from riprap.core.burr import app
    from riprap.core.burr import heat_answer as ha
    from riprap.core.burr.synthesis import _render

    for q in ("Which is more flood prone, Red Hook or Hollis?", "Is Red Hook more flood prone than Hollis?",
              "Which floods more, Red Hook or Hollis?"):
        plan = heuristic_plan(q)
        assert plan["intent"] == "compare", q
        assert [(t["type"], t["text"]) for t in plan["targets"]] == [("nta", "Red Hook"), ("nta", "Hollis")], q
    # Two scenarios at one place are still one place.
    assert heuristic_plan("gowanus stormwater flooding 2050 vs 2080 scenario, whats the difference")["intent"] == "neighborhood"
    ran = []

    def runner(query, sub):
        ran.append((query, sub["intent"], sub.get("question")))
        return {"paragraph": f"The record for {query}.", "lat": 40.7, "deployment": "nyc", "grounding": {"tier": "no_llm"}}

    out = app.run_compare("Which is more flood prone, Red Hook or Hollis?", plan | {"targets": plan["targets"]}, runner)
    # Each is read as an area, with no question passed down, so the question's own words are not adopted.
    assert ran == [("Red Hook", "neighborhood", None), ("Hollis", "neighborhood", None)]
    p = out["paragraph"]
    assert p.startswith("**Comparison.**\nRiprap computes no score and does not rank places against each other.")
    assert p.index("## PLACE A: Red Hook") < p.index("---") < p.index("## PLACE B: Hollis")
    assert "flood prone" not in p and "The record for Hollis." in p
    # A place outside every city Riprap covers is named as such.
    gone = app.run_compare("q", plan, lambda q, s: {"paragraph": "x", "lat": 33.4, "deployment": None})
    assert "Hollis is outside the cities Riprap covers" in gone["paragraph"]
    # A second place Riprap cannot match is named, and so is the place the answer is for.
    assert ha.not_placed("Is East Harlem hotter than Phoenix?") == ["Phoenix"]
    assert ha.not_placed("Is East Harlem hotter than usual?") == [] and ha.not_placed("Is Mott Haven hotter than Riverdale?") == []
    note = _render([], [], [], question="Is East Harlem hotter than Phoenix?", place="East Harlem (North), Manhattan")
    assert "also names Phoenix, which Riprap could not match" in note and "for East Harlem (North), Manhattan alone" in note
    # Three places are not a pair: the answer says which were named and which one it is for.
    q = "Which floods more, Red Hook, Hollis or Coney Island?"
    assert heuristic_plan(q)["intent"] == "neighborhood"
    three = _render([], [], [], question=q, place="Red Hook, Brooklyn")
    assert "more than one place (Red Hook, Hollis and Coney Island)" in three and "this answer is for Red Hook, Brooklyn" in three


def test_two_places_the_rules_found_are_not_handed_to_the_model_planner(monkeypatch):
    from riprap.core.burr import app

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr("app.planner.plan", lambda q, ledger=None: (_ for _ in ()).throw(AssertionError("asked")))
    plan = app.plan_for("Which is more flood prone, Red Hook or Hollis?")
    assert plan["intent"] == "compare" and len(plan["targets"]) == 2


FEMA = {"fema_nfhl": "This address sits in FEMA flood zone AE, per NFHL FIRM panel 3604970192F, effective 2007.",
        "fema_pfirm": "FEMA's preliminary flood map (PFIRM issued 2015-01-30) places this address in zone AE."}


def test_an_insurance_or_advice_question_is_declined_first_then_given_the_fema_zone(monkeypatch):
    from riprap.core.burr.synthesis import ADVICE_POINTER, NO_ADVICE, Doc

    q = "How much is flood insurance for 80 Pioneer Street?"
    texts = {**T, **FEMA}
    assert heuristic_plan(q)["intent"] == "single_address" and ra.recognised(q)
    # The effective map first, chosen by source and not by its wording; no sensors, no complaints.
    assert ra.answer(q, dict(reversed(texts.items())), {}) == ("no_advice", ["fema_nfhl", "fema_pfirm"])
    for advice in ("Should I buy the house at 2017 East 17th Street?", "Is 80 Pioneer Street safe from flooding?",
                   "Is it safe to rent a basement apartment at 153-10 Peck Avenue, Queens?",
                   "What will flooding do to property values near 80 Pioneer Street?"):
        assert ra.answer(advice, texts, {})[0] == "no_advice", advice
    # A map by name, a preamble, and an asset's register are not advice.
    assert ra.answer("What does the flood insurance rate map show for 80 Pioneer Street?", texts, {})[0] == "facts"
    assert ra.answer("I am buying a house at 80 Pioneer Street. Has it flooded since Ida?", texts,
                     {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 14}})[0] == "yes"
    assert not ra.asks_advice("Is the school near 80 Pioneer Street safe from flooding?")
    docs = [Doc("floodnet", "Live Observer", T["floodnet"], False), Doc("fema_pfirm", "Hazard Reader", FEMA["fema_pfirm"], False),
            Doc("fema_nfhl", "Hazard Reader", FEMA["fema_nfhl"], False)]
    out = _synthesize(monkeypatch, docs, q)
    answer, footer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[:2]
    assert answer.startswith(NO_ADVICE) and "does not price flood insurance" in NO_ADVICE
    assert answer.index("effective 2007") < answer.index("preliminary flood map") and "FloodNet" not in answer
    assert footer.startswith(f"**Out of scope.** {ADVICE_POINTER}") and "https://www.floodhelpny.org" in ADVICE_POINTER
    assert out["grounding"]["answer_lead"] == "no_advice" and out["grounding"]["answer_mode"] == "rules"
    # With no FEMA reading the statement stands alone: it does not announce a zone and show none.
    bare = _synthesize(monkeypatch, docs[:1], q)["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert bare == NO_ADVICE


def test_the_line_here_is_what_they_show_is_never_followed_by_nothing(monkeypatch):
    from riprap.core.burr.synthesis import CANNOT_ANSWER, LEAD_PHRASES, NOTHING_TO_SHOW, Doc

    q = "How deep did the water get on 183rd Street in Hollis during Ida?"
    area = {"nyc311_nta": "40 NYC 311 flood-related complaints filed inside this area in the last 3 years.",
            "sandy_nta": "0.0% of this area lies inside the 2012 Hurricane Sandy inundation extent."}
    # No house number: read for the neighbourhood, where the marks are not read. Say so and what to type.
    assert ra.answer(q, area, {}) == ("needs_address", [])
    assert ra.answer(q.replace("on 183rd", "at 90-01 183rd"), {"ida_hwm": "USGS surveyed 2 marks."}, {})[1] == ["ida_hwm"]
    docs = [Doc(k, "Live Observer", v, False) for k, v in area.items()]
    out = _synthesize(monkeypatch, docs, q, intent="neighborhood")
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer == LEAD_PHRASES["needs_address"] and "Type the address with its house number" in answer
    assert "Here is what they show" not in out["paragraph"] and "word for word" not in out["paragraph"]
    assert out["grounding"]["answered"] is False
    # A named source that returned nothing at an address: the line says nothing is shown.
    silent = _synthesize(monkeypatch, [Doc("nyc311", "Live Observer", T["nyc311"], False)],
                         "What is the FEMA flood zone at 80 Pioneer Street?")["paragraph"]
    assert NOTHING_TO_SHOW in silent and CANNOT_ANSWER not in silent


def test_a_change_question_about_paving_is_told_first_that_the_two_figures_are_not_a_change(monkeypatch):
    from app import experimental
    from riprap.core.burr.synthesis import Doc

    q = "Has QN12 become more paved since 2018?"
    city = "New York City's 2017 land cover map shows that 67.1% of this area is paved or built over (18.9% tree canopy)."
    model = "Experimental: a satellite land-cover model estimates that 70.7% of this area is paved or built over (13.4% tree canopy)."
    texts = {"city_landcover_nta": city, "landcover_nta": model}
    assert ra.answer(q, texts, {}) == ("no_change_record", ["city_landcover_nta", "landcover_nta"])
    assert ra.answer("How much of QN12 is paved?", texts, {})[0] == "facts"  # no change asked: the figures as before
    monkeypatch.setattr(experimental, "evaluation", lambda key: {
        "district_paved_gap_points_median_abs": 1.8, "district_paved_gap_points_max": 7.8,
        "canopy_vs_city_map_2017_words": "4.2 to 5.0 points less tree canopy than the city's 2017 map in 3 of its 4 yearly maps"})
    docs = [Doc("city_landcover_nta", "Cornerstone", city, False), Doc("landcover_nta", "Cornerstone", model, True)]
    values = {"city_landcover_nta": {"built_pct": 67.1, "year": 2017}, "landcover_nta": {"built_pct": 70.7, "year": 2026}}
    answer = _synthesize(monkeypatch, docs, q, values, intent="neighborhood")["paragraph"].split("**Answer.**\n")[1]
    assert answer.startswith("Riprap has no like-for-like record of change in land cover here.")
    assert answer.index("different methods") < answer.index("differ by 3.6 points") < answer.index("67.1%") < answer.index("70.7%")
    assert "within what the model was off by" in answer and "at most 7.8" in answer
    # A difference larger than the model's tested gap is not called within it.
    values["landcover_nta"]["built_pct"] = 80.0
    wide = _synthesize(monkeypatch, docs, q, values, intent="neighborhood")["paragraph"]
    assert "within what the model" not in wide and "is not a measured change" in wide
    # A question about canopy that quotes the model's share is told first how that share has read.
    trees = _synthesize(monkeypatch, docs, "How much tree canopy is there in QN12?", values, intent="neighborhood")["paragraph"]
    said = "The experimental model's maps show 4.2 to 5.0 points less tree canopy than the city's 2017 map in 3 of its 4"
    assert said in trees and trees.index(said) < trees.index("13.4% tree canopy")


def test_the_models_block_lists_only_a_model_a_sentence_quotes():
    from app.models_info import for_briefing

    ran = {"trace": [{"step": "landcover_nta", "ok": True, "elapsed_s": 0.1}], "landcover_nta": {"built_pct": 70.7}}
    assert for_briefing({**ran, "paragraph": "483 complaints were filed inside this area [nyc311_nta]."}) == []
    (listed,) = for_briefing({**ran, "paragraph": "Experimental: 70.7% of this area is paved [landcover_nta]."})
    assert listed["name"] == "NYC land-cover model (experimental)"


JUDGEMENT = r"high[- ]risk|flood[- ]prone|\bdangerous|\bworst\b|\bsafest\b|\briskiest\b"


def test_no_sentence_riprap_writes_judges_a_place_or_adopts_the_questions_word_for_it(monkeypatch):
    import re

    from riprap.core.burr import app, intake, synthesis, templated_reconciler
    from riprap.core.burr.synthesis import Doc
    from riprap.core.pebbles.bridge import get_registry

    # Every fixed sentence: leads, notes, refusals, the disclaimer, and each source's sentence template.
    fixed = [v for mod in (synthesis, templated_reconciler, intake, app) for k, v in vars(mod).items()
             if k.isupper() and isinstance(v, str)]
    fixed += [*synthesis.LEAD_PHRASES.values(), templated_reconciler._scope_header()]
    for name in ("nyc", "federal"):
        for p in get_registry(name).all():
            n = p.manifest.narration
            fixed += [n.template or "", n.short or "", p.manifest.title or "", p.manifest.fallback.message or ""]
    assert len(fixed) > 100
    for text in fixed:
        assert not re.search(JUDGEMENT, text, re.I), text
    # The disclaimer that travels with every briefing, in the JSON and MCP paragraph as on the page.
    head = templated_reconciler._scope_header()
    assert "not an assessment of any property or of the people who live there" in head
    assert "computes no score or rating" in head and "records can be missing where people report less" in head
    # A question that uses such a word is answered without it.
    docs = [Doc("nyc311", "Live Observer", T["nyc311"], False), Doc("floodnet", "Live Observer", T["floodnet"], False)]
    for q in ("Is 80 Pioneer Street in a high risk, flood prone area?", "Is this the worst block for flooding in Red Hook?",
              "How dangerous is flooding at 80 Pioneer Street?"):
        out = _synthesize(monkeypatch, docs, q)
        assert out["grounding"]["answered"] and not re.search(JUDGEMENT, out["paragraph"], re.I), q


def test_every_result_says_which_path_produced_it(monkeypatch):
    from riprap.core.burr import app
    from riprap.mcp import server

    assert app.answer_path({"grounding": {"tier": "no_llm", "answer_mode": "rules"}}) == "rules"
    assert app.answer_path({"grounding": {"tier": "llm", "answer_mode": "extractive"}}) == "llm"
    assert app.answer_path({"plan": {"llm_calls": [{"model": "m"}]}, "grounding": {"tier": "no_llm"}}) == "llm"  # routed
    monkeypatch.setattr(app, "_tier", lambda: "no_llm")
    refused = app.run("Should I sue my landlord over the flooding?")  # a refusal: no source is read
    assert refused["intent"] == "out_of_scope" and refused["answer_path"] == "rules"
    plan = heuristic_plan("Red Hook vs Hollis")
    both = app.run_compare("Red Hook vs Hollis", plan, lambda q, s: {"paragraph": q, "lat": 40.7, "deployment": "nyc"})
    assert both["answer_path"] == "rules"
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q: refused)
    assert server.get_briefing("80 Pioneer Street, Brooklyn", "Should I sue my landlord?")["answer_path"] == "rules"
