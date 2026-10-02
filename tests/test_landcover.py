"""The experimental land-cover source reads one raster per year (five bands
of percent at 30 m), reports the latest year with enough ground in view, and
never reads a change between years. Offline."""

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
    """A 3 km square of 30 m cells per year: the west `west_paved` columns
    (of 100) paved, the rest tree canopy, unless `mixed` gives every cell the
    same mix; `cloud_rows` rows at the top have no value."""
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)

    def write(year: int, west_paved: int = 50, cloud_rows: int = 0, mixed: dict | None = None):
        a = np.zeros((5, 100, 100), "uint8")  # percent of each cell in each group
        a[lc.PAVED, :, :west_paved] = 100
        a[lc.TREES, :, west_paved:] = 100
        if mixed:
            a[:] = 0
            for band, pct in mixed.items():
                a[band] = pct
        a[:, :cloud_rows] = 255
        with rasterio.open(tmp_path / f"landcover_{year}.tif", "w", driver="GTiff", dtype="uint8", count=5, height=100,
                           width=100, crs="EPSG:32618", transform=from_origin(x - 1500, y + 1500, 30, 30),
                           nodata=255) as dst:
            dst.write(a)
            dst.update_tags(dates=f"{year}-06-20;{year}-07-20")

    (tmp_path / "landcover.json").write_text(json.dumps({
        "noise_points": 2.0, "noise_points_small": 2.7, "eval_year": 2021,
        "district_paved_vs_city_map": "1.7 points above", "district_paved_gap_points_max": 7.8,
        "between_years_worst": "2018 and 2024", "between_years_beyond_noise": 49, "between_years_districts": 59}))
    monkeypatch.setattr(lc, "EO_DIR", tmp_path)
    monkeypatch.setattr(experimental, "EVAL_DIR", tmp_path)
    lc._dates_at.cache_clear()
    yield write
    lc._dates_at.cache_clear()


def test_shares_of_the_latest_year_with_the_hedge(maps):
    maps(2018, west_paved=50)
    v = lc.for_point(LAT, LON)
    assert v["year"] == 2018 and 47 <= v["built_pct"] <= 53 and 47 <= v["green_pct"] <= 53
    assert v["tree_pct"] == v["green_pct"]
    n = v["narrative"]
    assert n.startswith("Experimental: a satellite land-cover model estimates that") and "is paved or built over" in n
    assert "against the city's own 2021 six-inch map, on squares it never trained on" in n
    assert "district's paved share 1.7 points above the map's" in n and "Rely on NYC's own land cover maps" in n


def test_mixed_cells_are_averaged_not_counted(maps):
    # Every cell 40% roof, 35% canopy, 25% grass: counting one label per cell would say 0% or 100% paved.
    maps(2018, mixed={lc.PAVED: 40, lc.TREES: 35, lc.GRASS: 25})
    v = lc.for_point(LAT, LON)
    assert v["built_pct"] == 40.0 and v["green_pct"] == 60.0 and v["tree_pct"] == 35.0
    assert "(35.0% tree canopy)" in v["narrative"]


def test_years_are_never_compared_and_the_sentence_says_why(maps):
    maps(2018, mixed={lc.PAVED: 20, lc.TREES: 80})
    maps(2026, mixed={lc.PAVED: 80, lc.TREES: 20})  # 60 points more paved: still not read as change
    v = lc.for_point(LAT, LON)
    assert v["year"] == 2026 and v["built_pct"] == 80.0
    assert "first_year" not in v and "built_change_points" not in v and "by_year" not in v
    n = v["narrative"]
    assert "no change between years is read from it" in n
    assert "between 2018 and 2024, 49 of 59 districts' paved shares differ by more than 2.0 points" in n
    assert "in 2018" not in n  # the older map's share is not quoted


def test_a_clouded_latest_year_falls_back_to_the_year_before(maps):
    maps(2021, mixed={lc.PAVED: 30, lc.GRASS: 70})
    maps(2026, mixed={lc.PAVED: 60, lc.GRASS: 40}, cloud_rows=100)  # nothing in view
    v = lc.for_point(LAT, LON)
    assert v["year"] == 2021 and v["built_pct"] == 30.0


def test_an_evaluation_file_from_an_older_batch_does_not_break_the_sentence(maps, tmp_path):
    maps(2018)
    (tmp_path / "landcover.json").write_text(json.dumps({"noise_points": 2.0}))
    n = lc.for_point(LAT, LON)["narrative"]
    assert "its saved evaluation is out of date" in n and "no change between years is read from it" in n


def test_no_saved_map_means_no_value(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "EO_DIR", tmp_path)
    assert lc.for_point(LAT, LON) is None
