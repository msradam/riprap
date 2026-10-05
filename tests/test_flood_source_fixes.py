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
