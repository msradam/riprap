"""The Prithvi-EO Ida pebbles read the batch outputs (refactor 8). A small
fixture raster and NTA table stand in for data/eo/. Offline."""

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
gpd = pytest.importorskip("geopandas")

from pyproj import Transformer  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import Point, box  # noqa: E402

from app.flood_layers import prithvi_water as pw  # noqa: E402

LON, LAT = -73.778, 40.7128  # Hollis
POST = "S2A_MSIL2A_20210902T154911_R054_T18TWL_20210903T050849"
PRE = "S2A_MSIL2A_20210813T154911_R054_T18TWL_20210814T063950"


@pytest.fixture
def eo(tmp_path, monkeypatch):
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    a = np.zeros((200, 200), "uint8")  # 2 km square at 10 m, centred on the point
    a[95:105, 95:105] = 1              # 100 new-water pixels = 10,000 m2 at the point
    a[:, :20] = 255                    # the west edge was not observed
    tr = from_origin(x - 1000, y + 1000, 10, 10)
    tif = tmp_path / f"prithvi_new_water_{pw.EVENT}.tif"
    with rasterio.open(tif, "w", driver="GTiff", dtype="uint8", count=1, height=200, width=200,
                       crs="EPSG:32618", transform=tr, nodata=255) as dst:
        dst.write(a, 1)
        dst.update_tags(rain_date=pw.EVENT, post_scene=POST, pre_scene=PRE, model=pw.MODEL)
    nta = gpd.GeoDataFrame({"nta2020": ["QN1206"], "ntaname": ["Hollis"], "frac_new_water": [0.0025],
                            "frac_observed": [0.9]},
                           geometry=[box(LON - 0.01, LAT - 0.01, LON + 0.01, LAT + 0.01)], crs="EPSG:4326")
    nta.to_parquet(tmp_path / f"prithvi_new_water_{pw.EVENT}_by_nta.parquet")
    monkeypatch.setattr(pw, "EO_DIR", tmp_path)
    pw._tags.cache_clear()
    yield
    pw._tags.cache_clear()


def test_point_reports_new_water_nta_share_scenes_and_the_caveat(eo):
    v = pw.summary_for_point(LAT, LON)
    assert 9_000 <= v["new_water_m2_within_radius"] <= 10_000
    assert v["nta_name"] and 0 <= v["nta_frac_new_water"] <= 1  # computed from the raster
    n = v["narrative"]
    assert n.startswith("Experimental: a satellite model (Prithvi-EO 2.0, NYC fine-tune) on Sentinel-2 scenes from 2021-09-02, "
                        "compared with 2021-08-13")
    assert "not evidence of no flooding" in n


def test_unobserved_area_says_the_model_saw_nothing(eo):
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    lon, lat = Transformer.from_crs(32618, 4326, always_xy=True).transform(x - 900, y)  # in the 255 strip
    v = pw.summary_for_point(lat, lon, radius_m=50)
    assert v["frac_observed_within_radius"] == 0.0 and "saw nothing" in v["narrative"]


def test_area_share_is_of_the_observed_part(eo):
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(LON, LAT)
    sq = gpd.GeoSeries([box(x - 500, y - 500, x + 500, y + 500)], crs=32618).to_crs(4326).iloc[0]
    v = pw.summary_for_polygon(sq)
    assert v["new_water_m2"] == 10_000 and v["frac_observed"] == 1.0
    assert abs(v["frac_new_water"] - 0.01) < 0.001


def test_map_layer_is_polygons_of_new_water(eo):
    fc = pw.layer_geojson(LAT, LON, r=300)
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 1
    assert Point(LON, LAT).within(gpd.GeoDataFrame.from_features(fc["features"], crs=4326).union_all().buffer(0.0005))


def test_missing_outputs_mean_no_value(tmp_path, monkeypatch):
    monkeypatch.setattr(pw, "EO_DIR", tmp_path)
    assert pw.summary_for_point(LAT, LON) is None and pw.summary_for_polygon(box(0, 0, 1, 1)) is None
