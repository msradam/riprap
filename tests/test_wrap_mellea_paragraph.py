"""neighborhood.py and development_check.py both route through Mellea
rejection sampling (reconcile_strict_streaming) when strict=True, a
different code path from their own _reconcile() fallback. A live query
against neighborhood.py confirmed the strict path skipped wrap_with_scope
entirely (9/13 compliance, missing ASTM 4.1/4.5/4.6) even after _reconcile()
was fixed — because strict mode never calls _reconcile() at all. This
shared helper (mirroring app/fsm.py's single_address strict path) is now
the one place all three call sites route through."""
from __future__ import annotations

from app.reconcile import NON_SCOPE_FOOTER, SCOPE_HEADER, wrap_mellea_paragraph


def test_wraps_a_real_paragraph():
    para = "Body text long enough to pass the stall-guard threshold easily [doc_1]."
    out = wrap_mellea_paragraph(para)
    assert out.startswith(SCOPE_HEADER)
    assert out.endswith(NON_SCOPE_FOOTER)
    assert para in out


def test_leaves_empty_paragraph_alone():
    assert wrap_mellea_paragraph("") == ""


def test_leaves_short_stalled_paragraph_alone():
    short = "Too short."
    assert wrap_mellea_paragraph(short) == short
