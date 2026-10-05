"""Backtest the experimental Battery surge forecast against the gauge.

    uv sync --extra ml
    python3 gpu_lock.py uv run --frozen --no-sync python scripts/backtest_surge.py   # 2025-01-01 to now
    uv run python scripts/backtest_surge.py --start 2025-06-01 --step-hours 12

Held out: the model's card gives its data as 2015-01-01 to 2024-12-31,
split 70/15/15 in time, with the checkpoint chosen on the validation part.
Every window here starts on or after 2025-01-01, so nothing scored was used
to train the model or to choose its checkpoint. For each start hour the
model reads the 1,024 hours before it and writes the next 96; the observed
residual for those 96 hours is the truth.

The same windows are scored for six baselines that need no model:

  zero         the predicted tide alone
  last_value   the last residual held (persistence)
  mean_24h     the mean of the last 24 hours held
  mean_input   the mean of the 1,024 input hours held
  damped       the last residual decaying toward the input mean,
               mean + phi**h * (last - mean), with phi fitted on 2015 to 2024
  climatology  the 2015 to 2024 mean residual of the calendar month

phi and the monthly means are fitted on the residual before 2025 only (the
series scripts/finetune_chronos2_surge.py reads, cached in
outputs/surge_cache/).

The rule, written before the result was read: the forecast stays in default
briefings only if its mean error is below every baseline's with a 95%
interval for the difference that excludes zero, and it foresees at least a
third of the distinct events that reached the minor flood stage. `rule` in
the result file says which part failed.

Writes data/experimental/surge.json, which `app.experimental.hedge` reads
for the accuracy clause of every surge sentence, and prints the table
docs/MODELS.md quotes. `scripts/backtest_surge_candidates.py` imports
`series`, `windows`, `score`, `block` and `block_ci` to score other models
on the same windows.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINES = ("zero", "last_value", "mean_24h", "mean_input", "damped", "climatology")
WORDS = {"zero": "the predicted tide alone", "last_value": "holding the last value",
         "mean_24h": "holding the last day's mean", "mean_input": "holding the mean of the hours it reads",
         "damped": "the last value fading toward the mean of the hours it reads",
         "climatology": "the month's usual value"}
FIT_END = date(2025, 1, 1)  # the model's training data ends 2024-12-31; nothing here is fitted on a later hour
SURGE_M = 0.5
EVENT_GAP_H = 48  # hours over a threshold less than two days apart are one event
MIN_EVENT_SHARE = 1 / 3
key = lambda t: t.strftime("%Y-%m-%d %H:%M")  # noqa: E731


def series(start: date, last: datetime, hourly=None):
    """Hours, residuals (m) and predicted tide (m) from the context before
    `start` to `last`. `hourly` defaults to the live NOAA fetch."""
    import numpy as np

    from app.live import ttm_battery_surge as surge

    hourly = hourly or surge.hourly
    first = datetime.combine(start, datetime.min.time(), UTC) - timedelta(hours=surge.CONTEXT_HOURS + 48)
    observed, tide = hourly("water_level", first, last), hourly("predictions", first, last)
    hours = [first.replace(minute=0, second=0, microsecond=0) + timedelta(hours=i)
             for i in range(int((last - first).total_seconds() // 3600))]
    res = np.array([observed[key(t)] - tide[key(t)] if key(t) in observed and key(t) in tide else np.nan for t in hours])
    tide_m = np.array([tide.get(key(t), np.nan) for t in hours])
    return hours, res, tide_m


def windows(hours, res, start: date, step_hours: int) -> list[int]:
    """Start indices of the complete windows on or after `start`."""
    import numpy as np

    from app.live.ttm_battery_surge import CONTEXT_HOURS as C
    from app.live.ttm_battery_surge import HORIZON_HOURS as H

    # a gap in the gauge record: the app declines such a window too (residual_history)
    return [i for i in range(C, len(hours) - H, step_hours)
            if hours[i].date() >= start and not np.isnan(res[i - C:i + H]).any()]


def score(start: str, truth, tide, minor_m: float, forecasts: dict) -> dict:
    """One window's row: the per-forecast errors and flood calls."""
    import numpy as np

    total = tide + truth
    return {"start": start, "peak_obs": float(truth.max()), "peak_abs_obs": float(np.abs(truth).max()),
            "flood_obs": bool(total.max() >= minor_m),
            **{f"mae_{k}": float(np.abs(f - truth).mean()) for k, f in forecasts.items()},
            **{f"peak_err_{k}": float(abs(f.max() - truth.max())) for k, f in forecasts.items()},
            **{f"flood_{k}": bool((tide + f).max() >= minor_m) for k, f in forecasts.items()}}


def mean(sel, col) -> float:
    import numpy as np

    return round(float(np.mean([r[col] for r in sel])), 3)


def block(sel, names) -> dict:
    return {"n_windows": len(sel), **{f"mae_{k}_m": mean(sel, f"mae_{k}") for k in names},
            **{f"peak_error_{k}_m": mean(sel, f"peak_err_{k}") for k in names}} if sel else {"n_windows": 0}


def block_ci(d, block_len: int = 14, n: int = 2000) -> list[float]:
    """A 95% interval for the mean of the per-window differences `d`, from a
    moving-block bootstrap (windows a day apart share three of four days, so
    they are resampled in runs of `block_len`)."""
    import numpy as np

    d = np.asarray(d)
    rng = np.random.default_rng(0)
    starts = rng.integers(0, len(d) - block_len + 1, size=(n, -(-len(d) // block_len)))
    boot = np.array([d[(s[:, None] + np.arange(block_len)).ravel()[:len(d)]].mean() for s in starts])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def fit_before_test(C: int, H: int) -> tuple[float, int, dict[int, float]]:
    """The damping per hour that gives the lowest mean error on one window a
    day of the residual before FIT_END, the number of windows, and the mean
    residual of each calendar month over the same years."""
    import numpy as np

    sys.path.insert(0, str(ROOT / "scripts"))
    import finetune_chronos2_surge as ft

    assert ft.END.date() == FIT_END, "the fit must end where the model's training data does"
    hours, res = ft.residuals()
    idx = [i for i in range(C, len(res) - H + 1, 24) if not np.isnan(res[i - C:i + H]).any()]
    past, truth = np.stack([res[i - C:i] for i in idx]), np.stack([res[i:i + H] for i in idx])
    m, h = past.mean(axis=1, keepdims=True), np.arange(1, H + 1)
    grid = np.round(np.arange(0.900, 1.0001, 0.001), 3)
    mae = [np.abs(m + (past[:, -1:] - m) * phi ** h - truth).mean() for phi in grid]
    month = np.array([t.month for t in hours])
    return float(grid[int(np.argmin(mae))]), len(idx), {k: float(np.nanmean(res[month == k])) for k in range(1, 13)}


def events(hit_hours: set[int]) -> list[set[int]]:
    """Hour indices grouped into events: a gap of EVENT_GAP_H or more starts a new one."""
    out: list[set[int]] = []
    last = None
    for i in sorted(hit_hours):
        if last is None or i - last >= EVENT_GAP_H:
            out.append(set())
        out[-1].add(i)
        last = i
    return out


def hits(rows, names, obs: str, call: str) -> dict:
    """For one threshold: the windows and distinct events that reached it,
    and for each forecast how many it called and its false alarms. An event
    counts as foreseen when any window holding one of its hours was called."""
    sel = [r for r in rows if r[obs]]
    evs = events(set().union(*(r[f"{obs}_hours"] for r in rows)))
    return {"windows_that_reached_it": len(sel), "events": len(evs),
            **{f"{k}_said_so": sum(r[f"{call}_{k}"] for r in sel) for k in names},
            **{f"{k}_events_said_so": sum(any(r[f"{call}_{k}"] and r[f"{obs}_hours"] & e for r in sel) for e in evs)
               for k in names},
            **{f"{k}_false_alarms": sum(r[f"{call}_{k}"] for r in rows if not r[obs]) for k in names}}


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest the experimental Battery surge forecast against the gauge.")
    ap.add_argument("--start", type=date.fromisoformat, default=FIT_END)
    ap.add_argument("--end", type=date.fromisoformat, default=None, help="default: today")
    ap.add_argument("--step-hours", type=int, default=24)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "experimental" / "surge.json")
    a = ap.parse_args()
    if a.start < FIT_END:
        ap.error(f"--start must be on or after {FIT_END}: earlier hours trained the model and fitted the baselines")

    import numpy as np

    from app.live import ttm_battery_surge as surge
    from riprap.core import http

    http.USER_AGENT = "riprap-backtest/1.0"  # a batch job, not the app

    C, H = surge.CONTEXT_HOURS, surge.HORIZON_HOURS
    phi, n_fit, monthly = fit_before_test(C, H)
    last = datetime.combine(a.end, datetime.min.time(), UTC) if a.end else datetime.now(UTC)
    hours, res, tide_m = series(a.start, last)
    minor_m = surge._flood_stages_ft()["minor"] * surge.M_PER_FT
    clim = np.array([monthly[t.month] for t in hours])

    rows, decay = [], phi ** np.arange(1, H + 1)
    for i in windows(hours, res, a.start, a.step_hours):
        past, truth = res[i - C:i], res[i:i + H]
        forecasts = {"model": np.array(surge.predict(past)), "zero": np.zeros(H),
                     "last_value": np.full(H, past[-1]), "mean_24h": np.full(H, past[-24:].mean()),
                     "mean_input": np.full(H, past.mean()), "damped": past.mean() + (past[-1] - past.mean()) * decay,
                     "climatology": clim[i:i + H]}
        r = score(key(hours[i]), truth, tide_m[i:i + H], minor_m, forecasts)
        r.update(surge_obs=bool(truth.max() >= SURGE_M), peak_model=float(forecasts["model"].max()),
                 flood_obs_hours={i + int(j) for j in np.flatnonzero(tide_m[i:i + H] + truth >= minor_m)},
                 surge_obs_hours={i + int(j) for j in np.flatnonzero(truth >= SURGE_M)},
                 **{f"surge_{k}": bool(f.max() >= SURGE_M) for k, f in forecasts.items()})
        rows.append(r)
    if not rows:
        print("no complete window in the range")
        return 1

    names = ("model", *BASELINES)
    storm = [r for r in rows if r["peak_abs_obs"] >= 0.5]
    flood, surge_hits = hits(rows, names, "flood_obs", "flood"), hits(rows, names, "surge_obs", "surge")
    mae = {k: float(np.mean([r[f"mae_{k}"] for r in rows])) for k in names}
    versus = {k: {"mae_model_minus_baseline_m": round(mae["model"] - mae[k], 4),
                  "ci95_m": block_ci([r["mae_model"] - r[f"mae_{k}"] for r in rows])} for k in BASELINES}
    best = min(BASELINES, key=mae.get)
    beats_all = all(v["ci95_m"][1] < 0 for v in versus.values())
    sees_floods = flood["model_events_said_so"] >= MIN_EVENT_SHARE * flood["events"] > 0
    out = {
        "model": surge.MODEL.repo, "revision": surge.MODEL.revision, "station": surge.STATION_ID,
        "run_date": str(date.today()), "first": rows[0]["start"][:10], "last": rows[-1]["start"][:10],
        "step_hours": a.step_hours, "context_hours": C, "horizon_hours": H,
        "held_out": {"model_training_data_ends": str(FIT_END - timedelta(days=1)), "baselines_fitted_before": str(FIT_END),
                     "first_window_starts": rows[0]["start"], "overlap_hours": 0},
        "baselines": {"damping_per_hour": phi, "damping_fit_windows": n_fit, "damping_fit_years": "2015 to 2024",
                      "climatology_monthly_mean_m": {str(k): round(v, 3) for k, v in monthly.items()}, "words": WORDS},
        # The fields the hedge sentence reads.
        "n_windows": len(rows), "mae_m": round(mae["model"], 3), "baseline_mae_m": mean(rows, "mae_mean_24h"),
        "mae_cm": round(100 * mae["model"], 1), "baseline_mae_cm": round(100 * mean(rows, "mae_mean_24h"), 1),
        "best_baseline": best, "best_baseline_words": WORDS[best], "best_baseline_mae_cm": round(100 * mae[best], 1),
        "n_flood_windows": flood["windows_that_reached_it"], "n_flood_foreseen": flood["model_said_so"],
        "n_flood_events": flood["events"], "n_flood_events_foreseen": flood["model_events_said_so"],
        "all": block(rows, names),
        "model_minus_baseline": versus,
        "mean_forecast_peak_residual_m": mean(rows, "peak_model"),
        "residual_peak_at_least_0.5_m": block(storm, names),
        "minor_flood_stage": {"stage_m_mllw": round(minor_m, 3), **flood},
        "residual_reached_0.5_m": surge_hits,
        "rule": {"text": "in default briefings only if the mean error is below every baseline's with a 95% interval "
                         "that excludes zero and at least a third of the distinct minor-flood events are foreseen",
                 "beats_every_baseline": beats_all, "foresees_a_third_of_flood_events": bool(sees_floods),
                 "in_default_briefings": bool(beats_all and sees_floods)},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
