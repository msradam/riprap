"""FEMA National Flood Hazard Layer — effective flood zone + map vintage.

hazards.fema.gov ArcGIS REST, no auth. Two point queries: layer 28
(S_Fld_Haz_Ar, the effective flood-zone polygons) for the zone, and
layer 3 (S_FIRM_Pan) for the FIRM panel and its effective date — the
map vintage that FEMA 1.5 (and the `firm_citation_has_vintage`
compliance predicate) requires alongside any flood-map claim.

Returns None only when the service answered and maps nothing at the point
(open water, no effective FIRM). A failed query (a timeout, an HTTP error,
a reset connection, an empty or malformed reply, an ArcGIS error body)
raises, so the run records the source as failed and the briefing lists it
as not checked. A failure never reads as "no zone here".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from riprap.core.pebbles._http import fetch_url_json

DOC_ID = "fema_nfhl"
CITATION = "FEMA National Flood Hazard Layer (hazards.fema.gov)"
URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
# The preliminary maps: the same layers, one service over. Layer 0 lists the
# preliminary study covering a point with the date FEMA issued it.
PRELIM_URL = "https://hazards.fema.gov/arcgis/rest/services/PrelimPending/Prelim_NFHL/MapServer"

_ZONE_LAYER = 28
_PANEL_LAYER = 3
_PRELIM_AVAILABILITY_LAYER = 0


def _point_query(
    layer: int, lat: float, lon: float, out_fields: str, cache_ttl_s: int, base: str = URL
) -> list[dict[str, Any]]:
    url = (
        f"{base}/{layer}/query?geometry={lon},{lat}"
        f"&geometryType=esriGeometryPoint&inSR=4326"
        f"&spatialRel=esriSpatialRelIntersects"
        f"&outFields={out_fields}&returnGeometry=false&f=json"
    )
    try:
        data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=20.0)
    except ValueError as e:  # the service answers some failures with HTTP 200 and an empty or broken body
        raise httpx.HTTPError(f"FEMA's map service sent an unreadable reply for layer {layer}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        # An ArcGIS error arrives as HTTP 200 with {"error": ...} and no "features".
        why = data.get("error") if isinstance(data, dict) else data
        raise httpx.HTTPError(f"FEMA's map service sent no features list for layer {layer}: {str(why)[:200]}")
    return data["features"]


# Zone X covers both the 0.2% annual chance floodplain and areas of minimal
# hazard; the subtype tells them apart, so it is read out plainly.
_SUBTYPE_READING = {
    "0.2 PCT ANNUAL CHANCE FLOOD HAZARD": "the 0.2% annual chance, or 500-year, floodplain",
    "AREA OF MINIMAL FLOOD HAZARD": "an area of minimal flood hazard",
}


def zone_reading(subtype: str | None) -> str | None:
    """A plain reading of a FEMA zone subtype, or None when there is none."""
    if not subtype or not subtype.strip():
        return None
    s = subtype.strip()
    return _SUBTYPE_READING.get(s.upper(), s.lower())


def summary_for_point(lat: float, lon: float, cache_ttl_s: int = 86400) -> dict[str, Any] | None:
    zones = _point_query(_ZONE_LAYER, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF,DFIRM_ID", cache_ttl_s)
    if not zones:
        return None
    zone = zones[0]["attributes"]

    panel_id: str | None = None
    eff_year: int | None = None
    eff_date: str | None = None
    try:
        panels = _point_query(_PANEL_LAYER, lat, lon, "FIRM_PAN,EFF_DATE,DFIRM_ID", cache_ttl_s)
        # Panel polygons overlap along the water (at Staten Island's shore
        # two New Jersey countywide panels cover the point as well as
        # NYC's), so cite a panel from the zone's own study when there is
        # one, and the most recently effective of those.
        dated = [p["attributes"] for p in panels if p["attributes"].get("EFF_DATE")]
        same_study = [a for a in dated if a.get("DFIRM_ID") == zone.get("DFIRM_ID")]
        dated = same_study or dated
        if dated:
            latest = max(dated, key=lambda a: a["EFF_DATE"])
            panel_id = latest.get("FIRM_PAN")
            eff = datetime.fromtimestamp(latest["EFF_DATE"] / 1000, UTC)
            eff_year, eff_date = eff.year, eff.date().isoformat()
    except httpx.HTTPError:
        pass  # zone still citable; narrative falls back to zone-only

    fld_zone = zone.get("FLD_ZONE")
    sfha = zone.get("SFHA_TF") == "T"
    bits = [f"This address sits in FEMA flood zone {fld_zone}"]
    if sfha:
        bits.append(" (a Special Flood Hazard Area)")
    elif (reading := zone_reading(zone.get("ZONE_SUBTY"))):
        bits.append(f" ({reading})")
    # Which map and its date, and what it is for. The effective FIRM is the
    # National Flood Insurance Program's official map (44 CFR 59.1: "an
    # official map of a community, on which the Federal Insurance
    # Administrator has delineated both the special hazard areas and the risk
    # premium zones"); in New York City, "FEMA uses the 2007 FIRMs for
    # compliance with NFIP" (NYC Hazard Mitigation Plan, flooding profile).
    if panel_id and eff_year:
        bits.append(f" on FEMA's effective flood map (FIRM panel {panel_id}, effective {eff_date})")
    else:
        bits.append(" on FEMA's effective flood map")
    bits.append(", the map in force for the National Flood Insurance Program.")
    return {
        "fld_zone": fld_zone,
        "zone_subty": zone.get("ZONE_SUBTY"),
        "sfha": sfha,
        "firm_panel": panel_id,
        "effective_year": eff_year,
        "effective_date": eff_date,  # the FIRM panel's; the citation's vintage
        "narrative": "".join(bits),
    }


def preliminary_for_point(lat: float, lon: float, cache_ttl_s: int = 86400) -> dict[str, Any] | None:
    """The preliminary flood zone (PFIRM) at a point, with the date FEMA
    issued the preliminary study, read from the service's own availability
    layer (the panel records carry no date until the map goes to print).
    None when the service answered and no preliminary study covers the
    point; a failed query raises (see the module docstring)."""
    zones = _point_query(_ZONE_LAYER, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM",
                         cache_ttl_s, PRELIM_URL)
    studies = _point_query(_PRELIM_AVAILABILITY_LAYER, lat, lon, "DFIRM_ID,PRELM_ISSUE_DATE",
                           cache_ttl_s, PRELIM_URL)
    if not zones or not studies:
        return None
    zone, study = zones[0]["attributes"], studies[0]["attributes"]
    issued = study.get("PRELM_ISSUE_DATE")
    issue_date = datetime.fromtimestamp(issued / 1000, UTC).date().isoformat() if issued else None
    fld_zone = zone.get("FLD_ZONE")
    sfha = zone.get("SFHA_TF") == "T"
    bfe = zone.get("STATIC_BFE")
    bfe = float(bfe) if bfe is not None and bfe > -9000 else None
    # The effective and preliminary maps use different vertical datums in NYC
    # (NGVD29 and NAVD88), so an elevation is printed with its own.
    datum = (zone.get("V_DATUM") or "").strip()
    reading = " (a Special Flood Hazard Area)" if sfha else (
        f" ({r})" if (r := zone_reading(zone.get("ZONE_SUBTY"))) else "")
    when = f" issued {issue_date}" if issue_date else ""
    narrative = (f"FEMA's preliminary flood map (PFIRM{when}, community {study.get('DFIRM_ID')}) places "
                 f"this address in zone {fld_zone}{reading}"
                 + (f", static base flood elevation {bfe:g} ft{f' {datum}' if datum else ''}" if bfe is not None else "")
                 # Its own sentence: the lead rules read a source's first
                 # sentence for a result, and "not" there reads as an absence.
                 + ". A preliminary map is not the effective map and does not set flood insurance.")
    return {
        "fld_zone": fld_zone,
        "zone_subty": zone.get("ZONE_SUBTY"),
        "sfha": sfha,
        "static_bfe_ft": bfe,
        "vertical_datum": datum or None,
        "community": study.get("DFIRM_ID"),
        "issue_date": issue_date,  # the citation's vintage
        "narrative": narrative,
    }
