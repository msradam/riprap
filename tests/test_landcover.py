"""The experimental land-cover source reads one raster per year and holds
a change between years against the model's own noise. Offline."""

import json

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from pyproj import Transformer  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

from app import experimental  # noqa: E402
from app.eo import landcover as lc  # noqa: E402

LON, LAT = -73.778, 40.7128


@pytest.fixture
def maps(tmp_path, monkeypatch):
    """2018: the west half built, the east half trees. 2026: `extra_cols`
    more columns of the east half built, and `cloud_rows` rows at the top
    with no label. Noise: 2 points for a district, 3 for a neighbourhood
    (and for the 500 m circle of an address)."""
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)

    def write(year: int, extra_cols: int, cloud_rows: int = 0):
        a = np.full((200, 200), lc.TREES, "uint8")
        a[:, :100 + extra_cols] = lc.BUILT
        a[:cloud_rows] = 255
        with rasterio.open(tmp_path / f"landcover_{year}.tif", "w", driver="GTiff", dtype="uint8", count=1, height=200,
                           width=200, crs="EPSG:32618", transform=from_origin(x - 1000, y + 1000, 10, 10),
                           nodata=255) as dst:
            dst.write(a, 1)
            dst.update_tags(dates="2018-05-01;2018-07-02")

    (tmp_path / "landcover.json").write_text(json.dumps({
        "noise_points": 2.0, "noise_points_small": 3.0, "eval_year": 2021, "group_agreement_pct": 80.0,
        "green_found_pct": 60.0, "district_built_vs_worldcover": "9.0 points above"}))
    monkeypatch.setattr(lc, "EO_DIR", tmp_path)
    monkeypatch.setattr(experimental, "EVAL_DIR", tmp_path)
    lc._dates_at.cache_clear()
    yield write
    lc._dates_at.cache_clear()


def test_shares_of_the_latest_year_with_the_hedge(maps):
    maps(2018, 0)
    v = lc.for_point(LAT, LON)
    assert v["year"] == 2018 and 48 <= v["built_pct"] <= 52 and 48 <= v["green_pct"] <= 52
    n = v["narrative"]
    assert n.startswith("Experimental: a satellite land-cover model labels") and "as paved or built over" in n
    assert "it agreed with ESA WorldCover (its own label source) on 80.0% of" in n and "Rely on NYC's own land cover map" in n


def test_a_change_inside_the_noise_is_no_change(maps):
    maps(2018, 0)
    maps(2026, 1)  # about 1 point more built: inside the 2 points of noise
    v = lc.for_point(LAT, LON)
    assert v["first_year"] == 2018 and abs(v["built_change_points"]) <= 2
    assert v["noise_points"] == 3.0  # an address is judged by the neighbourhood-scale noise, not the district's
    assert "so no change is measurable and no trend in runoff follows from it" in v["narrative"]
    assert "possibly" not in v["narrative"]


def test_a_difference_beyond_the_noise_is_stated_and_no_trend_is_read_from_it(maps):
    # Across the city such differences appear as often as the noise alone produces them.
    maps(2018, 0)
    maps(2026, 30)  # about 15 points more built
    v = lc.for_point(LAT, LON)
    assert v["built_change_points"] > 10
    assert "more than the 3.0 points by which two images of one year usually differ" in v["narrative"]
    assert "so no trend in paving or runoff is read from it" in v["narrative"] and "possibly" not in v["narrative"]


def test_a_cloud_gap_in_one_year_is_not_read_as_change(maps):
    # 2026 lost its top rows to cloud: the two years are compared on the
    # pixels both labelled, and with too few in common they are not compared.
    maps(2018, 0)
    maps(2026, 0, cloud_rows=60)  # the circle keeps over 80% of its pixels
    v = lc.for_point(LAT, LON)
    assert v["built_change_points"] == 0 and v["built_pct"] == v["built_pct_first"]
    maps(2026, 0, cloud_rows=95)  # under 80% in common
    v = lc.for_point(LAT, LON)
    assert "first_year" not in v and "in 2018 the" not in v["narrative"]


def test_an_evaluation_file_from_an_older_batch_does_not_break_the_sentence(maps, tmp_path):
    maps(2018, 0)
    (tmp_path / "landcover.json").write_text(json.dumps({"noise_points": 2.0}))
    assert "its saved evaluation is out of date" in lc.for_point(LAT, LON)["narrative"]


def test_no_saved_map_means_no_value(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "EO_DIR", tmp_path)
    assert lc.for_point(LAT, LON) is None
