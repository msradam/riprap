"""Three citation URLs in _DOC_META were confirmed 404 by live curl checks
(2026-07-12): the DEP Stormwater dataset was retired and consolidated into
a single collection page, NTA-map and NYCHA-Developments were both renamed.
No network calls here — that would be flaky in CI — just a regression
guard against the exact dead ids reappearing."""
from __future__ import annotations

from app.reconcile import _DOC_META

_DEAD_DATASET_IDS = ("d73m-mf6p", "d3qk-pfyz", "i9rv-hdr5")


def test_no_known_dead_dataset_ids():
    for doc_id, meta in _DOC_META.items():
        url = meta.get("url", "")
        for dead in _DEAD_DATASET_IDS:
            assert dead not in url, f"{doc_id} still points at retired dataset {dead}: {url}"


def test_dep_tiers_point_at_the_current_collection():
    for doc_id in ("dep_stormwater", "dep_moderate_current", "dep_extreme_2080",
                   "dep_extreme_2080_nta", "dep_moderate_2050_nta", "dep_moderate_current_nta"):
        assert "9i7c-xyvv" in _DOC_META[doc_id]["url"]
