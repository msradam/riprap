"""Keep the flood-related records in a 311 feed.

Set per manifest under `config.record_filter`:

  kind: category_table    a reviewed map from the city's category name to a
                          label, for a city whose feed gives a category
                          (Chicago, Seattle)
      field: ...          the category field
      labels: {category: label}   any label other than not_flooding keeps

A feed with no reviewed table is not counted at all: an unfiltered count
of service requests says nothing about flooding. (A text classifier for
such feeds was specified and never shipped with weights; it is in history
at 8b87165.)
"""

from __future__ import annotations


def apply(records: list[dict], cfg: dict | None, source: str = "",  # noqa: ARG001 - kept for the adapters' call
          truncated: bool = False) -> tuple[list[dict], dict]:
    """(kept records, info). `info` has the counts before and after; with
    no filter configured, everything passes. `truncated` means the feed hit
    its fetch limit, so the count is of the latest records only."""
    if not cfg:
        return records, {}
    if cfg.get("kind") != "category_table":
        raise ValueError(f"record_filter: unknown kind {cfg.get('kind')!r}")
    labels, field = cfg.get("labels") or {}, cfg.get("field")
    if records and not any(r.get(field) for r in records):
        # A renamed column would file every record as not flooding: "0 of 200".
        raise ValueError(f"record_filter: no record has the category field {field!r}")
    kept = [r for r in records if labels.get(str(r.get(field) or ""), "not_flooding") != "not_flooding"]
    return kept, {"filter": "category_table", "n_before": len(records), "n_kept": len(kept),
                  "filter_note": "are in categories reviewed as flood-related",
                  "n_before_phrase": f"the latest {len(records)}" if truncated else str(len(records))}
