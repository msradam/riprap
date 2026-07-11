from __future__ import annotations

import time

from app import power_mac


def test_combined_power_regex_extracts_milliwatts():
    line = "Combined Power (CPU + GPU + ANE): 4321 mW\n"
    m = power_mac._COMBINED_RE.search(line)
    assert m is not None
    assert float(m.group(1)) == 4321.0


def test_read_instant_w_none_when_no_sample_yet(monkeypatch):
    monkeypatch.setattr(power_mac, "_started", True)
    monkeypatch.setattr(power_mac, "_last_w", None)
    assert power_mac.read_instant_w() is None


def test_read_instant_w_returns_fresh_sample(monkeypatch):
    monkeypatch.setattr(power_mac, "_started", True)
    monkeypatch.setattr(power_mac, "_last_w", 12.5)
    monkeypatch.setattr(power_mac, "_last_seen", time.monotonic())
    assert power_mac.read_instant_w() == 12.5


def test_read_instant_w_none_when_stale(monkeypatch):
    monkeypatch.setattr(power_mac, "_started", True)
    monkeypatch.setattr(power_mac, "_last_w", 12.5)
    monkeypatch.setattr(power_mac, "_last_seen", time.monotonic() - 999)
    assert power_mac.read_instant_w() is None
