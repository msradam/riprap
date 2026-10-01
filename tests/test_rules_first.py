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


# The rules branch of synthesize, with the switch on as it is by default.

def _rules_run(monkeypatch, docs, question, focus=None):
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the model was asked")))
    state = {"intent": "single_address", "plan": {"question": question, "focus": focus or {}}}
    return syn.synthesize(state)


def test_the_default_is_rules_first_and_zero_turns_it_off(monkeypatch):
    import importlib

    monkeypatch.delenv("RIPRAP_RULES_FIRST", raising=False)
    assert importlib.reload(syn).RULES_FIRST is True
    monkeypatch.setenv("RIPRAP_RULES_FIRST", "0")
    assert importlib.reload(syn).RULES_FIRST is False
    monkeypatch.delenv("RIPRAP_RULES_FIRST")
    importlib.reload(syn)


def test_rules_do_not_answer_from_a_source_that_was_unavailable(monkeypatch):
    docs = [Doc("nws_alerts", "Projector", "NWS alerts unavailable for this point.", False)]
    out = _rules_run(monkeypatch, docs, "Is there a flood warning here?")
    assert out["grounding"]["answered"] is False and out["grounding"]["answer_mode"] == "rules"
    assert "No." not in out["paragraph"]


def test_rules_put_an_experimental_source_last(monkeypatch):
    docs = [Doc("floodnet", "Live Observer", "Experimental: 2 sensors within 600 m have logged 3 flood events.", True),
            Doc("nyc311", "Live Observer", "7 NYC 311 flood-related complaints filed within 200 m in the last 5 years.", False)]
    out = _rules_run(monkeypatch, docs, "What flooding has been recorded near 80 Pioneer Street, Brooklyn?")
    answer = [c["doc_ids"][0] for c in out["grounding"]["claims"] if c["section"] == "answer"]
    assert answer == ["nyc311", "floodnet"]


def test_rules_state_the_count_of_the_kind_asked(monkeypatch):
    text = "12 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years: 9 sewer backup, 3 street flooding."
    docs = [Doc("nyc311", "Live Observer", text, False)]
    monkeypatch.setattr(syn, "RULES_FIRST", True)
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [SimpleNamespace(doc_id="nyc311", pebble_id="nyc311")], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    out = syn.synthesize({"intent": "single_address",
                          "nyc311": {"n": 12, "years": 5, "by_kind": {"sewer backup": 9, "street flooding": 3}},
                          "plan": {"question": "How many street flooding complaints near 80 Pioneer Street, Brooklyn?"}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("3 street flooding complaints in the last 5 years, counting the 311 descriptors")
    assert out["grounding"]["answer_mode"] == "rules" and out["grounding"]["answer_lead"] == "count"


def test_a_rule_lead_that_fails_the_lead_checks_is_dropped_and_the_facts_stand(monkeypatch):
    monkeypatch.setattr(syn.rule_answer, "answer", lambda q, texts, values: ("no", ["nyc311"]))
    docs = [Doc("nyc311", "Live Observer", "7 NYC 311 flood-related complaints filed within 200 m in the last 5 years.", False)]
    out = _rules_run(monkeypatch, docs, "Has 80 Pioneer Street, Brooklyn flooded?", focus={"time_frame": "past"})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: 7 NYC 311") and "No." not in answer
