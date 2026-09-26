"""Neighbourhood evidence: polygon-scope pebble functions.

Thin wrappers over the existing polygon summaries that add a `narrative`
sentence, so the polygon manifests in deployments/nyc/manifests/*_nta.yaml
render through the same `{narrative}` template path as point pebbles.
Each takes a WGS84 shapely polygon (the resolved NTA).
"""

from __future__ import annotations

from app.context import dob_permits, microtopo, nyc311
from app.flood_layers import dep_stormwater, sandy_inundation


def _pct(x: float) -> float:
    return round(x * 100, 1)


def sandy(polygon) -> dict:
    v = sandy_inundation.coverage_for_polygon(polygon)
    v["narrative"] = (
        f"{_pct(v['fraction'])}% of this area lies inside the 2012 Hurricane Sandy "
        f"inundation extent (area {round(v['polygon_area_m2'] / 1e6, 2)} km²)."
    )
    return v


def dep(polygon, scenario: str) -> dict:
    v = dep_stormwater.coverage_for_polygon(polygon, scenario)
    c = v["fraction_class"]
    v["narrative"] = (
        f"{v['label']}: {_pct(v['fraction_any'])}% of this area is modeled to flood "
        f"({_pct(c.get(1, 0))}% nuisance, over 4 in to 1 ft; {_pct(c.get(2, 0))}% 1 to 4 ft; "
        f"{_pct(c.get(3, 0))}% over 4 ft)."
    )
    v["fraction_class"] = {str(k): val for k, val in c.items()}  # JSON-safe keys
    return v


def complaints(polygon, years: int = 3) -> dict:
    v = nyc311.summary_for_polygon(polygon, years=years)
    top = next(iter(v.get("by_descriptor") or {}), None)
    v["narrative"] = (
        f"{v['n']} NYC 311 flood-related complaints were filed inside this area in the "
        f"last {years} years." + (f" Most common descriptor: {top}." if top else "")
    )
    return v


def terrain(polygon) -> dict | None:
    v = microtopo.microtopo_for_polygon(polygon)
    if not v:
        return None
    bits = [f"Median ground elevation {v['elev_median_m']} m (10th percentile {v['elev_p10_m']} m)"]
    if v.get("frac_hand_lt1") is not None:
        bits.append(f"{_pct(v['frac_hand_lt1'])}% of the area sits less than 1 m above the "
                    "nearest drainage (HAND)")
    v["narrative"] = "; ".join(bits) + "."
    return v


def permits(polygon) -> dict:
    v = dob_permits.summary_for_polygon(polygon, top_n=5)
    v["narrative"] = (
        f"{v['n_total']} active NYC DOB construction permits inside this area since "
        f"{v['since']}: {v['n_in_sandy']} inside the 2012 Sandy extent and {v['n_in_dep_any']} "
        "inside at least one DEP stormwater scenario (current conditions to 2080 sea-level rise)."
    )
    return v
