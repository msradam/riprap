"""Every intent's briefing must carry the SCOPE_HEADER/NON_SCOPE_FOOTER that
the 13 compliance predicates check for (ASTM 4.1/4.5/4.6). single_address got
this via app/reconcile.py's own reconcile(); neighborhood, development_check,
and live_now each have their own standalone _reconcile() that called
verify_paragraph() directly and returned, skipping wrap_with_scope() entirely
— confirmed live: a real neighborhood.py query scored 9/13, missing exactly
those three checks. Each _reconcile() now wraps its cleaned paragraph too."""
from __future__ import annotations

from app.reconcile import NON_SCOPE_FOOTER, SCOPE_HEADER


def test_neighborhood_reconcile_wraps_scope(monkeypatch):
    from app.intents import neighborhood

    monkeypatch.setattr(neighborhood.llm, "chat",
                        lambda **k: {"message": {"content": "Body text [doc_1]."}})
    monkeypatch.setattr("app.reconcile.verify_paragraph", lambda raw, docs: (raw, []))

    cleaned, audit = neighborhood._reconcile([{"role": "document doc_1", "content": "x"}])

    assert cleaned.startswith(SCOPE_HEADER)
    assert cleaned.endswith(NON_SCOPE_FOOTER)
    assert "Body text [doc_1]." in cleaned


def test_development_check_reconcile_wraps_scope(monkeypatch):
    from app.intents import development_check

    monkeypatch.setattr(development_check.llm, "chat",
                        lambda **k: {"message": {"content": "Body text [doc_1]."}})
    monkeypatch.setattr("app.reconcile.verify_paragraph", lambda raw, docs: (raw, []))

    cleaned, audit = development_check._reconcile([{"role": "document doc_1", "content": "x"}])

    assert cleaned.startswith(SCOPE_HEADER)
    assert cleaned.endswith(NON_SCOPE_FOOTER)


def test_live_now_reconcile_wraps_scope(monkeypatch):
    from app.intents import live_now

    monkeypatch.setattr(live_now.llm, "chat",
                        lambda **k: {"message": {"content": "Body text [doc_1]."}})
    monkeypatch.setattr("app.reconcile.verify_paragraph", lambda raw, docs: (raw, []))

    cleaned, audit = live_now._reconcile([{"role": "document doc_1", "content": "x"}])

    assert cleaned.startswith(SCOPE_HEADER)
    assert cleaned.endswith(NON_SCOPE_FOOTER)
