"""NYC Geosearch is tried first only for unambiguous NYC matches: the query
names a borough/ZIP and the hit's house number + street are in the query.
Geosearch's fuzzy matches (typos, out-of-city streets) must fall through."""
from __future__ import annotations

from app import geocode as g


def _hit(number, street):
    return g.GeocodeHit(address=f"{number} {street}", borough="Brooklyn", lat=40.69, lon=-73.99,
                        bbl="3002760007", bin=None, raw={"housenumber": number, "street": street})


def test_accepts_exact_match(monkeypatch):
    monkeypatch.setattr(g, "geocode", lambda text, limit=1: [_hit("189", "ATLANTIC AVENUE")])
    assert g._geosearch_exact("189 Atlantic Ave., Brooklyn, NY") is not None


def test_accepts_ordinal_street(monkeypatch):
    monkeypatch.setattr(g, "geocode", lambda text, limit=1: [_hit("2017", "EAST 17 STREET")])
    assert g._geosearch_exact("2017 E 17th St, Brooklyn, NY 11229") is not None


def test_rejects_fuzzy_street(monkeypatch):
    monkeypatch.setattr(g, "geocode", lambda text, limit=1: [_hit("189", "PROSPECT AVENUE")])
    assert g._geosearch_exact("189 Atantic Avnue, Brooklyn") is None


def test_skips_geosearch_without_nyc_place(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Geosearch must not be called")
    monkeypatch.setattr(g, "geocode", boom)
    assert g._geosearch_exact("257 Washington Ave, Albany NY") is None
