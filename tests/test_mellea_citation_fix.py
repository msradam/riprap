from __future__ import annotations

from app.mellea_validator import _check_every_claim_cited, _fix_parenthetical_citations


def test_fixes_exact_doc_id_match_in_parens():
    text = "There were **63** service requests (albany_311) nearby."
    fixed = _fix_parenthetical_citations(text, {"albany_311", "fema_nfhl"})
    assert "[albany_311]" in fixed
    assert "(albany_311)" not in fixed


def test_leaves_ordinary_parenthetical_prose_alone():
    text = "The reading was elevated (approximately) at the time of survey."
    fixed = _fix_parenthetical_citations(text, {"albany_311", "fema_nfhl"})
    assert fixed == text


def test_leaves_non_matching_lowercase_token_alone():
    text = "Flood zone X (unmapped) near the address."
    fixed = _fix_parenthetical_citations(text, {"albany_311", "fema_nfhl"})
    assert fixed == text


def test_real_albany_regression_case():
    """The exact sentence shape that failed citations_dense in production:
    two claims cited with (doc_id) instead of [doc_id]."""
    text = (
        "Six service requests related to flooding were recorded within "
        "an **800 m radius** of the address (albany_flood_311), and "
        "there are **63 general service requests** within **300 m** "
        "(albany_311)."
    )
    valid = {"albany_flood_311", "albany_311", "fema_nfhl", "usgs_gauges"}
    fixed = _fix_parenthetical_citations(text, valid)
    check = _check_every_claim_cited()
    assert not check(text), "sanity: unfixed text should fail the check"
    assert check(fixed), "fixed text should pass citations_dense"
