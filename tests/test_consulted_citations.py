"""Every consulted source that produced a value is citable on a question
page, not only the sources the answer text cites; the answer's own
citations come first. A refusal has none. The LLM is scripted."""

from types import SimpleNamespace

from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc

TEXTS = {"nyc311": "82 NYC 311 flood-related complaints filed within 200 m in the last 5 years.",
         "sandy_inundation": "This address sits outside the 2012 Sandy footprint.",
         "floodnet": "No FloodNet sensors deployed within 600 m of this address."}


def test_uncited_consulted_sources_keep_their_citation(monkeypatch):
    docs = [Doc(i, "Live Observer", t, False) for i, t in TEXTS.items()]
    items = [SimpleNamespace(doc_id=i, pebble_id=i) for i in TEXTS]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {e.doc_id: {"doc_id": e.doc_id} for e in items})
    reply = {"answer": {"lead": "count", "facts": ["nyc311"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address",
                          "plan": {"question": "How many 311 complaints near 80 Pioneer Street?"}})
    assert "[sandy_inundation]" not in out["paragraph"]
    # The answer's source first, then every other consulted source.
    assert list(out["citations"]) == ["nyc311", "sandy_inundation", "floodnet"]


def test_refusal_has_no_citations():
    out = syn.synthesize({"intent": "out_of_scope", "plan": {"explanation": "Not a flood question."}})
    assert out["citations"] == {}
