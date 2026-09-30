"""NYS DOH hospitals in NYC near a point, with flood exposure per hospital.
The class table and the query live in app.registers.exposure."""
from __future__ import annotations

from app.registers import exposure


def summary_for_point(lat: float, lon: float, radius_m: float | None = None,
                      max_hospitals: int | None = None) -> dict:
    return exposure.summary_for_point(lat, lon, "doh_hospitals", radius_m, max_hospitals)
