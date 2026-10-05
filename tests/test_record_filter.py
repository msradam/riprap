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


def test_a_city_311_sentence_says_the_window_it_counts(monkeypatch):
    """The feed is read newest first with no date filter: the sentence gives
    the date of the oldest request fetched, so "3 of the latest 200" has a window."""
    from riprap.core.burr.evidence import sentence_for
    from riprap.core.pebbles import SpatialQuery, load_registry
    from riprap.core.pebbles.adapters import socrata_records
    from riprap.core.pebbles.deployments import deployment_root

    rows = [{"sr_type": "Water On Street Complaint", "created_date": "2026-09-30T08:00:00.000"},
            {"sr_type": "Pothole in Street Complaint", "created_date": "2026-03-01T08:00:00.000"}]
    monkeypatch.setattr(socrata_records, "fetch_url_json", lambda *a, **k: rows)
    pebble = load_registry(deployment_root("chicago")).get("chicago_311")
    value = pebble.fetch(SpatialQuery(lat=41.878, lon=-87.636)).value
    assert value["window_phrase"] == " created since 2026-03-01"
    assert sentence_for(value, pebble.manifest) == (
        "Experimental: 1 of 2 Chicago 311 service requests within 200 m of this address created since 2026-03-01 "
        "are in categories reviewed as flood-related.")
