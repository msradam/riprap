"""Every briefing in the shipped gallery passes the disclosure checks. A
walkthrough found default briefings failing one of the 13 (a register's
name list named a scenario with no year) while the docs said they pass."""

import json
from pathlib import Path

import pytest

from riprap.core.compliance.predicates import check_briefing

GALLERY = Path(__file__).resolve().parents[1] / "web" / "sveltekit" / "src" / "lib" / "gallery"
ENTRIES = sorted(p for p in GALLERY.glob("*.json") if p.name != "index.json")


@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: p.stem)
def test_gallery_briefing_passes_every_disclosure_check(path):
    final = json.loads(path.read_text())["final"]
    if final.get("intent") in ("out_of_scope", "not_implemented"):
        pytest.skip("a refusal is fixed text, not a briefing")
    failed = check_briefing(final["paragraph"]).failed
    assert [(r.name, r.evidence[:1]) for r in failed] == []
