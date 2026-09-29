"""Shaper for the three DEP stormwater scenario pebbles.

`dep_stormwater.join_raster()` returns the Flooding_Category code: 0
outside, 1 nuisance rainfall flooding (4 in to under 1 ft), 2 deep and
contiguous rainfall flooding (1 ft or more), 3 the scenario's future high
tide area (coastal tidal inundation, 2050 and 2080 files only). Class 3
is a different hazard, not deeper flooding. The labels live in
`dep_stormwater.class_label`. Downstream consumers expect a dict with the
int class, that label, a citation naming the scenario, and a `narrative`
the manifest's narration.template renders verbatim.

Class 0 (outside this scenario) returns an "outside" record, because
"not in the modeled extent" answers scenario questions. Only a missing
reading returns None.
"""
from __future__ import annotations

# Imported where used: the registry loads every shaper at startup, and
# dep_stormwater pulls in geopandas.


def result(cls: int, scenario: str) -> str:
    """One scenario's result as a short phrase, for lists of scenarios."""
    from app.flood_layers.dep_stormwater import TIDE_CLASS, class_label, tide_words

    if not cls:
        return "outside the modeled flooding"
    if cls == TIDE_CLASS:
        return f"inside the future high tide area ({tide_words(scenario)}), not rainfall flooding"
    return f"{class_label(cls, scenario)} from rainfall"


def shape(value, manifest) -> dict | None:
    if value is None:
        return None  # no raster reading at all: offline, not "outside"
    from app.flood_layers.dep_stormwater import TIDE_CLASS, class_label, tide_words

    cls = max(int(value), 0)
    sid = getattr(manifest, "id", "")
    citation = (manifest.provenance.citation
                or f"NYC DEP Stormwater Flood Map — {manifest.title}")
    # Type-keyed narrative the manifest's narration.template renders.
    # The scenario name (e.g. "3.66 in/hr, 2080 SLR") is
    # extracted from manifest.title's parenthetical; if absent, fall
    # back to a class-only sentence.
    title = manifest.title or ""
    paren_start = title.find("(")
    paren_end = title.rfind(")")
    scenario = (f"the NYC DEP stormwater scenario ({title[paren_start + 1:paren_end]})"
                if paren_start >= 0 and paren_end > paren_start else "the NYC DEP stormwater scenario")
    # "current SLR" names no time horizon; the disclosure check needs one.
    scenario = scenario.replace("current SLR", "current sea level, near-term")
    if cls == 0:
        # Outside the modeled extent is an answer, not missing data.
        narrative = f"This address is outside the modeled flooding in {scenario}."
    elif cls == TIDE_CLASS:
        narrative = (f"This address is inside the future high tide area of {scenario}: "
                     f"{tide_words(sid)}, not the scenario's rainfall flooding.")
    else:
        narrative = (f"{scenario[0].upper()}{scenario[1:]} models {class_label(cls, sid)} "
                     "from rainfall at this address.")
    return {
        "depth_class": cls,
        "depth_label": class_label(cls, sid),
        "citation": citation,
        "narrative": narrative,
    }
