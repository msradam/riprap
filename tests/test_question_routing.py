"""Question-driven routing: pebble selection, planner validation, the
answer section, and fixed refusals. No LLM, no network."""
from __future__ import annotations

from app.planner import _validate, plan_schema
from riprap.core.burr.intake import heuristic_plan
from riprap.core.burr.stones import FLOOR, select_pebbles
from riprap.core.burr.synthesis import CANNOT_ANSWER, Doc, _render, verify
from riprap.core.burr.templated_reconciler import SCOPE_REFUSAL, refusal
from riprap.core.pebbles.bridge import get_registry

NYC = get_registry("nyc")
POINT = [p.id for p in NYC.all() if p.manifest.spatial.scope == "point"]


def test_bare_address_runs_every_point_pebble():
    plan = {"intent": "single_address", "question": "", "pebbles": [], "catalog": [p.id for p in NYC.all()]}
    assert set(select_pebbles(plan, NYC)) == set(POINT)


def test_no_llm_plan_runs_every_pebble():
    assert set(select_pebbles(heuristic_plan("80 Pioneer Street, Brooklyn, NY"), NYC)) == set(POINT)


def test_question_runs_choice_plus_floor_only():
    plan = {"intent": "single_address", "question": "How many 311 complaints?",
            "pebbles": ["nyc311"], "catalog": [p.id for p in NYC.all()]}
    assert set(select_pebbles(plan, NYC)) == {"nyc311", *FLOOR["single_address"]}


def test_plan_from_another_catalog_falls_back_to_everything():
    plan = {"intent": "single_address", "question": "q", "pebbles": ["nyc311"], "catalog": ["nyc311"]}
    assert set(select_pebbles(plan, NYC)) == set(POINT)


def test_neighborhood_selection_stays_in_polygon_scope():
    plan = {"intent": "neighborhood", "question": "q", "pebbles": ["nyc311_nta", "nyc311"],
            "catalog": [p.id for p in NYC.all()]}
    assert set(select_pebbles(plan, NYC)) == {"nyc311_nta", *FLOOR["neighborhood"]}


def test_planner_validation_drops_unknown_ids_and_defaults_focus():
    p = _validate({"intent": "single_address", "targets": [{"type": "address", "text": "1 Main St"}],
                   "question": "Q?", "focus": {"hazard": "lava"}, "pebbles": ["nyc311", "made_up"]},
                  raw_query="Q?", catalog_ids=["nyc311", "sandy"])
    assert p.pebbles == ["nyc311"] and p.focus["hazard"] == "flood" and p.focus["time_frame"] == "any"


def test_plan_schema_enumerates_catalog_ids():
    assert plan_schema(["a", "b"])["properties"]["pebbles"]["items"]["enum"] == ["a", "b"]


DOCS = [Doc("nyc311", "Live observer", "82 flood-related 311 complaints within 200 m in 5 years.", False)]


def test_answer_claims_are_verified_like_others():
    good = {"section": "answer", "text": "82 flood complaints were filed.", "doc_ids": ["nyc311"], "numbers": ["82"]}
    bad = {"section": "answer", "text": "120 flood complaints were filed.", "doc_ids": ["nyc311"], "numbers": ["120"]}
    kept, dropped = verify([good, bad], DOCS, ("answer",))
    assert kept == [{**good, "text": "82 flood complaints were filed."}]
    assert "120" in dropped[0]["reason"]
    # without a question, "answer" is not a valid section
    assert not verify([good], DOCS)[0]


def test_render_opens_with_answer_or_cannot_answer_line():
    kept = [{"section": "answer", "text": "82 flood complaints were filed", "doc_ids": ["nyc311"], "numbers": ["82"]}]
    docs = DOCS + [Doc("sandy_inundation", "Hazard reader", "This address sits outside the Sandy extent.", False)]
    kept2 = kept + [{"section": "Hazard reader", "text": "It sits outside the Sandy extent",
                     "doc_ids": ["sandy_inundation"], "numbers": []}]
    text = _render(kept2, docs, ["Hazard reader", "Live observer"], question="How many complaints?")
    assert text.index("**Answer.**\n82 flood complaints") < text.index("**Hazard reader.**")
    empty = _render([], DOCS, ["Live observer"], question="How many complaints?")
    assert f"**Answer.**\n{CANNOT_ANSWER}" in empty
    assert "**Answer.**" not in _render([], DOCS, ["Live observer"])


def test_out_of_scope_gets_fixed_text():
    assert heuristic_plan("Should I buy the house at 2017 East 17th Street?")["intent"] == "out_of_scope"
    heat = heuristic_plan("Is 560 Grand Street a heat island in the summer?")
    assert heat["intent"] == "out_of_scope" and heat["focus"]["hazard"] == "heat"
    assert refusal({"intent": "out_of_scope", "plan": {"focus": {"hazard": "flood"}}}) == SCOPE_REFUSAL
    assert "heat" in refusal({"intent": "out_of_scope", "plan": {"focus": {"hazard": "heat"}}})


def test_numbers_from_the_users_question_are_exempt():
    claim = {"section": "answer", "text": "82 complaints were filed near 2017 East 17th Street.",
             "doc_ids": ["nyc311"], "numbers": ["82"]}
    assert not verify([claim], DOCS, ("answer",))[0]
    exempt = frozenset(["2017", "17"])
    assert verify([claim], DOCS, ("answer",), exempt)[0]


def test_section_used_only_by_the_answer_is_omitted():
    kept = [{"section": "answer", "text": "82 flood complaints were filed", "doc_ids": ["nyc311"], "numbers": ["82"]}]
    text = _render(kept, DOCS, ["Live observer"], question="How many complaints?")
    assert "**Live observer.**" not in text


def test_question_is_the_users_text_and_bare_places_have_none():
    from app.planner import _validate

    targets = [{"type": "address", "text": "2017 East 17th Street, Brooklyn, NY 11229"}]
    echoed = {"intent": "single_address", "targets": targets,
              "question": "2017 East 17th Street, Brooklyn, NY 11229", "pebbles": ["sandy"]}
    assert _validate(echoed, "2017 East 17th Street, Brooklyn, NY 11229", ["sandy"]).question == ""
    invented = {**echoed, "question": "What is the flood risk for 80 Pioneer Street?"}
    assert _validate(invented, "80 Pioneer Street, Brooklyn, NY", ["sandy"]).question == ""
    asked = "Has 2017 East 17th Street flooded since Ida"
    assert _validate({**echoed, "question": "paraphrase"}, asked, ["sandy"]).question == asked


def test_out_of_scope_rules_override_the_llm_planner(monkeypatch):
    from riprap.core.burr import app as burr_app

    class P:
        intent, targets, rationale, question = "single_address", [{"type": "address", "text": "x"}], "", "q"
        focus, pebbles, catalog = {}, ["sandy"], ["sandy"]

    monkeypatch.setattr(burr_app, "_tier", lambda: "llm")
    monkeypatch.setattr("app.planner.plan", lambda q, ledger=None: P)
    assert burr_app.plan_for("Should I buy the house at 2017 East 17th Street?")["intent"] == "out_of_scope"
    assert burr_app.plan_for("Has 2017 East 17th Street flooded?")["intent"] == "single_address"


def test_focus_floor_adds_what_an_analyst_checks():
    cat = [p.id for p in NYC.all()]
    past = {"intent": "single_address", "question": "q", "pebbles": [], "catalog": cat,
            "focus": {"time_frame": "past", "assets": ["schools"]}}
    assert {"nyc311", "floodnet", "ida_hwm", "sandy", "doe_schools"} <= set(select_pebbles(past, NYC))
    now = {**past, "intent": "live_now", "focus": {"time_frame": "now", "assets": []}}
    assert set(select_pebbles(now, NYC)) == {"nws_alerts", "nws_obs", "floodnet", "noaa_tides"}
    area = {**past, "intent": "neighborhood", "focus": {"time_frame": "past", "assets": []}}
    assert set(select_pebbles(area, NYC)) == {"area_boundary", "sandy_nta", "dep_moderate_2050_nta", "nyc311_nta"}


def test_empty_section_is_hidden_when_the_answer_covers_its_stone():
    from riprap.core.burr.synthesis import Doc

    docs = [Doc("sandy_inundation", "Hazard Reader", "Inside the Sandy footprint.", False),
            Doc("fema_nfhl", "Hazard Reader", "Zone AE.", False),
            Doc("nyc311", "Live Observer", "82 complaints.", False)]
    kept = [{"section": "answer", "text": "It was inside the Sandy footprint", "doc_ids": ["sandy_inundation"],
             "numbers": []}]
    text = _render(kept, docs, ["Hazard Reader", "Live Observer"], question="Did Sandy flood it?")
    assert "**Hazard Reader.**" not in text  # covered by the answer
    # Refactor 6: a Stone with facts but no claim is hidden too; its facts are in the evidence cards.
    assert "**Live Observer.**" not in text and "No grounded evidence" not in text


def test_a_stone_whose_sources_returned_nothing_says_what_it_consulted():
    from riprap.core.burr.synthesis import Doc

    docs = [Doc("sandy_inundation", "Hazard Reader", "Inside the Sandy footprint.", False)]
    kept = [{"section": "answer", "text": "Inside the Sandy footprint", "doc_ids": ["sandy_inundation"], "numbers": []}]
    text = _render(kept, docs, ["Hazard Reader", "Live Observer"], question="Did Sandy flood it?",
                   empty={"Live Observer": ["FloodNet sensors", "NYC 311 complaints"]})
    assert "**Live Observer.**\nConsulted FloodNet sensors and NYC 311 complaints; they returned nothing" in text


def test_a_later_claim_that_restates_the_answer_is_left_out():
    from riprap.core.burr.synthesis import Doc

    fact = "4376 complaints inside this area in the last 3 years: 568 street flooding."
    docs = [Doc("nyc311_nta", "Live Observer", fact, False)]
    kept = [{"section": "answer", "text": fact, "doc_ids": ["nyc311_nta"], "numbers": []},
            {"section": "Live Observer", "text": "QN12 has had 568 street flooding complaints in the past 3 years",
             "doc_ids": ["nyc311_nta"], "numbers": []}]
    text = _render(kept, docs, ["Live Observer"], question="How many street flooding complaints?")
    assert text.count("568") == 1 and "**Live Observer.**" not in text


def test_a_named_future_day_is_refused_but_a_past_day_is_not():
    assert heuristic_plan("Will 200 Water Street, Manhattan flood next Tuesday?")["intent"] == "out_of_scope"
    assert heuristic_plan("Is 80 Pioneer Street going to flood tomorrow?")["intent"] == "out_of_scope"
    assert heuristic_plan("Did 80 Pioneer Street, Brooklyn flood on Monday?")["intent"] != "out_of_scope"
    assert heuristic_plan("Is there flooding near 80 Pioneer Street right now?")["intent"] == "live_now"


def test_compare_with_one_place_twice_is_a_single_address():
    from app.planner import _validate

    t = {"type": "address", "text": "200 Water Street, Manhattan"}
    p = _validate({"intent": "compare", "targets": [t, dict(t)]}, "Will 200 Water Street flood?", [])
    assert p.intent == "single_address" and p.targets == [t]


def test_a_dep_question_runs_every_dep_scenario():
    cat = [p.id for p in NYC.all()]
    plan = {"intent": "single_address", "question": "Is it in any of the DEP stormwater flood scenarios?",
            "pebbles": ["dep_extreme_2080"], "catalog": cat, "focus": {"time_frame": "future", "assets": []}}
    assert {"dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080"} <= set(select_pebbles(plan, NYC))
