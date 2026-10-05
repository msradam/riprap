"""What a "right now" answer says. The public tools are better at the live
picture (the FloodNet dashboard, the Weather Service, Notify NYC), so the
answer reports what Riprap's sources read, each with its time, and points
there. Offline: the fetches are stubbed."""

from app.context import floodnet, nws_obs
from app.context.floodnet import FloodEvent, Sensor
from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc


def _obs(monkeypatch, props):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"properties": {"timestamp": "2026-10-01T03:35:00+00:00", **props}}

    monkeypatch.setattr(nws_obs.http, "get", lambda *a, **k: R())
    return nws_obs.summary_for_point(40.711, -73.778)


def test_a_dry_observation_says_it_is_dry(monkeypatch):
    v = _obs(monkeypatch, {"textDescription": "Clear", "temperature": {"value": 18.0}})
    assert v["raining"] is False
    assert ": clear, 18.0°C, no precipitation reported, observed 2026-10-01 03:35 UTC." in v["narrative"]


def test_a_wet_observation_says_what_is_falling(monkeypatch):
    v = _obs(monkeypatch, {"textDescription": "Light Rain", "temperature": {"value": 17.0},
                           "precipitationLastHour": {"value": 2.5}})
    assert v["raining"] is True
    assert "light rain, 17.0°C, 2.5 mm precip in the last hour" in v["narrative"]
    wet = _obs(monkeypatch, {"textDescription": "Heavy Rain", "temperature": {"value": 17.0}})
    assert wet["raining"] is True and "no precipitation" not in wet["narrative"]  # the gauge field can lag the sky


def test_floodnet_dates_its_newest_event_and_flags_one_still_open(monkeypatch):
    from datetime import UTC, datetime, timedelta

    recent = (datetime.now(UTC) - timedelta(hours=2)).isoformat(timespec="seconds").replace("+00:00", "")
    sensors = [Sensor("a", "Q - 183rd St", "183rd St", "Queens", "good", None)]
    events = [FloodEvent("a", "2026-08-20T22:57:57.692", "2026-08-20T23:40:00", 492, "flood")]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: events)
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "in the last 3 years, the most recent starting 2026-08-20 22:57 UTC (every date here is a UTC day)." in v["narrative"]
    # What was read, no more: an event under way may still be labelled "short" or not at all in the API.
    assert "No event that FloodNet's API labels a flood was open at it when this was read (" in v["narrative"]
    assert ("UTC); an event under way may not be labelled yet, and FloodNet's dashboard (dataviz.floodnet.nyc) "
            "shows the current readings.") in v["narrative"]
    assert v["n_events_open_24h"] == 0 and "no end time" not in v["narrative"]
    events.append(FloodEvent("a", recent, None, 60, "flood"))
    v = floodnet.summary_for_point(40.71, -73.78)
    assert v["n_events_open_24h"] == 1
    assert "1 event that started in the last 24 hours had no end time when this was read." in v["narrative"]


def test_a_now_answer_points_to_the_live_tools(monkeypatch):
    docs = [Doc("nws_alerts", "Projector", "No active NWS flood, coastal or tropical storm alerts at this point.", False),
            Doc("floodnet", "Live Observer", "2 FloodNet sensors within 600 m have recorded 14 events.", False)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    q = "Is it flooding right now near 90-01 183rd Street, Queens?"
    out = syn.synthesize({"intent": "live_now", "plan": {"question": q}}, use_llm=False)
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: No active NWS") and "Yes." not in answer and "No." not in answer
    assert "**Out of scope.** Riprap reads records, not the street. For a live depth reading use the FloodNet dashboard" in out["paragraph"]
    assert out["grounding"]["answer_mode"] == "rules" and out["grounding"]["tier"] == "no_llm"
