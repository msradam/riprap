"""The entailment check's plumbing, with the model replaced by a stub."""

from riprap.core.burr import entailment as en
from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc


def test_low_scoring_answer_claims_are_dropped_and_others_pass(monkeypatch):
    monkeypatch.setenv("RIPRAP_ENTAILMENT", "gliclass")
    monkeypatch.setitem(en.THRESHOLDS, "gliclass", 0.5)
    monkeypatch.setattr(en, "available", lambda: (True, ""))
    monkeypatch.setattr(en, "p_supported", lambda claim, ev, b=None: 0.9 if "alerts" in claim else 0.1)
    claims = [{"section": "answer", "text": "There are 3 active alerts.", "doc_ids": ["nws_alerts"]},
              {"section": "answer", "text": "It is raining hard.", "doc_ids": ["nws_alerts"]},
              {"section": "Projector", "text": "Unrelated body claim.", "doc_ids": ["nws_alerts"]}]
    kept, dropped, info = en.check(claims, {"nws_alerts": "3 active NWS alerts."})
    assert [c["text"] for c in kept] == ["There are 3 active alerts.", "Unrelated body claim."]
    assert dropped[0]["reason"] == en.DROP_REASON and info["ran"]


def test_skipped_check_says_why(monkeypatch):
    monkeypatch.setenv("RIPRAP_ENTAILMENT", "off")
    kept, dropped, info = en.check([{"section": "answer", "text": "x", "doc_ids": []}], {})
    assert not dropped and info == {"ran": False, "reason": "entailment check off (RIPRAP_ENTAILMENT=off)"}


def test_briefing_says_which_checks_ran(monkeypatch):
    monkeypatch.setenv("RIPRAP_ANSWER_MODE", "guarded")
    monkeypatch.setenv("RIPRAP_ENTAILMENT", "off")
    docs = [Doc("nws_alerts", "Projector", "There are 3 active NWS alerts at this point.", False)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"claims": [{"section": "answer", "text": "There are 3 active NWS alerts.", "doc_ids": ["nws_alerts"],
                         "numbers": []}]}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "live_now", "plan": {"question": "Any alerts?"}})
    assert out["paragraph"].rstrip().endswith(
        "Checks run: citations and numbers on every claim; five answer rules on the answer; "
        "entailment check off (RIPRAP_ENTAILMENT=off).")
