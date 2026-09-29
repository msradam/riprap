"""The tide residual compares the observation with the prediction for the
same time, not the first prediction of the hour."""

from app.context.noaa_tides import _prediction_at

PRED = [{"t": "2026-09-29 16:00", "v": "1.10"}, {"t": "2026-09-29 16:18", "v": "1.40"},
        {"t": "2026-09-29 16:24", "v": "1.50"}, {"t": "2026-09-29 16:30", "v": "1.60"}]


def test_prediction_for_the_observation_time():
    assert _prediction_at(PRED, "2026-09-29 16:24")["v"] == "1.50"
    assert _prediction_at(PRED, "2026-09-29 16:21")["v"] == "1.40"


def test_no_time_or_bad_time_falls_back_to_the_first():
    assert _prediction_at(PRED, None)["v"] == "1.10"
    assert _prediction_at(PRED, "not a time")["v"] == "1.10"
    assert _prediction_at([], "2026-09-29 16:24") is None
