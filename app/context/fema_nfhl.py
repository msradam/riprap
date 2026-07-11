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

_ZONE_LAYER = 28
_PANEL_LAYER = 3


def _point_query(
    layer: int, lat: float, lon: float, out_fields: str, cache_ttl_s: int
) -> list[dict[str, Any]]:
    url = (
        f"{URL}/{layer}/query?geometry={lon},{lat}"
        f"&geometryType=esriGeometryPoint&inSR=4326"
        f"&spatialRel=esriSpatialRelIntersects"
        f"&outFields={out_fields}&returnGeometry=false&f=json"
    )
    data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=20.0)
    return data.get("features") or []


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
    try:
        panels = _point_query(_PANEL_LAYER, lat, lon, "FIRM_PAN,EFF_DATE", cache_ttl_s)
        # A point on a panel boundary intersects several panels — cite
        # the most recently effective one.
        dated = [p["attributes"] for p in panels if p["attributes"].get("EFF_DATE")]
        if dated:
            latest = max(dated, key=lambda a: a["EFF_DATE"])
            panel_id = latest.get("FIRM_PAN")
            eff_year = datetime.fromtimestamp(latest["EFF_DATE"] / 1000, UTC).year
    except httpx.HTTPError:
        pass  # zone still citable; narrative falls back to zone-only

    fld_zone = zone.get("FLD_ZONE")
    sfha = zone.get("SFHA_TF") == "T"
    bits = [f"This address sits in FEMA flood zone {fld_zone}"]
    if sfha:
        bits.append(" (a Special Flood Hazard Area)")
    if panel_id and eff_year:
        bits.append(f", per NFHL FIRM panel {panel_id}, effective {eff_year}")
    bits.append(".")
    return {
        "fld_zone": fld_zone,
        "zone_subty": zone.get("ZONE_SUBTY"),
        "sfha": sfha,
        "firm_panel": panel_id,
        "effective_year": eff_year,
        "narrative": "".join(bits),
    }
