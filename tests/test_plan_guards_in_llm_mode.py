"""The fixed refusals decided in code (an invalid district, a ZIP alone, an
intersection, a retrospective) hold in LLM mode without a model call.

Before this, "QN15" reached the LLM planner in LLM mode, which took ten
seconds and answered "covers flood evidence only", a refusal for the
wrong reason; the no-LLM path had named the valid range all along."""
import pytest

from riprap.core.burr import app


@pytest.mark.parametrize("query,words", [
    ("QN15", "QN01 to QN14"),
    ("11693", "ZIP code"),
    ("Broadway and 116th Street", "intersection"),
    ("What would Riprap have said about 80 Pioneer Street, Brooklyn in 2019?", "past date"),
])
def test_code_refusals_skip_the_llm_planner(monkeypatch, query, words):
    import app.planner as planner

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr(planner, "plan", lambda *a, **k: pytest.fail("the LLM planner must not run"))
    plan = app.plan_for(query)
    assert plan["intent"] == "not_implemented"
    assert words in plan["rationale"]


def test_a_street_address_in_the_query_outranks_a_neighborhood_plan(monkeypatch):
    """A long question naming 90-01 183rd Street got a neighbourhood plan for
    "Hollis, Queens", which resolved to no area, so nothing was answered."""
    import app.planner as planner

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr(app, "llm_bare", lambda: False, raising=False)
    monkeypatch.setattr(planner, "plan", lambda *a, **k: planner.Plan(
        intent="neighborhood", targets=[{"type": "nta", "text": "Hollis, Queens"}], rationale="x",
        question="Has the block around 90-01 183rd Street in Hollis, Queens flooded since Ida?"))
    plan = app.plan_for("Has the block around 90-01 183rd Street in Hollis, Queens flooded since Ida?")
    assert plan["intent"] == "single_address"
    assert plan["targets"] == [{"type": "address", "text": "90-01 183rd Street, Hollis, Queens"}]


def test_a_question_stays_a_question_when_the_planner_is_unreachable(monkeypatch):
    """Ollama killed mid-run: the page said "no question was asked, so no LLM
    was needed" over a place briefing. The fallback plan keeps the question
    so synthesis reports the model as unavailable instead."""
    import app.planner as planner

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr(app, "llm_bare", lambda: False, raising=False)

    def down(*a, **k):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(planner, "plan", down)
    q = "Was 615 Midland Avenue, Staten Island inside the area Hurricane Sandy flooded?"
    plan = app.plan_for(q)
    assert plan["intent"] == "single_address" and plan["question"] == q
    assert "question" not in app.plan_for("615 Midland Avenue, Staten Island")


def test_a_district_code_in_the_query_outranks_the_planners_words(monkeypatch):
    """"How many flood complaints has Queens Community Board 12 had?" got a
    neighbourhood plan for the words "Queens Community Board 12", which
    match no tabulation area; the parser had read QN12 all along."""
    import app.planner as planner

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr(app, "llm_bare", lambda: False, raising=False)
    monkeypatch.setattr(planner, "plan", lambda *a, **k: planner.Plan(
        intent="neighborhood", targets=[{"type": "nta", "text": "Queens Community Board 12"}], rationale="x",
        question="How many flood complaints has Queens Community Board 12 had?"))
    plan = app.plan_for("How many flood complaints has Queens Community Board 12 had?")
    assert plan["intent"] == "neighborhood"
    assert plan["targets"] == [{"type": "district", "text": "QN12"}]


def test_a_named_building_stays_a_point_when_the_model_calls_it_an_area(monkeypatch):
    """"Red Hook Houses: which is worse there, flooding or heat?" got a
    neighbourhood plan for "Red Hook Houses", which is no tabulation area."""
    import app.planner as planner

    q = "Red Hook Houses: which is worse there, flooding or heat?"
    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr(app, "llm_bare", lambda: False, raising=False)
    monkeypatch.setattr(planner, "plan", lambda *a, **k: planner.Plan(
        intent="neighborhood", targets=[{"type": "nta", "text": "Red Hook Houses"}], rationale="x", question=q))
    plan = app.plan_for(q)
    assert plan["intent"] == "single_address" and plan["targets"][0]["type"] == "address"
    assert plan["targets"][0]["text"].startswith("Red Hook Houses")
