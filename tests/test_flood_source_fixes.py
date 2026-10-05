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


def test_permit_dates_compare_as_dates(monkeypatch):
    """The file writes 'MM/DD/YYYY'; as text '12/29/2025' sorts after
    '04/01/2026', so the older permit of a job was kept as its latest."""
    from shapely.geometry import box

    from app.context import dob_permits

    class R:
        def raise_for_status(self): pass

        def json(self):
            base = {"job__": "1", "job_type": "NB", "gis_latitude": "40.7", "gis_longitude": "-73.8"}
            return [{**base, "issuance_date": "12/29/2025", "expiration_date": "01/15/2026"},
                    {**base, "issuance_date": "04/01/2026", "expiration_date": "04/01/2099"}]

    monkeypatch.setattr(dob_permits.http, "get", lambda *a, **k: R())
    assert dob_permits._iso("12/29/2025") == "2025-12-29" and dob_permits._iso("2020-06-05T00:00:00") == "2020-06-05"
    (job,) = dob_permits.permits_in_polygon(box(-73.9, 40.6, -73.7, 40.8))
    assert (job.issuance_date, job.expiration_date) == ("2026-04-01", "2099-04-01")


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


def test_no_alerts_sentence_claims_only_the_alerts_it_checks():
    from app.context import nws_alerts

    none = nws_alerts._NONE["flood"]
    assert "wind" not in none
    assert not nws_alerts._relevant("Wind Advisory", "flood") and not nws_alerts._relevant("High Wind Warning", "flood")
    for event in ("Flood Warning", "Coastal Flood Advisory", "Tropical Storm Warning"):  # the three the sentence names
        assert nws_alerts._relevant(event, "flood")


def test_a_development_is_inside_sandy_by_the_share_of_its_outline():
    import geopandas as gpd
    import pytest
    from shapely.geometry import box

    from app.assets import nycha

    # Two buildings: the larger is wholly inside the extent, and the centre
    # point of the pair falls in the gap between them, outside it.
    extent = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10)], crs="EPSG:2263")
    site = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10).union(box(30, 0, 34, 10))], crs="EPSG:2263")
    assert not extent.geometry.iloc[0].contains(site.geometry.iloc[0].centroid)
    assert nycha.footprint_share(site, extent) == [pytest.approx(100 / 140)]
    assert nycha.footprint_share(gpd.GeoDataFrame(geometry=[box(50, 50, 60, 60)], crs="EPSG:2263"), extent) == [0.0]


def test_the_housing_register_counts_hammel_and_states_its_rule():
    """The sanity check: 20 developments by centre point, 39 with 10% or
    more of the outline inside; Hammel (94% inside) was missed."""
    from app.registers import exposure
    from app.registers._loader import load_register

    rows = {r["name"]: r for r in load_register("nycha")}
    assert sum(1 for r in rows.values() if r["snap"]["sandy"]) == 39
    assert rows["HAMMEL"]["snap"]["sandy"] and rows["HAMMEL"]["sandy_share"] > 0.9
    assert not rows["GOWANUS"]["snap"]["sandy"]  # 0.7% of its outline: named, not counted
    s = exposure.summary_for_point(40.6787, -73.9897, "nycha")  # 400 Carroll Street
    assert "10% or more of their mapped outline inside the 2012 Sandy extent" in s["narrative"]
    assert "centre point inside one of three modeled DEP stormwater scenarios" in s["narrative"] and "the Limited Flood map is not tested" in s["narrative"]
    assert "Under 10% of the outline inside the 2012 Sandy extent (not counted): GOWANUS" in s["narrative"]
    assert s["n_inside_sandy_2012"] == 2 and s["n_near_sandy_edge"] == 1


def test_schools_are_public_schools_with_their_vintage_and_the_right_link():
    """The file is the 2019 to 2020 school year's and 263 of its 1,992 rows
    are charter schools, so "NYC DOE school" was the wrong label."""
    from app.registers import exposure
    from riprap.core.pebbles.bridge import get_registry

    s = exposure.summary_for_point(40.677, -74.0105, "doe_schools")  # Red Hook
    assert "NYC DOE school" not in s["narrative"]
    assert s["narrative"].startswith(f"{s['n_schools']} public schools inside a mapped flood extent within 1500 m")
    assert "2019 to 2020 school year, charter schools included" in s["narrative"]
    assert "location point is inside" in s["narrative"]  # the rule for a point asset
    by_name = {f["loc_name"]: f for f in s["schools"]}
    assert by_name["PAVE Academy Charter School"]["managed_by"] == "Charter"
    assert by_name["P.S. 015 Patrick F. Daly"]["managed_by"] == "DOE"
    for pebble_id in ("doe_schools", "doe_schools_nta"):
        m = get_registry("nyc").get(pebble_id).manifest
        assert m.provenance.source_url.endswith("/2019-2020-School-Point-Locations/a3nt-yts4")
        assert "DOE school" not in m.title


def test_a_distant_stream_gauge_is_not_quoted(monkeypatch):
    """350 Fifth Avenue was given the Bronx River, 15.7 km away."""
    from datetime import UTC, datetime

    import dataretrieval.waterdata as wd
    import pandas as pd
    from shapely.geometry import Point

    from app.context import usgs_gauges

    def one_gauge_at(lat, lon):
        df = pd.DataFrame([{"monitoring_location_id": "USGS-01302020", "geometry": Point(lon, lat),
                            "parameter_code": "00065", "value": 0.61, "time": pd.Timestamp(datetime.now(UTC))}])
        monkeypatch.setattr(wd, "get_latest_continuous", lambda **k: (df, None))
        monkeypatch.setattr(wd, "get_monitoring_locations", lambda **k: (
            pd.DataFrame([{"monitoring_location_name": "BRONX RIVER AT NY BOTANICAL GARDEN AT BRONX NY"}]), None))

    one_gauge_at(40.8623, -73.8744)
    far = usgs_gauges.summary_for_point(40.7484, -73.9857)  # 350 Fifth Avenue
    assert far["n_gauges_in_area"] == 0 and "Bronx River" not in far["narrative"]
    assert far["narrative"].endswith("within 5 km of this address.")
    near = usgs_gauges.summary_for_point(40.8600, -73.8800)
    assert near["n_gauges_in_area"] == 1 and "Bronx River" in near["narrative"]


def test_tide_sentence_says_the_station_is_the_nearest_and_where_it_is(monkeypatch):
    from app.context import noaa_tides

    monkeypatch.setattr(noaa_tides, "_fetch", lambda sid, product: (
        {"data": [{"v": "4.31", "t": "2026-10-05 14:36"}]} if product == "water_level"
        else {"predictions": [{"v": "4.05", "t": "2026-10-05 14:36"}]}))
    n = noaa_tides.summary_for_point(40.6936, -73.7822)["narrative"]  # the centre of QN12
    assert n.startswith("Latest reading at Kings Point, NY, the nearest NOAA tide station in a straight line (")
    assert " km away, on Long Island Sound): 4.31 ft above MLLW" in n


def test_sandy_area_sentence_gives_the_flooded_area_and_the_whole(monkeypatch):
    from app.areas import nta_evidence

    monkeypatch.setattr(nta_evidence.sandy_inundation, "coverage_for_polygon", lambda polygon: {
        "overlap_area_m2": 190_000.0, "polygon_area_m2": 24_700_000.0, "fraction": 0.0077, "inside": True})
    n = nta_evidence.sandy(None)["narrative"]
    assert n == ("0.8% of this area lies inside the 2012 Hurricane Sandy inundation extent "
                 "(0.19 km² of the area's 24.7 km²).")


def test_named_lists_carry_their_extent_and_say_modeled_for_a_scenario():
    """A list of named facilities is a statement about a mapped extent: the
    event or the scenario is named, a scenario is called modeled, and the
    count is not of "flood-exposed" facilities."""
    import re

    from app.registers import exposure

    coney = (40.5757, -73.986)
    for asset_class in exposure.CLASSES:
        n = exposure.summary_for_point(*coney, asset_class)["narrative"]
        assert "flood-exposed" not in n
        lists = re.findall(r"\. ([^.:]+): ", n)  # the label before each list of names
        assert lists, asset_class
        for label in lists:
            assert "2012 Sandy extent" in label or "modeled DEP extreme scenario (2080 sea-level rise)" in label, label
    hospitals = exposure.summary_for_point(*coney, "doh_hospitals")["narrative"]
    assert "each read at the one point the state file gives for it" in hospitals


def test_the_terrain_value_carries_no_wetness_index_or_area_drainage_share():
    """The district clause "less than 1 m above the nearest drainage
    channel" was removed, but the JSON still gave the same figure
    (frac_hand_lt1) and the address value a wetness index, from the same
    synthetic channels."""
    import dataclasses

    from app.areas import nta
    from app.context import microtopo

    assert "twi" not in {f.name for f in dataclasses.fields(microtopo.Microtopo)}
    area = nta.resolve("Hollis")[0]["geometry"]
    v = microtopo.microtopo_for_polygon(area)
    assert v is None or set(v) == {"n_cells", "elev_min_m", "elev_median_m", "elev_p10_m", "elev_max_m"}
