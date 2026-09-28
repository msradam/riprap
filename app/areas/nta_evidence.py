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
    # The figure the evidence card leads with (the card's big line).
    v["headline_value"] = f"{_pct(v['fraction'])}% inside the 2012 Sandy extent"
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
    v["headline_value"] = f"{_pct(v['fraction_any'])}% modeled to flood"
    return v


def complaints(polygon, years: int = 3) -> dict:
    return nyc311.summary_for_polygon(polygon, years=years)


def terrain(polygon) -> dict | None:
    v = microtopo.microtopo_for_polygon(polygon)
    if not v:
        return None
    bits = [f"Median ground elevation {v['elev_median_m']} m (10th percentile {v['elev_p10_m']} m)"]
    if v.get("frac_hand_lt1") is not None:
        bits.append(f"{_pct(v['frac_hand_lt1'])}% of the area sits less than 1 m above the "
                    "nearest drainage channel (HAND, height above nearest drainage)")
    v["narrative"] = "; ".join(bits) + "."
    v["headline_value"] = f"median ground elevation {v['elev_median_m']} m"
    return v


def permits(polygon) -> dict:
    v = dob_permits.summary_for_polygon(polygon, top_n=5)
    v["narrative"] = (
        f"{v['n_total']} active NYC DOB construction permits inside this area since "
        f"{v['since']}: {v['n_in_sandy']} inside the 2012 Sandy extent and {v['n_in_dep_any']} "
        "inside at least one DEP stormwater scenario (current conditions to 2080 sea-level rise)."
    )
    v["headline_value"] = f"{v['n_total']} active permit{'s' if v['n_total'] != 1 else ''}"
    return v


def boundary(polygon) -> dict:
    """The resolved area's outline for the map, simplified to about 20 m,
    as GeoJSON. A community district is the union of its 2020 NTAs."""
    from shapely.geometry import mapping

    return {
        "geojson": mapping(polygon.simplify(0.0002, preserve_topology=True)),
        "narrative": ("The outline on the map is this area's boundary from the NYC Department of City "
                      "Planning's 2020 Neighborhood Tabulation Areas; a community district is drawn as "
                      "the union of its tabulation areas, which approximates the district."),
    }
