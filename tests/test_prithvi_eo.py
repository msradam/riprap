"""The experimental satellite source reads the batch outputs: new water
after Ida, and which of the other saved storms showed any. Small fixture
rasters stand in for data/eo/. Offline."""

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
gpd = pytest.importorskip("geopandas")

from pyproj import Transformer  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import box  # noqa: E402

from app.flood_layers import prithvi_water as pw  # noqa: E402

LON, LAT = -73.778, 40.7128  # Hollis
POST = "S2A_MSIL2A_20210902T154911_R054_T18TWL_20210903T050849"
PRE = "S2A_MSIL2A_20210813T154911_R054_T18TWL_20210814T063950"
EVENTS = ("2020-04-13", pw.IDA, "2023-09-29", "2024-08-06")


def _write(path, arrays, x, y, **tags):
    with rasterio.open(path, "w", driver="GTiff", dtype="uint8", count=len(arrays), height=200, width=200,
                       crs="EPSG:32618", transform=from_origin(x - 1000, y + 1000, 10, 10),
                       nodata=255 if len(arrays) == 1 else None) as dst:
        for i, a in enumerate(arrays, 1):
            dst.write(a, i)
        dst.update_tags(**tags)


@pytest.fixture
def eo(tmp_path, monkeypatch):
    """A 2 km square at 10 m centred on the point. Ida and one other storm
    show 100 pixels of new water at the point; two more storms show none.
    The west edge was never observed."""
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    for i, e in enumerate(EVENTS):
        a = np.zeros((200, 200), "uint8")
        if i < 2:
            a[95:105, 95:105] = 1          # 100 pixels = 10,000 m2
        a[:, :20] = 255
        _write(tmp_path / f"prithvi_new_water_{e}.tif", [a], x, y, rain_date=e, post_scene=POST, pre_scene=PRE)
    monkeypatch.setattr(pw, "EO_DIR", tmp_path)
    pw._tags_at.cache_clear()
    yield
    pw._tags_at.cache_clear()


def test_a_point_reports_ida_its_scenes_the_other_storms_and_the_hedge(eo):
    v = pw.summary_for_point(LAT, LON)
    assert 9_000 <= v["new_water_m2"] <= 10_000 and v["radius_m"] == 500
    n = v["narrative"]
    assert n.startswith("Experimental: a satellite model on Sentinel-2 scenes from 2021-09-02, the day after Hurricane "
                        "Ida, compared with 2021-08-13, showed")
    assert "of 3 other heavy-rain events since 2017 with a clear pass over this place, it showed new water after 1 (2020-04-13)" in n
    assert "Limits:" in n and "street and basement flooding" in n and "Rely on" in n
    assert "prone" not in n and "linger" not in n  # what it showed, never a tendency


def test_an_unobserved_place_says_the_model_saw_nothing(eo):
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    lon, lat = Transformer.from_crs(32618, 4326, always_xy=True).transform(x - 900, y)  # in the unobserved strip
    v = pw.summary_for_point(lat, lon, radius_m=50)
    assert v["frac_observed"] == 0.0 and "saw nothing here" in v["narrative"] and v["other_events"] == []


def test_an_area_share_is_of_the_observed_part(eo):
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    sq = gpd.GeoSeries([box(x - 500, y - 500, x + 500, y + 500)], crs=32618).to_crs(4326).iloc[0]
    v = pw.summary_for_polygon(sq)
    assert v["new_water_m2"] == 10_000 and v["frac_observed"] == 1.0 and abs(v["frac_new_water"] - 0.01) < 0.001
    assert [o["rain_date"] for o in v["other_events"] if o["new_water_m2"]] == ["2020-04-13"]


def test_a_partly_observed_area_says_how_much_was_seen(eo):
    # The raster's "not observed" pixels were once read as outside the area, so this was always 100%.
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    sq = gpd.GeoSeries([box(x - 1000, y - 500, x, y + 500)], crs=32618).to_crs(4326).iloc[0]  # 200 m of 1,000 unobserved
    v = pw.summary_for_polygon(sq)
    assert abs(v["frac_observed"] - 0.8) < 0.02 and "(80% of it observed)" in v["narrative"]


def test_missing_outputs_mean_no_value(tmp_path, monkeypatch):
    monkeypatch.setattr(pw, "EO_DIR", tmp_path)
    assert pw.summary_for_point(LAT, LON) is None and pw.summary_for_polygon(box(0, 0, 1, 1)) is None
