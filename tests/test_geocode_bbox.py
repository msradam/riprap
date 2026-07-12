"""Geocoding is biased to the active deployment's coverage bbox so an
ambiguous name resolves in-region (e.g. "Red Hook" -> Brooklyn, not the
same-named village in Dutchess County). These tests guard the wiring
without hitting the live Nominatim API."""

import app.geocode as gc


def test_active_bbox_resolves_nyc(monkeypatch):
    monkeypatch.setenv("RIPRAP_DEPLOYMENT", "deployments/nyc")
    gc._active_deployment_bbox.cache_clear()
    bbox = gc._active_deployment_bbox()
    assert bbox is not None
    min_lon, min_lat, max_lon, max_lat = bbox
    # Red Hook, Brooklyn (~40.675, -74.01) is inside; the Dutchess County
    # village of Red Hook (~41.99) is not.
    assert min_lat <= 40.675 <= max_lat
    assert not (min_lat <= 41.99 <= max_lat)


def test_geocode_one_tries_region_bounded_first(monkeypatch):
    monkeypatch.setenv("RIPRAP_DEPLOYMENT", "deployments/nyc")
    gc._active_deployment_bbox.cache_clear()
    calls = []

    def fake_nominatim(text, *, viewbox=None, bounded=False):
        calls.append({"viewbox": viewbox, "bounded": bounded})
        return gc.GeocodeHit(
            address="Red Hook, Brooklyn",
            borough="Brooklyn",
            lat=40.675,
            lon=-74.01,
            bbl=None,
            bin=None,
            raw={},
        )

    monkeypatch.setattr(gc, "geocode_nominatim", fake_nominatim)
    monkeypatch.setattr(gc, "geocode", lambda text, limit=5: [])  # skip enrichment

    hit = gc.geocode_one("Red Hook")
    assert hit is not None and hit.borough == "Brooklyn"
    # First attempt is region-bounded with a viewbox derived from the bbox.
    assert calls[0]["bounded"] is True
    (lat1, lon1), (lat2, lon2) = calls[0]["viewbox"]
    assert lat1 <= 40.675 <= lat2 and lon1 <= -74.01 <= lon2


def test_geocode_one_falls_back_when_out_of_region(monkeypatch):
    monkeypatch.setenv("RIPRAP_DEPLOYMENT", "deployments/nyc")
    gc._active_deployment_bbox.cache_clear()
    calls = []

    def fake_nominatim(text, *, viewbox=None, bounded=False):
        calls.append(bounded)
        if bounded:
            return None  # nothing inside the served region
        return gc.GeocodeHit(
            address="Willis Tower, Chicago",
            borough=None,
            lat=41.8787,
            lon=-87.636,
            bbl=None,
            bin=None,
            raw={},
        )

    monkeypatch.setattr(gc, "geocode_nominatim", fake_nominatim)

    hit = gc.geocode_one("Willis Tower, Chicago, IL")
    assert hit is not None and abs(hit.lat - 41.8787) < 0.01
    # Bounded attempt first, then unbounded national fallback.
    assert calls == [True, False]


def test_looks_non_us_detects_foreign_country_names():
    assert gc._looks_non_us("10 Downing Street, London")
    assert gc._looks_non_us("Tokyo Tower, Minato, Tokyo, Japan")
    assert not gc._looks_non_us("189 Atlantic Ave, Brooklyn, NY")
    assert not gc._looks_non_us("233 S Wacker Dr, Chicago, IL")  # US, not foreign


def test_geocode_one_refuses_forced_us_match_for_foreign_address(monkeypatch):
    """country_codes="us" makes Nominatim force-fit *something* in the US
    for a genuinely foreign query — e.g. "10 Downing Street, London"
    silently resolving to a "Downing Street" in Oklahoma. Once a query
    names a real foreign place, geocode_one must confirm via one
    unrestricted lookup and refuse (return None) rather than accept
    whatever the US-biased path would have force-fit."""
    monkeypatch.delenv("RIPRAP_DEPLOYMENT", raising=False)
    gc._active_deployment_bbox.cache_clear()

    def fake_nominatim(text, *, viewbox=None, bounded=False, country_codes="us"):
        assert country_codes is None, "the confirmation lookup must be unrestricted"
        return gc.GeocodeHit(
            address="10 Downing Street, London, UK",
            borough=None, lat=51.5034, lon=-0.1276, bbl=None, bin=None,
            raw={"address": {"country_code": "gb"}},
        )

    monkeypatch.setattr(gc, "geocode_nominatim", fake_nominatim)
    assert gc.geocode_one("10 Downing Street, London") is None


def test_geocode_one_allows_us_match_when_unrestricted_lookup_agrees(monkeypatch):
    """A false-positive non-US hint (e.g. a street literally named after
    a foreign country) shouldn't block a real US address — only an
    unrestricted lookup that actually resolves outside the US does."""
    monkeypatch.delenv("RIPRAP_DEPLOYMENT", raising=False)
    gc._active_deployment_bbox.cache_clear()

    def fake_nominatim(text, *, viewbox=None, bounded=False, country_codes="us"):
        return gc.GeocodeHit(
            address="1 China Street, Chicago, IL", borough=None,
            lat=41.88, lon=-87.63, bbl=None, bin=None,
            raw={"address": {"country_code": "us"}},
        )

    monkeypatch.setattr(gc, "geocode_nominatim", fake_nominatim)
    monkeypatch.setattr(gc, "geocode", lambda text, limit=5: [])
    hit = gc.geocode_one("1 China Street, Chicago, IL")
    assert hit is not None and hit.lat == 41.88


def test_geocode_one_catches_locality_dropped_from_extracted_target(monkeypatch):
    """Real production case: a planner LLM extracts "10 Downing Street"
    as the target from "what's the flood risk at 10 Downing Street in
    London?", dropping "London" entirely — text alone has no non-US
    signal left. scope_hint carries the original query so the check
    still fires."""
    monkeypatch.delenv("RIPRAP_DEPLOYMENT", raising=False)
    gc._active_deployment_bbox.cache_clear()

    def fake_nominatim(text, *, viewbox=None, bounded=False, country_codes="us"):
        assert country_codes is None
        return gc.GeocodeHit(
            address="10 Downing Street, London, UK",
            borough=None, lat=51.5034, lon=-0.1276, bbl=None, bin=None,
            raw={"address": {"country_code": "gb"}},
        )

    monkeypatch.setattr(gc, "geocode_nominatim", fake_nominatim)
    assert not gc._looks_non_us("10 Downing Street"), \
        "sanity: the narrow target string alone must NOT carry the signal"
    result = gc.geocode_one(
        "10 Downing Street",
        scope_hint="what's the flood risk at 10 Downing Street in London?",
    )
    assert result is None
