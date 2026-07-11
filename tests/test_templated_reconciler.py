"""Per-sentence citation repair in the no-LLM reconciler.

`every_numeric_claim_cited` (SPJ 7.1) audits per sentence, so a
multi-sentence pebble narrative with one trailing citation fails the
predicate on its earlier sentences. `_cite_numeric_sentences` is the
repair; these tests are the regression seal on the NYC 12/13 bug.
"""

from __future__ import annotations

from riprap.core.burr.templated_reconciler import _cite_numeric_sentences
from riprap.core.compliance.predicates import every_numeric_claim_cited


def test_each_numeric_sentence_gets_marker():
    body = (
        "34 NYC 311 flood-related complaints filed within 200 m of this "
        "location in the last 5 years. Most common descriptor: Sewer Backup."
    )
    out = _cite_numeric_sentences(body, "nyc311")
    assert "200 m of this location in the last 5 years [nyc311]." in out
    # No unit-number in the descriptor sentence — left uncluttered.
    assert out.endswith("Most common descriptor: Sewer Backup.")


def test_abbreviation_fragments_without_numbers_untouched():
    body = (
        "No marks were surveyed within 800 m of this address. Nearest mark: "
        "Intersection of Carroll St. and Nevins St., Brooklyn (1459 m away)."
    )
    out = _cite_numeric_sentences(body, "ida_hwm")
    # The 'Carroll St.' fragment the naive splitter produces has no
    # unit-number, so no marker lands mid-name.
    assert "Carroll St. and" in out
    assert "(1459 m away) [ida_hwm]." in out


def test_already_cited_sentences_untouched():
    body = "Stage 2.31 ft at the gauge [usgs_gauges]."
    assert _cite_numeric_sentences(body, "usgs_gauges") == body


def test_repaired_paragraph_passes_the_predicate():
    body = (
        "Elevation 16.79 m; HAND 16.66 m above nearest drainage; TWI 9.46. "
        "Local basin relief: 10.61 m."
    )
    out = _cite_numeric_sentences(body, "microtopo")
    assert every_numeric_claim_cited(out).passed
