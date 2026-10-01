"""Build a register of exposed assets for one asset class.

Every asset of the class is joined to the 2012 Sandy inundation zone and
the three DEP stormwater scenarios. An asset inside any of them goes into
data/registers/<asset_class>.json with its flags, its DEP depth classes
and its terrain reading; assets inside none are left out, which is what
the register sentence says ("the register lists only ...").
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
SCENARIOS = ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current")


def _snap(lat: float, lon: float) -> dict:
    """What the register sentence reads back for one asset."""
    from riprap.core.pebbles.bridge import fetch_pebble  # noqa: PLC0415

    sandy, _, _ = fetch_pebble("sandy", lat, lon)
    dep = {s: {"depth_class": (v or {}).get("depth_class")} for s in SCENARIOS
           if (v := fetch_pebble(s, lat, lon)[0]) is not None}
    return {"sandy": bool(sandy), "dep": dep, "microtopo": fetch_pebble("microtopo", lat, lon)[0]}


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
    g["sandy"] = sandy_inundation.join(g).astype(int)
    for scen in SCENARIOS:
        g[scen] = (dep_stormwater.join(g, scen)["depth_class"] > 0).astype(int)
    ll = g.geometry.to_crs("EPSG:4326")
    g["lat"], g["lon"] = ll.y, ll.x
    exposed = g[g[["sandy", *SCENARIOS]].sum(axis=1) > 0].sort_values("name")
    print(f"{len(exposed)} of {len(g)} {asset_class} records are inside the Sandy zone or a DEP scenario",
          file=sys.stderr)
    rows, seen = [], set()
    for _, row in exposed.iterrows():
        key = (round(float(row["lat"]), 5), round(float(row["lon"]), 5))
        if key in seen:
            continue
        seen.add(key)
        rows.append({**{k: row.get(k) for k in g.columns if k != "geometry"},
                     "lat": float(row["lat"]), "lon": float(row["lon"]),
                     "snap": _snap(float(row["lat"]), float(row["lon"]))})
    out.write_text(json.dumps({"asset_class": asset_class, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "rows": rows}, default=str))
    print(f"wrote {len(rows)} rows -> {out}", file=sys.stderr)
    return out
