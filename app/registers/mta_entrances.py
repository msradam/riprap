"""MTA subway entrances near a point, with flood exposure per entrance.
The class table and the query live in app.registers.exposure."""
from __future__ import annotations

from app.registers import exposure

MTA_ENTRANCES = exposure.CLASSES["mta_entrances"].geojson


def summary_for_point(lat: float, lon: float, radius_m: float | None = None,
                      max_entrances: int | None = None) -> dict:
    return exposure.summary_for_point(lat, lon, "mta_entrances", radius_m, max_entrances)
