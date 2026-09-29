"""The FloodNet peak depth names its date and comes only from sensors in
good working order; a flagged sensor is named in words, never by its raw
status code. Offline: the API calls are stubbed."""

from app.context import floodnet
from app.context.floodnet import FloodEvent, Sensor


def _stub(monkeypatch, status, other="good"):
    sensors = [Sensor("frank", "Q - 183rd St", "183rd St", "Queens", status, None),
               Sensor("other", "Q - 90th Ave", "90th Ave", "Queens", other, None)]
    events = [FloodEvent("frank", "2026-05-20T23:21:49.842", None, 1172, "flood"),
              FloodEvent("other", "2025-07-14T10:00:00", None, 300, "flood")]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: events)


def test_a_flagged_sensor_is_not_the_peak(monkeypatch):
    _stub(monkeypatch, "noisy")
    out = floodnet.summary_for_point(40.71, -73.78)
    n = out["narrative"]
    assert "1172" not in n and "noisy" not in n
    assert ("Peak depth recorded by the sensors in good working order: 300 mm on 2025-07-14. "
            "1 of the sensors that logged events is flagged by FloodNet for maintenance, "
            "so its depths are not used for the peak.") in n
    assert out["peak_event"]["max_depth_mm"] == 300
    assert [s["status_words"] for s in out["sensors"]] == ["flagged by FloodNet for maintenance",
                                                          "in good working order"]


def test_no_good_sensor_with_an_event_means_no_peak(monkeypatch):
    _stub(monkeypatch, "needs_driverail", other="non-ota")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert "Peak depth" not in n and "driverail" not in n and "non-ota" not in n
    assert n.endswith("2 of the sensors that logged events are flagged by FloodNet for maintenance, "
                      "so their depths are not used for the peak.")


def test_good_variants_count_as_good(monkeypatch):
    _stub(monkeypatch, "good - fs")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("Peak depth recorded by the sensors in good working order: 1172 mm on 2026-05-20.")
