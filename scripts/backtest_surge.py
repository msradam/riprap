"""Backtest the experimental Battery surge forecast against the gauge.

    uv sync --extra ml
    uv run python scripts/backtest_surge.py            # 2025-01-01 to now
    uv run python scripts/backtest_surge.py --start 2025-06-01 --step-hours 12

Every window starts after the model's training data ends (2024-12-31).
For each start hour the model reads the 1,024 hours before it and writes
the next 96; the observed residual for those 96 hours is the truth. The
same windows are scored for three one-line baselines: zero (the predicted
tide alone), the last value held, and the mean of the last 24 hours held.

Writes data/experimental/surge.json, which `app.experimental.hedge` reads
for the accuracy clause of every surge sentence, and prints the table
docs/MODELS.md quotes. `scripts/backtest_surge_candidates.py` imports
`series`, `windows`, `score` and `block` to score other models on the
same windows.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINES = ("zero", "last_value", "mean_24h")
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest the experimental Battery surge forecast against the gauge.")
    ap.add_argument("--start", type=date.fromisoformat, default=date(2025, 1, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=None, help="default: today")
    ap.add_argument("--step-hours", type=int, default=24)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "experimental" / "surge.json")
    a = ap.parse_args()

    import numpy as np

    from app.live import ttm_battery_surge as surge

    C, H = surge.CONTEXT_HOURS, surge.HORIZON_HOURS
    last = datetime.combine(a.end, datetime.min.time(), UTC) if a.end else datetime.now(UTC)
    hours, res, tide_m = series(a.start, last)
    minor_m = surge._flood_stages_ft()["minor"] * surge.M_PER_FT

    rows = []
    for i in windows(hours, res, a.start, a.step_hours):
        past, truth = res[i - C:i], res[i:i + H]
        forecasts = {"model": np.array(surge.predict(past)), "zero": np.zeros(H),
                     "last_value": np.full(H, past[-1]), "mean_24h": np.full(H, past[-24:].mean())}
        rows.append(score(key(hours[i]), truth, tide_m[i:i + H], minor_m, forecasts))
    if not rows:
        print("no complete window in the range")
        return 1

    names = ("model", *BASELINES)
    storm = [r for r in rows if r["peak_abs_obs"] >= 0.5]
    floods = [r for r in rows if r["flood_obs"]]
    out = {
        "model": surge.MODEL.repo, "revision": surge.MODEL.revision, "station": surge.STATION_ID,
        "run_date": str(date.today()), "first": rows[0]["start"][:10], "last": rows[-1]["start"][:10],
        "step_hours": a.step_hours, "context_hours": C, "horizon_hours": H,
        # The fields the hedge sentence reads.
        "n_windows": len(rows), "mae_m": mean(rows, "mae_model"), "baseline_mae_m": mean(rows, "mae_mean_24h"),
        "mae_cm": round(100 * mean(rows, "mae_model"), 1), "baseline_mae_cm": round(100 * mean(rows, "mae_mean_24h"), 1),
        "n_flood_windows": len(floods), "n_flood_foreseen": sum(r["flood_model"] for r in floods),
        "all": block(rows, names),
        "residual_peak_at_least_0.5_m": block(storm, names),
        "minor_flood_stage": {
            "stage_m_mllw": round(minor_m, 3), "windows_that_reached_it": len(floods),
            **{f"{k}_said_so": sum(r[f"flood_{k}"] for r in floods) for k in names},
            **{f"{k}_false_alarms": sum(r[f"flood_{k}"] for r in rows if not r["flood_obs"]) for k in names}},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
