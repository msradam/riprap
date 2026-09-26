"""Granite TimeSeries TTM r2: the shared in-process runner plus the
experimental per-address 311 flood-complaint forecast.

The zero-shot Battery surge nowcast that used to live here is deleted:
it had no evaluation and the fine-tuned `ttm_battery_surge` supersedes
it. The 311 forecast is univariate with no rainfall input and no
backtest, so it is labelled experimental and makes no trend claim.

Citation: Ekambaram, V., et al. (2024). "Tiny Time Mixers (TTMs):
Fast Pre-trained Models for Enhanced Zero/Few-Shot Forecasting of
Multivariate Time Series." NeurIPS 2024.
"""
from __future__ import annotations

import importlib.util
import logging
import threading

import numpy as np

from riprap.core import http

log = logging.getLogger("riprap.ttm_forecast")

CITATION = ("IBM Granite TimeSeries TTM r2 (Ekambaram et al. 2024, NeurIPS); "
            "ibm-granite/granite-timeseries-ttm-r2 via granite-tsfm")

CONTEXT_LENGTH = 512
PREDICTION_LENGTH = 96

# 311 daily-counts forecast — TTM r2's smallest pretrained config is
# 512 context which is awkward for weekly counts on a single address.
# Daily aggregation (512 days ≈ 17 months of complaint history) lets
# the model run natively at its standard resolution; we forecast the
# next 96 days (~3 months).
DAILY_CONTEXT = 512
DAILY_PREDICTION = 96
NYC_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
NYC_311_FLOOD_DESCRIPTORS = (
    "Sewer Backup (Use Comments) (SA)",
    "Catch Basin Clogged/Flooding (Use Comments) (SC)",
    "Street Flooding (SJ)",
    "Manhole Overflow (Use Comments) (SA1)",
    "Flooding on Street",
)


# ---- Lazy-loaded model singleton -----------------------------------------

_MODELS: dict[tuple[int, int], object] = {}
_MODEL_LOAD_ERROR: str | None = None
# One lock for every TTM load in the process (this module, floodnet_forecast
# and ttm_battery_surge): the Stones fan-out runs pebbles on threads, and
# transformers' lazy imports fail when two threads load models at once.
MODEL_LOAD_LOCK = threading.Lock()
# Set when the optional `ml` extra is absent; TTM pebbles then skip
# before any network call.
ML_MISSING = (None if importlib.util.find_spec("torch") and importlib.util.find_spec("tsfm_public")
              else "the ml extra is not installed (uv sync --extra ml)")


def _load_model(context_length: int = CONTEXT_LENGTH,
                prediction_length: int = PREDICTION_LENGTH):
    """TTM r2 is configured per (context, prediction) length pair. Cache
    by that pair so the surge forecaster (512→96) and the weekly 311
    forecaster (52→4) each get their own model handle on first use."""
    global _MODEL_LOAD_ERROR
    key = (context_length, prediction_length)
    if key in _MODELS:
        return _MODELS[key]
    with MODEL_LOAD_LOCK:
        return _load_model_locked(key)


def _load_model_locked(key: tuple[int, int]):
    global _MODEL_LOAD_ERROR
    context_length, prediction_length = key
    if key in _MODELS:
        return _MODELS[key]
    if _MODEL_LOAD_ERROR is not None:
        return None
    if ML_MISSING:
        _MODEL_LOAD_ERROR = ML_MISSING
        return None
    try:
        import torch  # noqa: F401

        # Import the registered class names before get_model so that
        # transformers' lazy registry can resolve them by string.
        from transformers import PreTrainedModel  # noqa: F401
        from tsfm_public import TinyTimeMixerForPrediction  # noqa: F401
        from tsfm_public.toolkit.get_model import get_model
        m = get_model(
            "ibm-granite/granite-timeseries-ttm-r2",
            context_length=context_length,
            prediction_length=prediction_length,
        )
        m.eval()
        _MODELS[key] = m
        log.info("TTM r2 loaded (context=%d horizon=%d)",
                 context_length, prediction_length)
        return m
    except Exception as e:
        _MODEL_LOAD_ERROR = repr(e)
        log.exception("TTM model load failed; future calls will be skipped")
        return None


# ---- Forecast --------------------------------------------------------------

def _run_ttm(history: np.ndarray,
             context_length: int = CONTEXT_LENGTH,
             prediction_length: int = PREDICTION_LENGTH,
             cadence: str = "h") -> np.ndarray | None:
    """Channel-wise standardize, run the in-process CPU model,
    de-standardize. Returns a `prediction_length`-step forecast in input
    units, or None when the model cannot load."""
    global _MODEL_LOAD_ERROR
    mu = float(history.mean())
    sigma = float(history.std() + 1e-6)
    normed = (history - mu) / sigma

    try:
        model = _load_model(context_length, prediction_length)
    except Exception as e:
        _MODEL_LOAD_ERROR = f"{type(e).__name__}: {e}"
        log.exception("TTM model load raised: %r", e)
        return None
    if model is None:
        return None
    try:
        import torch
    except ImportError:
        _MODEL_LOAD_ERROR = "torch not available on this deployment"
        return None
    x = torch.from_numpy(normed.astype(np.float32))[None, :, None]
    try:
        with torch.no_grad():
            out = model(past_values=x)
    except Exception as e:
        _MODEL_LOAD_ERROR = f"{type(e).__name__}: {e}"
        log.exception("TTM inference failed: %r", e)
        return None
    pred = out.prediction_outputs[0, :, 0].cpu().numpy()
    return pred * sigma + mu


# ---- Per-address daily 311 flood-complaint forecast ----------------------

def _fetch_311_flood_daily(lat: float, lon: float,
                            radius_m: int = 200,
                            days: int = DAILY_CONTEXT,
                            ) -> tuple[np.ndarray, list[str]] | None:
    """Pull `days` of daily flood-complaint counts within `radius_m` of
    (lat, lon) from NYC OpenData. Returns (counts_array_length_days,
    date_labels) or None on failure. Missing days are zero-filled."""
    from collections import defaultdict
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    end = _dt.utcnow().date()
    start = end - _td(days=days + 1)
    descs = " OR ".join(f"descriptor='{d}'" for d in NYC_311_FLOOD_DESCRIPTORS)
    where = (
        f"created_date between '{start.isoformat()}T00:00:00' and "
        f"'{end.isoformat()}T23:59:59' AND "
        f"latitude IS NOT NULL AND longitude IS NOT NULL AND "
        f"({descs}) AND "
        f"within_circle(location, {lat}, {lon}, {radius_m})"
    )
    try:
        r = http.get(NYC_311_URL,
                      params={"$select": "created_date",
                              "$where": where,
                              "$limit": "50000"},
                      timeout=20.0)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        log.warning("311 flood fetch for TTM failed: %r", e)
        return None

    counts: dict[str, int] = defaultdict(int)
    for row in rows or []:
        ds = (row.get("created_date") or "")[:10]
        if not ds:
            continue
        counts[ds] += 1

    series: list[int] = []
    labels: list[str] = []
    for i in range(days):
        d = end - _td(days=days - 1 - i)
        d_iso = d.isoformat()
        labels.append(d_iso)
        series.append(counts.get(d_iso, 0))
    return np.array(series, dtype=np.float32), labels


def weekly_311_forecast_for_point(lat: float, lon: float,
                                  radius_m: int = 200) -> dict:
    """TTM r2 zero-shot forecast on per-address daily 311
    flood-complaint counts. Despite the name — kept for FSM-call-site
    stability — this now operates on daily resolution (TTM r2's
    smallest native config is 512 context, awkward for weekly).
    History: 512 days (~17 months); forecast: 96 days (~3 months).
    Returns daily and weekly summaries so the reconciler narration
    stays human-readable.

    Designed not to raise. Returns `available: False` with a reason
    field on any failure path."""
    if ML_MISSING:
        return {"available": False, "reason": ML_MISSING}
    series = _fetch_311_flood_daily(lat, lon, radius_m=radius_m)
    if series is None:
        return {"available": False, "reason": "311 history fetch failed"}
    history, labels = series
    forecast = _run_ttm(history, DAILY_CONTEXT, DAILY_PREDICTION)
    if forecast is None:
        return {"available": False,
                "reason": _MODEL_LOAD_ERROR or "TTM inference failed"}

    fc_clipped = np.clip(forecast, 0, None)
    hist_total = int(history.sum())
    hist_mean_per_day = float(history.mean())
    hist_recent_mean_30d = float(history[-30:].mean())
    fc_total = float(fc_clipped.sum())
    fc_mean_per_day = float(fc_clipped.mean())
    fc_peak_day = float(fc_clipped.max())
    fc_peak_day_offset = int(fc_clipped.argmax()) + 1

    # Aggregate to weekly equivalents for the briefing narration —
    # readers think in weeks, not days.
    history_weekly_mean = hist_mean_per_day * 7
    forecast_weekly_mean = fc_mean_per_day * 7

    return {
        "available": True,
        "radius_m": radius_m,
        "days_context": DAILY_CONTEXT,
        "days_horizon": DAILY_PREDICTION,
        "history_total_complaints": hist_total,
        "history_mean_per_day": round(hist_mean_per_day, 3),
        "history_recent_30d_mean": round(hist_recent_mean_30d, 3),
        "history_weekly_equivalent": round(history_weekly_mean, 2),
        "forecast_total_next_horizon": round(fc_total, 1),
        "forecast_mean_per_day": round(fc_mean_per_day, 3),
        "forecast_weekly_equivalent": round(forecast_weekly_mean, 2),
        "forecast_peak_day": round(fc_peak_day, 2),
        "forecast_peak_day_offset": fc_peak_day_offset,
        "context_window_start": labels[0] if labels else None,
        "context_window_end": labels[-1] if labels else None,
    }
