"""Per-query deployment routing — the data-correctness gate.

The architectural promise: a Boston query never fires NYC's `ida_hwm`
pebble, regardless of which deployment the server happened to boot
with. These tests are the regression seal on that promise.
"""
from __future__ import annotations

from riprap.core.pebbles.deployments import (
    deployment_by_name,
    discover_deployments,
    pick_deployment,
)


def test_all_shipped_cities_have_a_coverage_bbox():
    """Every place-routed deployment declares a bbox + city. Heat/air
    deployments are hazard-routed and intentionally bbox-less."""
    deps = {d.name: d for d in discover_deployments()}
    for name in ("nyc", "boston", "chicago", "seattle", "sf", "albany"):
        d = deps.get(name)
        assert d is not None, f"deployments/{name} missing from discovery"
        assert d.bbox is not None, f"deployments/{name} has no coverage.bbox"
        assert d.city, f"deployments/{name} coverage.city is missing"


def test_city_centroids_route_to_their_deployment():
    """Each shipped city's city-hall point picks its own deployment.

    A miss here is the bug the user called out: 'Hurricane Ida ran for
    Boston' — i.e. the routing put a Boston point into the NYC fan-out.
    """
    cases = [
        ("NYC City Hall",        40.7128, -74.0060, "nyc"),
        ("Boston City Hall",     42.3601, -71.0589, "boston"),
        ("Chicago Loop",         41.8781, -87.6298, "chicago"),
        ("Seattle Pike Place",   47.6094, -122.3422, "seattle"),
        ("SF Civic Center",      37.7793, -122.4192, "sf"),
        ("Albany City Hall",     42.6526, -73.7562, "albany"),
    ]
    for label, lat, lon, expected in cases:
        d = pick_deployment(lat, lon)
        assert d is not None, f"{label} ({lat}, {lon}) didn't route to any deployment"
        assert d.name == expected, (
            f"{label} routed to {d.name!r}, expected {expected!r} — "
            f"this is the cross-city data leak that lets NYC's ida_hwm "
            f"fire for {label}."
        )


def test_out_of_coverage_point_returns_none():
    """An address outside every shipped deployment's bbox returns None.
    Caller short-circuits to 'not covered yet' instead of fanning out
    every NYC pebble against a non-NYC point."""
    # Albuquerque, NM — outside every shipped bbox.
    assert pick_deployment(35.0844, -106.6504) is None


def test_no_coords_returns_none():
    """Geocoding failed (e.g. unparseable address) → no routing."""
    assert pick_deployment(None, None) is None
    assert pick_deployment(40.0, None) is None


def test_deployment_by_name_lookup():
    assert deployment_by_name("nyc") is not None
    assert deployment_by_name("boston") is not None
    assert deployment_by_name("does_not_exist") is None


def test_stones_pebbles_for_filters_by_deployment():
    """The Stone fan-out function returns only the active deployment's
    pebbles — the regression seal on the data-leak fix."""
    from riprap.core.burr.stones import _pebbles_for

    boston_cornerstone = set(_pebbles_for("cornerstone", "boston"))
    nyc_cornerstone = set(_pebbles_for("cornerstone", "nyc"))

    # NYC Cornerstone includes ida_hwm, sandy, dep_*, prithvi_water, etc.
    assert "ida_hwm" in nyc_cornerstone
    assert "sandy" in nyc_cornerstone
    # Boston Cornerstone must NOT include them — this is the bug fix.
    assert "ida_hwm" not in boston_cornerstone, (
        "Boston cornerstone fan-out contains ida_hwm — Hurricane Ida is "
        "a New York 2021 event and must not fire for Boston queries."
    )
    assert "sandy" not in boston_cornerstone


def test_pebbles_for_none_sentinel_returns_federal_only():
    """Out-of-coverage sentinel produces only federal pebbles —
    city-specific ones (sandy, dep_*, nyc311) are dropped, but the
    federal pebbles (nws_obs, nws_alerts) that resolve any CONUS
    lat/lon still fire so the briefing has something to report."""
    from riprap.core.burr.stones import _pebbles_for
    # cornerstone has fema_nfhl from the federal manifest.
    assert _pebbles_for("cornerstone", "__none__") == ["fema_nfhl"]
    # touchstone has nws_obs + usgs_gauges from the federal manifests.
    assert sorted(_pebbles_for("touchstone", "__none__")) == ["nws_obs", "usgs_gauges"]
    # lodestone has nws_alerts from the federal manifest.
    assert "nws_alerts" in _pebbles_for("lodestone", "__none__")


def test_federal_pebbles_auto_merge_into_every_city():
    """nws_alerts + nws_obs live in deployments/federal/ and auto-merge
    into every spatially-routed deployment. No city should re-declare
    them (deduped); every city should still fan out federal pebbles
    when fed CONUS coords."""
    from riprap.core.burr.stones import _pebbles_for

    for city, lat, lon in [
        ("nyc",     40.7128, -74.0060),
        ("boston",  42.3601, -71.0589),
        ("chicago", 41.8781, -87.6298),
        ("seattle", 47.6094, -122.3422),
        ("sf",      37.7793, -122.4192),
    ]:
        touchstone = _pebbles_for("touchstone", city, lat=lat, lon=lon)
        lodestone = _pebbles_for("lodestone", city, lat=lat, lon=lon)
        assert "nws_obs" in touchstone, (
            f"{city}: federal nws_obs failed to auto-merge into touchstone"
        )
        assert "nws_alerts" in lodestone, (
            f"{city}: federal nws_alerts failed to auto-merge into lodestone"
        )


def test_federal_pebbles_not_duplicated_in_city_dirs():
    """Each federal pebble exists in exactly one manifest file — the
    federal one. Drift here defeats the dedup."""
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    for fid in ("nws_alerts", "nws_obs"):
        matches = list(repo.glob(f"deployments/*/manifests/{fid}.yaml"))
        assert len(matches) == 1, (
            f"federal pebble {fid!r} found in {len(matches)} manifests: "
            f"{[str(m.relative_to(repo)) for m in matches]} — expected exactly one (federal)."
        )
        assert "federal" in str(matches[0]), (
            f"federal pebble {fid!r} is in {matches[0]}, not deployments/federal/"
        )


def test_per_pebble_coverage_filter_out_of_conus():
    """A point outside CONUS (e.g. Tokyo) fires zero pebbles even when
    we point at a known deployment — the per-pebble coverage filter
    catches global queries that bypassed the deployment router."""
    from riprap.core.burr.stones import _pebbles_for
    # Tokyo — outside CONUS, outside every city bbox.
    assert _pebbles_for("touchstone", "nyc", lat=35.6762, lon=139.6503) == []
    assert _pebbles_for("lodestone", "nyc", lat=35.6762, lon=139.6503) == []


def test_build_documents_covers_non_nyc_deployment_pebbles():
    """build_documents' out-of-NYC scope_note branch predates multi-city
    support and only ever emitted a national live-conditions snapshot +
    geocode — a non-NYC deployment's own hazard/empirical pebbles
    (fema_nfhl, usgs_gauges, <city>_311) never became documents at all,
    so the LLM had nothing to cite and wrote a plausible-sounding "no
    data available" briefing that directly contradicted real, present
    state data. Regression seal: this exact gap was live on Modal for
    all 5 non-NYC cities on 2026-07-11 (a `git checkout` had also wiped
    the routed_deployment_doc_ids / trim_docs_to_plan extra_keep fix in
    the same incident, masking this deeper bug until both were fixed)."""
    from app.reconcile import build_documents

    state = {
        "deployment": "chicago",
        "geocode": {"address": "233 S Wacker Dr", "lat": 41.878, "lon": -87.636},
        "fema_nfhl": {
            "fld_zone": "X", "firm_panel": "17031C0419J", "effective_year": 2008,
            "narrative": "This address sits in FEMA flood zone X, per NFHL FIRM panel 17031C0419J, effective 2008.",
        },
        "usgs_gauges": {
            "stage_ft": -1.67, "discharge_cfs": 425.0,
            "narrative": "Nearest USGS stream gauge: stage -1.67 ft, discharge 425.0 ft³/s.",
        },
        "chicago_311": {
            "n_records": 200, "n_truncated": True, "radius_m": 200,
            "top_by_sr_type": [{"value": "Graffiti Removal Request", "count": 53}],
        },
    }
    docs = build_documents(state)
    doc_ids = {d["role"].split(" ", 1)[1] for d in docs if d["role"].startswith("document ")}
    assert {"fema_nfhl", "usgs_gauges", "chicago_311", "geocode", "scope_note"} <= doc_ids, (
        f"build_documents only produced {doc_ids} for a routed Chicago "
        f"query with real fema_nfhl/usgs_gauges/chicago_311 data present "
        f"in state — the reconciler would see nothing to cite."
    )
    # The 311 document must actually carry the record count, not just
    # exist — a present-but-empty document is as useless as a missing one.
    doc_311 = next(d for d in docs if d["role"] == "document chicago_311")
    assert "200" in doc_311["content"]


def test_build_documents_keeps_two_311_variants_separate():
    """Albany ships albany_311 (all requests, 300 m) and albany_flood_311
    (flood-filtered, 800 m) as distinct pebbles. Regression seal for a
    confirmed live citation-swap bug: a briefing once attributed BOTH
    counts to a single doc_id, misrepresenting a 300 m-radius total as
    part of the 800 m-radius flood-specific query. Two separate documents
    is what lets the model (or an auditor) tell them apart at all."""
    from app.reconcile import build_documents

    state = {
        "deployment": "albany",
        "geocode": {"address": "24 Eagle St", "lat": 42.652, "lon": -73.756},
        "albany_311": {"n_records": 62, "radius_m": 300},
        "albany_flood_311": {"n_records": 6, "radius_m": 800},
    }
    docs = build_documents(state)
    by_id = {d["role"].split(" ", 1)[1]: d["content"] for d in docs}
    assert "albany_311" in by_id and "albany_flood_311" in by_id
    assert "62" in by_id["albany_311"] and "300" in by_id["albany_311"]
    assert "6" in by_id["albany_flood_311"] and "800" in by_id["albany_flood_311"]


def test_deployment_state_keys_covers_every_shipped_pebble():
    """step_reconcile's Burr reads=[...] must declare every pebble id
    across every deployment, or a non-NYC deployment's pebbles never
    reach state.get() inside the reconcile action at all. Regression
    seal: this exact function was silently dropped by a bad `git
    checkout` once already (2026-07-11) and broke every reconcile call
    with an ImportError that no local test caught, because nothing
    imported app.reconcile.deployment_state_keys directly."""
    from app.reconcile import deployment_state_keys
    keys = deployment_state_keys()
    assert "deployment" in keys
    for pid in ("nyc311", "chicago_311", "boston_311", "sf_311",
                "albany_311", "albany_flood_311", "fema_nfhl", "usgs_gauges"):
        assert pid in keys, f"{pid!r} missing from deployment_state_keys()"


def test_routed_deployment_doc_ids_matches_the_registry():
    """routed_deployment_doc_ids(snap) must return exactly the routed
    deployment's own pebble ids, not NYC's or another city's."""
    from app.reconcile import routed_deployment_doc_ids

    chicago_ids = routed_deployment_doc_ids({"deployment": "chicago"})
    assert "chicago_311" in chicago_ids
    assert "fema_nfhl" in chicago_ids  # federal, auto-merged
    assert "nyc311" not in chicago_ids
    assert "sandy" not in chicago_ids

    assert routed_deployment_doc_ids({"deployment": "__none__"}) == set()
    assert routed_deployment_doc_ids({}) == set()
    assert routed_deployment_doc_ids({"deployment": "not_a_real_city"}) == set()


def test_trim_docs_to_plan_keeps_extra_keep_ids():
    """Without extra_keep, trim_docs_to_plan only knows NYC's pebble-id
    shapes (PREFIXES_BY_SPECIALIST) — a non-NYC deployment's pebbles
    (chicago_311, fema_nfhl, ...) don't match any prefix and get
    silently dropped even when they're the only real data for that
    query. extra_keep=routed_deployment_doc_ids(snap) is the fix."""
    from app.reconcile import routed_deployment_doc_ids, trim_docs_to_plan

    docs = [
        {"role": "document geocode", "content": "x"},
        {"role": "document chicago_311", "content": "x"},
        {"role": "document fema_nfhl", "content": "x"},
        {"role": "document sandy", "content": "x"},  # NYC-only
    ]
    extra_keep = routed_deployment_doc_ids({"deployment": "chicago"})

    without = trim_docs_to_plan(docs, {"sandy"})
    ids_without = {m["role"].split(" ", 1)[1] for m in without if m["role"].startswith("document ")}
    assert "chicago_311" not in ids_without, (
        "chicago_311 survived trimming without extra_keep — this test's "
        "premise is wrong, re-check PREFIXES_BY_SPECIALIST."
    )

    with_keep = trim_docs_to_plan(docs, {"sandy"}, extra_keep=extra_keep)
    ids_with = {m["role"].split(" ", 1)[1] for m in with_keep if m["role"].startswith("document ")}
    assert "chicago_311" in ids_with
    assert "fema_nfhl" in ids_with
    assert "geocode" in ids_with  # ALWAYS_KEEP, unrelated to extra_keep


def test_per_pebble_coverage_filter_conus_but_not_city():
    """A point inside CONUS but outside every city bbox still gets
    federal pebbles (NWS Alerts works for Albuquerque too)."""
    from riprap.core.burr.stones import _pebbles_for
    abq = _pebbles_for("touchstone", "nyc", lat=35.0844, lon=-106.6504)
    assert "nws_obs" in abq, (
        "Albuquerque is in CONUS — NWS METAR observations should fire."
    )
    # NYC-specific pebbles (floodnet, nyc311, prithvi_live) should NOT
    # fire for Albuquerque because they inherit the NYC bbox.
    assert "floodnet" not in abq
    assert "nyc311" not in abq
