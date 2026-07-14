"""Regression tests for the print-PDF font vendoring (docs/design/handoff/
CLAUDE-CODE-PROMPT.md Task 2/6). The document-hash-reproducibility claim
in print_pdf.py's docstring depends on @font-face pointing at bytes that
actually ship in the repo, not a font-family name Pango happens to find
installed on the machine running it.
"""

from __future__ import annotations

from pathlib import Path

from app.print_pdf import _FONTS_DIR, _font_face_css, _render_html


def test_vendored_font_files_exist_on_disk():
    for filename in (
        "sofia-sans-400.woff",
        "sofia-sans-600.woff",
        "sofia-sans-700.woff",
        "sofia-sans-800.woff",
        "overpass-mono-400.woff",
        "overpass-mono-600.woff",
    ):
        assert (_FONTS_DIR / filename).is_file(), f"missing {filename}"


def test_font_face_css_references_real_files_by_absolute_uri():
    css = _font_face_css()
    assert css.count("@font-face") == 6
    for filename in ("sofia-sans-400.woff", "overpass-mono-400.woff"):
        uri = (_FONTS_DIR / filename).as_uri()
        assert uri in css
        assert Path(filename).name in Path(uri.removeprefix("file://")).name


def test_rendered_html_carries_no_ibm_plex_or_the_contrast_bug_hex():
    html_doc = _render_html({"query": "1 Main St", "paragraph": "Test."}, "deadbeef")
    assert "IBM Plex" not in html_doc
    # #64748B measures 4.01:1 on the sunken surface — a real AA failure;
    # replaced everywhere in the print path by #4E5A6E (min 5.88:1).
    assert "64748b" not in html_doc.lower()
    assert "Sofia Sans" in html_doc
    assert "Overpass Mono" in html_doc
