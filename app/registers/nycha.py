"""Flood-exposed NYCHA developments near a point, from the baked register.
The class table and the query live in app.registers.exposure."""
from __future__ import annotations

from app.registers import exposure


def summary_for_point(lat: float, lon: float, radius_m: float | None = None,
                      max_developments: int | None = None) -> dict:
    return exposure.summary_for_point(lat, lon, "nycha", radius_m, max_developments)
