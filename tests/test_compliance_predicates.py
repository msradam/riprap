"""Regression tests for riprap.core.compliance.predicates.

No test file existed for the 13 compliance predicates before this one —
a real gap for a project whose trust story rests on them. Starting with
the one bug found and fixed live: projection_has_horizon false-flagging
an honest "no data available" sentence as an unhedged projection.
"""
from __future__ import annotations

from riprap.core.compliance.predicates import projection_has_horizon


def test_absence_sentence_does_not_need_a_horizon():
    """Riprap is explicitly instructed (EXTRA_SYSTEM_PROMPT in
    app/reconcile.py) to write exactly this kind of sentence instead of
    speculating when no modeled-scenario document exists. Verified live
    (2026-07-11 6-city sweep against a 3B reconciler, which leans on this
    sentence shape more often than the 8B): 5 of 6 non-NYC cities were
    false-flagged here before the fix, on this exact sentence shape."""
    cases = [
        "No modeled scenario data is available for this address from the dep_* documents or terrain models.",
        "No modeled scenario data is available for this address from the FEMA Resilient Infrastructure Grantee (RAG) documents or microtopography tools.",
        "No modeled-scenario data is available for this section.",
        "This is not yet reflected in any mapped FEMA flood zone.",
        "Specific depth or duration modeling cannot be reported for this address.",
    ]
    for s in cases:
        r = projection_has_horizon(s)
        assert r.passed, f"false positive on absence sentence: {s!r} — evidence: {r.evidence}"


def test_unhedged_projection_without_horizon_still_fails():
    """The exemption must not swallow genuine violations."""
    r = projection_has_horizon(
        "The DEP stormwater model projects flooding of up to 2 ft in this scenario."
    )
    assert not r.passed
    assert r.evidence


def test_projection_with_explicit_horizon_passes():
    r = projection_has_horizon(
        "Sea-level rise projections for the Battery gauge show potential increases up to 40 in by 2100 under extreme scenarios."
    )
    assert r.passed
