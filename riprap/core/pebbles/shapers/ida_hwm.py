"""Shaper for ida_hwm — produces the legacy `vars(HWMSummary)` dict shape.

Downstream FSM/reconcile/score consumers expect the flat layout from
app.flood_layers.ida_hwm.HWMSummary. This shaper unwraps the canonical
baked_vector adapter output into that shape so the bridge can drop in
without touching downstream code.
"""
from __future__ import annotations

FEW_MARKS = ("USGS's file holds 159 Ida high-water marks for all of New York State, so no mark nearby is not a "
             "record that the place stayed dry.")


def shape(value: dict | None, manifest=None) -> dict | None:
    if value is None:
        return None
    aggs = value.get("aggregations") or {}
    nearest = value.get("nearest")
    nearest_props = (nearest or {}).get("properties") or {}
    features = value.get("features") or []

    sample_sites = []
    for feat in features:
        site = (feat.get("properties") or {}).get("site_description")
        if site:
            sample_sites.append(site)
        if len(sample_sites) >= 5:
            break

    points = []
    for feat in features:
        props = feat.get("properties") or {}
        points.append({
            "lat": feat["lat"],
            "lon": feat["lon"],
            "site": props.get("site_description"),
            "elev_ft": props.get("elev_ft"),
            "height_above_gnd_ft": props.get("height_above_gnd"),
            "distance_m": feat["distance_m"],
        })

    n = value["n_within_radius"]
    radius = value["radius_m"]
    max_elev = _round(aggs.get("max_elev_ft"), 2)
    max_above = _round(aggs.get("max_height_above_gnd_ft"), 2)
    nearest_dist = _round((nearest or {}).get("distance_m"), 0)
    nearest_site = nearest_props.get("site_description")
    # Templatable narrative for the manifest's narration.template.
    # Two shapes: the affirmative case ("we found N marks…") and the
    # honest-negative case ("no marks within radius — the nearest is X").
    # The latter matches the NWS "no active alerts" all-clear card; users
    # see Riprap asked the question and the answer was reassuring.
    # Height above ground is what a reader means by "how deep", so it is
    # what the sentence gives, for the highest mark and for the nearest. The
    # elevation is a water surface above a survey datum (NAVD88 for every
    # NY Ida mark) with no ground reference: 30.6 ft beside 400 Carroll
    # Street was a mark up the hill in Park Slope, next to an address at
    # about 2 m. It is stated only when no mark in range has a height above
    # ground, with its datum and what it is.
    datums = {(f.get("properties") or {}).get("vertical_datum") for f in features}
    datum = datums.pop() if len(datums) == 1 else None
    if n and n > 0:
        bits = [f"USGS surveyed {n} Hurricane Ida high-water mark{'' if n == 1 else 's'} within"
                f" {radius} m of this address"]
        if max_above is not None:
            bits.append(f"; the highest stood {max_above} ft above ground")
        elif max_elev is not None and datum:
            bits.append(f"; none has a recorded height above ground, and the highest water surface stood at "
                        f"{max_elev} ft {datum} (an elevation above the survey datum, not a depth of water)")
        if nearest_site and nearest_dist is not None:
            above = nearest_props.get("height_above_gnd")
            height = f", {_round(above, 2)} ft above ground" if above is not None else ""
            bits.append(
                f". Nearest mark: {nearest_site} ({int(nearest_dist)} m away{height})"
            )
        narrative = "".join(bits) + "."
    else:
        # No mark nearby is not a record of a dry street: the file holds 159 marks for the whole state
        # (data/ida_2021_hwms_ny.geojson, as the USGS query in the citation returns; a test counts them).
        narrative = (
            f"No Hurricane Ida (Sept 2021) high-water marks were surveyed "
            f"within {radius} m of this address. {FEW_MARKS}"
        )
        if nearest_site and nearest_dist is not None:
            narrative += (
                f" Nearest USGS-surveyed mark: {nearest_site} "
                f"({int(nearest_dist)} m away)."
            )
    return {
        "n_within_radius": n,
        "radius_m": radius,
        "max_elev_ft": max_elev,
        "max_height_above_gnd_ft": max_above,
        "nearest_dist_m": nearest_dist,
        "nearest_site": nearest_site,
        "nearest_elev_ft": nearest_props.get("elev_ft"),
        "vertical_datum": datum,
        "sample_sites": sample_sites,
        "points": points,
        "narrative": narrative,
    }


def _round(v, ndigits: int):
    if v is None:
        return None
    return round(v, ndigits)
