"""Build a register of exposed assets for one asset class.

Every asset of the class is joined to the 2012 Sandy inundation zone and
the three DEP stormwater scenarios. An asset inside any of them goes into
data/registers/<asset_class>.json with its flags, its DEP depth classes
and its terrain reading; assets inside none are left out, which is what
the register sentence says ("the register lists only ...").

An asset whose point is outside the Sandy outline but within 50 m of it
is kept too (`near_sandy_edge`): the outline is not exact to a building,
so such an asset is named as near the edge, never counted as exposed and
never silently dropped.

A loader of outlines (NYCHA developments) sets `sandy` itself, from the
share of each outline inside the extent (`sandy_share`); a development
with some of its outline inside but under the threshold is kept the same
way, named and not counted.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from app.flood_layers import dep_stormwater, sandy_inundation

ROOT = Path(__file__).resolve().parent.parent
REGISTERS_DIR = ROOT / "data" / "registers"
# The Limited Flood map (dep_limited_current) is not tested: adding it means rebuilding both registers from
# their source files, and the register sentence (app/registers/exposure.py, `scope`) names the three that are.
SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current")


def _snap(lat: float, lon: float) -> dict:
    """What the register sentence reads back for one asset."""
    from riprap.core.pebbles.bridge import fetch_pebble  # noqa: PLC0415

    sandy, _, _ = fetch_pebble("sandy", lat, lon)
    if not isinstance(sandy, dict):
        raise RuntimeError("the Sandy layer did not answer; a register built without it would say no asset was inside")
    dep = {}
    for s in SCENARIOS:
        v = fetch_pebble(s, lat, lon)[0]
        if not isinstance(v, dict):
            raise RuntimeError(f"the {s} layer did not answer; a register built without it would say the asset is outside")
        dep[s] = {"depth_class": v.get("depth_class")}
    return {"sandy": bool(sandy.get("inside")), "dep": dep, "microtopo": fetch_pebble("microtopo", lat, lon)[0]}


def build_register(asset_class: str, loader: Callable, *,
                   meta_keys: tuple[str, ...] = ("name", "address", "borough"),
                   regenerate: bool = False) -> Path:
    """Write data/registers/<asset_class>.json. `loader` returns a
    GeoDataFrame of point geometries with at least the `meta_keys` columns.
    One row per location: several schools in one building are one row."""
    out = REGISTERS_DIR / f"{asset_class}.json"
    if out.exists() and not regenerate:
        print(f"already exists: {out}; pass regenerate=True to rebuild", file=sys.stderr)
        return out
    REGISTERS_DIR.mkdir(exist_ok=True, parents=True)
    g = loader()
    if g.crs is None or g.crs.to_string() != "EPSG:2263":
        g = g.to_crs("EPSG:2263")
    by_share = "sandy_share" in g.columns
    if not by_share:
        g["sandy"] = sandy_inundation.join(g).astype(int)
    for scen in SCENARIOS:
        g[f"{scen}_class"] = dep_stormwater.join(g, scen)["depth_class"].fillna(0).astype(int)
        g[scen] = (g[f"{scen}_class"] > 0).astype(int)
    ll = g.geometry.to_crs("EPSG:4326")
    g["lat"], g["lon"] = ll.y, ll.x
    if by_share:
        g["near_sandy_edge"] = ((g["sandy"] == 0) & (g["sandy_share"] > 0)).astype(int)
    else:
        g["near_sandy_edge"] = [int(not inside and sandy_inundation.at_point(pt)["edge_m"] is not None)
                                for inside, pt in zip(g["sandy"], g.geometry, strict=True)]
    exposed = g[g[["sandy", "near_sandy_edge", *SCENARIOS]].sum(axis=1) > 0].sort_values("name")
    print(f"{len(exposed)} of {len(g)} {asset_class} records are inside the Sandy zone or a DEP scenario, "
          f"or just outside the Sandy rule ({int(g['near_sandy_edge'].sum())} near its edge or partly inside)", file=sys.stderr)
    rows, seen = [], set()
    for _, row in exposed.iterrows():
        key = (round(float(row["lat"]), 5), round(float(row["lon"]), 5))
        if key in seen:
            continue
        seen.add(key)
        snap = _snap(float(row["lat"]), float(row["lon"]))
        # The joins above put the row in the register, so they also decide its
        # flags: the point readings can differ from them by a pixel at an edge,
        # and a row must not be listed for one reason and counted by another.
        snap["sandy"] = bool(row["sandy"])
        for s in SCENARIOS:
            snap["dep"][s]["depth_class"] = max(int(snap["dep"][s]["depth_class"] or 0), int(row[f"{s}_class"]))
        rows.append({**{k: row.get(k) for k in g.columns if k != "geometry" and not k.endswith("_class")},
                     "lat": float(row["lat"]), "lon": float(row["lon"]), "snap": snap})
    out.write_text(json.dumps({"asset_class": asset_class, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "rows": rows}, default=str))
    print(f"wrote {len(rows)} rows -> {out}", file=sys.stderr)
    return out
