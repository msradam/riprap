"""The 311 record filter: reviewed category tables, the distilled text
classifier (stubbed), its cache, and the fallback without weights."""

from riprap.core.pebbles import record_filter as rf

CHICAGO = {"kind": "category_table", "field": "sr_type",
           "labels": {"Water On Street Complaint": "street_flooding"}}
MODEL = {"kind": "flood_311_model", "text_fields": ["service_details", "status_notes"], "join": " | ",
         "id_field": "id", "threshold": 0.5}


def test_category_table_keeps_reviewed_flood_categories():
    recs = [{"sr_type": "Water On Street Complaint"}, {"sr_type": "Pothole in Street Complaint"}]
    kept, info = rf.apply(recs, CHICAGO, "chicago_311", truncated=True)
    assert kept == recs[:1]
    assert info["n_kept"] == 1 and info["n_before_phrase"] == "the latest 2"


def test_without_weights_records_pass_and_the_note_says_so(monkeypatch):
    monkeypatch.delenv("RIPRAP_311_FILTER_PATH", raising=False)
    kept, info = rf.apply([{"service_details": "flooding"}], MODEL, "sf_311")
    assert len(kept) == 1 and info["filter"] == "none"
    assert "without a flood filter" in info["filter_note"]


def test_model_filter_keeps_above_threshold_and_caches(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rf, "available", lambda: (True, ""))
    monkeypatch.setenv("RIPRAP_311_FILTER_CACHE", str(tmp_path / "c.sqlite"))
    monkeypatch.setattr(rf, "p_flood", lambda text: calls.append(text) or (0.9 if "flooded" in text else 0.1))
    recs = [{"id": 1, "service_details": "street_flooded", "status_notes": "open"},
            {"id": 2, "service_details": "graffiti"}, {"id": 3}]
    kept, info = rf.apply(recs, MODEL, "sf_311")
    assert [r["id"] for r in kept] == [1] and info["n_no_text"] == 1
    assert calls[0] == "street flooded | open"  # underscores read as spaces, fields joined as trained
    rf.apply(recs, MODEL, "sf_311")
    assert len(calls) == 2  # the second pass came from the cache
