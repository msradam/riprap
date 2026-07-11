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
