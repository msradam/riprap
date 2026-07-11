"""USGS NWIS instantaneous values — live stream gauges near a point.

waterservices.usgs.gov/nwis/iv, no auth, 15-minute cadence. National
coverage, so this ships as a federal pebble: every deployment gets the
nearest active stream gauge's stage (and discharge where published).
For Albany that's Patroon Creek at Albany (01359135); for NYC it's the
harbor-adjacent gauges; cities with no gauge in the search box skip
the pebble cleanly (summary_for_point returns None).
"""

from __future__ import annotations

import time
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx

from riprap.core.pebbles._http import fetch_url_json

DOC_ID = "usgs_gauges"
CITATION = "USGS NWIS instantaneous values (waterservices.usgs.gov)"
URL = "https://waterservices.usgs.gov/nwis/iv/"

# NWIS rejects wider boxes with a 503 despite the documented 25-sq-deg
# limit; 0.25° total width is empirically the reliable ceiling.
_BOX_DEG = 0.125  # search half-width; ~14 km N-S
_PARAM_STAGE = "00065"  # gage height, ft
_PARAM_DISCHARGE = "00060"  # discharge, ft³/s


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _pretty_name(raw: str) -> str:
    """USGS site names arrive all-caps ('PATROON CREEK AT ALBANY NY');
    title-case them but keep the trailing state code upper."""
    words = raw.title().split()
    if words and len(words[-1]) == 2:
        words[-1] = words[-1].upper()
    return " ".join(words)


def _latest(series: dict) -> tuple[str, str] | None:
    values = series["values"][0]["value"]
    if not values:
        return None
    return values[-1]["value"], values[-1]["dateTime"]


def summary_for_point(lat: float, lon: float, cache_ttl_s: int = 900) -> dict[str, Any] | None:
    bbox = f"{lon - _BOX_DEG:.4f},{lat - _BOX_DEG:.4f},{lon + _BOX_DEG:.4f},{lat + _BOX_DEG:.4f}"
    url = (
        f"{URL}?format=json&bBox={bbox}"
        f"&parameterCd={_PARAM_STAGE},{_PARAM_DISCHARGE}&siteStatus=active"
    )
    # NWIS throws intermittent 503s under load; one retry rides most out.
    # A bbox with no matching sites is a 404, not an empty list — after
    # the retry, treat any HTTP failure as "no gauge here".
    for attempt in (1, 2):
        try:
            data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=15.0)
            break
        except httpx.HTTPError:
            if attempt == 2:
                return None
            time.sleep(1.5)

    sites: dict[str, dict[str, Any]] = {}
    for ts in data.get("value", {}).get("timeSeries", []):
        info = ts["sourceInfo"]
        site_no = info["siteCode"][0]["value"]
        loc = info["geoLocation"]["geogLocation"]
        site = sites.setdefault(
            site_no,
            {
                "site_no": site_no,
                "site_name": _pretty_name(info["siteName"]),
                "lat": loc["latitude"],
                "lon": loc["longitude"],
            },
        )
        param = ts["variable"]["variableCode"][0]["value"]
        latest = _latest(ts)
        if latest is None:
            continue
        if param == _PARAM_STAGE:
            site["stage_ft"], site["obs_time"] = float(latest[0]), latest[1]
        elif param == _PARAM_DISCHARGE:
            site["discharge_cfs"] = float(latest[0])

    gauged = [s for s in sites.values() if "stage_ft" in s]
    if not gauged:
        return None
    for s in gauged:
        s["distance_km"] = round(_haversine_km(lat, lon, s["lat"], s["lon"]), 1)
    nearest = min(gauged, key=lambda s: s["distance_km"])

    # '2026-07-09T23:15:00.000-05:00' → '2026-07-09 23:15' for prose.
    obs_time = str(nearest.get("obs_time", ""))[:16].replace("T", " ")

    bits = [
        f"Nearest USGS stream gauge, {nearest['site_name']} "
        f"({nearest['site_no']}, {nearest['distance_km']} km away): "
        f"stage {nearest['stage_ft']} ft"
    ]
    if "discharge_cfs" in nearest:
        bits.append(f", discharge {nearest['discharge_cfs']} ft³/s")
    bits.append(f", observed {obs_time}.")
    # Gauge coordinates stay out of the value: the scalars card variant
    # renders every numeric field as a hero stat, and a bare 42.66/-73.74
    # reads as noise next to stage/discharge.
    out: dict[str, Any] = {
        "site_no": nearest["site_no"],
        "site_name": nearest["site_name"],
        "distance_km": nearest["distance_km"],
        "stage_ft": nearest["stage_ft"],
        "obs_time": obs_time,
        "n_gauges_in_area": len(gauged),
        "narrative": "".join(bits),
    }
    if "discharge_cfs" in nearest:
        out["discharge_cfs"] = nearest["discharge_cfs"]
    return out
