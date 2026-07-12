"""geocode_target must pass the full raw query as scope_hint, not just the
planner-extracted target — see app/geocode.py's geocode_one docstring for
why (target extraction routinely drops the city/country a locality check
needs)."""
from __future__ import annotations

from burr.core import State

from riprap.core.burr.intake import geocode_target


def test_geocode_target_forwards_raw_query_as_scope_hint(monkeypatch):
    calls = []

    def fake_geocode_one(text, *, scope_hint=None):
        calls.append({"text": text, "scope_hint": scope_hint})
        return None  # out of scope — exercises the same path as production

    monkeypatch.setattr("app.geocode.geocode_one", fake_geocode_one)

    state = State({
        "query": "what's the flood risk at 10 Downing Street in London?",
        "first_target": "10 Downing Street",
        "trace": [],
    })
    geocode_target(state)

    assert len(calls) == 1
    assert calls[0]["text"] == "10 Downing Street"
    assert calls[0]["scope_hint"] == "what's the flood risk at 10 Downing Street in London?"
