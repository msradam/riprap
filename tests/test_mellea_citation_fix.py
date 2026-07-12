from __future__ import annotations

from app.mellea_validator import (
    _check_every_claim_cited,
    _failing_sentences_for_citations,
    _fix_parenthetical_citations,
)


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


def test_street_address_numbers_dont_need_their_own_citation():
    """Real production case from development_check output: a summary
    sentence re-lists street numbers from addresses already cited
    earlier in the document ("Flagged projects" bullets), purely for
    readability. Re-citing each one again is not a fresh claim."""
    check = _check_every_claim_cited()
    text = (
        "The flagged projects are concentrated on Coffey St, Imlay Street, "
        "Smith Street, Sullivan Street, and Richards Street, with a mix of "
        "new building (20 Coffey St, 100 Sullivan St) and major alteration "
        "(62 Imlay St, 570 Smith St, 206 Richards St) projects."
    )
    assert check(text), "street numbers in addresses should not trip citations_dense"
    assert _failing_sentences_for_citations(text) == []


def test_genuine_uncited_statistic_still_fails():
    """The street-address exemption must not swallow real uncited claims."""
    check = _check_every_claim_cited()
    text = "There were 63 service requests within 300 m of the address."
    assert not check(text)
    assert _failing_sentences_for_citations(text) != []


def test_street_address_number_with_citation_elsewhere_in_sentence_still_passes():
    check = _check_every_claim_cited()
    text = "20 Coffey St is a new building permit issued in 2025 [dob_permits]."
    assert check(text)


def test_bullet_item_citation_covers_all_its_internal_clauses():
    """Real production case from development_check output: a bulleted
    list item packs several period-delimited clauses (address, permit
    details, DEP scenario) under a single citation at the end — the
    same convention as a human-written footnoted list, one citation per
    item, not one per clause. Splitting the bullet into independent
    "sentences" at each internal period made every clause but the last
    read as uncited."""
    check = _check_every_claim_cited()
    text = (
        "- **20 Coffey St, Brooklyn (BBL 3-00589-0003).** new building, "
        "permit issued 11/26/2025; owner **20 COFFEY LLC**. In Sandy "
        "zone: True; in DEP scenarios: dep_extreme_2080; max DEP depth "
        "class: 3. [dob_permits]"
    )
    assert check(text)
    assert _failing_sentences_for_citations(text) == []


def test_bullet_item_without_any_citation_still_fails():
    """The bullet-line extension must not blanket-exempt bullets that
    genuinely have no citation at all."""
    check = _check_every_claim_cited()
    text = "- **20 Coffey St, Brooklyn.** new building, permit issued 11/26/2025."
    assert not check(text)
    assert _failing_sentences_for_citations(text) != []


def test_prose_sentence_after_a_bullet_is_not_extended_by_it():
    """A non-bulleted sentence following a bulleted line must keep its
    own, tighter sentence boundary — only lines that are themselves
    bullets get the wider span."""
    check = _check_every_claim_cited()
    text = (
        "- 20 Coffey St. new building. [dob_permits].\n"
        "The majority of projects fall within the Sandy inundation zone "
        "and involve 63 total permits."
    )
    assert not check(text), "the trailing prose sentence has an uncited '63' of its own"
