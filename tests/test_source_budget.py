"""A source that does not answer within the budget is reported as such and
the briefing goes on; its thread is left to finish on its own.

Live, the DOB permits query for MN01 took 104 s and the page waited for
all of it."""
import time

from burr.core import State

from riprap.core.burr import pebble as pb


def test_a_slow_source_is_reported_after_the_budget(monkeypatch):
    monkeypatch.setattr(pb, "SOURCE_BUDGET_S", 0.3)

    def slow(*a, **k):
        time.sleep(1.5)
        return {"n": 1}, {"n": 1}, None

    monkeypatch.setattr(pb, "fetch_pebble", slow)
    step = pb.pebble_action("dob_permits_nta")
    t0 = time.time()
    out = step(State({"lat": 40.7, "lon": -74.0, "deployment": "nyc", "polygon_wkt": None, "nta": None, "trace": []}))
    assert time.time() - t0 < 1.0
    rec = out["trace"][-1]
    assert rec["ok"] is False and rec["err"] == "no answer within 0 s" and out["dob_permits_nta"] is None


def test_a_prompt_source_is_unaffected(monkeypatch):
    monkeypatch.setattr(pb, "fetch_pebble", lambda *a, **k: ({"n": 2}, {"n": 2}, None))
    out = pb.pebble_action("nyc311")(State({"lat": 40.7, "lon": -74.0, "deployment": "nyc", "polygon_wkt": None,
                                            "nta": None, "trace": []}))
    assert out["trace"][-1]["ok"] is True and out["nyc311"] == {"n": 2}
