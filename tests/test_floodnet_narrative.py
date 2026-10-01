"""The FloodNet peak depth names its date and comes only from sensors in
good working order; a flagged sensor is named in words, never by its raw
status code, and its highest reading is stated apart from the peak, with
its flag (FloodNet's published record and the press print that reading).
Offline: the API calls are stubbed."""

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
    assert "noisy" not in n
    assert n.endswith("Peak depth recorded by the sensors in good working order: 300 mm (11.8 in) on 2025-07-14. "
                      "1 sensor that logged events is flagged by FloodNet for maintenance, "
                      "so its depths are not used for the peak. "
                      "The highest depth a flagged sensor recorded was 1172 mm (46.1 in) on 2026-05-20.")
    assert out["peak_event"]["max_depth_mm"] == 300
    assert out["flagged_peak_event"]["max_depth_mm"] == 1172
    assert [s["status_words"] for s in out["sensors"]] == ["flagged by FloodNet for maintenance",
                                                          "in good working order"]


def test_no_good_sensor_with_an_event_means_no_peak(monkeypatch):
    _stub(monkeypatch, "needs_driverail", other="non-ota")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert "Peak depth" not in n and "driverail" not in n and "non-ota" not in n
    assert ("2 sensors that logged events are flagged by FloodNet for maintenance, "
            "so their depths are not used for the peak.") in n


def test_good_variants_count_as_good(monkeypatch):
    _stub(monkeypatch, "good - fs")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("Peak depth recorded by the sensors in good working order: 1172 mm (46.1 in) on 2026-05-20.")


def test_the_flagged_sentence_is_cited():
    from riprap.core.burr.evidence import cite

    t = ("Peak depth recorded by the sensors in good working order: 300 mm on 2025-07-14. "
         "1 sensor that logged events is flagged by FloodNet for maintenance, so its depths are not used for the peak.")
    assert cite(t, "floodnet").endswith("used for the peak [floodnet].")


def test_events_are_asked_for_up_to_now(monkeypatch):
    """FloodNet's table holds events stamped 2080; the window closes at now."""
    seen = {}
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: seen.update(v) or {"sensor_events": []})
    floodnet.flood_events_for(["frank"])
    assert "_lte:$until" in floodnet._EVENTS_Q and seen["until"][:4] <= "2027" and seen["since"] < seen["until"]
