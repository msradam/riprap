"""The rules-first switch: with a model configured, a question the rules
recognise is planned and answered with no model call, and the model is
asked only for the rest. Offline: the model is a stub that counts calls."""

from types import SimpleNamespace

from riprap.core.burr import app
from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc

Q = "Was 80 Pioneer Street, Brooklyn inside the area Hurricane Sandy flooded in 2012?"
DOCS = [Doc("sandy_inundation", "Hazard Reader", "This address sits within the 2012 Sandy inundation footprint.", False),
        Doc("fema_nfhl", "Hazard Reader", "This address sits in FEMA flood zone AE.", False)]


def _planner_that_counts(monkeypatch):
    calls = []

    def plan(q, ledger=None):
        calls.append(q)
        return SimpleNamespace(intent="single_address", targets=[{"type": "address", "text": "80 Pioneer Street"}],
                               rationale="r", question=q, focus={"time_frame": "past"}, pebbles=["sandy"], catalog=[])

    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr("app.planner.plan", plan)
    return calls


def test_rules_first_plans_a_recognised_question_without_the_model(monkeypatch):
    calls = _planner_that_counts(monkeypatch)
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    plan = app.plan_for(Q)
    assert calls == [] and plan["question"] == Q and plan["targets"][0]["text"] == "80 Pioneer Street, Brooklyn"
    monkeypatch.setattr(syn, "RULES_FIRST", False)
    app.plan_for(Q)
    assert calls == [Q]  # the switch off: the model plans, as before


def test_rules_first_asks_the_model_only_what_the_rules_do_not_recognise(monkeypatch):
    calls = _planner_that_counts(monkeypatch)
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    odd = "Tell me something about 80 Pioneer Street, Brooklyn and its council member"
    app.plan_for(odd)
    assert calls == [odd]


def test_rules_first_answers_in_code_and_records_it(monkeypatch):
    asked = []
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    monkeypatch.setattr(syn, "_documents", lambda state: (DOCS, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: asked.append(1) or ({"answer": {"lead": "no", "facts": []}}, "m"))
    out = syn.synthesize({"intent": "single_address", "sandy": {"inside": True, "edge_m": None},
                          "plan": {"question": Q, "focus": {"time_frame": "past"}}})
    g = out["grounding"]
    assert asked == [] and g["answer_mode"] == "rules" and g["tier"] == "no_llm" and g["answered"] is True
    assert "This address sits within the 2012 Sandy inundation footprint" in out["paragraph"]


def test_when_the_model_does_not_reply_the_rules_answer_and_say_why(monkeypatch):
    def down(*a, **k):
        raise syn.llm.LLMUnavailable("connection refused")

    monkeypatch.setattr(syn, "_documents", lambda state: (DOCS, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn.llm, "chat_json", down)
    out = syn.synthesize({"intent": "single_address", "plan": {"question": Q, "focus": {"time_frame": "past"}}})
    g = out["grounding"]
    assert g["answer_mode"] == "rules" and "connection refused" in g["fallback_reason"]
