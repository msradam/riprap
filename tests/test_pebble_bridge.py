"""Smoke test for the pebble bridge — the FSM-facing helper that the legacy
step_* functions now delegate to.

Asserts:
  - registry loads from RIPRAP_DEPLOYMENT (default deployments/nyc)
  - fetch_pebble returns (value, trace_summary, None) for a working pebble
  - trace_summary keys match the manifest's trace_summary block
"""
from __future__ import annotations

from riprap.core.pebbles.bridge import fetch_pebble

TEST_LAT = 40.7282
TEST_LON = -73.7949


def test_fetch_pebble_ida_hwm_returns_value_and_trace():
    value, trace_summary, err = fetch_pebble("ida_hwm", TEST_LAT, TEST_LON)
    assert err is None
    assert value is not None
    assert "n_within_radius" in value
    # Trace summary uses renamed keys per manifest.
    assert set(trace_summary.keys()) == {
        "n_within_800m", "max_height_above_gnd_ft", "nearest_m",
    }
    assert trace_summary["n_within_800m"] == value["n_within_radius"]
    assert trace_summary["nearest_m"] == value["nearest_dist_m"]


def test_a_failed_source_gives_a_plain_reason():
    """The "Not checked." section printed a raw exception ("python_call:
    summary_for_point raised: HTTP 429 after 0/1 chunks; catch
    QuotaExhausted..."). A reader gets the reason in plain words."""
    from riprap.core.pebbles.bridge import plain_reason

    assert plain_reason("python_call: summary_for_point raised: HTTP 429 after 0/1 chunks; catch QuotaExhausted to resume") == \
        "the service refused the request: too many requests (HTTP 429)"
    assert plain_reason("rest_json: HTTP error: Server error '503 Service Unavailable' for url 'https://x'") == \
        "the service reported an error of its own (HTTP 503)"
    assert plain_reason("python_call: preliminary_for_point raised: timed out") == "the service did not answer in time"
    assert plain_reason("no answer within 45 s") == "the service did not answer in time"
    assert plain_reason("FloodNet did not respond when this briefing ran.") == "FloodNet did not respond when this briefing ran."
    assert plain_reason("python_call: complaints raised: more than 50000 flood-related 311 requests; not counted") == \
        "more than 50000 flood-related 311 requests; not counted"
