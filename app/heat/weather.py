"""Heat from the weather record: what the stations measured, what the
National Weather Service forecasts, and what it has warned of.

  * `station_record`: days at or above 90 F this year and last, the 1991 to
    2020 average and the year's highest reading, at the nearest of the city's
    three long-record stations (NOAA Regional Climate Centers, ACIS);
  * `forecast`: the Weather Service's seven-day highs and its highest
    apparent temperature for the 2.5 km forecast cell around the place;
  * `alerts`: its active heat advisories, watches and warnings.

The traps:

  * a station is one point, kilometres from most addresses, and each reads
    differently (Central Park, under trees, counts fewer 90 F days than
    LaGuardia). The sentence names the station and the distance;
  * a forecast is the Weather Service's, for a grid cell, not a prediction
    for a building. The sentence says so, and quotes the office's advisory
    thresholds beside it so a reader can hold the two together.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from riprap.core import http

ACIS_URL = "https://data.rcc-acis.org/StnData"
# The city's three threaded long-record stations (ACIS ids), with their coordinates.
# The instruments' coordinates as ACIS and NCEI give them. (api.weather.gov rounds Central Park to whole arc
# minutes, 530 m from the instrument at Belvedere Castle.)
STATIONS = (("NYCthr", "Central Park", 40.77898, -73.96925), ("LGAthr", "LaGuardia Airport", 40.77945, -73.88027),
            ("JFKthr", "JFK Airport", 40.63915, -73.7639))
NORMAL = (1991, 2020)
NY = ZoneInfo("America/New_York")
# NWS New York (OKX) criteria, weather.gov/okx/wwa_definitions, read 2026-10-02.
CRITERIA = ("The Weather Service's New York office issues a Heat Advisory when it expects the heat index to reach "
            "95°F for two days in a row or 100°F at any time, and an Extreme Heat Warning at 105°F for two hours")


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def station_record(lat: float, lon: float, today: date | None = None) -> dict | None:
    today = today or datetime.now(NY).date()
    sid, name, slat, slon = min(STATIONS, key=lambda s: _km(lat, lon, s[2], s[3]))
    yearly = {"interval": "yly", "duration": "yly"}
    r = http.post(ACIS_URL, timeout=20.0, ttl_s=6 * 3600, json={
        "sid": sid, "sdate": f"{NORMAL[0]}-01-01", "edate": str(today), "meta": ["name", "valid_daterange"],
        "elems": [{"name": "maxt", **yearly, "reduce": {"reduce": "cnt_ge_90", "add": "mcnt"}},
                  {"name": "maxt", **yearly, "reduce": {"reduce": "max", "add": "date"}}]})
    r.raise_for_status()
    body = r.json()
    rows = {int(y): (count, peak) for y, count, peak in body.get("data") or [] if count[0] != "M"}
    if not rows or max(rows) - 1 not in rows:
        return None
    year = max(rows)  # the year of the latest reading: on 1 January the new year has none yet
    by_year = {y: int(c[0]) for y, (c, _) in rows.items()}
    max_by_year = {y: [int(p[0]), p[1]] for y, (_, p) in rows.items() if p[0] != "M"}
    normal_years = [by_year[y] for y in range(NORMAL[0], NORMAL[1] + 1) if y in by_year]
    if len(normal_years) < 30:
        return None
    normal = round(sum(normal_years) / len(normal_years))
    through = body["meta"]["valid_daterange"][0][1]
    peak_f, peak_day = rows[year][1]
    # The station's all-time record, over its whole period of record (cached a day; it rarely changes).
    record = None
    try:
        rr = http.post(ACIS_URL, timeout=20.0, ttl_s=24 * 3600, json={
            "sid": sid, "sdate": "por", "edate": "por", "meta": ["valid_daterange"],
            "elems": [{"name": "maxt", "interval": "dly", "duration": "dly", "smry": {"reduce": "max", "add": "date"},
                       "smry_only": 1}]})
        rr.raise_for_status()
        (rec_f, rec_day), since = rr.json()["smry"][0], rr.json()["meta"]["valid_daterange"][0][0]
        record = {"record_f": int(rec_f), "record_date": rec_day, "record_since": since[:4]}
    except Exception:  # noqa: BLE001 - the year's figures stand without the record
        pass
    dist = round(_km(lat, lon, slat, slon), 1)
    n, last = by_year[year], by_year[year - 1]
    narrative = (f"At {name}, the nearest long-record weather station ({dist} km away), the air temperature reached 90°F "
                 f"on {n} day{'s' if n != 1 else ''} in {year} through {through} and on {last} in {year - 1}; "
                 f"a full year averaged {normal} in {NORMAL[0]} to {NORMAL[1]}. The highest reading of {year} was "
                 f"{peak_f}°F on {peak_day}"
                 + (f", and the station's record is {record['record_f']}°F, set on {record['record_date']} (records "
                    f"from {record['record_since']})" if record else "")
                 + ". These are the station's readings, not this address's.")
    return {"station": name, "station_id": sid, "distance_km": dist, "year": year, "through": through,
            "days_ge_90": n, "days_ge_90_last_year": last, "normal_days_ge_90": normal, "by_year": by_year,
            "max_by_year": max_by_year, **(record or {}),
            "max_f": int(peak_f), "max_date": peak_day, "narrative": narrative,
            "headline_value": f"{n} days at 90°F or above in {year} ({name})"}


def _grid(lat: float, lon: float) -> dict:
    r = http.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", headers={"Accept": "application/geo+json"},
                 timeout=8.0, ttl_s=24 * 3600)  # the cell for a point does not move
    r.raise_for_status()
    return r.json()["properties"]


def _f(c: float) -> int:
    return round(c * 9 / 5 + 32)


def forecast(lat: float, lon: float) -> dict | None:
    grid = _grid(lat, lon)
    r = http.get(grid["forecast"], headers={"Accept": "application/geo+json"}, timeout=8.0)
    r.raise_for_status()
    props = r.json()["properties"]
    days = [p for p in props["periods"] if p["isDaytime"] and p.get("temperatureUnit") == "F"]
    if not days:
        return None
    issued = datetime.fromisoformat(props["updateTime"]).astimezone(NY)
    highs = [{"day": p["name"], "date": p["startTime"][:10], "high_f": p["temperature"]} for p in days]
    hottest = max(highs, key=lambda h: h["high_f"])
    out = {"office": grid["gridId"], "grid": f"{grid['gridX']},{grid['gridY']}", "issued": issued.strftime("%Y-%m-%d %H:%M"),
           "highs": highs, "max_high_f": hottest["high_f"], "max_high_date": hottest["date"]}
    listing = ", ".join(f"{h['high_f']}°F {h['day'] if i else h['day'].lower()}" for i, h in enumerate(highs))
    narrative = (f"Over the next 7 days the National Weather Service expects daytime highs of {listing} in the 2.5 km grid "
                 f"cell around this place (issued {out['issued']} Eastern)")
    # The highest apparent temperature (the heat index when it is hot) in the same forecast.
    try:
        g = http.get(grid["forecastGridData"], headers={"Accept": "application/geo+json"}, timeout=8.0)
        g.raise_for_status()
        values = [(v["validTime"], v["value"]) for v in g.json()["properties"]["apparentTemperature"]["values"]
                  if v["value"] is not None]
        now = datetime.now(UTC)
        ahead = [(t, c) for t, c in values if datetime.fromisoformat(t.split("/")[0]) >= now.replace(minute=0, second=0, microsecond=0)]
        if ahead:
            t, c = max(ahead, key=lambda v: v[1])
            when = datetime.fromisoformat(t.split("/")[0]).astimezone(NY)
            out["max_apparent_f"], out["max_apparent_at"] = _f(c), when.strftime("%Y-%m-%d %H:%M")
            narrative += (f"; the highest apparent temperature it gives, which is the heat index when it is hot, is "
                          f"{out['max_apparent_f']}°F on {when:%A %B} {when.day}")
    except Exception:  # noqa: BLE001 - the highs stand without the hourly grid
        pass
    out["narrative"] = f"{narrative}. {CRITERIA}. The Weather Service wrote this for an area; it is not a prediction for a building."
    out["headline_value"] = f"high of {hottest['high_f']}°F forecast in the next week"
    return out


def observation(lat: float, lon: float) -> dict | None:
    """The latest air temperature at the nearest weather station, with the
    heat index when the station reports one (it does only when it is hot)."""
    from app.context.nws_obs import STATIONS as OBS_STATIONS

    sid, name, slat, slon = min(OBS_STATIONS, key=lambda s: _km(lat, lon, s[2], s[3]))
    r = http.get(f"https://api.weather.gov/stations/{sid}/observations/latest", headers={"Accept": "application/geo+json"},
                 timeout=8.0)
    r.raise_for_status()
    p = r.json().get("properties") or {}
    temp_c = (p.get("temperature") or {}).get("value")
    if temp_c is None or not p.get("timestamp"):
        return None
    at = datetime.fromisoformat(p["timestamp"]).astimezone(NY)
    hi_c, rh = (p.get("heatIndex") or {}).get("value"), (p.get("relativeHumidity") or {}).get("value")
    dist = round(_km(lat, lon, slat, slon), 1)
    name = name.split(",")[0]
    narrative = f"The air at {name}, the nearest weather station ({dist} km away), was {_f(temp_c)}°F at {at:%H:%M} Eastern on {at:%Y-%m-%d}"
    if hi_c is not None:
        narrative += f", with a heat index of {_f(hi_c)}°F"
    elif rh is not None:
        narrative += f", with {rh:.0f}% humidity and no heat index reported (the station reports one only when it is hot)"
    return {"station": name, "station_id": sid, "distance_km": dist, "observed": at.strftime("%Y-%m-%d %H:%M"),
            "temp_f": _f(temp_c), "heat_index_f": _f(hi_c) if hi_c is not None else None,
            "humidity_pct": round(rh) if rh is not None else None,
            "narrative": narrative + ". This is the station's reading, not this address's.",
            "headline_value": f"{_f(temp_c)}°F at {name}"}


def alerts(lat: float, lon: float) -> dict:
    from app.context import nws_alerts

    return nws_alerts.summary_for_point(lat, lon, kind="heat")


def _at_centre(fn):
    """The area version of a point source that is the same for a place and
    the district around it: read at the area's centre."""
    def area(polygon):
        c = polygon.centroid
        v = fn(c.y, c.x)
        if isinstance(v, dict) and v.get("narrative"):
            v = {**v, "narrative": (v["narrative"].replace("at this point", "for this area").replace("around this place", "at the centre of this area")
                                    .replace("not this address's", "not this area's"))}
        return v
    return area


station_record_area, forecast_area, alerts_area = _at_centre(station_record), _at_centre(forecast), _at_centre(alerts)
observation_area = _at_centre(observation)
