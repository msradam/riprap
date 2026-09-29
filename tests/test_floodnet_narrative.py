"""The FloodNet peak depth names its date and says when FloodNet flags the
peak's sensor. Offline: the API calls are stubbed."""

from app.context import floodnet
from app.context.floodnet import FloodEvent, Sensor


def _stub(monkeypatch, status):
    sensors = [Sensor("frank", "Q - 183rd St", "183rd St", "Queens", status, None),
               Sensor("other", "Q - 90th Ave", "90th Ave", "Queens", "good", None)]
    events = [FloodEvent("frank", "2026-05-20T23:21:49.842", None, 1172, "flood"),
              FloodEvent("other", "2025-07-14T10:00:00", None, 300, "flood")]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: events)


def test_peak_names_its_date_and_a_flagged_sensor(monkeypatch):
    _stub(monkeypatch, "noisy")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("Peak depth recorded by these sensors: 1172 mm on 2026-05-20, "
                      "at a sensor FloodNet marks as noisy.")


def test_peak_at_a_good_sensor_has_no_flag(monkeypatch):
    _stub(monkeypatch, "good")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("Peak depth recorded by these sensors: 1172 mm on 2026-05-20.")
