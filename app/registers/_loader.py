"""Shared loader for the pre-built register JSONs in data/registers/.

Each asset register (public housing, schools, hospitals, subway
entrances) is built once by scripts/build_register.py, which joins every
asset to the Sandy extent and the DEP stormwater scenarios; a query then
reads the saved rows and finds the nearest by great-circle distance, in
milliseconds, where the full polygon join took minutes.

The housing and school registers hold only assets inside one of those
layers. An asset inside none is left out, and the register sentence says
so ("the register lists only ...")."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

REGISTERS_DIR = Path(__file__).resolve().parents[2] / "data" / "registers"


@lru_cache(maxsize=8)
def load_register(asset_class: str) -> list[dict]:
    """Return the rows list from data/registers/<asset_class>.json. The
    caller treats each row as opaque except for the lat/lon fields."""
    p = REGISTERS_DIR / f"{asset_class}.json"
    with open(p) as f:  # a missing file raises: unavailable, never "0 nearby"
        d = json.load(f)
    return list(d.get("rows", []))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _degree_box(lat: float, radius_m: float) -> tuple[float, float]:
    """Half-widths in degrees of a box that contains every point within
    radius_m: a degree of longitude shrinks with the cosine of the
    latitude (84 km at NYC against 111 km at the equator), so the box
    was 750 m wide east to west when it was drawn as 800 m."""
    dlat = radius_m / 90_000
    return dlat, dlat / math.cos(math.radians(lat))


def nearest_n(rows: list[dict], lat: float, lon: float,
              radius_m: float, n: int | None) -> list[tuple[float, dict]]:
    """Return up to N rows (all rows when n is None) within radius_m of
    (lat, lon), sorted by distance ascending. Each entry is (distance_m, row).
    The degree box trims the candidates before the haversine."""
    dlat, dlon = _degree_box(lat, radius_m)
    candidates: list[tuple[float, dict]] = []
    for r in rows:
        rlat = r.get("lat")
        rlon = r.get("lon")
        if rlat is None or rlon is None:
            continue
        rlat, rlon = float(rlat), float(rlon)
        if abs(rlat - lat) > dlat or abs(rlon - lon) > dlon:
            continue
        d = haversine_m(lat, lon, rlat, rlon)
        if d <= radius_m:
            candidates.append((d, r))
    candidates.sort(key=lambda t: t[0])
    return candidates[:n]


def narrative(one: str, many: str, n: int, radius_m: float, n_sandy: int, n_dep: int,
              *, scope: str = "", n_checked: int | None = None) -> str:
    """The register sentence. `scope` says what an exposed-only register
    counted, so its count does not read as every asset in range; when
    `n_checked` is below `n`, the exposure counts cover only the nearest
    `n_checked`. The shape "N ... within R m ...: a inside the 2012 Sandy
    ... b inside the DEP" is what answer_checks._REGISTER_RE parses."""
    of = f"; of the nearest {n_checked}" if n_checked is not None and n_checked < n else ""
    return (f"{n} {one if n == 1 else many} within {radius_m:g} m of this address{scope}{of}: "
            f"{n_sandy} inside the 2012 Sandy inundation extent and {n_dep} inside the DEP "
            "extreme stormwater scenario (2080 sea-level rise)")
