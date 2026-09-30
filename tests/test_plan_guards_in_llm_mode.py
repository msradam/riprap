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
