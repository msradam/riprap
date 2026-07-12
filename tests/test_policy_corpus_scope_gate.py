"""step_policy_corpus must not run RAG retrieval when there's no real
geocode — otherwise its generic "flood resilience plan, vulnerability,
hardening, mitigation" query tail alone pulls back real policy-corpus PDF
chunks by topic similarity, with zero connection to whatever address was
actually asked about, and the reconciler cites them as if they grounded
an answer. Real production case: an out-of-coverage London query still
got NYCHA/DEP/Con Edison citations synthesized into a confident paragraph."""
from __future__ import annotations

from burr.core import State

from riprap.core.burr.capstone import step_policy_corpus


def test_skips_retrieval_when_no_geocode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "riprap.core.pebbles.bridge.fetch_pebble",
        lambda *a, **k: calls.append((a, k)) or (None, {}, "should not be called"),
    )

    state = State({"lat": None, "lon": None, "geocode": None,
                   "sandy": None, "dep": {}, "intent": "single_address",
                   "trace": []})
    result = step_policy_corpus(state)

    assert calls == [], "RAG retrieval must not run with no geocode"
    assert result["rag"] == []
    assert result["policy_corpus"] is None


def test_runs_retrieval_when_geocode_present(monkeypatch):
    calls = []

    def fake_fetch_pebble(*a, **k):
        calls.append((a, k))
        return ({"rag_hits": [{"doc_id": "rag_nycha"}], "entities": {}}, {"n_hits": 1}, None)

    monkeypatch.setattr("riprap.core.pebbles.bridge.fetch_pebble", fake_fetch_pebble)

    state = State({
        "lat": 40.68, "lon": -73.99,
        "geocode": {"address": "80 Pioneer St, Brooklyn"},
        "sandy": None, "dep": {}, "intent": "single_address", "trace": [],
    })
    result = step_policy_corpus(state)

    assert len(calls) == 1, "RAG retrieval must still run for a real geocode"
    assert result["rag"] == [{"doc_id": "rag_nycha"}]
