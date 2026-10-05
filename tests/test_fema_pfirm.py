"""The preliminary FIRM reader takes the vintage from FEMA's availability
layer, since the preliminary panel records carry no date."""
import pytest

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


def test_effective_panel_comes_from_the_zones_own_study(monkeypatch):
    """At Staten Island's shore two New Jersey countywide panels cover the
    point as well as NYC's. The panel cited is from the zone's study, even
    when a neighbouring county's panel is newer."""
    zone = [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F",
                            "DFIRM_ID": "360497"}}]
    panels = [{"attributes": {"FIRM_PAN": "34017C0114D", "EFF_DATE": 1400000000000, "DFIRM_ID": "34017C"}},
              {"attributes": {"FIRM_PAN": "3604970189F", "EFF_DATE": 1188950400000, "DFIRM_ID": "360497"}}]
    monkeypatch.setattr(fema_nfhl, "_point_query",
                        lambda layer, lat, lon, fields, ttl, base=fema_nfhl.URL: zone if layer == 28 else panels)
    v = fema_nfhl.summary_for_point(40.642, -74.076)
    assert v["firm_panel"] == "3604970189F" and v["effective_year"] == 2007


def test_each_fema_sentence_names_its_map_and_date(monkeypatch):
    """Two FEMA maps cover New York City. The effective one (2007) is in
    force for the National Flood Insurance Program; the preliminary one
    (2015) is not. Each sentence says which map it reads and its date."""
    zone = [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "T", "DFIRM_ID": "360497",
                            "STATIC_BFE": 12, "V_DATUM": "NAVD88"}}]
    panels = [{"attributes": {"FIRM_PAN": "3604970192F", "EFF_DATE": 1188950400000, "DFIRM_ID": "360497"}}]
    monkeypatch.setattr(fema_nfhl, "_point_query", lambda layer, lat, lon, fields, ttl, base=fema_nfhl.URL:
                        zone if layer == 28 else _STUDY if base == fema_nfhl.PRELIM_URL else panels)
    effective = fema_nfhl.summary_for_point(40.678, -74.0095)["narrative"]
    assert effective == ("This address sits in FEMA flood zone AE (a Special Flood Hazard Area) on FEMA's effective "
                         "flood map (FIRM panel 3604970192F, effective 2007-09-05), the map in force for the National "
                         "Flood Insurance Program.")
    preliminary = fema_nfhl.preliminary_for_point(40.678, -74.0095)["narrative"]
    assert preliminary.startswith("FEMA's preliminary flood map (PFIRM issued 2015-01-30, community 360497) places")
    assert "does not set flood insurance" in preliminary


def test_the_nyc_preliminary_sentence_says_which_map_the_city_and_fema_use():
    """The city's own account (NYC Hazard Mitigation Plan, flooding profile,
    read 2026-10-05): "New York City applies whichever map (2015 PFIRMs or
    2007 FIRMs) is the more restrictive of the two for Building Code and
    zoning purposes" and "FEMA uses the 2007 FIRMs for compliance with NFIP"."""
    from riprap.core.burr.evidence import sentence_for
    from riprap.core.pebbles import load_registry

    m = load_registry("deployments/nyc").get("fema_pfirm").manifest
    text = sentence_for({"narrative": "FEMA's preliminary flood map (PFIRM issued 2015-01-30) places this address in zone X."}, m)
    assert ("New York City applies whichever of the 2015 preliminary maps or the 2007 effective maps is more restrictive "
            "for Building Code and zoning purposes, and FEMA uses the 2007 effective maps for the National Flood "
            "Insurance Program") in text


class _Reply:
    def __init__(self, body):
        self.text = body

    def raise_for_status(self):
        pass

    def json(self):
        import json

        return json.loads(self.text)


def _raises(exc):
    def get(*a, **k):
        raise exc
    return get


@pytest.mark.parametrize("reader", [fema_nfhl.summary_for_point, fema_nfhl.preliminary_for_point])
@pytest.mark.parametrize("how", ["timeout", "http error", "reset", "empty body", "malformed body", "arcgis error"])
def test_a_failed_fema_query_raises_and_never_reads_as_no_zone(monkeypatch, reader, how):
    """Every failure path: a timeout, an HTTP error, a reset connection, an
    empty or malformed reply, and ArcGIS's error body under HTTP 200. Each
    once returned None, the same as "nothing mapped here"."""
    import httpx

    from riprap.core.pebbles import _http

    request = httpx.Request("GET", "https://hazards.fema.gov/")
    get = {
        "timeout": _raises(httpx.ReadTimeout("timed out", request=request)),
        "http error": _raises(httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))),
        "reset": _raises(httpx.ReadError("connection reset by peer", request=request)),
        "empty body": lambda *a, **k: _Reply(""),
        "malformed body": lambda *a, **k: _Reply("<html>Service unavailable</html>"),
        "arcgis error": lambda *a, **k: _Reply('{"error": {"code": 500, "message": "Error performing query operation"}}'),
    }[how]
    monkeypatch.setattr(_http.http, "get", get)
    with pytest.raises(httpx.HTTPError):
        reader(40.5795, -73.8375)


def test_a_point_no_map_covers_is_an_answer_not_a_failure(monkeypatch):
    from riprap.core.pebbles import _http

    monkeypatch.setattr(_http.http, "get", lambda *a, **k: _Reply('{"features": []}'))
    assert fema_nfhl.summary_for_point(40.30, -73.50) is None
    assert fema_nfhl.preliminary_for_point(40.30, -73.50) is None


def test_a_failed_reply_is_not_served_again_from_the_cache(monkeypatch, tmp_path):
    """FEMA's service answers some failures with HTTP 200 and an empty body
    or an error object. The HTTP cache kept any 200 for the call's lifetime
    (a day for FEMA), so one bad minute read as a failed source for a day."""
    import httpx

    from riprap.core import http

    replies = iter([httpx.Response(200, content=b""),
                    httpx.Response(200, json={"error": {"code": 500, "message": "Error performing query operation"}}),
                    httpx.Response(200, json={"features": [{"attributes": {"FLD_ZONE": "AE"}}]})])
    sent = []

    def handler(request):
        sent.append(request)
        return next(replies)

    monkeypatch.setenv("RIPRAP_HTTP_CACHE", str(tmp_path / "http.sqlite"))
    monkeypatch.setattr(http.httpx, "HTTPTransport", lambda: httpx.MockTransport(handler))
    http.client.cache_clear()
    try:
        for _ in range(2):  # the empty body, then the error object: each raises and neither is kept
            with pytest.raises(httpx.HTTPError):
                fema_nfhl._point_query(28, 40.58, -73.84, "FLD_ZONE", 86400)
        assert fema_nfhl._point_query(28, 40.58, -73.84, "FLD_ZONE", 86400) == [{"attributes": {"FLD_ZONE": "AE"}}]
        assert fema_nfhl._point_query(28, 40.58, -73.84, "FLD_ZONE", 86400) == [{"attributes": {"FLD_ZONE": "AE"}}]
        assert len(sent) == 3  # the good reply is cached; the failures were not
    finally:
        http.client.cache_clear()
        http._STORAGE.clear()
