"""Keep the flood-related records in a 311 feed (refactor 4).

Two kinds, set per manifest under `config.record_filter`:

  kind: flood_311_model   a 151M GLiClass distilled from Granite 4.1 8B's
                          option probabilities (System One round two); reads
                          each record's free text; used where a city gives
                          text (San Francisco, Boston, Albany)
      text_fields: [...]  record fields joined into the classifier's input
      join: " | "         how they are joined (as the experiment built its text)
      text_after: ...     keep only the text after this marker, if present
      id_field: ...       record id, for the cache
      threshold: ...      keep when P(any flood class) is at least this
  kind: category_table    a reviewed map from the city's category name to a
                          label; used where a city gives only a category
                          (Chicago, Seattle)
      field: ...          the category field
      labels: {category: label}   any label other than not_flooding keeps

The model's weights are not in the repo. Set RIPRAP_311_FILTER_PATH to the
directory `scripts/train_311_filter.py` writes. Without the weights or the
`ml` extra the records pass unfiltered and the value says so.
"""

from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from pathlib import Path

# The student was trained on these exact strings (the experiment's Task A,
# phrasing v1); changing them changes what the model sees.
QUESTION = "Classify this city 311 service request record by the kind of flooding it reports."
OPTIONS = {
    "street_flooding": "Rain, storm or tidal water ponding or flowing on a street, road, highway or sidewalk.",
    "sewer_backup": "Sewage or wastewater backing up out of the sewer system, including manhole overflows.",
    "basement_or_building_flooding": "Water entering or standing inside a basement, garage or other part of a building.",
    "drainage_infrastructure": "A clogged, damaged, missing or sinking catch basin, storm drain, grate or drain.",
    "not_flooding": "Anything else, including water main breaks, hydrant leaks and plumbing leaks.",
}
LABELS = [f"{k}: {d}" for k, d in OPTIONS.items()]


def model_path() -> Path | None:
    p = os.environ.get("RIPRAP_311_FILTER_PATH")
    return Path(p).expanduser() if p and Path(p).expanduser().is_dir() else None


@lru_cache(maxsize=1)
def _pipeline():
    import gliclass.pipeline
    import torch
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    gliclass.pipeline.tqdm = lambda it, *a, **k: it
    path = str(model_path())
    model = GLiClassModel.from_pretrained(path)
    tok = AutoTokenizer.from_pretrained(path, add_prefix_space=True)
    return ZeroShotClassificationPipeline(model, tok, classification_type="multi-label", device=torch.device("cpu"))


def class_probs(text: str) -> dict[str, float]:
    """The student's probabilities over the five classes, normalised the way
    the experiment scored it (multi-label scores divided by their sum)."""
    res = _pipeline()(text, LABELS, threshold=0.0, prompt=QUESTION)[0]
    s = {r["label"].split(":", 1)[0]: r["score"] for r in res}
    z = [s.get(k, 0.0) + 1e-9 for k in OPTIONS]
    return {k: v / sum(z) for k, v in zip(OPTIONS, z, strict=True)}


def p_flood(text: str) -> float:
    return 1.0 - class_probs(text)["not_flooding"]


def _cache() -> sqlite3.Connection:
    path = Path(os.environ.get("RIPRAP_311_FILTER_CACHE", "~/.cache/riprap/flood311.sqlite")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS p (key TEXT PRIMARY KEY, p REAL)")
    return con


def available() -> tuple[bool, str]:
    if model_path() is None:
        return False, "flood filter not installed (RIPRAP_311_FILTER_PATH unset)"
    try:
        import gliclass  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False, "flood filter not installed (ml extra missing)"
    return True, ""


def apply(records: list[dict], cfg: dict | None, source: str = "",
          truncated: bool = False) -> tuple[list[dict], dict]:
    """(kept records, info). `info` has the counts before and after and says
    whether the filter ran; with no filter configured, everything passes.
    `truncated` means the feed hit its fetch limit, so the count is of the
    latest records only."""
    if not cfg:
        return records, {}
    kept, info = _apply(records, cfg, source)
    info["n_before_phrase"] = f"the latest {len(records)}" if truncated else str(len(records))
    return kept, info


def _apply(records: list[dict], cfg: dict, source: str) -> tuple[list[dict], dict]:
    if cfg.get("kind") == "category_table":
        labels, field = cfg.get("labels") or {}, cfg.get("field")
        if records and not any(r.get(field) for r in records):
            # A renamed column would file every record as not flooding: "0 of 200".
            raise ValueError(f"record_filter: no record has the category field {field!r}")
        kept = [r for r in records if labels.get(str(r.get(field) or ""), "not_flooding") != "not_flooding"]
        return kept, {"filter": "category_table", "n_before": len(records), "n_kept": len(kept),
                      "filter_note": "are in categories reviewed as flood-related"}
    ok, why = available()
    if not ok:
        return records, {"filter": "none", "filter_reason": why, "n_before": len(records), "n_kept": len(records),
                         "filter_note": f"were counted without a flood filter ({why})"}
    threshold = float(cfg["threshold"])
    fields, id_field = cfg.get("text_fields") or [], cfg.get("id_field")
    join, marker = cfg.get("join", " | "), cfg.get("text_after")
    con, kept, no_text = _cache(), [], 0
    with con:
        for r in records:
            text = join.join(str(r[f]).replace("_", " ") for f in fields if r.get(f)).strip()
            if marker:
                text = text.split(marker, 1)[-1].strip()
            if not text:
                no_text += 1  # nothing for the classifier to read, so not counted
                continue
            key = f"{source}:{r.get(id_field)}" if id_field and r.get(id_field) else f"{source}:text:{text}"
            row = con.execute("SELECT p FROM p WHERE key = ?", (key,)).fetchone()
            p = row[0] if row else p_flood(text)
            if not row:
                con.execute("INSERT OR REPLACE INTO p VALUES (?, ?)", (key, p))
            if p >= threshold:
                kept.append({**r, "p_flood": round(p, 3)})
    if records and no_text == len(records):
        # Nothing was readable: the count is unknown, not "0 of N".
        raise ValueError(f"record_filter: none of the {len(records)} records has text for the flood classifier")
    note = "read as flood-related to a text classifier (experimental, not checked against hand labels)"
    if no_text:
        note += f"; {no_text} had no text to read and were not counted"
    return kept, {"filter": "flood_311_model", "threshold": threshold, "n_before": len(records),
                  "n_kept": len(kept), "n_no_text": no_text, "filter_note": note}
