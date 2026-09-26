"""Shaper for the three DEP stormwater scenario pebbles.

`dep_stormwater.join_raster()` returns an integer depth class (0 outside,
1 nuisance, 2 deep+contiguous 1-4 ft, 3 deep >4 ft). Downstream consumers
expect a dict with the int class, a human-readable label, a citation
naming the scenario, and a `narrative` the manifest's narration.template
renders verbatim.

Class 0 (outside this scenario) returns an "outside" record, because
"not in the modeled extent" answers scenario questions. Only a missing
reading returns None.
"""
from __future__ import annotations

_DEPTH_CLASS_LABELS = {
    0: "outside",
    1: "Nuisance (>4 in to 1 ft)",
    2: "Deep & Contiguous (1-4 ft)",
    3: "Deep Contiguous (>4 ft)",
}


def shape(value, manifest) -> dict | None:
    if value is None:
        return None  # no raster reading at all: offline, not "outside"
    cls = max(int(value), 0)
    label = _DEPTH_CLASS_LABELS.get(cls, "outside")
    citation = (manifest.provenance.citation
                or f"NYC DEP Stormwater Flood Map — {manifest.title}")
    # Type-keyed narrative the manifest's narration.template renders.
    # The scenario name (e.g. "Extreme — 3.66 in/hr, 2080 SLR") is
    # extracted from manifest.title's parenthetical; if absent, fall
    # back to a class-only sentence.
    title = manifest.title or ""
    paren_start = title.find("(")
    paren_end = title.rfind(")")
    scenario = (f"the NYC DEP stormwater scenario ({title[paren_start + 1:paren_end]})"
                if paren_start >= 0 and paren_end > paren_start else "the NYC DEP stormwater scenario")
    if cls == 0:
        # Outside the modeled extent is an answer, not missing data.
        narrative = f"This address is outside the modeled flooding in {scenario}."
    else:
        narrative = f"{scenario[0].upper()}{scenario[1:]} models flooding at this address: {label}."
    return {
        "depth_class": cls,
        "depth_label": label,
        "citation": citation,
        "narrative": narrative,
    }
