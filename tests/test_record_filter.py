"""The 311 record filter: a reviewed category table per city. A feed
without one is not counted at all."""

import pytest

from riprap.core.pebbles import record_filter as rf

CHICAGO = {"kind": "category_table", "field": "sr_type",
           "labels": {"Water On Street Complaint": "street_flooding"}}


def test_category_table_keeps_reviewed_flood_categories():
    recs = [{"sr_type": "Water On Street Complaint"}, {"sr_type": "Pothole in Street Complaint"}]
    kept, info = rf.apply(recs, CHICAGO, "chicago_311", truncated=True)
    assert kept == recs[:1]
    assert info["n_kept"] == 1 and info["n_before_phrase"] == "the latest 2"


def test_a_renamed_category_column_is_an_error_not_a_zero():
    with pytest.raises(ValueError):
        rf.apply([{"type": "Water On Street Complaint"}], CHICAGO, "chicago_311")


def test_an_unknown_filter_kind_is_an_error():
    with pytest.raises(ValueError):
        rf.apply([{"sr_type": "x"}], {"kind": "flood_311_model"}, "sf_311")


def test_no_filter_passes_everything():
    assert rf.apply([{"a": 1}], None) == ([{"a": 1}], {})
