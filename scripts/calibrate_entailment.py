"""Choose the entailment threshold on the System One Task B calibration split.

    uv run --extra ml python scripts/calibrate_entailment.py [gliclass|guardian] [--test]

data/calibration/task_b.csv is the experiment's Task B (experiment/system-one,
06e20e8): claims from stored briefings with their cited evidence, plus
perturbed copies (changed number, swapped document, flipped direction,
changed place) labelled unsupported. The split is the experiment's own:
20% of claims (all variants of a claim together), stratified by label,
seed 0. The threshold is the highest that keeps at least 95% of the
calibration split's true claims. --test also scores the test split.
Writes tests/entailment_calibration_<backend>.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KEEP_TRUE = 0.95


def split(df: pd.DataFrame, seed: int = 0) -> np.ndarray:
    """Copy of experiments/23_system_one/metrics.py:split, grouped by claim."""
    rng = np.random.default_rng(seed)
    first = df.groupby("group").label.first()
    cal: set = set()
    for _, g in first.groupby(first):
        ids = g.index.to_numpy()
        cal |= set(rng.choice(ids, size=max(1, round(0.2 * len(ids))), replace=False))
    return df.group.isin(cal).to_numpy()


def auroc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum())
                 / (len(pos) * len(neg)))


def main() -> None:
    from riprap.core.burr.entailment import p_supported

    backend = next((a for a in sys.argv[1:] if not a.startswith("-")), "gliclass")
    df = pd.read_csv(ROOT / "data/calibration/task_b.csv", keep_default_na=False)
    df["label"] = df.label.map({1: "supported", 0: "not_supported"})
    df["group"] = df.claim_id
    is_cal = split(df)
    parts = {"calibration": df[is_cal]} | ({"test": df[~is_cal]} if "--test" in sys.argv else {})
    out = {"backend": backend, "keep_true": KEEP_TRUE}
    for name, part in parts.items():
        t0, p = time.perf_counter(), []
        for r in part.itertuples():
            p.append(p_supported(r.claim, r.evidence, backend))
        p, y = np.array(p), (part.label == "supported").to_numpy().astype(int)
        res = {"n": len(part), "n_true": int(y.sum()), "auroc": round(auroc(y, p), 4),
               "seconds_per_claim": round((time.perf_counter() - t0) / len(part), 3)}
        if name == "calibration":
            out["threshold"] = float(np.quantile(p[y == 1], 1 - KEEP_TRUE))
        t = out["threshold"]
        res |= {"true_kept": round(float((p[y == 1] >= t).mean()), 4),
                "false_caught": round(float((p[y == 0] < t).mean()), 4),
                "caught_by_perturbation": {k: round(float((p[(y == 0) & (part.perturbation == k).to_numpy()] < t).mean()), 4)
                                           for k in sorted(set(part.perturbation) - {"none"})}}
        out[name] = res
        print(name, json.dumps(res), flush=True)
    out["threshold"] = round(out["threshold"], 6)
    (ROOT / f"tests/entailment_calibration_{backend}.json").write_text(json.dumps(out, indent=1) + "\n")
    print("threshold", out["threshold"])


if __name__ == "__main__":
    main()
