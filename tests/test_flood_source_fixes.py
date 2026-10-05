"""Sanity check of 5 October 2026, flood sources: each sentence fixed at
its cause says no more than its record supports."""

import numpy as np


def test_address_elevation_reads_the_cell_that_contains_the_point(monkeypatch):
    from rasterio.transform import from_origin

    from app.context import microtopo

    transform = from_origin(-74.0, 41.0, 0.01, 0.01)
    arr = np.arange(100, dtype="float32").reshape(10, 10)
    # The point is 70% of the way across cell (row 3, col 2): rounding read (4, 3).
    lat, lon = 41.0 - 3.6 * 0.01, -74.0 + 2.7 * 0.01
    assert microtopo._row_col(transform, lat, lon) == (3, 2)
    monkeypatch.setattr(microtopo, "_DEM_CACHE", {"arr": arr, "H": 10, "W": 10, "transform": transform,
                                                  "crs": "EPSG:4326", "twi": None, "hand": None})
    m = microtopo.microtopo_at(lat, lon)
    assert m.point_elev_m == 32.0
    assert m.narrative.startswith("Elevation 32.0 m (NAVD88);")  # the datum is in the sentence


def test_the_stated_datum_is_the_one_the_dem_file_declares():
    import pytest
    import rasterio

    from app.context import microtopo

    if not microtopo.DEM_PATH.exists():
        pytest.skip("the DEM is not in this checkout (git lfs pull)")
    with rasterio.open(microtopo.DEM_PATH) as ds:
        assert ds.tags()["vertical_datum"] == microtopo.VERTICAL_DATUM


def test_area_terrain_sentence_has_no_drainage_share(monkeypatch):
    from app.areas import nta_evidence

    monkeypatch.setattr(nta_evidence.microtopo, "microtopo_for_polygon",
                        lambda polygon: {"elev_median_m": 10.55, "elev_p10_m": 5.43, "frac_hand_lt1": 0.2878})
    v = nta_evidence.terrain(None)
    assert v["narrative"] == "Median ground elevation 10.55 m NAVD88 (10th percentile 5.43 m)."
    assert "drainage" not in v["narrative"] and "HAND" not in v["narrative"]


def test_permits_sentence_tests_expiry_and_names_the_file_it_reads(monkeypatch):
    from datetime import date, timedelta

    from shapely.geometry import box

    from app.areas import nta_evidence
    from app.context import dob_permits

    day = date.today()
    live, lapsed = (day + timedelta(days=30)).isoformat(), (day - timedelta(days=30)).isoformat()
    permits = [dob_permits.Permit(job_id=str(i), job_type="NB", job_type_label="new building", permit_status="ISSUED",
                                  issuance_date="2026-01-01", expiration_date=exp, address="", borough="Queens", bbl=None,
                                  lat=40.7, lon=-73.8, owner_business=None, permittee_business=None, nta_name=None)
               for i, exp in enumerate((live, lapsed, None))]
    monkeypatch.setattr(dob_permits, "permits_in_polygon", lambda *a, **k: permits)
    monkeypatch.setattr(dob_permits, "cross_reference_flood", lambda ps: [
        {**p.__dict__, "in_sandy": False, "dep_max_class": 0, "dep_scenarios": [], "any_flood_layer_hit": False} for p in ps])
    v = nta_evidence.permits(box(-73.9, 40.6, -73.7, 40.8))
    assert v["n_total"] == 3 and v["n_unexpired"] == 1
    assert "active" not in v["narrative"] and "active" not in v["headline_value"]
    assert "for 1 the latest permit has not expired" in v["narrative"]
    assert "DOB NOW" in v["narrative"] and "not every permit" in v["narrative"]


def test_a_plain_district_briefing_leaves_permits_out():
    from riprap.core.burr.stones import select_pebbles
    from riprap.core.pebbles.bridge import get_registry

    nyc = get_registry("nyc")
    assert "dob_permits_nta" not in select_pebbles({"intent": "neighborhood", "pebbles": None}, nyc)
    assert "dob_permits_nta" in select_pebbles({"intent": "development_check", "pebbles": None}, nyc)


def test_a_hospital_repeated_in_the_state_file_is_counted_once(monkeypatch, tmp_path):
    import json
    from dataclasses import replace

    from app.registers import exposure

    feat = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-74.087, 40.584]},
            "properties": {"fac_id": "1740", "facility_name": "Staten Island University Hosp-North"}}
    other = {**feat, "properties": {"fac_id": "1737", "facility_name": "Prince's Bay"}}
    p = tmp_path / "hospitals.geojson"
    p.write_text(json.dumps({"features": [feat, other, feat]}))
    monkeypatch.setitem(exposure.CLASSES, "doh_hospitals", replace(exposure.CLASSES["doh_hospitals"], geojson=p))
    exposure.geojson_rows.cache_clear()
    try:
        assert [r["fac_id"] for r in exposure.geojson_rows("doh_hospitals")] == ["1740", "1737"]
    finally:
        exposure.geojson_rows.cache_clear()


def test_the_shipped_hospital_file_has_one_row_per_facility():
    import json

    from app.registers import exposure

    with open(exposure.CLASSES["doh_hospitals"].geojson) as f:
        ids = [x["properties"]["fac_id"] for x in json.load(f)["features"]]
    assert len(ids) == len(set(ids)) == 61
