"""live_now has no geocoder of its own (module docstring: speed matters
more than a full geocode) and defaults to NYC/Battery whenever no borough
target resolves. Without a scope check, "flooding near albany" silently
became a Manhattan tide reading with no indication the location never
matched — a real production case. These tests guard the fix: decline
honestly instead of defaulting when the query names somewhere non-NYC."""
from __future__ import annotations

from app.intents.live_now import run
from app.planner import Plan


def test_declines_for_non_nyc_place(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.context.noaa_tides.summary_for_point",
        lambda *a, **k: calls.append((a, k)) or {},
    )
    plan = Plan(intent="live_now", targets=[], specialists=["noaa_tides"],
               rationale="Check current conditions near Albany.")

    result = run(plan, "was there some bad flooding near albany last year, "
                       "is that still gonna be a problem")

    assert calls == [], "no specialist should run for an unresolved non-NYC place"
    assert result["place"] is None
    assert "New York City only" in result["paragraph"]
    assert result["noaa_tides"] is None


def test_proceeds_for_resolved_nyc_borough(monkeypatch):
    monkeypatch.setattr(
        "app.context.noaa_tides.summary_for_point",
        lambda lat, lon: {"observed_ft_mllw": 2.5, "station_name": "The Battery",
                          "station_id": "8518750", "distance_km": 0.1},
    )
    monkeypatch.setattr("app.intents.live_now._reconcile",
                        lambda docs, on_token=None, system_prompt=None: ("ok", {"raw": "", "dropped": []}))
    plan = Plan(intent="live_now", targets=[{"type": "borough", "text": "Manhattan"}],
               specialists=["noaa_tides"], rationale="Check Manhattan conditions.")

    result = run(plan, "what's the current flood status in Manhattan")

    assert result["place"] == "Manhattan"
    assert result["noaa_tides"] is not None


def test_proceeds_with_default_nyc_when_query_is_generically_local(monkeypatch):
    """A vague query with no place signal at all (not non-NYC, just
    unspecified) should still fall through to the NYC default — this
    gate only fires on an explicit non-NYC signal, not on ambiguity."""
    monkeypatch.setattr(
        "app.context.noaa_tides.summary_for_point",
        lambda lat, lon: {"observed_ft_mllw": 2.5, "station_name": "The Battery",
                          "station_id": "8518750", "distance_km": 0.1},
    )
    monkeypatch.setattr("app.intents.live_now._reconcile",
                        lambda docs, on_token=None, system_prompt=None: ("ok", {"raw": "", "dropped": []}))
    plan = Plan(intent="live_now", targets=[], specialists=["noaa_tides"],
               rationale="Check current conditions.")

    result = run(plan, "is there any flooding happening right now")

    assert result["place"] == "NYC"
    assert result["noaa_tides"] is not None
