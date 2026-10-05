"""FloodNet (New York University and The City University of New York):
ultrasonic street flood sensors, read live.

Hasura GraphQL endpoint (early-access beta), no auth, about 450 deployments.
  - sensors_near(lat, lon, radius_m): list of deployments
  - flood_events_for(deployment_ids, since): events labelled flood per sensor

The data is CC BY-NC-SA 4.0 under FloodNet's Data Access License Agreement,
which forbids reposting it in whole or in part: nothing read here is written
to the repository, and every sentence built from it carries the licence in
its citation (the manifest's provenance block). The value a summary returns
holds sentences, counts, each highest depth with its date and the licence
fields. The per-sensor rows the answer rules need are under the private key
`_rows`, which no output path serves (riprap.core.pebbles.bridge.public_value).
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
    distance_m: float | None = None  # from the queried point; None for an area


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
    deploy_type
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
    for s in map(_sensor, d["deployments_within_radius"]):
        if s is None:
            continue
        if s.lat is not None and s.lon is not None:
            s.distance_m = _haversine_m(lat, lon, s.lat, s.lon)
            if s.distance_m > radius_m:
                continue
        out.append(s)
    return out


def _sensor(row: dict) -> Sensor | None:
    """A FloodNet street sensor from a deployments row. None for a row whose
    deploy_type is "tidal": those ten rows (ids noaa-tidal-..., usgs-tidal-...,
    such as "The Battery (8518750)") are NOAA and USGS tide gauges that
    FloodNet's table lists beside its own sensors. Counted as sensors they
    once made "1 FloodNet sensor ... 0 flood events" out of a USGS gauge."""
    if (row.get("deploy_type") or "").strip().lower() == "tidal":
        return None
    lat, lon = _parse_location(row.get("location"))
    return Sensor(row["deployment_id"], row["name"] or "", row.get("sensor_address_street") or "",
                  row.get("sensor_address_borough") or "", row.get("sensor_status") or "",
                  row.get("date_deployed"), lat, lon, row.get("date_down"))


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


def _period(sensors: list[Sensor], since: datetime) -> tuple[str, str, str]:
    """(the period the sensors could have recorded in, its first day, a
    sentence on sensors listed as down or ""). The events are read for the
    last 3 years, but a sensor installed inside that window recorded for
    less: the sentence says so. The down sentence stands alone: joined to
    the count it read as if the latest event began the outage."""
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
    down_sentence = ""
    if down:
        who = "It is" if one else f"{len(down)} of them {'is' if len(down) == 1 else 'are'}"
        down_sentence = f" {who} listed as down in FloodNet's API since {down[-1]}."
    return phrase, start, down_sentence


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
    deploy_type
    location
  }
}"""


def sensors_in(polygon) -> list[Sensor]:
    """Sensors inside a WGS84 polygon (a neighbourhood or a district)."""
    from shapely.geometry import Point

    return [s for s in map(_sensor, _gql(_ALL_Q, {})["deployments"])
            if s is not None and s.lat is not None and s.lon is not None and polygon.contains(Point(s.lon, s.lat))]


def _event(e: FloodEvent | None) -> dict | None:
    """What of an event leaves this module: its depth and its UTC day."""
    return {"max_depth_mm": e.max_depth_mm, "date": e.start_time[:10]} if e else None


def _local_date(start_time: str) -> str:
    """The New York calendar day of an event's start. The API's times are
    UTC: an event that began at 9:59 pm on 11 June in New York is stamped
    12 June, and a resident asks about the 11th."""
    from zoneinfo import ZoneInfo

    return (datetime.fromisoformat(start_time[:19]).replace(tzinfo=UTC)
            .astimezone(ZoneInfo("America/New_York")).date().isoformat())


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
    not_good = [s for s in sensors if not is_good(s.status)]
    other = {s.deployment_id for s in not_good} & set(by_dep)

    def highest(deployments) -> FloodEvent | None:
        return max((e for e in events if e.max_depth_mm is not None and e.deployment_id in deployments),
                   key=lambda e: e.max_depth_mm or 0, default=None)

    # The highest depth in the record is stated, whatever its sensor's status
    # today (the press printed 46 in at Hollis on 2026-05-20, from a sensor now
    # listed as "noisy"; the event is verified and in the city's Open Data table).
    top, peak, other_peak = highest(set(status)), highest(good), highest(other)
    n_sensors = len(sensors)
    n_events = len(events)
    # Two sensors a block apart log one storm as two events: the days are counted too.
    days = sorted({e.start_time[:10] for e in events})
    by_year: dict[str, int] = {}
    for e in sorted(events, key=lambda e: e.start_time):
        by_year[e.start_time[:4]] = by_year.get(e.start_time[:4], 0) + 1
    latest = max(events, key=lambda e: e.start_time, default=None)
    now = datetime.now(UTC)
    day_ago = (now - timedelta(hours=24)).isoformat(timespec="seconds").replace("+00:00", "")
    # "Is it flooding now" reads every event labelled flood: today's are not yet reviewed.
    open_now = [e for e in listed if not e.end_time and e.start_time >= day_ago]
    period, period_start, down_sentence = _period(sensors, _window_start())
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
            f"FloodNet's definition) "
            + (f"on {len(days)} {'day' if len(days) == 1 else 'separate days'} " if n_events > 1 else "")
            + period
            # The newest event dates the record, and answers "is it flooding now".
            # Every date in these sentences is the UTC day of an event's start: said once, here.
            + (f", the most recent starting {latest.start_time[:16].replace('T', ' ')} UTC (every date here is a UTC day)."
               if latest else ".")
        )
        narrative += down_sentence
        if n_events > 1:
            # A question about one year reads its count here, not the period's total.
            parts = [f"{n} in {y}" for y, n in by_year.items()]
            narrative += f" By UTC calendar year: {', '.join(parts[:-1])}{' and ' if len(parts) > 1 else ''}{parts[-1]}."
        if unreviewed:
            k = len(unreviewed)
            narrative += (f" FloodNet's API lists {k} more event{'' if k == 1 else 's'} labelled flood here that "
                          f"{'is' if k == 1 else 'are'} still to be verified by a person; Riprap counts verified events only.")
        if not open_now and all(is_good(s.status) for s in sensors) and all(e.end_time for e in listed):
            # What "is it flooding right now" asks. Said only when every sensor is listed as good
            # and no event, however old, is still open in the record. Its own sentence:
            # the lead rules read the first sentence as the finding, and a "no" there once
            # turned 8 logged events into an absence. The time makes it a cited sentence.
            # Only events the API labels "flood" are read, and an event under way may still
            # be labelled "short" or not at all: the sentence says what was read, no more.
            # ponytail: reading open events of any label would need a second query; add it
            # if the dashboard pointer proves not enough.
            narrative += (f" No event that FloodNet's API labels a flood was open at {'it' if n_sensors == 1 else 'them'} "
                          f"when this was read ({now.strftime('%Y-%m-%d %H:%M')} UTC); an event under way may not be "
                          "labelled yet, and FloodNet's dashboard (dataviz.floodnet.nyc) shows the current readings.")
        if open_now:
            narrative += (f" {len(open_now)} event{'' if len(open_now) == 1 else 's'} that started in the last "
                          "24 hours had no end time when this was read.")
        if top is not None:
            # Every counted event is one the API marks as verified by a person: said beside the
            # depth, so a status such as "noisy" is not read as doubt about a published reading.
            narrative += (f" The highest depth in FloodNet's record for {'this sensor' if n_sensors == 1 else 'these sensors'} "
                          f"in that period is {_depth(top.max_depth_mm)} on {top.start_time[:10]}, in an event the API marks "
                          f"as verified by a person, at a sensor {status_words(status[top.deployment_id])} "
                          f"({now.strftime('%Y-%m-%d')})")
            narrative += "." if top.deployment_id in good else (
                "; that is the sensor's status now, which the API does not give for the day of the event.")
        if not_good and (n_sensors > 1 or top is None):
            # The statuses are quoted, with or without events: "0 flood events" from two sensors
            # listed as "low_charge" and "non-ota" is not the same finding as from two listed as good.
            # How many of the events are theirs is said: "14 events" once hid that 11 came from one such sensor.
            k = len(not_good)
            quoted = ", ".join(f'"{x}"' if x else "no status" for x in sorted({s.status.strip() for s in not_good}))
            narrative += (f" {k} of the {n_sensors} sensor{'' if n_sensors == 1 else 's'} {'is' if k == 1 else 'are'} listed "
                          f"with a status other than \"good\" in FloodNet's API when this was read ({quoted})")
            if n_events:
                narrative += (f" and recorded {sum(len(by_dep[d]) for d in other)} of the "
                              f"{n_events} event{'' if n_events == 1 else 's'}.")
            else:
                narrative += "; FloodNet notes that a sensor that is offline or awaiting repair may miss a flood."
    return {
        "n_sensors": n_sensors,
        "n_flood_events_3y": n_events,
        "n_flood_events_good_3y": sum(1 for e in events if e.deployment_id in good),
        "n_event_days": len(days),
        "by_year": by_year,
        "n_events_unreviewed": len(unreviewed),
        # The first day the count covers: the window's start, or the earliest
        # install date when every sensor is younger than the window.
        "period_start": period_start,
        "n_sensors_with_events": len(by_dep),
        "n_sensors_not_good": len(not_good),
        # Each a depth and its UTC day, never the event row.
        "highest_event": _event(top),
        "peak_event": _event(peak),  # the highest among sensors listed as good
        "other_status_peak_event": _event(other_peak),  # the highest among the others
        "latest_event_start": latest.start_time[:16] if latest else None,
        "n_events_open_24h": len(open_now),
        "status_read_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
        "narrative": narrative,
        # Private: for the answer rules only (the block test, a question about one day). One
        # row per sensor with verified events, nearest first; no id, name, street or coordinate.
        # Each event carries its New York date beside its UTC one: a named day is matched on it.
        # Every output path drops it (riprap.core.pebbles.bridge.public_value).
        "_rows": sorted(
            ({"distance_m": None if s.distance_m is None else round(s.distance_m, 1), "status": s.status,
              "events": [{**_event(e), "local_date": _local_date(e.start_time)}
                         for e in sorted(by_dep[s.deployment_id], key=lambda e: e.start_time)]}
             for s in sensors if s.deployment_id in by_dep),
            key=lambda r: (r["distance_m"] is None, r["distance_m"] or 0)),
    }


def summary_for_point(lat: float, lon: float, radius_m: float = 600) -> dict:
    return _summary(sensors_near(lat, lon, radius_m), f"within {int(radius_m)} m",
                    f"No FloodNet sensors deployed within {int(radius_m)} m of this address.")


def summary_for_polygon(polygon) -> dict:
    """The sensors inside a neighbourhood or a district. (It once named the
    streets with the most events; a street beside a count is a per-sensor
    record, which FloodNet's licence does not let Riprap repost.)"""
    return _summary(sensors_in(polygon), "inside this area", "No FloodNet sensors are deployed inside this area.")
