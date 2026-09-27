---
type: reference
---

# Calibration data

Copied unchanged from the System One experiment on branch
`experiment/system-one`, commit `06e20e8`, directory
`experiments/23_system_one/`. The labels are automatic (silver or
perturbation), not owner judgements.

| File | Source in the experiment | What it is | Used by |
|---|---|---|---|
| `task_b.csv` | `data/task_b.csv` | 198 claims from stored briefings with their cited evidence, and 530 perturbed copies labelled unsupported (changed number, swapped document, flipped direction, changed place) | `scripts/calibrate_entailment.py` picks the entailment threshold on its calibration split |
| `task_a.csv` | `data/task_a.csv` | 398 311 records from NYC, San Francisco, Boston and Albany; silver labels from each city's category field (the classifier never sees it) | `scripts/train_311_filter.py` scores the filter and picks its threshold on the calibration split |
| `distill_pool.csv` | `data/distill_pool.csv` | 2,500 unlabelled 311 records from the experiment's API cache, none in `task_a.csv` | training data for the 311 filter |
| `distill_teacher_a1_granite8b.jsonl` | `results/raw/p_a1_v1_mps.jsonl` | Granite 4.1 8B option probabilities for each pool record (the A1 readout, phrasing v1) | soft labels for the 311 filter |

The split is the experiment's: 20% of items (Task B: of claims, with all
of a claim's variants together), stratified by label, seed 0.
