"""A query that names no findable place gets told so, and runs no source.

Before this, "asdfgh qwerty" ran every federal source on lat None, they
all failed, and the briefing read "Failed to respond: FEMA ...; NWS ...",
which blames the sources for a place that does not exist."""
from riprap.core.burr.app import build_app
from riprap.core.burr.templated_reconciler import nothing_built


def test_no_place_text_names_the_query_and_blames_no_source():
    state = {"lat": None, "query": "asdfgh qwerty", "trace": [],
             "consulted": [{"id": "fema_nfhl", "title": "FEMA NFHL"}]}
    text = nothing_built(state)
    assert 'could not match "asdfgh qwerty" to a place' in text
    assert "Failed to respond" not in text and "FEMA" not in text


def test_unresolved_address_runs_no_source(monkeypatch):
    import app.geocode as gc

    monkeypatch.setattr(gc, "geocode_one", lambda *a, **k: None)
    plan = {"intent": "single_address", "targets": [{"type": "address", "text": "asdfgh qwerty"}]}
    _, _, state = build_app("asdfgh qwerty", plan, no_llm=True).run(halt_after=["reconcile"])
    steps = [t["step"] for t in state["trace"]]
    assert steps == ["geocode", "reconcile_templated"], steps
    assert 'could not match "asdfgh qwerty"' in state["paragraph"]
