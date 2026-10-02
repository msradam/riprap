"""Fine-tune Chronos-2 on the Battery surge residual, for the candidate backtest.

    python3 gpu_lock.py uv run --with 'chronos-forecasting==2.3.2' \\
        python scripts/finetune_chronos2_surge.py

Data: the hourly surge residual at NOAA 8518750 (water level minus predicted
tide, MLLW, metres, fetched as `app.live.ttm_battery_surge.hourly` does),
2015-01-01 to 2024-12-31, the span the current TTM r2 model was trained on.
Nothing from 2025 on is read. NOAA series are cached per year under
outputs/surge_cache/ and fetched one request at a time.

Split: training is every hour before 2024-07-01, cut into unbroken runs at
gauge gaps (2015 to 2024 has none, so it is one run); Chronos-2's own sampler draws random 1,024-in, 96-out windows
from them. Validation is one window a day starting 2024-07-01 to 2024-12-28
(its context reaches back into the training months, its targets do not).
The Trainer scores the validation quantile loss every 100 steps and keeps
the best checkpoint.

Model: `amazon/chronos-2` at 29ec376, LoRA through `Chronos2Pipeline.fit`
(the peft defaults of chronos-forecasting 2.3.2: rank 8 on the attention
projections and the output layer), 700 steps of batch 64, learning rate
5e-5 decaying linearly, context 1,024, prediction length 96, on the Apple
GPU. The package suggests 1e-5 for LoRA; with only 700 steps the one run
used 5e-5 and lets the validation loss pick the checkpoint. Batch 256
swapped on a 32 GB machine (70 s a step); batch 64 ran at about 3 s a step.

The run of 2026-10-02 took 31 minutes. The validation loss was lowest at
step 200 (8.607, against 8.668 at 100 and 8.712 at 700), and that
checkpoint is the one kept. The adapter is merged and the full model saved
as safetensors to outputs/surge_models/chronos2_battery/ with training.json
(the loss curve and the validation MAE beside zero-shot), which
`scripts/backtest_surge_candidates.py --finetuned <dir>` scores.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

BASE, BASE_SHA = "amazon/chronos-2", "29ec3766d36d6f73f0696f85560a422f50e8498c"
FIRST, VAL_START, END = datetime(2015, 1, 1, tzinfo=UTC), datetime(2024, 7, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)
OUT = ROOT / "outputs" / "surge_models" / "chronos2_battery"
CACHE = ROOT / "outputs" / "surge_cache"


def residuals():
    """Hours and residuals (m, NaN where either series is missing), 2015 to 2024."""
    import numpy as np

    obs, tide = {}, {}
    for y in range(FIRST.year, END.year):
        a, b = datetime(y, 1, 1, tzinfo=UTC), datetime(y, 12, 31, 23, tzinfo=UTC)  # end is inclusive at NOAA
        for product, d in (("water_level", obs), ("predictions", tide)):
            d.update(polite_year(product, a, b))
        print(f"{y}: {len(obs)} observed hours so far", file=sys.stderr)
    hours = [FIRST + timedelta(hours=i) for i in range(int((END - FIRST).total_seconds() // 3600))]
    k = [t.strftime("%Y-%m-%d %H:%M") for t in hours]  # END is exclusive, so a 2025 key is never read
    return hours, np.array([obs[x] - tide[x] if x in obs and x in tide else np.nan for x in k])


def polite_year(product: str, start: datetime, end: datetime, pause_s: float = 3.0) -> dict[str, float]:
    """One year of one product, cached, fetched a month at a time with a pause
    between requests (NOAA answered 403 to back-to-back monthly requests)."""
    from app.live import ttm_battery_surge as surge

    path = CACHE / f"{product}_{start:%Y%m%d%H}_{end:%Y%m%d%H%M}.json"
    if path.exists():
        return json.loads(path.read_text())
    out, cur = {}, start
    while cur < end:
        nxt = min(cur + timedelta(days=30), end)
        out.update(surge.hourly(product, cur, nxt))  # one request: the span is within its 30-day chunk
        time.sleep(pause_s)
        cur = nxt
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def runs(x, min_len: int):
    """The unbroken stretches of x at least min_len long."""
    import numpy as np

    ok = np.concatenate([[False], ~np.isnan(x), [False]])
    edges = np.flatnonzero(np.diff(ok.astype(int)))
    return [x[s:e] for s, e in zip(edges[::2], edges[1::2], strict=True) if e - s >= min_len]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--steps", type=int, default=700)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    import numpy as np

    from app.live.ttm_battery_surge import CONTEXT_HOURS as C
    from app.live.ttm_battery_surge import HORIZON_HOURS as H

    hours, res = residuals()
    split = hours.index(VAL_START)
    train = runs(res[:split], C + H)
    val_idx = [i for i in range(split, len(hours) - H + 1, 24) if not np.isnan(res[i - C:i + H]).any()]
    val = [res[i - C:i + H] for i in val_idx]
    print(f"train: {len(train)} runs, {sum(map(len, train))} hours (longest {max(map(len, train))}); "
          f"val: {len(val)} windows {hours[val_idx[0]]:%Y-%m-%d} to {hours[val_idx[-1]]:%Y-%m-%d}; "
          f"missing hours 2015-2024: {int(np.isnan(res).sum())}", file=sys.stderr)
    if a.fetch_only:
        return 0

    import torch
    from chronos import Chronos2Pipeline
    from huggingface_hub import snapshot_download

    torch.manual_seed(0)
    np.random.seed(0)  # Chronos2Dataset samples windows with np.random
    base = Chronos2Pipeline.from_pretrained(
        snapshot_download(BASE, revision=BASE_SHA, allow_patterns=["config.json", "*.safetensors"]),
        device_map=a.device, use_safetensors=True)
    work = ROOT / "outputs" / "surge_models" / "chronos2_battery_run"
    from transformers import TrainerCallback

    curve, best = [], {}

    class Record(TrainerCallback):  # the Trainer keeps only the best checkpoint, so its own log is cut short
        def on_log(self, args, state, control, logs=None, **kw):
            curve.append({"step": state.global_step, **{k: logs[k] for k in ("loss", "eval_loss") if k in (logs or {})}})

        def on_train_end(self, args, state, control, **kw):
            best["checkpoint"] = state.best_model_checkpoint

    t0 = time.time()
    ft = base.fit([x.astype("float32") for x in train], prediction_length=H, validation_inputs=[x.astype("float32") for x in val],
                  finetune_mode="lora", context_length=C, learning_rate=a.lr, num_steps=a.steps,
                  batch_size=a.batch_size, min_past=C, output_dir=work, logging_steps=50, save_safetensors=True,
                  callbacks=[Record()])
    minutes = (time.time() - t0) / 60
    curve = [c for c in curve if len(c) > 1]
    print(f"fit took {minutes:.1f} min", file=sys.stderr)

    merged = Chronos2Pipeline(model=ft.model.merge_and_unload().to("cpu"))
    merged.save_pretrained(a.out, safe_serialization=True)

    # Median MAE on the validation windows, zero-shot against fine-tuned, on CPU.
    past = torch.from_numpy(np.stack([v[:C] for v in val]).astype("float32")).unsqueeze(1)
    truth = np.stack([v[C:] for v in val])
    zero = Chronos2Pipeline.from_pretrained(snapshot_download(BASE, revision=BASE_SHA), device_map="cpu",
                                            use_safetensors=True)
    tuned = Chronos2Pipeline.from_pretrained(a.out, device_map="cpu", use_safetensors=True)
    mae = {}
    for name, p in (("zero_shot", zero), ("finetuned", tuned)):
        with torch.no_grad():
            q, _ = p.predict_quantiles(past, prediction_length=H, quantile_levels=[0.5])
        mae[name] = round(float(np.abs(torch.stack(q)[:, 0, :, 0].numpy() - truth).mean()), 4)
    info = {"base": BASE, "base_commit": BASE_SHA, "mode": "lora", "steps": a.steps, "learning_rate": a.lr,
            "batch_size": a.batch_size, "context_hours": C, "horizon_hours": H, "train_hours_before": str(VAL_START.date()),
            "validation": [str(hours[val_idx[0]].date()), str(hours[val_idx[-1]].date()), len(val)],
            "fit_minutes": round(minutes, 1),
            "best_step": int(best["checkpoint"].rsplit("-", 1)[1]) if best.get("checkpoint") else None, "validation_median_mae_m": mae, "curve": curve,
            "run_date": str(date.today())}
    (a.out / "training.json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps({k: v for k, v in info.items() if k != "curve"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
