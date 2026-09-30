"""The preliminary FIRM reader takes the vintage from FEMA's availability
layer, since the preliminary panel records carry no date."""
from app.context import fema_nfhl

_ZONE = [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "T", "STATIC_BFE": 11}}]
_STUDY = [{"attributes": {"DFIRM_ID": "360497", "PRELM_ISSUE_DATE": 1422615600000}}]


def test_preliminary_zone_carries_issue_date_and_bfe(monkeypatch):
    monkeypatch.setattr(fema_nfhl, "_point_query",
                        lambda layer, lat, lon, fields, ttl, base=fema_nfhl.URL: _ZONE if layer == 28 else _STUDY)
    v = fema_nfhl.preliminary_for_point(40.677, -74.0105)
    assert v["fld_zone"] == "AE" and v["sfha"] and v["static_bfe_ft"] == 11.0
    assert v["issue_date"] == "2015-01-30"
    assert "PFIRM issued 2015-01-30" in v["narrative"] and "base flood elevation 11 ft" in v["narrative"]
    assert "preliminary map is not the effective map" in v["narrative"]


def test_no_bfe_when_the_zone_has_none(monkeypatch):
    zone = [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F",
                            "STATIC_BFE": -9999}}]
    monkeypatch.setattr(fema_nfhl, "_point_query",
                        lambda layer, lat, lon, fields, ttl, base=fema_nfhl.URL: zone if layer == 28 else _STUDY)
    v = fema_nfhl.preliminary_for_point(40.711, -73.777)
    assert v["static_bfe_ft"] is None and "base flood elevation" not in v["narrative"]
    assert "zone X (an area of minimal flood hazard)" in v["narrative"]
