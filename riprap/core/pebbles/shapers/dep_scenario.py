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


def code(value) -> int | None:
    """The Flooding_Category code of a reading (0 outside), under the key
    it has now or the one it had (`depth_class`, a name that read as a
    depth stated for the address)."""
    if not isinstance(value, dict):
        return None
    c = value.get("category_code", value.get("depth_class"))
    return None if c is None else int(c)


def shared_edge(values: dict) -> str:
    """One clause for the maps on which the point is at a mapped edge, when
    two or more are: four maps once each printed "about 3 m from the nearest
    flooding mapped on it", a metre figure from a model that disclaims
    location precision. "" when fewer than two maps have an edge (the one
    map's own phrase then carries it: see `result`)."""
    edges = [v["edge_m"] for v in values.values() if isinstance(v, dict) and v.get("edge_m")]
    if len(edges) < 2:
        return ""
    which = "each of these maps" if len(edges) == len(values) else f"{len(edges)} of these maps"
    return f"; on {which} the point is {_edge(max(edges), 'mapped flooding')}"


EDGE_M = 10  # "at the edge" within this; farther off the distance is said plainly (44 m is not an edge)


def _edge(edge_m, of: str) -> str:
    """'at the edge of <of> (within about 6 m)' or 'about 44 m from the edge of <of>'."""
    return (f"at the edge of {of} (within about {edge_m} m)" if edge_m <= EDGE_M
            else f"about {edge_m} m from the edge of {of}")


def result(value: dict, scenario: str, edge: bool = True) -> str:
    """One map's reading as a short phrase, for lists of maps. With
    `edge=False` the nearness of a mapped edge is left to `shared_edge`."""
    from app.flood_layers.dep_stormwater import TIDE_CLASS, domain

    cls, edge_m = code(value), value.get("edge_m") if edge else None
    if not cls:
        return "no flooding category" + (f", {_edge(edge_m, 'flooding mapped on it')}" if edge_m else "")
    notes = (["coastal tidal inundation, not rainfall flooding"] if cls == TIDE_CLASS else []) + (
        [_edge(edge_m, "the mapped flooding")] if edge_m else [])
    return f'the category "{domain(scenario)[cls]}"' + (f" ({'; '.join(notes)})" if notes else "")


def shape(value, manifest) -> dict | None:
    if value is None:
        return None  # no raster reading at all: offline, not "outside"
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT, PLAN_CHANCE, domain, limits, named

    value = value if isinstance(value, dict) else {"depth_class": value}
    cls = max(code(value), 0)
    value = {**value, "category_code": cls}
    sid = manifest.id
    narrative = (f"The city's stormwater flood map {named(sid)} shows {result(value, sid)} at the point mapped for "
                 f"this address. {limits(sid)} {PLAN_CHANCE}")
    if cls == 0:
        narrative += f" {OUTSIDE_CAVEAT}"
    return {
        # The map's Flooding_Category at the point: a category of a scenario map,
        # never a depth for the address (the keys were depth_class and depth_label).
        "category_code": cls,
        "category": domain(sid).get(cls),  # the city's own category name; None when outside
        "edge_m": value.get("edge_m"),
        "citation": manifest.provenance.citation or f"NYC Stormwater Flood Maps, {manifest.title}",
        "narrative": narrative,
    }
