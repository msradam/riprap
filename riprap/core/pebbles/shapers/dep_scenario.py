"""Shaper for the NYC stormwater flood map pebbles.

`dep_stormwater.at_point()` returns the Flooding_Category code under the
point (0 outside, 1 nuisance rainfall flooding, 2 deep and contiguous
rainfall flooding, 3 the map's future high tide category, 2050 and 2080
files only) and the distance to the mapped edge when it is near. Class 3
is a different hazard, not deeper flooding.

The sentence says no more than the city's disclaimer allows: what the map
shows at the point mapped for the address, by the city's own map and
category names, then that the map is a modelled scenario and not a
forecast, covers public areas and rain only, and gives no exact depth.
An outside reading carries NYC Emergency Management's caveat that most
buildings damaged in Ida were outside every mapped scenario.

Class 0 (outside this map's flooding) returns an "outside" record,
because that answers scenario questions. Only a missing reading returns
None.
"""
from __future__ import annotations

# Imported where used: the registry loads every shaper at startup, and
# dep_stormwater pulls in geopandas.


def result(value: dict, scenario: str) -> str:
    """One map's reading as a short phrase, for lists of maps."""
    from app.flood_layers.dep_stormwater import TIDE_CLASS, domain

    cls, edge = value["depth_class"], value.get("edge_m")
    if not cls:
        return "no flooding category" + (f" (about {edge} m from the nearest flooding mapped on it)" if edge else "")
    notes = (["coastal tidal inundation, not rainfall flooding"] if cls == TIDE_CLASS else []) + (
        [f"about {edge} m from the edge of the mapped flooding"] if edge else [])
    return f'the category "{domain(scenario)[cls]}"' + (f" ({'; '.join(notes)})" if notes else "")


def shape(value, manifest) -> dict | None:
    if value is None:
        return None  # no raster reading at all: offline, not "outside"
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT, class_label, domain, limits, named

    value = value if isinstance(value, dict) else {"depth_class": value}
    cls = max(int(value["depth_class"]), 0)
    value = {**value, "depth_class": cls}
    sid = manifest.id
    narrative = (f"The city's stormwater flood map {named(sid)} shows {result(value, sid)} at the point mapped for "
                 f"this address. {limits(sid)}")
    if cls == 0:
        narrative += f" {OUTSIDE_CAVEAT}"
    return {
        "depth_class": cls,
        "depth_label": class_label(cls, sid),
        "category": domain(sid).get(cls),  # the city's own category name; None when outside
        "edge_m": value.get("edge_m"),
        "citation": manifest.provenance.citation or f"NYC Stormwater Flood Maps, {manifest.title}",
        "narrative": narrative,
    }
