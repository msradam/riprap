"""FloodNet NYC — live ultrasonic flood sensor network.

Hasura GraphQL endpoint, no auth, ~350 sensors. Used for:
  - sensors_near(lat, lon, radius_m) → list of deployments
  - flood_events_for(deployment_ids, since) → labeled flood events per sensor
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from riprap.core import http

URL = "https://api.floodnet.nyc/v1/graphql"
DOC_ID = "floodnet"
CITATION = "FloodNet NYC ultrasonic depth sensors (api.floodnet.nyc)"


@dataclass
class Sensor:
    deployment_id: str
    name: str
    street: str
    borough: str
    status: str
    deployed_at: str | None
    lat: float | None = None
    lon: float | None = None


@dataclass
class FloodEvent:
    deployment_id: str
    start_time: str
    end_time: str | None
    max_depth_mm: int | None
    label: str | None


def _gql(query: str, variables: dict[str, Any]) -> dict:
    r = http.post(URL, json={"query": query, "variables": variables},
                   timeout=20)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(f"FloodNet GraphQL error: {j['errors']}")
    return j["data"]


_NEAR_Q = """
query Near($lat: Float!, $lon: Float!, $r: Float!) {
  deployments_within_radius(args:{lat:$lat, lon:$lon, radius_meters:$r},
                            order_by:{date_deployed: asc}) {
    deployment_id
    name
    sensor_address_street
    sensor_address_borough
    sensor_status
    date_deployed
    location
  }
}"""


def _parse_location(loc) -> tuple[float | None, float | None]:
    """Hasura PostGIS geometry returned as a GeoJSON object."""
    if not loc or not isinstance(loc, dict):
        return None, None
    coords = loc.get("coordinates")
    if not coords or len(coords) < 2:
        return None, None
    return coords[1], coords[0]  # (lat, lon) from (lon, lat)


def sensors_near(lat: float, lon: float, radius_m: float = 1000) -> list[Sensor]:
    d = _gql(_NEAR_Q, {"lat": lat, "lon": lon, "r": radius_m})
    out = []
    for row in d["deployments_within_radius"]:
        slat, slon = _parse_location(row.get("location"))
        out.append(Sensor(
            deployment_id=row["deployment_id"],
            name=row["name"] or "",
            street=row.get("sensor_address_street") or "",
            borough=row.get("sensor_address_borough") or "",
            status=row.get("sensor_status") or "",
            deployed_at=row.get("date_deployed"),
            lat=slat,
            lon=slon,
        ))
    return out


_EVENTS_Q = """
query Events($ids: [String!], $since: timestamp!, $until: timestamp!) {
  sensor_events(where:{
      deployment_id:{_in:$ids},
      start_time:{_gte:$since, _lte:$until},
      label:{_eq:"flood"}
  }, order_by:{start_time: desc}, limit: 200) {
    deployment_id
    start_time
    end_time
    max_depth_proc_mm
    label
  }
}"""


def flood_events_for(deployment_ids: list[str],
                     since: datetime | None = None) -> list[FloodEvent]:
    if not deployment_ids:
        return []
    if since is None:
        since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365 * 3)
    # The table holds events stamped 2080 (a sensor clock fault), so the
    # window is closed at now: "the last 3 years" must not reach forward.
    d = _gql(_EVENTS_Q, {
        "ids": deployment_ids,
        "since": since.isoformat(timespec="seconds").replace("+00:00", ""),
        # (the end of the current hour, so an hour's queries share one cache key)
        "until": (datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        .isoformat(timespec="seconds").replace("+00:00", ""),
    })
    return [
        FloodEvent(
            deployment_id=row["deployment_id"],
            start_time=row["start_time"],
            end_time=row.get("end_time"),
            max_depth_mm=row.get("max_depth_proc_mm"),
            label=row.get("label"),
        )
        for row in d["sensor_events"]
    ]


def is_good(status: str) -> bool:
    """FloodNet's own status codes: "good" and its variants ("good - fs")
    mark a sensor in working order; every other code ("noisy",
    "needs_driverail", "non-ota", "dead") is a maintenance flag."""
    return (status or "").strip().lower().startswith("good")


def status_words(status: str) -> str:
    """A FloodNet status code in words, for anything a reader sees."""
    return "in good working order" if is_good(status) else "flagged by FloodNet for maintenance"


def _depth(mm: int) -> str:
    """'815 mm (32.1 in)': the record is in millimetres, the press prints inches."""
    return f"{mm} mm ({mm / 25.4:.1f} in)"


def summary_for_point(lat: float, lon: float, radius_m: float = 600) -> dict:
    """One-shot summary used by the FSM node and the cited paragraph."""
    sensors = sensors_near(lat, lon, radius_m)
    ids = [s.deployment_id for s in sensors]
    events = flood_events_for(ids)
    by_dep: dict[str, list[FloodEvent]] = {}
    for e in events:
        by_dep.setdefault(e.deployment_id, []).append(e)
    # The peak depth comes only from sensors in good working order: a
    # flagged sensor's reading (a noisy 1172 mm) is not reported as the peak.
    good = {s.deployment_id for s in sensors if is_good(s.status)}
    peak = max((e for e in events if e.max_depth_mm is not None and e.deployment_id in good),
               key=lambda e: e.max_depth_mm or 0, default=None)
    flagged = {s.deployment_id for s in sensors if not is_good(s.status)} & set(by_dep)
    flagged_peak = max((e for e in events if e.max_depth_mm is not None and e.deployment_id in flagged),
                       key=lambda e: e.max_depth_mm or 0, default=None)
    n_sensors = len(sensors)
    n_events = len(events)
    latest = max(events, key=lambda e: e.start_time, default=None)
    day_ago = (datetime.now(UTC) - timedelta(hours=24)).isoformat(timespec="seconds").replace("+00:00", "")
    open_now = [e for e in events if not e.end_time and e.start_time >= day_ago]
    # Templatable narrative for the manifest's narration.template.
    # Honest negative ("0 sensors within range") still useful — same
    # contract as the NWS / ida_hwm all-clear cards.
    if n_sensors == 0:
        narrative = (
            f"No FloodNet sensors deployed within {int(radius_m)} m of "
            f"this address."
        )
    else:
        narrative = (
            f"{n_sensors} FloodNet community sensor{'' if n_sensors == 1 else 's'} within "
            f"{int(radius_m)} m {'has' if n_sensors == 1 else 'have'} logged {n_events} "
            f"above-curb flood event{'' if n_events == 1 else 's'} in the last 3 years"
            # The newest event dates the record, and answers "is it flooding now".
            + (f", the most recent starting {latest.start_time[:16].replace('T', ' ')} UTC." if latest else ".")
        )
        if open_now:
            narrative += (f" {len(open_now)} event{'' if len(open_now) == 1 else 's'} that started in the last "
                          "24 hours had no end time when this was read.")
        if peak is not None and peak.max_depth_mm is not None:
            narrative += (
                f" Peak depth recorded by the sensors in good working order: "
                f"{_depth(peak.max_depth_mm)} on {peak.start_time[:10]}."
            )
        if flagged:
            k = len(flagged)
            # "1 sensor" (a number with its noun) so the sentence is cited like the others.
            narrative += (f" {k} sensor{'' if k == 1 else 's'} that logged events {'is' if k == 1 else 'are'} "
                          f"flagged by FloodNet for maintenance, so {'its' if k == 1 else 'their'} depths are not "
                          f"used for the peak.")
            # The flagged reading is still in FloodNet's published record, and
            # others print it (46.1 in at Hollis on 2026-05-20), so it is stated with its flag.
            if flagged_peak is not None:
                narrative += (f" The highest depth a flagged sensor recorded was {_depth(flagged_peak.max_depth_mm)} "
                              f"on {flagged_peak.start_time[:10]}.")
    return {
        "n_sensors": n_sensors,
        "sensors": [{**vars(s), "status_words": status_words(s.status)} for s in sensors],
        "n_flood_events_3y": n_events,
        "n_sensors_with_events": len(by_dep),
        "peak_event": vars(peak) if peak else None,
        "flagged_peak_event": vars(flagged_peak) if flagged_peak else None,
        "latest_event_start": latest.start_time if latest else None,
        "n_events_open_24h": len(open_now),
        "narrative": narrative,
    }
