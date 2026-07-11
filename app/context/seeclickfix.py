"""SeeClickFix — 311-equivalent service requests for cities without an
open-data-portal 311 export (Albany NY runs its 311 intake on SeeClickFix).

Public API, no auth: https://seeclickfix.com/open311/v2 wraps the same data,
but the native v2 API (seeclickfix.com/api/v2/issues) supports lat/lng +
distance sorting directly. The API has no hard radius cutoff we can trust
(`max_distance` is only honoured together with `sort=distance` and is in
miles), so we over-fetch nearest-first and haversine-filter to `radius_m`
in Python — same contract as the CKAN adapter's bbox-then-refine approach.

Returns the records shape the socrata/ckan pebbles emit
(`n_records`, `n_truncated`, `radius_m`, `sample`, `top_by_request_type`)
so narration templates and UI cards work unchanged.
"""

from __future__ import annotations

from collections import Counter
from math import asin, cos, radians, sin, sqrt
from typing import Any

from riprap.core.pebbles._http import fetch_url_json

DOC_ID = "seeclickfix"
URL = "https://seeclickfix.com/api/v2/issues"

_PER_PAGE = 100  # SeeClickFix API maximum


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


def records_near(
    lat: float,
    lon: float,
    radius_m: int = 300,
    sample_cap: int = 5,
    cache_ttl_s: int = 1800,
    request_types: str | None = None,
) -> dict[str, Any] | None:
    """`request_types` is a comma-separated list of SeeClickFix
    request-type ids (server-side category filter) — city-specific;
    look them up via `issues[].request_type.id` for the target city."""
    url = f"{URL}?lat={lat}&lng={lon}&sort=distance&per_page={_PER_PAGE}&details=false"
    if request_types:
        url += f"&request_types={request_types}"
    data = fetch_url_json(url, cache_ttl_s=cache_ttl_s, timeout_s=15.0)
    issues = data.get("issues") if isinstance(data, dict) else None
    if not isinstance(issues, list):
        return None

    records = [
        i
        for i in issues
        if isinstance(i.get("lat"), (int, float))
        and isinstance(i.get("lng"), (int, float))
        and _haversine_m(lat, lon, i["lat"], i["lng"]) <= radius_m
    ]
    n = len(records)
    sample = [
        {
            "summary": r.get("summary"),
            "status": r.get("status"),
            "created_at": r.get("created_at"),
            "address": r.get("address"),
        }
        for r in records[:sample_cap]
    ]
    counter = Counter(str(r.get("summary") or "?") for r in records)
    return {
        "n_records": n,
        # nearest-first fetch: if every fetched issue was in-radius, the
        # page boundary may have cut off more in-radius issues.
        "n_truncated": len(issues) >= _PER_PAGE and n == len(issues),
        "radius_m": radius_m,
        "sample": sample,
        "top_by_request_type": [{"value": v, "count": c} for v, c in counter.most_common(5)],
    }
