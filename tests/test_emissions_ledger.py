"""Energy labels: hosted endpoints are always unknown, a declared wattage
gives an estimate for local endpoints, and totals appear only when every
call has a figure."""
from __future__ import annotations

from app import emissions


def _call(base_url: str) -> dict:
    with emissions.measure_call(base_url, "m") as rec:
        pass
    return rec


def test_hosted_endpoint_is_unknown_even_with_declared_watts(monkeypatch):
    monkeypatch.setenv("RIPRAP_ENERGY_WATTS", "30")
    monkeypatch.setattr(emissions, "_zeus", lambda: None)
    rec = _call("https://api.example.com/v1")
    assert rec["energy_status"] == "unknown" and rec["wh"] is None


def test_local_endpoint_with_declared_watts_is_estimated(monkeypatch):
    monkeypatch.setenv("RIPRAP_ENERGY_WATTS", "30")
    monkeypatch.setattr(emissions, "_zeus", lambda: None)
    rec = _call("http://localhost:11434/v1")
    assert rec["energy_status"] == "estimated" and rec["wh"] is not None


def test_total_only_when_every_call_has_a_figure():
    est = {"energy_status": "estimated", "wh": 0.01, "duration_s": 1.0}
    unk = {"energy_status": "unknown", "wh": None, "duration_s": 1.0}
    assert emissions.summarize([est])["total_wh"] == 0.01
    both = emissions.summarize([est, unk])
    assert both["total_wh"] is None and both["energy_status"] == "mixed"
    assert emissions.summarize([])["total_wh"] is None
