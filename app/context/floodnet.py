"""FloodNet (New York University and The City University of New York):
ultrasonic street flood sensors, read live.

Hasura GraphQL endpoint (early-access beta), no auth, about 450 deployments.
  - sensors_near(lat, lon, radius_m): list of deployments
  - flood_events_for(deployment_ids, since): events labelled flood per sensor

The data is CC BY-NC-SA 4.0 under FloodNet's Data Access License Agreement,
which forbids reposting it: nothing read here is written to the repository,
and every sentence built from it carries the licence in its citation
(the manifest's provenance block).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from riprap.core import http

URL = "https://api.floodnet.nyc/v1/graphql"
DOC_ID = "floodnet"
WINDOW_YEARS = 3
# Carried in every value built here, beside the fuller record in the citation
# (the manifests' provenance block holds the same strings; a test compares them).
LICENSE = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
ATTRIBUTION = "FloodNet (New York University and The City University of New York)"


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
    removed_at: str | None = None  # the API's date_down


@dataclass
class FloodEvent:
    deployment_id: str
    start_time: str
    end_time: str | None
    max_depth_mm: int | None
    label: str | None
    # The API's review state: "human" once a person has verified the event,
    # "for-review" or null before that. Only human-verified events are in
    # FloodNet's NYC Open Data table (aq7i-eu5q).
    annotated_by: str | None = "human"


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
    date_down
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
            removed_at=row.get("date_down"),
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
    annotated_by
  }
}"""


def _window_start() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365 * WINDOW_YEARS)


def flood_events_for(deployment_ids: list[str],
                     since: datetime | None = None) -> list[FloodEvent]:
    """Every event the API labels flood, reviewed or not: see is_reviewed."""
    if not deployment_ids:
        return []
    if since is None:
        since = _window_start()
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
            annotated_by=row.get("annotated_by"),
        )
        for row in d["sensor_events"]
    ]


def is_reviewed(event: FloodEvent) -> bool:
    """True for an event a person has verified (annotated_by "human"). On
    5 October 2026 the API labelled 4,125 events flood: 3,427 verified,
    407 "for-review", the rest unannotated; the Open Data table of verified
    events held 3,422. Riprap counts the verified ones."""
    return event.annotated_by == "human"


def is_good(status: str) -> bool:
    """A sensor whose status in the API is "good" or a variant ("good - fs").
    What any other value ("signal", "noisy", "low_charge", "retired") means
    for a reading is not published, so Riprap quotes the value and does not
    interpret it. Setting such sensors aside is Riprap's rule, not FloodNet's."""
    return (status or "").strip().lower().startswith("good")


def status_words(status: str) -> str:
    """The status value as the API lists it, quoted. It is the status when
    the API was read, not the status at the time of any past event."""
    status = (status or "").strip()
    return f'listed as "{status}" in FloodNet\'s API when this was read' if status else "with no status listed in FloodNet's API"


def _period(sensors: list[Sensor], since: datetime) -> tuple[str, str]:
    """(the period the sensors could have recorded in, its first day). The
    events are read for the last 3 years, but a sensor installed inside
    that window recorded for less: the sentence says so."""
    window = since.date().isoformat()
    dates = sorted(s.deployed_at[:10] for s in sensors if s.deployed_at)
    young = [d for d in dates if d > window]
    one = len(sensors) == 1
    if sensors and len(young) == len(sensors):  # no sensor is as old as the window
        start = dates[0]
        if one:
            phrase = f"since it was installed on {start}"
        elif start == dates[-1]:
            phrase = f"since they were installed on {start}"
        else:
            phrase = f"since {start}, the earliest install date among them (the latest is {dates[-1]})"
    else:
        start = window
        phrase = f"in the last {WINDOW_YEARS} years"
        if young:
            phrase += f" ({len(young)} of them installed during that period, the latest on {young[-1]})"
    down = sorted(s.removed_at[:10] for s in sensors if s.removed_at)
    if down:
        phrase += f"; {'it is' if one else f'{len(down)} of them ' + ('is' if len(down) == 1 else 'are')} listed as down since {down[-1]}"
    return phrase, start


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
    date_down
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
                              row.get("date_deployed"), lat, lon, row.get("date_down")))
    return out


def _summary(sensors: list[Sensor], where: str, none: str) -> dict:
    """The value and the sentence for a set of sensors. `where` places them
    ("within 600 m", "inside this area"); `none` is the sentence when
    there are none."""
    ids = [s.deployment_id for s in sensors]
    listed = flood_events_for(ids)
    # The count, the dates and the depths come from events a person verified.
    events = [e for e in listed if is_reviewed(e)]
    unreviewed = [e for e in listed if not is_reviewed(e)]
    by_dep: dict[str, list[FloodEvent]] = {}
    for e in events:
        by_dep.setdefault(e.deployment_id, []).append(e)
    status = {s.deployment_id: s.status for s in sensors}
    good = {s.deployment_id for s in sensors if is_good(s.status)}
    other = {s.deployment_id for s in sensors if not is_good(s.status)} & set(by_dep)

    def highest(deployments) -> FloodEvent | None:
        return max((e for e in events if e.max_depth_mm is not None and e.deployment_id in deployments),
                   key=lambda e: e.max_depth_mm or 0, default=None)

    # The highest depth in the record is stated first, whatever its sensor's
    # status (the press printed 46 in at Hollis on 2026-05-20, from a sensor
    # now listed as "noisy"), then the highest among sensors listed as good.
    top, peak, other_peak = highest(set(status)), highest(good), highest(other)
    n_sensors = len(sensors)
    n_events = len(events)
    latest = max(events, key=lambda e: e.start_time, default=None)
    now = datetime.now(UTC)
    day_ago = (now - timedelta(hours=24)).isoformat(timespec="seconds").replace("+00:00", "")
    # "Is it flooding now" reads every event labelled flood: today's are not yet reviewed.
    open_now = [e for e in listed if not e.end_time and e.start_time >= day_ago]
    period, period_start = _period(sensors, _window_start())
    # An honest negative ("no sensors in range") is still useful: the same
    # contract as the NWS and Ida mark all-clear sentences.
    if n_sensors == 0:
        narrative = none
    else:
        narrative = (
            f"{n_sensors} FloodNet sensor{'' if n_sensors == 1 else 's'} {where} "
            f"{'has' if n_sensors == 1 else 'have'} recorded "
            f"{'at least ' if len(listed) >= EVENT_LIMIT else ''}{n_events} "
            # FloodNet's definition of a flood event, in the sentence that counts them.
            f"flood event{'' if n_events == 1 else 's'} ({'' if n_events == 1 else 'each '}a series of depth readings above 10 mm at the sensor, "
            f"FloodNet's definition) {period}"
            # The newest event dates the record, and answers "is it flooding now".
            + (f", the most recent starting {latest.start_time[:16].replace('T', ' ')} UTC." if latest else ".")
        )
        if unreviewed:
            k = len(unreviewed)
            narrative += (f" FloodNet's API lists {k} more event{'' if k == 1 else 's'} labelled flood here that "
                          f"{'is' if k == 1 else 'are'} still to be verified by a person; Riprap counts verified events only.")
        if not open_now and all(is_good(s.status) for s in sensors) and all(e.end_time for e in listed):
            # What "is it flooding right now" asks. Said only when every sensor is listed as good
            # and no event, however old, is still open in the record. Its own sentence:
            # the lead rules read the first sentence as the finding, and a "no" there once
            # turned 8 logged events into an absence. The time makes it a cited sentence.
            narrative += (f" FloodNet's record showed no flood event under way at {'it' if n_sensors == 1 else 'them'} "
                          f"when this was read ({now.strftime('%Y-%m-%d %H:%M')} UTC).")
        if open_now:
            narrative += (f" {len(open_now)} event{'' if len(open_now) == 1 else 's'} that started in the last "
                          "24 hours had no end time when this was read.")
        if top is not None:
            narrative += (f" The highest depth in FloodNet's record for {'this sensor' if n_sensors == 1 else 'these sensors'} "
                          f"in that period is {_depth(top.max_depth_mm)} on {top.start_time[:10]}, at a sensor "
                          f"{status_words(status[top.deployment_id])} ({now.strftime('%Y-%m-%d')})")
            if top.deployment_id in good:
                narrative += "."
            else:
                narrative += "; that is the sensor's status now, which the API does not give for the day of the event."
                if peak is not None:
                    narrative += (f" Among the sensors listed as good, the highest depth is "
                                  f"{_depth(peak.max_depth_mm)} on {peak.start_time[:10]}.")
        if other:
            k = len(other)
            # "1 sensor" (a number with its noun) so the sentence is cited like the others.
            # How many of the events are theirs is said: "14 events" once hid that 11 came from one such sensor.
            n_theirs = sum(len(by_dep[d]) for d in other)
            narrative += (f" {k} sensor{'' if k == 1 else 's'} with a status other than good recorded {n_theirs} of the "
                          f"{n_events} event{'' if n_events == 1 else 's'}; Riprap, not FloodNet, chooses to rest a yes or no "
                          f"answer only on events from sensors listed as good.")
    return {
        "n_sensors": n_sensors,
        "sensors": [{**vars(s), "status_words": status_words(s.status), "n_events": len(by_dep.get(s.deployment_id, ()))}
                    for s in sensors],
        "n_flood_events_3y": n_events,
        "n_flood_events_good_3y": sum(1 for e in events if e.deployment_id in good),
        "n_events_unreviewed": len(unreviewed),
        # The first day the count covers: the window's start, or the earliest
        # install date when every sensor is younger than the window.
        "period_start": period_start,
        "n_sensors_with_events": len(by_dep),
        "highest_event": vars(top) if top else None,
        "peak_event": vars(peak) if peak else None,  # the highest among sensors listed as good
        "flagged_peak_event": vars(other_peak) if other_peak else None,  # the highest among the others
        "latest_event_start": latest.start_time if latest else None,
        "n_events_open_24h": len(open_now),
        "status_read_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
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
