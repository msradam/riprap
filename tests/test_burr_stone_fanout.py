"""Smoke test for the Burr Stones fan-out: one MapActions runs every
data-Stone pebble for the intent, and point pebbles never run for a
neighbourhood (polygon) query."""
from __future__ import annotations

from burr.core import ApplicationBuilder, State, action

from riprap.core.burr.stones import StonesAction, pebbles_for


@action(reads=[], writes=["lat", "lon", "deployment", "intent", "polygon_wkt", "trace"])
def _seed(state: State) -> State:
    return state.update(lat=40.7100, lon=-73.9800, deployment="nyc", intent="single_address",
                        polygon_wkt=None, trace=[])


def test_point_intent_fans_out_baked_pebbles(monkeypatch):
    # Keep it offline: run only the file-backed pebbles.
    only = {"sandy", "ida_hwm", "microtopo"}
    monkeypatch.setattr("riprap.core.burr.stones.pebbles_for",
                        lambda *a, **k: [p for p in pebbles_for(*a, **k) if p in only])
    app = (
        ApplicationBuilder()
        .with_actions(seed=_seed, stones=StonesAction())
        .with_transitions(("seed", "stones"))
        .with_entrypoint("seed")
        .with_state(trace=[])
        .build()
    )
    _, _, final = app.run(halt_after=["stones"])
    assert isinstance(final["sandy"], dict) and "inside" in final["sandy"]
    assert isinstance(final["ida_hwm"], dict)
    assert isinstance(final["microtopo"], dict)
    assert {t["step"] for t in final["trace"]} == only


def test_intent_selects_point_or_polygon_pebbles():
    point = pebbles_for("nyc", 40.71, -73.98, "single_address")
    polygon = pebbles_for("nyc", 40.71, -73.98, "neighborhood")
    live = pebbles_for("nyc", 40.71, -73.98, "live_now")
    assert "sandy" in point and "sandy_nta" not in point
    assert "sandy_nta" in polygon and "sandy" not in polygon
    assert "nyc311" in live and "sandy" not in live
