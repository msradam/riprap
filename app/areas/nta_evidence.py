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
    rain = _pct(c.get(1, 0) + c.get(2, 0))
    label = dep_stormwater.class_label
    v["narrative"] = (
        f"{v['label']}: {rain}% of this area is modeled to flood from rainfall, "
        f"{_pct(c.get(1, 0))}% as {label(1, scenario)} and {_pct(c.get(2, 0))}% as {label(2, scenario)}"
    )
    v["headline_value"] = f"{rain}% modeled to flood from rainfall"
    # Class 3 is the scenario's future high tide area, not deeper rainfall
    # flooding; the current-sea-level file has none.
    if dep_stormwater.SCENARIOS[scenario]["year"]:
        tide = _pct(c.get(3, 0))
        v["narrative"] += (f"; {tide}% is in the future high tide area "
                           f"({dep_stormwater.tide_words(scenario)})")
        v["headline_value"] += f", {tide}% future high tide"
    v["narrative"] += "."
    v["fraction_class"] = {str(k): val for k, val in c.items()}  # JSON-safe keys
    return v


def complaints(polygon, query=None, years: int = 3) -> dict:
    """A community district (QN12) is counted by the 311 record's own
    community_board field, the official definition; a neighborhood by
    its NTA polygon. The district's NTA-union outline stays on the map."""
    code = (query.extras.get("area_code") if query else None) or ""
    if nyc311.community_board(code):
        return nyc311.summary_for_district(code, years=years)
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


def assets(polygon, asset_class: str) -> dict:
    """The exposed assets of one class inside the area, by name."""
    from app.registers import exposure

    return exposure.summary_for_polygon(polygon, asset_class)


_PROFILES_URL = "https://planninglabs.carto.com/api/v2/sql"
_PROFILES_TABLE = "community_district_profiles_v202402"  # the table the profiles site itself reads
_BORO_DIGIT = {"MN": 1, "BX": 2, "BK": 3, "QN": 4, "SI": 5}


def floodplain(polygon, query=None) -> dict | None:  # noqa: ARG001 - polygon keeps the area-pebble signature
    """Buildings, residential units and residents in the 1% annual chance
    floodplain of a community district, as NYC Planning's Community
    District Profiles count them. None for an area that is not a district:
    the profiles exist per district only."""
    from riprap.core import http

    code = ((query.extras.get("area_code") if query else None) or "").upper().replace(" ", "")
    if not nyc311.community_board(code):
        return None
    borocd = _BORO_DIGIT[code[:2]] * 100 + int(code[2:])
    r = http.get(_PROFILES_URL, timeout=20, params={
        "q": f"SELECT fp_100_bldg, fp_100_resunits, fp_100_pop, fp_100_area FROM {_PROFILES_TABLE} WHERE borocd = {borocd}"})
    r.raise_for_status()
    rows = r.json().get("rows") or []
    if not rows:
        raise ValueError(f"the district profiles table has no row for {borocd}")
    v = {k: rows[0].get(k) for k in ("fp_100_bldg", "fp_100_resunits", "fp_100_pop", "fp_100_area")}
    bldg, units, pop = (int(v[k] or 0) for k in ("fp_100_bldg", "fp_100_resunits", "fp_100_pop"))
    return {"community_district": code, "n_buildings": bldg, "n_residential_units": units, "n_residents_2010": pop,
            "floodplain_sq_mi": v["fp_100_area"],
            "narrative": (f"NYC Planning's Community District Profile counts {bldg:,} building{'s' if bldg != 1 else ''}, "
                          f"{units:,} residential unit{'s' if units != 1 else ''} and {pop:,} "
                          f"resident{'s' if pop != 1 else ''} in the 1% annual chance floodplain of this district "
                          "(the floodplain of FEMA's 2015 preliminary and 2007 maps; residents from the 2010 census, "
                          "by census block).")}


def alerts(polygon) -> dict:
    """Active Weather Service alerts for the area, read at its centre
    (alerts are issued by forecast zone, far larger than a district)."""
    from app.context import nws_alerts

    c = polygon.centroid
    v = nws_alerts.summary_for_point(c.y, c.x)
    if v.get("narrative"):
        v["narrative"] = v["narrative"].replace(" at this point", " for this area (read at its centre)")
    return v


def sea_level(polygon) -> dict:  # noqa: ARG001 - one projection for the whole city
    from app.context import npcc4_slr

    return npcc4_slr.get_projections()
