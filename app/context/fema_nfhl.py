"""FEMA National Flood Hazard Layer — effective flood zone + map vintage.

hazards.fema.gov ArcGIS REST, no auth. Two point queries: layer 28
(S_Fld_Haz_Ar, the effective flood-zone polygons) for the zone, and
layer 3 (S_FIRM_Pan) for the FIRM panel and its effective date — the
map vintage that FEMA 1.5 (and the `firm_citation_has_vintage`
compliance predicate) requires alongside any flood-map claim.

Returns None when the point is unmapped (open water / no effective
FIRM); the manifest's `on_none: offline` + `fallback.on_offline: skip`
then drop the pebble cleanly.
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
    data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=20.0)
    return data.get("features") or []


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
    try:
        zones = _point_query(_ZONE_LAYER, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF", cache_ttl_s)
    except httpx.HTTPError:
        return None
    if not zones:
        return None
    zone = zones[0]["attributes"]

    panel_id: str | None = None
    eff_year: int | None = None
    eff_date: str | None = None
    try:
        panels = _point_query(_PANEL_LAYER, lat, lon, "FIRM_PAN,EFF_DATE", cache_ttl_s)
        # A point on a panel boundary intersects several panels — cite
        # the most recently effective one.
        dated = [p["attributes"] for p in panels if p["attributes"].get("EFF_DATE")]
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
    if panel_id and eff_year:
        bits.append(f", per NFHL FIRM panel {panel_id}, effective {eff_year}")
    bits.append(".")
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
    None when no preliminary study covers the point."""
    try:
        zones = _point_query(_ZONE_LAYER, lat, lon, "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
                             cache_ttl_s, PRELIM_URL)
        studies = _point_query(_PRELIM_AVAILABILITY_LAYER, lat, lon, "DFIRM_ID,PRELM_ISSUE_DATE",
                               cache_ttl_s, PRELIM_URL)
    except httpx.HTTPError:
        return None
    if not zones or not studies:
        return None
    zone, study = zones[0]["attributes"], studies[0]["attributes"]
    issued = study.get("PRELM_ISSUE_DATE")
    issue_date = datetime.fromtimestamp(issued / 1000, UTC).date().isoformat() if issued else None
    fld_zone = zone.get("FLD_ZONE")
    sfha = zone.get("SFHA_TF") == "T"
    bfe = zone.get("STATIC_BFE")
    bfe = float(bfe) if bfe is not None and bfe > -9000 else None
    reading = " (a Special Flood Hazard Area)" if sfha else (
        f" ({r})" if (r := zone_reading(zone.get("ZONE_SUBTY"))) else "")
    when = f" issued {issue_date}" if issue_date else ""
    narrative = (f"FEMA's preliminary flood map (PFIRM{when}, community {study.get('DFIRM_ID')}) places "
                 f"this address in zone {fld_zone}{reading}"
                 + (f", static base flood elevation {bfe:g} ft" if bfe is not None else "")
                 + "; a preliminary map is not the effective map and does not set flood insurance.")
    return {
        "fld_zone": fld_zone,
        "zone_subty": zone.get("ZONE_SUBTY"),
        "sfha": sfha,
        "static_bfe_ft": bfe,
        "community": study.get("DFIRM_ID"),
        "issue_date": issue_date,  # the citation's vintage
        "narrative": narrative,
    }
