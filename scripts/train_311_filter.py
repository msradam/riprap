"""Rebuild the 311 flood filter: GLiClass modern-base distilled from Granite
4.1 8B's option probabilities, as in System One round two.

    uv run --extra ml python scripts/train_311_filter.py --pool PATH [--teacher PATH] [--out DIR] [--device mps|cpu]

Recipe copied from experiments/23_system_one/scripts/finetune_gliclass.py
(an unpublished experiment, System One), task a: base
knowledgator/gliclass-modern-base-v3.0 at ac369222ca4375ca66ebaf7fb5220f223514c035
(safetensors only); a pool of unlabelled 311 records (--pool, a CSV with
item_id and text columns) labelled with the teacher's soft probabilities
(--teacher, default data/calibration/distill_teacher_a1_granite8b.jsonl,
keyed by item_id); lr 3e-5, about 300
optimizer steps, seed 0; the released config's problem type set to
multi-label with focal-loss reduction "none", without which training is a
silent no-op. The experiment never saved its model, so this rebuilds it.

Then it scores the student on data/calibration/task_a.csv (silver labels;
the experiment's calibration and test split) and picks the keep threshold
on P(any flood class) on the calibration split: the one with the best
Youden's J (flood recall plus non-flood rejection, minus one). Not F1:
the calibration split is about 63% flood while live feeds are about 1 to 2%
flood, and F1 on it chose a threshold that keeps almost everything. Writes the model (safetensors) and
provenance.json to --out (default ~/.cache/riprap/flood311_gliclass), and
the scores to tests/flood311_filter_eval.json. Point
RIPRAP_311_FILTER_PATH at --out to use it.

The pool is not in the repository. The original 2,500-record pool held
residents' email addresses in its 311 free text and was removed from the
history; it must never be committed again, and the script refuses a pool
path inside the repository unless git ignores it. To rebuild a pool, see
"Rebuilding the training pool" in data/calibration/README.md. The committed
teacher file matches only the original pool's item ids, so a rebuilt pool
also needs new teacher probabilities.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
BASE = ("knowledgator/gliclass-modern-base-v3.0", "ac369222ca4375ca66ebaf7fb5220f223514c035")
SEED, STEPS = 0, 300
CAL = ROOT / "data" / "calibration"


def _check_pool_path(pool: Path) -> None:
    """A pool inside the repository must be git-ignored: it holds 311 free text."""
    try:
        pool.resolve().relative_to(ROOT)
    except ValueError:
        return  # outside the repository
    if subprocess.run(["git", "check-ignore", "-q", str(pool)], cwd=ROOT).returncode != 0:
        sys.exit(f"{pool} is inside the repository and not git-ignored; keep 311 pools out of the repo")


def train(device: str, pool_path: Path, teacher_path: Path):
    import torch
    from gliclass import GLiClassModel
    from gliclass.data_processing import (
        AugmentationConfig,
        DataCollatorWithPadding,
        GLiClassDataset,
    )
    from gliclass.training import Trainer, TrainingArguments
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    from riprap.core.pebbles.record_filter import LABELS, OPTIONS, QUESTION

    torch.manual_seed(SEED)
    random.seed(SEED)
    base = snapshot_download(BASE[0], revision=BASE[1], allow_patterns=["*.safetensors", "*.json", "*.txt"],
                             ignore_patterns=["*.bin", "*.pt", "*.pth", "*.pkl", "*.py"])
    pool = pd.read_csv(pool_path, keep_default_na=False)
    teacher = {r["item_id"]: r["probs"] for r in map(json.loads, teacher_path.read_text().splitlines())}
    examples = [{"text": r.text, "all_labels": LABELS, "prompt": QUESTION,
                 "true_labels": {f"{k}: {OPTIONS[k]}": float(teacher[r.item_id].get(k, 0.0)) for k in OPTIONS}}
                for r in pool.itertuples()]
    model = GLiClassModel.from_pretrained(base)
    model.config.problem_type = "multi_label_classification"
    model.config.focal_loss_reduction = "none"
    tok = AutoTokenizer.from_pretrained(base, add_prefix_space=True)
    ds = GLiClassDataset(examples, tok, AugmentationConfig(enabled=False), max_length=1024,
                         problem_type="multi_label_classification", architecture_type=model.config.architecture_type,
                         prompt_first=model.config.prompt_first)
    epochs = min(40, max(2, -(-STEPS * 8 // len(examples))))
    args = TrainingArguments(output_dir=tempfile.mkdtemp(prefix="train_311_"), learning_rate=3e-5, others_lr=1e-4,
                             num_train_epochs=epochs, per_device_train_batch_size=8, weight_decay=0.01,
                             save_strategy="no", report_to=[], logging_steps=25, seed=SEED,
                             use_cpu=device == "cpu", dataloader_pin_memory=False)
    Trainer(model=model, args=args, train_dataset=ds,
            data_collator=DataCollatorWithPadding(device=torch.device(device))).train()
    return model.eval(), tok, len(examples), epochs


def evaluate(out: Path) -> dict:
    from calibrate_entailment import split

    from riprap.core.pebbles import record_filter as rf

    os.environ["RIPRAP_311_FILTER_PATH"] = str(out)
    rf._pipeline.cache_clear()
    df = pd.read_csv(CAL / "task_a.csv", keep_default_na=False)
    df["label"] = df.silver_label.replace("", np.nan)
    df["group"] = df.item_id
    is_cal = split(df)
    t0 = time.perf_counter()
    probs = [rf.class_probs(t) for t in df.text]
    sec = (time.perf_counter() - t0) / len(df)
    df["pred"] = [max(p, key=p.get) for p in probs]
    df["p_flood"] = [1 - p["not_flooding"] for p in probs]
    lab = df.label.notna()
    test, cal = lab & ~is_cal, lab & is_cal
    y_cal = (df.label[cal] != "not_flooding").to_numpy()
    best, best_f1 = (-1.0, 0.5), (0.0, 0.5)
    for t in np.unique(df.p_flood[cal]):
        keep = (df.p_flood[cal] >= t).to_numpy()
        tp, fp, fn = (keep & y_cal).sum(), (keep & ~y_cal).sum(), (~keep & y_cal).sum()
        j = tp / max(1, y_cal.sum()) - fp / max(1, (~y_cal).sum())
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        best = max(best, (float(j), float(t)))
        best_f1 = max(best_f1, (float(f1), float(t)))
    threshold = best[1]
    y_test = (df.label[test] != "not_flooding").to_numpy()
    keep_test = (df.p_flood[test] >= threshold).to_numpy()
    return {"silver_test_accuracy": round(float((df.pred[test] == df.label[test]).mean()), 4),
            "n_test": int(test.sum()), "n_calibration": int(cal.sum()), "threshold": round(threshold, 4),
            "calibration_youden_j": round(best[0], 4),
            "threshold_by_f1_not_used": round(best_f1[1], 4),
            "test_flood_recall": round(float((keep_test & y_test).sum() / max(1, y_test.sum())), 4),
            "test_not_flooding_dropped": round(float((~keep_test & ~y_test).sum() / max(1, (~y_test).sum())), 4),
            "test_accuracy_by_city": {c: round(float((df.pred[test & (df.city == c)] == df.label[test & (df.city == c)]).mean()), 4)
                                      for c in sorted(df.city[test].unique())},
            "cpu_seconds_per_record": round(sec, 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", help="CSV of unlabelled 311 records (item_id, text); kept outside the repo")
    ap.add_argument("--teacher", default=str(CAL / "distill_teacher_a1_granite8b.jsonl"),
                    help="teacher probabilities as JSON lines keyed by item_id")
    ap.add_argument("--out", default="~/.cache/riprap/flood311_gliclass")
    ap.add_argument("--device", default="mps", choices=["mps", "cpu"])
    ap.add_argument("--eval-only", action="store_true", help="rescore a saved model, no training")
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    if a.eval_only:
        prov = json.loads((out / "provenance.json").read_text())
        prov["scores"] = evaluate(out)
        (out / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
        (ROOT / "tests" / "flood311_filter_eval.json").write_text(json.dumps(prov, indent=1) + "\n")
        print(json.dumps(prov["scores"], indent=1))
        return
    if not a.pool:
        ap.error("--pool is required to train (see data/calibration/README.md)")
    pool = Path(a.pool).expanduser()
    _check_pool_path(pool)
    t0 = time.perf_counter()
    model, tok, n, epochs = train(a.device, pool, Path(a.teacher).expanduser())
    train_s = time.perf_counter() - t0
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out, safe_serialization=True)
    tok.save_pretrained(out)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    scores = evaluate(out)
    prov = {"base": {"repo": BASE[0], "sha": BASE[1]},
            "teacher": "ibm-granite/granite-4.1-8b @ 1504002f, A1 option-probability readout, phrasing v1",
            "training_data": f"{pool.name} with {Path(a.teacher).name} ({n} records)",
            "recipe": "experiments/23_system_one/scripts/finetune_gliclass.py, task a, in an unpublished experiment (System One)",
            "script": "scripts/train_311_filter.py", "riprap_commit": commit, "device": a.device,
            "n_train": n, "epochs": epochs, "train_seconds": round(train_s), "scores": scores}
    (out / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    (ROOT / "tests" / "flood311_filter_eval.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main()
