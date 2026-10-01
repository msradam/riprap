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
    """Sensors within radius_m, by the same great-circle distance the Ida
    marks use. FloodNet's own radius function measures a little differently:
    a sensor 599 m away by this measure (with nine flood events) was left
    out of a 600 m search. So the service is asked for a wider ring and the
    distance is decided here."""
    from app.flood_layers.ida_hwm import _haversine_m

    d = _gql(_NEAR_Q, {"lat": lat, "lon": lon, "r": radius_m + 50})
    out = []
    for row in d["deployments_within_radius"]:
        slat, slon = _parse_location(row.get("location"))
        if slat is not None and slon is not None and _haversine_m(lat, lon, slat, slon) > radius_m:
            continue
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


# The limit is far above any place's count (City Island's sensors logged
# 436 events in three years, and a limit of 200 once reported 200).
EVENT_LIMIT = 5000
_EVENTS_Q = """
query Events($ids: [String!], $since: timestamp!, $until: timestamp!) {
  sensor_events(where:{
      deployment_id:{_in:$ids},
      start_time:{_gte:$since, _lte:$until},
      label:{_eq:"flood"}
  }, order_by:{start_time: desc}, limit: 5000) {
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


_ALL_Q = """
query All {
  deployments(limit: 5000) {
    deployment_id
    name
    sensor_address_street
    sensor_address_borough
    sensor_status
    date_deployed
    location
  }
}"""


def sensors_in(polygon) -> list[Sensor]:
    """Sensors inside a WGS84 polygon (a neighbourhood or a district)."""
    from shapely.geometry import Point

    out = []
    for row in _gql(_ALL_Q, {})["deployments"]:
        lat, lon = _parse_location(row.get("location"))
        if lat is not None and lon is not None and polygon.contains(Point(lon, lat)):
            out.append(Sensor(row["deployment_id"], row["name"] or "", row.get("sensor_address_street") or "",
                              row.get("sensor_address_borough") or "", row.get("sensor_status") or "",
                              row.get("date_deployed"), lat, lon))
    return out


def _summary(sensors: list[Sensor], where: str, none: str) -> dict:
    """The value and the sentence for a set of sensors. `where` places them
    ("within 600 m", "inside this area"); `none` is the sentence when
    there are none."""
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
    # An honest negative ("no sensors in range") is still useful: the same
    # contract as the NWS and Ida mark all-clear sentences.
    if n_sensors == 0:
        narrative = none
    else:
        narrative = (
            f"{n_sensors} FloodNet community sensor{'' if n_sensors == 1 else 's'} {where} "
            f"{'has' if n_sensors == 1 else 'have'} logged "
            f"{'at least ' if n_events >= EVENT_LIMIT else ''}{n_events} "
            f"above-curb flood event{'' if n_events == 1 else 's'} in the last 3 years"
            # The newest event dates the record, and answers "is it flooding now".
            + (f", the most recent starting {latest.start_time[:16].replace('T', ' ')} UTC." if latest else ".")
        )
        if open_now:
            narrative += (f" {len(open_now)} event{'' if len(open_now) == 1 else 's'} that started in the last "
                          "24 hours had no end time when this was read.")
        elif all(is_good(s.status) for s in sensors) and all(e.end_time for e in events):
            # What "is it flooding right now" asks. Said only when every sensor is in working
            # order and no event, however old, is still open in the record.
            narrative += (f" FloodNet's record showed no flood event under way at {'it' if n_sensors == 1 else 'them'} "
                          "when this was read.")
        if peak is not None and peak.max_depth_mm is not None:
            narrative += (
                f" Peak depth recorded by the sensors in good working order: "
                f"{_depth(peak.max_depth_mm)} on {peak.start_time[:10]}."
            )
        if flagged:
            k = len(flagged)
            # "1 sensor" (a number with its noun) so the sentence is cited like the others.
            # How many of the events are theirs is said: "14 events" once hid that 11 came from a flagged sensor.
            n_theirs = sum(len(by_dep[d]) for d in flagged)
            narrative += (f" {k} sensor{'' if k == 1 else 's'} that logged {n_theirs} of these events "
                          f"{'is' if k == 1 else 'are'} flagged by FloodNet for maintenance, so "
                          f"{'its' if k == 1 else 'their'} depths are not used for the peak.")
            # The flagged reading is still in FloodNet's published record, and
            # others print it (46.1 in at Hollis on 2026-05-20), so it is stated with its flag.
            if flagged_peak is not None:
                narrative += (f" The highest depth a flagged sensor recorded was {_depth(flagged_peak.max_depth_mm)} "
                              f"on {flagged_peak.start_time[:10]}.")
    return {
        "n_sensors": n_sensors,
        "sensors": [{**vars(s), "status_words": status_words(s.status), "n_events": len(by_dep.get(s.deployment_id, ()))}
                    for s in sensors],
        "n_flood_events_3y": n_events,
        "n_flood_events_good_3y": sum(1 for e in events if e.deployment_id in good),
        "n_sensors_with_events": len(by_dep),
        "peak_event": vars(peak) if peak else None,
        "flagged_peak_event": vars(flagged_peak) if flagged_peak else None,
        "latest_event_start": latest.start_time if latest else None,
        "n_events_open_24h": len(open_now),
        "narrative": narrative,
    }


def summary_for_point(lat: float, lon: float, radius_m: float = 600) -> dict:
    return _summary(sensors_near(lat, lon, radius_m), f"within {int(radius_m)} m",
                    f"No FloodNet sensors deployed within {int(radius_m)} m of this address.")


def summary_for_polygon(polygon) -> dict:
    """The sensors inside a neighbourhood or a district, with the streets
    that logged the most events."""
    out = _summary(sensors_in(polygon), "inside this area", "No FloodNet sensors are deployed inside this area.")
    busiest = sorted((s for s in out["sensors"] if s["n_events"]), key=lambda s: -s["n_events"])[:3]
    if busiest:
        out["narrative"] += " Most events: " + "; ".join(
            f"{s['street'] or s['name']} ({s['n_events']})" for s in busiest) + "."
    return out
