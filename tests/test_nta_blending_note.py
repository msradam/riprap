"""NTAs are hyphen-joined compounds of several named places. A live query
for "Red Hook, Brooklyn" resolved to NTA "Carroll Gardens-Cobble
Hill-Gowanus-Red Hook" (BK0601) with every figure blended across all four
places and no disclosure — the same NTA a neighborhood.py test hit earlier
this session. blending_note() gives neighborhood.py and development_check.py
a deterministic sentence to prepend when that happens."""
from __future__ import annotations

from app.areas.nta import blending_note

RED_HOOK_TARGET = {
    "nta_code": "BK0601",
    "nta_name": "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "borough": "Brooklyn",
}
PARK_SLOPE_TARGET = {
    "nta_code": "BK0704",
    "nta_name": "Park Slope",
    "borough": "Brooklyn",
}


def test_notes_when_query_names_one_part_of_a_compound_nta():
    note = blending_note("flood exposure for Red Hook, Brooklyn", RED_HOOK_TARGET)
    assert note is not None
    assert "Red Hook" in note
    assert "Carroll Gardens-Cobble Hill-Gowanus-Red Hook" in note
    assert "Gowanus" in note  # names at least one of the other blended parts


def test_no_note_when_query_names_the_full_compound_nta():
    note = blending_note(
        "flood exposure for Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
        RED_HOOK_TARGET,
    )
    assert note is None


def test_no_note_for_a_single_part_nta():
    note = blending_note("flood exposure for Park Slope", PARK_SLOPE_TARGET)
    assert note is None


def test_no_note_when_query_gives_no_hint_which_part_was_meant():
    """A borough-level or generic query has no sub-place signal to react
    to — silence, not a guess at which part the user meant."""
    note = blending_note("flood exposure in Brooklyn", RED_HOOK_TARGET)
    assert note is None
