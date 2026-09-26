"""USGS Water Data OGC API: latest stream-gauge values near a point.

api.waterdata.usgs.gov `latest-continuous`, read through `dataretrieval`.
It replaces the legacy waterservices.usgs.gov/nwis/iv service, which is
being degraded and shuts down in Q1 2027. National coverage, so this
ships as a federal pebble: every deployment gets the nearest active
stream gauge's stage (and discharge where published). Points with no
active gauge in the search box skip cleanly (summary_for_point returns
None).

No key is needed. Unauthenticated requests share USGS's small hourly
quota; set API_USGS_PAT (read by dataretrieval) to raise it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

log = logging.getLogger("riprap.usgs_gauges")

DOC_ID = "usgs_gauges"
CITATION = "USGS Water Data OGC API, latest continuous values (api.waterdata.usgs.gov)"

_BOX_DEG = 0.125  # search half-width; ~14 km N-S
_PARAM_STAGE = "00065"  # gage height, ft
_PARAM_DISCHARGE = "00060"  # discharge, ft³/s
# latest-continuous keeps the last value of retired gauges too (some date
# from the 1990s); anything older than this is not a live reading.
_MAX_AGE = timedelta(days=2)


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


def summary_for_point(lat: float, lon: float) -> dict[str, Any] | None:
    import dataretrieval.waterdata as wd  # noqa: PLC0415

    bbox = [lon - _BOX_DEG, lat - _BOX_DEG, lon + _BOX_DEG, lat + _BOX_DEG]
    try:
        df, _ = wd.get_latest_continuous(
            parameter_code=[_PARAM_STAGE, _PARAM_DISCHARGE], bbox=bbox
        )
    except Exception as e:  # noqa: BLE001 - an unreachable API skips the pebble
        log.warning("USGS latest-continuous failed: %r", e)
        return None
    if df is None or df.empty:
        return None
    df = df[df["time"] >= datetime.now(UTC) - _MAX_AGE]

    sites: dict[str, dict[str, Any]] = {}
    for row in df.itertuples():
        site = sites.setdefault(
            row.monitoring_location_id,
            {"site_id": row.monitoring_location_id, "lat": row.geometry.y, "lon": row.geometry.x},
        )
        if row.parameter_code == _PARAM_STAGE:
            site["stage_ft"], site["obs_time"] = float(row.value), row.time
        elif row.parameter_code == _PARAM_DISCHARGE:
            site["discharge_cfs"] = float(row.value)

    gauged = [s for s in sites.values() if "stage_ft" in s]
    if not gauged:
        return None
    for s in gauged:
        s["distance_km"] = round(_haversine_km(lat, lon, s["lat"], s["lon"]), 1)
    nearest = min(gauged, key=lambda s: s["distance_km"])

    site_no = nearest["site_id"].removeprefix("USGS-")
    try:
        ml, _ = wd.get_monitoring_locations(
            monitoring_location_id=nearest["site_id"], properties=["monitoring_location_name"]
        )
        site_name = _pretty_name(ml["monitoring_location_name"].iloc[0])
    except Exception:  # noqa: BLE001 - the name is cosmetic
        site_name = f"USGS {site_no}"

    obs_time = nearest["obs_time"].strftime("%Y-%m-%d %H:%M UTC")
    bits = [
        f"Nearest USGS stream gauge, {site_name} "
        f"({site_no}, {nearest['distance_km']} km away): "
        f"stage {nearest['stage_ft']} ft"
    ]
    if "discharge_cfs" in nearest:
        bits.append(f", discharge {nearest['discharge_cfs']} ft³/s")
    bits.append(f", observed {obs_time}.")
    # Gauge coordinates stay out of the value: the scalars card variant
    # renders every numeric field as a hero stat, and a bare 42.66/-73.74
    # reads as noise next to stage/discharge.
    out: dict[str, Any] = {
        "site_no": site_no,
        "site_name": site_name,
        "distance_km": nearest["distance_km"],
        "stage_ft": nearest["stage_ft"],
        "obs_time": obs_time,
        "n_gauges_in_area": len(gauged),
        "narrative": "".join(bits),
    }
    if "discharge_cfs" in nearest:
        out["discharge_cfs"] = nearest["discharge_cfs"]
    return out
