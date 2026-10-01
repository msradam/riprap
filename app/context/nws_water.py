"""The National Weather Service's water-level forecast for the nearest
harbour gauge (National Water Prediction Service, api.water.noaa.gov, no
key).

It is the forecast a reader should use: driven by forecast wind and
pressure, issued by the Weather Service, published with the gauge's own
flood stages. Riprap quotes its peak and says which stage that reaches.
It replaced a time-series model of Riprap's own that had no weather input
and did no better than the mean of the last day.
"""
from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt

from riprap.core import http

URL = "https://api.water.noaa.gov/nwps/v1/gauges"
# (NWPS id, name, lat, lon): the harbour gauges in the city with a forecast.
GAUGES = [
    ("BATN6", "The Battery", 40.7006, -74.0142),
    ("KPTN6", "Kings Point", 40.8113, -73.7657),
    ("BGNN6", "Bergen Point (Kill Van Kull)", 40.6390, -74.1463),
]
STAGES = ("major", "moderate", "minor")  # highest first


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def _json(path: str) -> dict:
    r = http.get(f"{URL}/{path}", timeout=20.0)
    r.raise_for_status()
    return r.json()


def summary_for_point(lat: float, lon: float) -> dict | None:
    """The forecast peak at the nearest gauge and the flood stage it
    reaches. None when the service has no current forecast for it."""
    lid, name, glat, glon = min(GAUGES, key=lambda g: _km(lat, lon, g[2], g[3]))
    gauge, fc = _json(lid), _json(f"{lid}/stageflow/forecast")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    ahead = [(d["validTime"], float(d["primary"])) for d in fc.get("data") or []
             if d.get("validTime", "") >= now and d.get("primary") is not None and float(d["primary"]) > -900]
    if not ahead:
        return None
    peak_time, peak = max(ahead, key=lambda d: d[1])
    stages = {k: float(v["stage"]) for k, v in ((gauge.get("flood") or {}).get("categories") or {}).items()
              if k in STAGES and v.get("stage") is not None and float(v["stage"]) > -900}
    category = next((k for k in STAGES if k in stages and peak >= stages[k]), None)
    when = lambda t: t[:16].replace("T", " ")  # noqa: E731
    text = (f"The National Weather Service forecasts a peak water level of {peak:.1f} ft above MLLW at {name} "
            f"on {when(peak_time)} UTC (forecast issued {when(fc.get('issuedTime', ''))} UTC)")
    if category:
        text += f", which reaches the gauge's {category} flood stage of {stages[category]:.1f} ft."
    elif "minor" in stages:
        text += f", below the gauge's minor flood stage of {stages['minor']:.1f} ft."
    else:
        text += "."
    return {"gauge_id": lid, "gauge_name": name, "distance_km": round(_km(lat, lon, glat, glon), 1),
            "forecast_peak_ft_mllw": round(peak, 2), "forecast_peak_time_utc": peak_time,
            "issued_utc": fc.get("issuedTime"), "flood_stages_ft": stages, "flood_category": category,
            "forecast_until_utc": ahead[-1][0], "narrative": text}
