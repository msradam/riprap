---
type: reference
---

# Calibration data

Copied unchanged from an unpublished experiment (System One), directory
`experiments/23_system_one/`. The labels are automatic (silver or
perturbation), not owner judgements.

| File | Source in the experiment | What it is | Used by |
|---|---|---|---|
| `task_b.csv` | `data/task_b.csv` | 198 claims from stored briefings with their cited evidence, and 530 perturbed copies labelled unsupported (changed number, swapped document, flipped direction, changed place) | the retired entailment check's threshold was picked on its calibration split (`scripts/calibrate_entailment.py` at the git tag `archive/guarded-answer-mode`) |
| `task_a.csv` | `data/task_a.csv` | 398 311 records from NYC, San Francisco, Boston and Albany; silver labels from each city's category field (the classifier never sees it) | `scripts/train_311_filter.py` scores the filter and picks its threshold on the calibration split |
| (not committed) `distill_pool.csv` | `data/distill_pool.csv` | 2,500 unlabelled 311 records from the experiment's API cache, none in `task_a.csv`; removed from the history because its free text held residents' email addresses | training data for the 311 filter, passed with `--pool` |
| `distill_teacher_a1_granite8b.jsonl` | `results/raw/p_a1_v1_mps.jsonl` | Granite 4.1 8B option probabilities for each pool record (the A1 readout, phrasing v1) | soft labels for the 311 filter |

The split is the experiment's: 20% of items (Task B: of claims, with all
of a claim's variants together), stratified by label, seed 0.

Personal email addresses that appeared in the free text of some 311
records were replaced with `[email removed]` on 2026-09-27 (refactor 5),
and phone numbers with `[phone removed]` on 2026-09-28 (refactor 6), the
same redaction the 311 adapters now apply at fetch time
(`riprap/core/redact.py`). The phone numbers found were agency numbers in
NYC resolution text (DEP, the Health Department, the State Attorney
General). The 311 filter was trained before these changes; the redaction
changes no label.

## Rebuilding the training pool

The pool is not in the repository and must never be committed: 311 free
text can hold residents' emails, phone numbers and names. `.gitignore`
lists `data/calibration/distill_pool.csv` and `experiments/**/distill_pool.csv`,
and `scripts/train_311_filter.py` refuses a pool path inside the repository
that git does not ignore.

1. Fetch 311 records from each city's API (NYC erm2-nwe9, San Francisco
   vw6y-z8j6, Boston's CKAN 311 resource, Albany SeeClickFix), with
   `riprap.core.pebbles._http.fetch_url_json(url, personal=True)`. That call
   skips the HTTP cache and removes emails and phone numbers from every
   string before returning.
2. Build each record's text as the city's manifest does (`text_fields` and
   `join` under `record_filter` in `deployments/<city>/manifests/*_311.yaml`),
   drop records in `task_a.csv`, and keep at most half the pool from any one
   city, as `prep_distill_pool.py` did in the unpublished experiment (System
   One). Write a CSV with `item_id` and `text` columns to a path outside the
   repository, for example `~/.cache/riprap/distill_pool.csv`.
3. Label every record with the teacher: Granite 4.1 8B's option
   probabilities with the A1 readout, as JSON lines
   `{"item_id": ..., "probs": {...}}`. The committed
   `distill_teacher_a1_granite8b.jsonl` matches only the original pool's
   item ids, so a new pool needs new labels. The teacher is an 8B model;
   run it with nothing else loaded on the GPU.
4. Train: `uv run --extra ml python scripts/train_311_filter.py --pool
   ~/.cache/riprap/distill_pool.csv --teacher PATH`.
