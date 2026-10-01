"""Experimental: a 96-hour forecast of the surge residual at The Battery.

The model is the owner's fine-tune of IBM's Granite TTM r2
(`msradam/Granite-TTM-r2-Battery-Surge`, Apache-2.0, 1.5 M parameters,
CPU). It reads the last 1,024 hourly values of the residual (observed
water level minus NOAA's predicted tide) at NOAA station 8518750 and
writes the next 96. Added to NOAA's tide predictions that gives a total
water level to hold against the gauge's flood stages.

What it can answer, always through `app.experimental.hedge`:
  * how far above the predicted tide the water may run in the next four
    days, and when;
  * whether the highest total reaches the gauge's minor flood stage.

What it cannot: anything a storm brings that the gauge has not felt yet
(it has no wind or pressure input), any gauge but The Battery, any street.
The Weather Service's own forecast for the gauge is the `nws_water_forecast`
source, and an answer quotes it beside this one.

Needs the `ml` extra; without it `fetch` returns the not-installed sentence.
`scripts/backtest_surge.py` scores it against the gauge.
"""
from __future__ import annotations

import importlib.util
import logging
import threading
from datetime import UTC, datetime, timedelta

from app import experimental

log = logging.getLogger("riprap.ttm_battery_surge")

MODEL = experimental.MODELS["surge"]
STATION_ID, STATION_NAME, NWPS_ID = "8518750", "The Battery", "BATN6"
NOAA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CONTEXT_HOURS, HORIZON_HOURS = 1024, 96
M_PER_FT = 0.3048
# A plain place briefing quotes the forecast only when it is notable: a
# residual of a foot or more, or a total at the minor flood stage.
NOTABLE_RESIDUAL_M = 0.3
MAX_STALE_HOURS = 6  # a forecast from older readings is not about the hours ahead

ML_MISSING = not (importlib.util.find_spec("torch") and importlib.util.find_spec("tsfm_public"))
_MODEL = None
_LOAD_LOCK = threading.Lock()  # pebbles run on threads; transformers' lazy imports are not thread-safe


def _model():
    global _MODEL
    with _LOAD_LOCK:
        if _MODEL is None:
            from huggingface_hub import snapshot_download
            from transformers import (
                PreTrainedModel,  # noqa: F401 - resolves the lazy registry under threads
            )
            from tsfm_public import TinyTimeMixerForPrediction

            path = snapshot_download(MODEL.repo, revision=MODEL.revision,
                                     allow_patterns=["config.json", "*.safetensors"])
            _MODEL = TinyTimeMixerForPrediction.from_pretrained(path, use_safetensors=True).eval()
    return _MODEL


def predict(residuals_m) -> list[float]:
    """The next 96 hourly residuals (m) from the last 1,024."""
    import numpy as np
    import torch

    past = torch.from_numpy(np.asarray(residuals_m, dtype="float32")[-CONTEXT_HOURS:]).reshape(1, CONTEXT_HOURS, 1)
    with torch.no_grad():
        out = _model()(past_values=past)
    return [float(v) for v in out.prediction_outputs.reshape(-1)]


def hourly(product: str, start: datetime, end: datetime) -> dict[str, float]:
    """One NOAA product at The Battery, hourly, metres above MLLW, keyed
    by "YYYY-MM-DD HH:MM" UTC. `water_level` or `predictions`."""
    from riprap.core import http

    out: dict[str, float] = {}
    cur = start
    while cur < end:  # the API serves at most 31 days of hourly data per request
        nxt = min(cur + timedelta(days=30), end)
        params = {"station": STATION_ID, "product": product, "datum": "MLLW", "units": "metric", "time_zone": "gmt",
                  "format": "json", "application": "riprap", "begin_date": cur.strftime("%Y%m%d %H:%M"),
                  "end_date": nxt.strftime("%Y%m%d %H:%M"),
                  "interval": "h"}
        r = http.get(NOAA_API, params=params, timeout=30, ttl_s=1800)
        r.raise_for_status()
        body = r.json()
        if body.get("error"):  # NOAA answers 200 with an error body
            raise RuntimeError(f"NOAA: {body['error'].get('message', body['error'])}")
        for row in body.get("data") or body.get("predictions") or []:
            if row.get("v") not in (None, ""):
                out[row["t"]] = float(row["v"])
        cur = nxt
    return out


def residual_history(end: datetime, hours: int = CONTEXT_HOURS) -> tuple[list[str], list[float]]:
    """The `hours` consecutive hourly residuals ending at the last hour the
    gauge reported, oldest first, with their times. Empty when that hour is
    more than MAX_STALE_HOURS before `end` or any hour of the run is
    missing: the model was trained and tested on unbroken hours
    (scripts/backtest_surge.py skips such windows too), so the caller
    declines."""
    fmt = "%Y-%m-%d %H:%M"
    start = end - timedelta(hours=hours + 48)
    observed, predicted = hourly("water_level", start, end), hourly("predictions", start, end)
    common = [t for t in observed if t in predicted]
    if not common:
        return [], []
    last = datetime.strptime(max(common), fmt).replace(tzinfo=UTC)
    times = [(last - timedelta(hours=i)).strftime(fmt) for i in range(hours - 1, -1, -1)]
    if end - last > timedelta(hours=MAX_STALE_HOURS) or any(t not in observed or t not in predicted for t in times):
        return [], []
    return times, [observed[t] - predicted[t] for t in times]


def _flood_stages_ft() -> dict[str, float]:
    """The Weather Service's flood stages for the gauge, ft above MLLW."""
    from app.context import nws_water

    cats = (nws_water._json(NWPS_ID).get("flood") or {}).get("categories") or {}
    return {k: float(v["stage"]) for k, v in cats.items()
            if k in nws_water.STAGES and v.get("stage") is not None and float(v["stage"]) > -900}


def summarize(last_time: str, forecast_m: list[float], tide_m: dict[str, float], stages_ft: dict[str, float]) -> dict:
    """The value and the hedged sentence for one forecast. `last_time` is
    the hour of the last observation; hour i of the forecast is i+1 hours
    after it."""
    t0 = datetime.strptime(last_time, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    stamp = [(t0 + timedelta(hours=i + 1)) for i in range(len(forecast_m))]
    when = lambda t: t.strftime("%Y-%m-%d %H:%M")  # noqa: E731
    peak_i = max(range(len(forecast_m)), key=forecast_m.__getitem__)
    peak_m = forecast_m[peak_i]
    totals = [(t, (tide_m[when(t)] + r) / M_PER_FT) for t, r in zip(stamp, forecast_m, strict=True) if when(t) in tide_m]
    out = {"available": True, "model": MODEL.repo, "revision": MODEL.revision, "station_id": STATION_ID,
           "station_name": STATION_NAME, "context_hours": CONTEXT_HOURS, "horizon_hours": len(forecast_m),
           "last_observation_utc": last_time, "forecast_peak_residual_m": round(peak_m, 2),
           "forecast_peak_residual_ft": round(peak_m / M_PER_FT, 1),
           "forecast_peak_residual_time_utc": when(stamp[peak_i]),
           "forecast_residual_m": [round(v, 3) for v in forecast_m], "flood_stages_ft": stages_ft}
    if peak_m > 0.005:
        statement = (f"the water at {STATION_NAME} may run up to {peak_m:.2f} m ({peak_m / M_PER_FT:.1f} ft) above "
                     f"NOAA's predicted tide in the next {len(forecast_m)} hours, counted from {last_time} UTC, most "
                     f"around {when(stamp[peak_i])} UTC")
    else:
        statement = (f"the water at {STATION_NAME} may stay at or below NOAA's predicted tide for the next "
                     f"{len(forecast_m)} hours, counted from {last_time} UTC")
    category = None
    if totals:
        peak_t, peak_total = max(totals, key=lambda p: p[1])
        peak_total = round(peak_total, 1)  # the stage is compared with the figure the sentence prints
        category = next((k for k in ("major", "moderate", "minor") if k in stages_ft and peak_total >= stages_ft[k]), None)
        out.update(forecast_peak_total_ft_mllw=peak_total, forecast_peak_total_time_utc=when(peak_t))
        statement += (f"; added to the predicted tide, the highest total would be {peak_total:.1f} ft above MLLW on "
                      f"{when(peak_t)} UTC")
        if category:
            statement += f", which would reach the gauge's {category} flood stage of {stages_ft[category]:.1f} ft"
        elif "minor" in stages_ft:
            statement += f", below the gauge's minor flood stage of {stages_ft['minor']:.1f} ft"
    out["flood_category"] = category
    out["notable"] = bool(category) or abs(peak_m) >= NOTABLE_RESIDUAL_M
    out["narrative"] = experimental.hedge("surge", statement, forecast=True)
    return out


def fetch() -> dict:
    """The pebble value. Always a dict: `available` False with a sentence
    saying why when the model is not installed or NOAA did not answer."""
    if ML_MISSING:
        return {"available": False, "installed": False,
                "narrative": experimental.not_installed("surge", "the Battery surge forecast model")}
    try:
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        times, residuals = residual_history(now)
        if len(residuals) < CONTEXT_HOURS:
            return {"available": False, "installed": True,
                    "error": f"the gauge's last {CONTEXT_HOURS} hourly readings have a gap or end more than "
                             f"{MAX_STALE_HOURS} hours ago; the model needs them unbroken"}
        tide = hourly("predictions", now - timedelta(hours=6), now + timedelta(hours=HORIZON_HOURS + 6))
        return {**summarize(times[-1], predict(residuals), tide, _flood_stages_ft()), "installed": True}
    except Exception as e:  # noqa: BLE001 - a failed forecast is a source that did not answer
        log.exception("ttm_battery_surge failed")
        return {"available": False, "installed": True, "error": f"{type(e).__name__}: {e}"}
