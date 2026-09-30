"""NWS API — active alerts at a point.

api.weather.gov/alerts/active?point={lat},{lon}, no auth, JSON.
NWS requires a User-Agent; the shared client in riprap.core.http sends one.

We surface only flood-relevant categories so the doc the reconciler
sees is short and on-topic.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from riprap.core import http

DOC_ID = "nws_alerts"
CITATION = "NWS public alert API (api.weather.gov/alerts)"

_FLOOD_EVENT_KEYWORDS = (
    "flood", "flash flood", "coastal flood", "high surf", "storm surge",
    "hurricane", "tropical storm", "tornado warning",  # high-impact context
    "rip current",
)


def _is_flood_relevant(event_name: str) -> bool:
    e = (event_name or "").lower()
    return any(k in e for k in _FLOOD_EVENT_KEYWORDS)


def alerts_at(lat: float, lon: float) -> list[dict[str, Any]]:
    r = http.get(
        "https://api.weather.gov/alerts/active",
        params={"point": f"{lat:.4f},{lon:.4f}"},
        headers={"Accept": "application/geo+json"},
        timeout=8.0,
    )
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties", {}) or {}
        event = p.get("event") or ""
        if not _is_flood_relevant(event):
            continue
        out.append({
            "id": p.get("id"),
            "event": event,
            "severity": p.get("severity"),
            "urgency": p.get("urgency"),
            "certainty": p.get("certainty"),
            "headline": p.get("headline"),
            "sent": p.get("sent"),
            "effective": p.get("effective"),
            "expires": p.get("expires"),
            "sender_name": p.get("senderName"),
            "areaDesc": p.get("areaDesc"),
        })
    return out


def summary_for_point(lat: float, lon: float) -> dict:
    try:
        active = alerts_at(lat, lon)
    except Exception as e:
        return {"n_active": 0, "alerts": [], "narrative": None, "error": str(e)}
    n = len(active)
    # A live source says when it looked, so a reader knows how old "active" is.
    checked = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    if n == 0:
        narrative = f"No active NWS flood, coastal or wind alerts at this point, checked {checked}."
    elif n == 1:
        narrative = (
            f"1 active NWS alert at this point, checked {checked}: "
            f"{active[0].get('event', 'unnamed event')} "
            f"({active[0].get('severity', '?')})."
        )
    else:
        narrative = (
            f"{n} active NWS alerts at this point, checked {checked}: "
            + ", ".join(
                f"{a.get('event', 'unnamed')} ({a.get('severity', '?')})"
                for a in active[:3]
            )
            + ("…" if n > 3 else ".")
        )
    return {
        "n_active": n,
        "alerts": active,
        "narrative": narrative,
        "checked_at": checked,
        "error": None,
    }
