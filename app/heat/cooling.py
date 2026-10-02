"""Places to cool off near a place: NYC Parks' spray showers and pools.

Reads data/heat/parks_cooling.json (scripts/bake_heat_records.py, from NYC
Open Data ckaz-6gaa and y5rm-wagw). The traps the sentence carries:

  * spray showers and outdoor pools run in summer only, and the tables do
    not say whether one is working today;
  * these are not the city's cooling centers. Those are libraries, older
    adult centers and other buildings that the city activates during a heat
    emergency; their list is published only then, by the city's finder,
    with no licence and no date on its records, so Riprap points to it and
    does not copy it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.heat.weather import _km

PATH = Path(__file__).resolve().parents[2] / "data" / "heat" / "parks_cooling.json"
RADIUS_M = 800  # a ten minute walk
CENTERS = ("Cooling centers are separate: the city opens them only during a heat emergency and lists them then at "
           "finder.nyc.gov/coolingcenters (or call 311).")
SEASON = "Spray showers and outdoor pools run in summer only, and the list does not say whether one is working today."


@lru_cache(maxsize=1)
def _data() -> dict | None:
    return json.loads(PATH.read_text()) if PATH.exists() else None


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _summary(sites: list[tuple[str, str, float]], where: str, d: dict) -> dict:
    """`sites` are (kind, park, metres or 0). Spray showers are counted by
    playground: the table has one row per spray feature."""
    showers = sorted({park for kind, park, _ in sites if kind == "spray shower"})
    outdoor = sorted({park for kind, park, _ in sites if kind == "outdoor pool"})
    indoor = sorted({park for kind, park, _ in sites if kind == "indoor pool"})
    dates = d["sources"]
    listed = f"(lists updated {dates['spray shower']['date_modified']} and {dates['pool']['date_modified']})"
    if not sites:
        narrative = f"NYC Parks lists no spray shower or public pool {where} {listed}. {CENTERS}"
    else:
        parts = [p for p in (showers and f"spray showers at {len(showers)} park{'' if len(showers) == 1 else 's'} or "
                                         f"playground{'' if len(showers) == 1 else 's'}",
                             outdoor and _plural(len(outdoor), "outdoor pool"),
                             indoor and _plural(len(indoor), "indoor pool")) if p]
        narrative = f"NYC Parks lists {', '.join(parts[:-1]) + ' and ' + parts[-1] if len(parts) > 1 else parts[0]} {where} {listed}"
        # The nearest of each park or playground, by name, so the list can be used.
        best: dict[str, tuple[str, str, float]] = {}
        for s in sorted((s for s in sites if s[2]), key=lambda s: s[2]):
            best.setdefault(f"{s[0]}|{s[1]}", s)
        near = list(best.values())[:6]
        if near:
            narrative += ("; the six nearest: " if len(best) > 6 else "; nearest first: ") + ", ".join(f"{park} ({kind}, {m:.0f} m)" for kind, park, m in near)
        elif outdoor or indoor:
            pools = [*outdoor, *indoor]
            narrative += f"; {'among the pools are' if len(pools) > 6 else 'the pools are'} {', '.join(pools[:6])}"
        narrative += f". {SEASON} {CENTERS}"
    return {"n_spray_shower_sites": len(showers), "n_outdoor_pools": len(outdoor), "n_indoor_pools": len(indoor),
            "n_sites": len(showers) + len(outdoor) + len(indoor), "spray_shower_sites": showers[:40],
            "pools": [*outdoor, *indoor], "narrative": narrative,
            "headline_value": f"{len(showers)} spray shower sites, {len(outdoor) + len(indoor)} pools"}


def for_point(lat: float, lon: float, radius_m: float = RADIUS_M) -> dict | None:
    d = _data()
    if d is None:
        return None
    near = [(kind, park, m) for kind, park, la, lo in d["sites"] if (m := 1000 * _km(lat, lon, la, lo)) <= radius_m]
    return {**_summary(near, f"within {radius_m:.0f} m of this address", d), "radius_m": radius_m}


def for_polygon(polygon) -> dict | None:
    from shapely import contains_xy

    d = _data()
    if d is None:
        return None
    inside = [(kind, park, 0.0) for kind, park, la, lo in d["sites"] if contains_xy(polygon, lo, la)]
    return _summary(inside, "in this area", d)
