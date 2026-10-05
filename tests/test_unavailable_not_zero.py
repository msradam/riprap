"""Unavailable is not zero (refactor 5, phase 3). For each register and
count source: a source that fails or cannot be read raises or reports a
failure, never a count of 0; a source that answered with nothing in range
reports a true 0. Offline: fetches are stubbed."""

import pytest

OCEAN = (40.30, -73.50)  # inside the NYC bounding box, no assets nearby


@pytest.mark.parametrize("asset_class,count", [
    ("mta_entrances", "n_entrances"), ("nycha", "n_developments"),
    ("doe_schools", "n_schools"), ("doh_hospitals", "n_hospitals"),
])
def test_register_with_nothing_in_range_is_a_true_zero(asset_class, count):
    from app.registers import exposure

    v = exposure.summary_for_point(*OCEAN, asset_class)
    assert v["available"] is True and v[count] == 0


@pytest.mark.parametrize("asset_class", ["nycha", "doe_schools"])
def test_missing_register_file_is_unavailable_not_zero(asset_class, monkeypatch, tmp_path):
    from app.registers import _loader, exposure

    monkeypatch.setattr(_loader, "REGISTERS_DIR", tmp_path)
    _loader.load_register.cache_clear()
    try:
        with pytest.raises(FileNotFoundError):
            exposure.summary_for_point(40.6755, -74.0110, asset_class)
    finally:
        _loader.load_register.cache_clear()


def _broken(*a, **k):
    raise OSError("layer unreadable")


def test_mta_failed_sandy_join_is_unavailable_not_outside(monkeypatch):
    from app.flood_layers import sandy_inundation
    from app.registers import exposure

    monkeypatch.setattr(sandy_inundation, "join", _broken)
    with pytest.raises(OSError):
        exposure.summary_for_point(40.7557, -73.9870, "mta_entrances")  # Times Square


def test_hospital_failed_exposure_lookup_is_unavailable_not_outside(monkeypatch):
    from app.flood_layers import sandy_inundation
    from app.registers import exposure

    monkeypatch.setattr(sandy_inundation, "inside_raster", _broken)
    monkeypatch.setattr(sandy_inundation, "join", _broken)
    with pytest.raises(OSError):
        exposure.summary_for_point(40.7390, -73.9754, "doh_hospitals", radius_m=2000)  # Bellevue


def test_value_reporting_its_own_error_is_a_failed_step(monkeypatch):
    from app.context import nws_alerts
    from riprap.core.pebbles.bridge import fetch_pebble

    monkeypatch.setattr(nws_alerts, "alerts_at", _broken)
    value, _, err = fetch_pebble("nws_alerts", 40.7, -74.0, deployment="federal")
    assert value is None and "layer unreadable" in err


def test_no_active_alerts_is_a_true_zero(monkeypatch):
    from app.context import nws_alerts
    from riprap.core.pebbles.bridge import fetch_pebble

    monkeypatch.setattr(nws_alerts, "alerts_at", lambda lat, lon, kind="flood": [])
    value, _, err = fetch_pebble("nws_alerts", 40.7, -74.0, deployment="federal")
    assert err is None and value["n_active"] == 0 and value["narrative"].startswith("No active")


def test_nyc311_failed_fetch_raises(monkeypatch):
    from app.context import nyc311

    monkeypatch.setattr(nyc311.http, "get", _broken)
    with pytest.raises(OSError):
        nyc311.summary_for_point(40.7, -74.0)


def test_nyc311_capped_count_is_a_floor():
    from app.context.nyc311 import Complaint, _summarize

    cs = [Complaint("1", "Street Flooding (SJ)", "2025-01-01", None, None)] * 3
    assert _summarize(cs, years=5, radius_m=200, limit=3)["narrative"].startswith("At least 3 ")


def test_311_category_filter_with_missing_field_is_unavailable_not_zero():
    from riprap.core.pebbles import record_filter

    cfg = {"kind": "category_table", "field": "sr_type", "labels": {"Water in Street": "street_flooding"}}
    with pytest.raises(ValueError):
        record_filter.apply([{"other": "x"}] * 5, cfg, "chicago_311")
    kept, info = record_filter.apply([{"sr_type": "Pothole"}] * 5, cfg, "chicago_311")
    assert kept == [] and info["n_kept"] == 0 and info["n_before_phrase"] == "5"  # a true zero


def test_dob_permits_missing_coordinates_is_unavailable_not_zero(monkeypatch):
    from app.context import dob_permits

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"job__": "1", "borough": "QUEENS"}]

    monkeypatch.setattr(dob_permits.http, "get", lambda *a, **k: R())
    with pytest.raises(ValueError):
        dob_permits.permits_in_bbox(40.7, -73.8, 40.8, -73.7)


# The same rule for extractive answers.

def test_lead_no_from_an_unavailable_source_is_refused():
    from riprap.core.burr.answer_checks import check_lead

    q = "Is there an active flood warning here?"
    docs = {"nws_alerts": "NWS alerts unavailable for this point."}
    assert any(k == "unavailable" for k, _ in check_lead("no", ["nws_alerts"], q, docs))
    ok = {"nws_alerts": "No active NWS flood / coastal / wind alerts at this point."}
    assert not check_lead("no", ["nws_alerts"], q, ok)  # a true zero may back a "no"


def test_count_of_zero_from_an_unavailable_source_is_refused():
    from riprap.core.burr.answer_checks import check_lead

    q = "How many 311 flood complaints were filed near here?"
    down = {"nyc311": {"n": 0, "error": "HTTP 503"}}
    docs = {"nyc311": "0 NYC 311 flood-related complaints filed within 200 m of this location."}
    assert any(k == "unavailable" for k, _ in check_lead("count", ["nyc311"], q, docs, down))
    answered = {"nyc311": {"n": 0, "by_kind": {}}}
    assert not check_lead("count", ["nyc311"], q, docs, answered)


def test_extractive_no_from_an_unavailable_source_falls_back_to_cannot_answer(monkeypatch):
    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import CANNOT_ANSWER, NOTHING_TO_SHOW, Doc

    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("nws_alerts", "Projector", "NWS alerts unavailable for this point.", False)], [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"claims": [], "answer": {"lead": "no", "facts": ["nws_alerts"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "live_now", "plan": {"question": "Is there a flood warning here?"}})
    # The "no" is dropped with its only fact, so there is nothing to show: the line that promises
    # "Here is what they show." is not printed over nothing.
    assert NOTHING_TO_SHOW in out["paragraph"] and CANNOT_ANSWER not in out["paragraph"]
    assert "No." not in out["paragraph"] and out["grounding"]["answer_lead"] == "cannot_answer"


# Refactor 6: say why a source said nothing.

def test_no_gauge_nearby_is_a_true_zero_and_an_api_error_fails(monkeypatch):
    import dataretrieval.waterdata as wd
    import pandas as pd

    from app.context import usgs_gauges

    monkeypatch.setattr(wd, "get_latest_continuous", lambda **k: (pd.DataFrame(), None))
    v = usgs_gauges.summary_for_point(40.30, -73.50)
    assert v["n_gauges_in_area"] == 0 and v["narrative"].startswith("No active USGS stream gauge")
    monkeypatch.setattr(wd, "get_latest_continuous", _broken)
    with pytest.raises(OSError):
        usgs_gauges.summary_for_point(40.30, -73.50)


def test_a_briefing_with_no_evidence_names_the_failed_sources():
    from riprap.core.burr.templated_reconciler import compose_briefing

    state = {"intent": "single_address", "deployment": "nyc", "plan": {"question": ""}, "lat": 40.7, "lon": -73.9,
             "consulted": [{"id": "fema_nfhl", "title": "FEMA National Flood Hazard Layer", "stone": "cornerstone"},
                           {"id": "nyc311", "title": "NYC 311 flood-related complaints (5y)", "stone": "touchstone"}],
             "trace": [{"step": "fema_nfhl", "ok": False}, {"step": "nyc311", "ok": False}]}
    paragraph, cites = compose_briefing(state)
    assert "Riprap could not build this briefing" in paragraph and cites == {}
    assert "Failed to respond: FEMA National Flood Hazard Layer; NYC 311 flood-related complaints (5y)." in paragraph
    assert "No grounded data available" not in paragraph


# A failed FEMA query is a failed step, and a source zero the table cannot support is not printed.

@pytest.mark.parametrize("pebble,deployment", [("fema_pfirm", "nyc"), ("fema_nfhl", "federal")])
def test_a_failed_fema_map_is_a_failed_step_not_a_silence(monkeypatch, pebble, deployment):
    import httpx

    from riprap.core.pebbles import _http
    from riprap.core.pebbles.bridge import fetch_pebble

    def reset(*a, **k):
        raise httpx.ReadError("connection reset by peer")

    monkeypatch.setattr(_http.http, "get", reset)
    value, _, err = fetch_pebble(pebble, 40.5795, -73.8375, deployment=deployment)
    assert value is None and "connection reset by peer" in err


def test_no_preliminary_study_at_a_point_does_not_apply_and_is_no_failure(monkeypatch):
    from app.context import fema_nfhl
    from riprap.core.pebbles.bridge import fetch_pebble

    monkeypatch.setattr(fema_nfhl, "_point_query", lambda *a, **k: [])
    assert fetch_pebble("fema_pfirm", 40.30, -73.50, deployment="nyc") == (None, {}, None)


@pytest.mark.parametrize("row,said,missing", [
    # QN06: 448 residential units and "0" residents.
    ({"fp_100_bldg": 19, "fp_100_resunits": 448, "fp_100_pop": 0}, "counts 19 buildings and 448 residential units in",
     "The profile gives no resident count for this district."),
    # QN12: buildings, and "0" for both.
    ({"fp_100_bldg": 5, "fp_100_resunits": 0, "fp_100_pop": 0}, "counts 5 buildings in",
     "The profile gives no residential unit or resident count for this district."),
])
def test_floodplain_zero_the_table_cannot_support_is_not_printed(monkeypatch, row, said, missing):
    from types import SimpleNamespace

    from app.areas import nta_evidence
    from riprap.core import http

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rows": [{**row, "fp_100_area": 0.01}]}

    monkeypatch.setattr(http, "get", lambda *a, **k: R())
    v = nta_evidence.floodplain(None, SimpleNamespace(extras={"area_code": "QN12"}))
    assert said in v["narrative"] and v["narrative"].endswith(missing)
    assert "0 resident" not in v["narrative"] and v["n_residents_2010"] is None
