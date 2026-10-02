"""Score newer zero-shot forecasters on the Battery surge backtest windows.

    python3 gpu_lock.py uv run --with 'chronos-forecasting==2.3.2' \\
        python scripts/backtest_surge_candidates.py

Reuses the series, window selection and metrics of scripts/backtest_surge.py,
so the windows are the 635 of data/experimental/surge.json (one a day,
2025-01-01 to 2026-09-27) and the current model and baselines are rescored
in the same run. Every candidate reads the same 1,024 hours and writes 96,
zero-shot, on CPU, from safetensors pinned to a commit. Models that give
quantiles are scored on the median; the flood-stage question is also asked
of their 90th percentile. NOAA series are cached under outputs/surge_cache/.

With --finetuned outputs/surge_models/chronos2_battery the Battery fine-tune
of Chronos-2 (scripts/finetune_chronos2_surge.py, trained before 2024-07-01, checkpoint chosen on the rest of 2024)
is scored too, as chronos_2_battery_ft.

Writes data/experimental/surge_candidates.json.
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import sys
import traceback
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import backtest_surge as bt  # noqa: E402

CACHE = ROOT / "outputs" / "surge_cache"
BATCH = 32

CANDIDATES = {
    # The repo's main branch is the 512-in, 30-out model; this branch is 1,024 in, 96 out.
    "granite_ttm_r3": {"repo": "ibm-granite/granite-timeseries-ttm-r3", "ref": "1024-96-r3", "package": "granite-tsfm"},
    "granite_flowstate_r1_1": {"repo": "ibm-granite/granite-timeseries-flowstate-r1", "ref": "r1.1",
                               "package": "granite-tsfm"},
    "granite_patchtst_fm_r2": {"repo": "ibm-granite/granite-timeseries-patchtst-fm-r2", "ref": "main",
                               "package": "granite-tsfm",
                               "licence_note": "Card metadata says openmdw-1.0. The card's License section and the "
                                               "repo's LICENSE file say it is dual-licensed under OpenMDW 1.0 and "
                                               "Apache 2.0, at the user's choice."},
    "chronos_2": {"repo": "amazon/chronos-2", "ref": "main", "package": "chronos-forecasting"},
}


def cached_hourly(product: str, start: datetime, end: datetime) -> dict[str, float]:
    from app.live import ttm_battery_surge as surge

    path = CACHE / f"{product}_{start:%Y%m%d%H}_{end:%Y%m%d%H%M}.json"
    if path.exists():
        return json.loads(path.read_text())
    out = surge.hourly(product, start, end)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def snapshot(repo: str, sha: str) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(repo, revision=sha, allow_patterns=["config.json", "*.safetensors"])


def batched(fn, past):
    """Run fn over the windows in batches; fn returns (median, p90 or None), each (n, 96)."""
    import numpy as np
    import torch

    meds, p90s = [], []
    with torch.no_grad():
        for j in range(0, len(past), BATCH):
            m, q = fn(torch.from_numpy(past[j:j + BATCH].astype("float32")))
            meds.append(np.asarray(m, dtype=float))
            p90s.append(None if q is None else np.asarray(q, dtype=float))
    return np.concatenate(meds), (None if p90s[0] is None else np.concatenate(p90s))


def run_ttm_r3(path, past, H):
    from tsfm_public import TinyTimeMixerForPrediction

    model = TinyTimeMixerForPrediction.from_pretrained(path, use_safetensors=True).eval()
    qs = model.multi_quantile_head_block.quantile_list
    i50, i90 = qs.index(0.5), qs.index(0.9)

    def fn(x):  # prediction_outputs is the median quantile
        q = model(past_values=x.unsqueeze(-1)).quantile_outputs  # (batch, quantiles, horizon, channels)
        return q[:, i50, :, 0], q[:, i90, :, 0]
    return batched(fn, past)


def run_flowstate(path, past, H):
    from tsfm_public import FlowStateForPrediction

    model = FlowStateForPrediction.from_pretrained(path, use_safetensors=True).eval()
    qs = model.config.quantiles
    i50, i90 = qs.index(0.5), qs.index(0.9)

    def fn(x):  # hourly data: the card's scale factor is 1.0
        q = model(past_values=x.unsqueeze(-1), batch_first=True, scale_factor=1.0, prediction_length=H,
                  prediction_type="median").quantile_outputs  # (batch, quantiles, horizon, channels)
        return q[:, i50, :, 0], q[:, i90, :, 0]
    return batched(fn, past)


def run_patchtst_fm(path, past, H):
    from tsfm_public import PatchTSTFMForPrediction

    model = PatchTSTFMForPrediction.from_pretrained(path, use_safetensors=True).eval()

    def fn(x):
        q = model(past_values=x.unsqueeze(-1), prediction_length=H, quantile_levels=[0.5, 0.9]).quantile_outputs
        q = q.reshape(q.shape[0], 2, H)  # (batch, quantiles, horizon)
        return q[:, 0], q[:, 1]
    return batched(fn, past)


def run_chronos2(path, past, H):
    import torch
    from chronos import Chronos2Pipeline

    pipe = Chronos2Pipeline.from_pretrained(path, device_map="cpu", use_safetensors=True)

    def fn(x):
        q, _ = pipe.predict_quantiles(x.unsqueeze(1), prediction_length=H, quantile_levels=[0.5, 0.9])
        q = torch.stack(q)  # (batch, variates, horizon, quantiles)
        return q[:, 0, :, 0], q[:, 0, :, 1]
    return batched(fn, past)


RUNNERS = {"granite_ttm_r3": run_ttm_r3, "granite_flowstate_r1_1": run_flowstate,
           "granite_patchtst_fm_r2": run_patchtst_fm, "chronos_2": run_chronos2}


def version(pkg: str) -> str | None:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", type=date.fromisoformat, default=date(2025, 1, 1))
    # The last window of surge.json starts 2026-09-27 00:00 and needs 96 hours after it.
    ap.add_argument("--end", type=datetime.fromisoformat, default=datetime(2026, 10, 1, 1, tzinfo=UTC))
    ap.add_argument("--step-hours", type=int, default=24)
    ap.add_argument("--only", nargs="*", default=list(CANDIDATES), help="candidate keys to run")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "experimental" / "surge_candidates.json")
    ap.add_argument("--finetuned", type=Path, default=None,
                    help="a Chronos-2 fine-tune from scripts/finetune_chronos2_surge.py, scored as chronos_2_battery_ft")
    a = ap.parse_args()

    import numpy as np
    from huggingface_hub import HfApi

    from app.live import ttm_battery_surge as surge

    C, H = surge.CONTEXT_HOURS, surge.HORIZON_HOURS
    end = a.end if a.end.tzinfo else a.end.replace(tzinfo=UTC)
    hours, res, tide_m = bt.series(a.start, end, hourly=cached_hourly)
    idx = bt.windows(hours, res, a.start, a.step_hours)
    minor_m = surge._flood_stages_ft()["minor"] * surge.M_PER_FT
    past = np.stack([res[i - C:i] for i in idx])
    truth = np.stack([res[i:i + H] for i in idx])
    tide = np.stack([tide_m[i:i + H] for i in idx])
    print(f"{len(idx)} windows, {hours[idx[0]]:%Y-%m-%d} to {hours[idx[-1]]:%Y-%m-%d}", file=sys.stderr)

    api = HfApi()
    points = {"current": np.stack([surge.predict(p) for p in past]), "zero": np.zeros_like(truth),
              "last_value": np.repeat(past[:, -1:], H, axis=1),
              "mean_24h": np.repeat(past[:, -24:].mean(axis=1, keepdims=True), H, axis=1)}
    p90 = {}
    meta = {"current": {"repo": surge.MODEL.repo, "commit": surge.MODEL.revision, "licence": "apache-2.0",
                        "package": "granite-tsfm", "package_version": version("granite-tsfm"),
                        "context_hours": C, "point": "the model's output"},
            **{b: {"baseline": True} for b in bt.BASELINES}}
    for name in a.only + (["chronos_2_battery_ft"] if a.finetuned else []):
        if name == "chronos_2_battery_ft":  # local weights from scripts/finetune_chronos2_surge.py
            train = json.loads((a.finetuned / "training.json").read_text())
            m = meta[name] = {"path": str(a.finetuned.resolve().relative_to(ROOT)), "licence": "apache-2.0",
                              "package": "chronos-forecasting", "package_version": version("chronos-forecasting"),
                              "context_hours": C, "finetune": {k: v for k, v in train.items() if k != "curve"}}
            try:
                med, q90 = run_chronos2(str(a.finetuned), past, H)
                if not np.isfinite(med).all():
                    raise RuntimeError("non-finite forecast values")
                points[name], p90[name], m["point"] = med, q90, "median"
            except Exception as e:  # noqa: BLE001 - recorded like any failed candidate
                m["error"] = f"{type(e).__name__}: {e}"
                print(f"{name} failed: {m['error']}", file=sys.stderr)
            continue
        spec = CANDIDATES[name]
        m = meta[name] = {"repo": spec["repo"], "ref": spec["ref"], "package": spec["package"],
                          "package_version": version(spec["package"]), "context_hours": C}
        try:
            info = api.model_info(spec["repo"], revision=spec["ref"])
            m["commit"] = info.sha
            card = api.model_info(spec["repo"]).card_data  # branch revisions may carry no README
            m["licence"] = (card or {}).get("license") if card else None
            if "licence_note" in spec:
                m["licence_note"] = spec["licence_note"]
            files = [s.rfilename for s in info.siblings]
            if not any(f.endswith(".safetensors") for f in files):
                raise RuntimeError(f"no safetensors at {info.sha}: {files}")
            print(f"running {name} at {info.sha}", file=sys.stderr)
            med, q90 = RUNNERS[name](snapshot(spec["repo"], info.sha), past, H)
            assert med.shape == truth.shape, (med.shape, truth.shape)
            if not np.isfinite(med).all():
                raise RuntimeError("non-finite forecast values")
            points[name] = med
            m["point"] = "median" if q90 is not None else "the model's output"
            if q90 is not None:
                p90[name] = q90
        except Exception as e:  # noqa: BLE001 - a failed candidate is recorded and the run goes on
            m["error"] = f"{type(e).__name__}: {e}"
            m["traceback"] = traceback.format_exc(limit=4)
            print(f"{name} failed: {m['error']}", file=sys.stderr)

    rows = [bt.score(bt.key(hours[i]), truth[w], tide[w], minor_m, {k: f[w] for k, f in points.items()})
            for w, i in enumerate(idx)]
    for w, r in enumerate(rows):
        for k, q in p90.items():
            r[f"flood_{k}_p90"] = bool((tide[w] + q[w]).max() >= minor_m)
    storm = [r for r in rows if r["peak_abs_obs"] >= 0.5]
    floods = [r for r in rows if r["flood_obs"]]

    def blk(sel, k):
        b = bt.block(sel, [k])
        return {"n_windows": b["n_windows"], "mae_m": b[f"mae_{k}_m"], "peak_error_m": b[f"peak_error_{k}_m"]}

    def flood(k):
        return {"said_so": sum(r[f"flood_{k}"] for r in floods),
                "false_alarms": sum(r[f"flood_{k}"] for r in rows if not r["flood_obs"])}

    def vs_current(k, block_len: int = 14, n: int = 2000) -> dict:
        """MAE minus the current model's over all windows, with a 95% interval
        from a moving-block bootstrap (windows a day apart share three of four
        days, so they are resampled in runs of `block_len`)."""
        d = np.array([r[f"mae_{k}"] - r["mae_current"] for r in rows])
        rng = np.random.default_rng(0)
        starts = rng.integers(0, len(d) - block_len + 1, size=(n, -(-len(d) // block_len)))
        boot = np.array([d[(s[:, None] + np.arange(block_len)).ravel()[:len(d)]].mean() for s in starts])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        return {"mae_minus_current_m": round(float(d.mean()), 4), "ci95_m": [round(float(lo), 4), round(float(hi), 4)],
                "block_windows": block_len}

    models = {}
    for k, m in meta.items():
        models[k] = dict(m)
        if k not in points:
            continue
        fl = flood(k)
        if k in p90:
            fl.update({f"p90_{x}": v for x, v in flood(f"{k}_p90").items()})
        models[k].update({"all": blk(rows, k), "residual_peak_at_least_0.5_m": blk(storm, k),
                          "minor_flood_stage": fl})
        if k != "current" and "current" in points:
            models[k]["all"]["against_current"] = vs_current(k)
    out = {"run_date": str(date.today()), "station": surge.STATION_ID, "first": rows[0]["start"][:10],
           "last": rows[-1]["start"][:10], "step_hours": a.step_hours, "context_hours": C, "horizon_hours": H,
           "n_windows": len(rows), "n_storm_windows": len(storm), "stage_m_mllw": round(minor_m, 3),
           "n_flood_windows": len(floods), "device": "cpu",
           "versions": {p: version(p) for p in ("torch", "transformers", "granite-tsfm", "chronos-forecasting",
                                                "huggingface-hub")},
           "models": models}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: {b: v.get(b) for b in ("all", "residual_peak_at_least_0.5_m", "minor_flood_stage", "error")}
                      for k, v in models.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
