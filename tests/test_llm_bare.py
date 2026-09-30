"""LLM mode spends the LLM only where there is a question (refactor 8)."""

from types import SimpleNamespace

from riprap.core.burr import app
from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc


def test_bare_place_skips_the_llm_planner(monkeypatch):
    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr("app.planner.plan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("planner called")))
    assert app.plan_for("80 Pioneer Street, Brooklyn")["intent"] == "single_address"
    assert app.plan_for("QN12")["targets"][0]["text"] == "QN12"


def test_bare_place_briefing_skips_the_llm(monkeypatch):
    monkeypatch.delenv("RIPRAP_LLM_BARE", raising=False)
    monkeypatch.setattr(syn, "_documents", lambda state: ([Doc("fema_nfhl", "Hazard Reader", "Zone AE.", False)],
                                                          [], None))
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM called")))
    monkeypatch.setattr(syn, "compose_briefing", lambda state: ("the cited evidence", {}))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": ""}})
    assert out["paragraph"] == "the cited evidence" and out["grounding"]["tier"] == "no_llm"
    assert "No question was asked" in out["grounding"]["note"]


def test_extractive_asks_for_the_answer_only(monkeypatch):
    seen = {}

    def chat(messages, schema, **k):
        seen["schema"], seen["system"] = schema, messages[0]["content"]
        return {"answer": {"lead": "yes", "facts": ["sandy_inundation"]}}, "scripted"

    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("sandy_inundation", "Hazard Reader", "This address sits inside the 2012 Sandy footprint.", False)],
        [SimpleNamespace(doc_id="sandy_inundation", pebble_id="sandy")], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    monkeypatch.setattr(syn.llm, "chat_json", chat)
    out = syn.synthesize({"intent": "single_address", "plan": {"question": "Was it inside the Sandy extent?"}})
    assert list(seen["schema"]["properties"]) == ["answer"] and "claims" not in seen["schema"]["required"]
    assert seen["system"].startswith("You answer a question") and "Yes. This address sits inside" in out["paragraph"]
