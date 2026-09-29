"""Live narrations state their observation time as "YYYY-MM-DD HH:MM UTC".
Offline: the HTTP and API calls are stubbed."""

from datetime import UTC, datetime, timedelta, timezone


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_noaa_tides_asks_for_utc_and_says_so(monkeypatch):
    from app.context import noaa_tides

    seen = []

    def get(url, params, timeout):
        seen.append(params["time_zone"])
        if params["product"] == "water_level":
            return _Resp({"data": [{"t": "2026-09-29 16:24", "v": "5.407"}]})
        return _Resp({"predictions": [{"t": "2026-09-29 16:24", "v": "5.0"}]})

    monkeypatch.setattr(noaa_tides.http, "get", get)
    n = noaa_tides.summary_for_point(40.70, -74.01)["narrative"]
    assert set(seen) == {"gmt"} and n.endswith(", observed 2026-09-29 16:24 UTC.")


def test_nws_obs_converts_the_timestamp_to_utc(monkeypatch):
    from app.context import nws_obs

    props = {"timestamp": "2026-09-29T08:10:00-04:00", "temperature": {"value": 18.0},
             "precipitationLastHour": {"value": 0}}
    monkeypatch.setattr(nws_obs.http, "get", lambda *a, **k: _Resp({"properties": props}))
    n = nws_obs.summary_for_point(40.78, -73.97)["narrative"]
    assert n.endswith(", observed 2026-09-29 12:10 UTC.")


def test_usgs_gauge_time_is_converted_to_utc(monkeypatch):
    import dataretrieval.waterdata as wd
    import pandas as pd
    from shapely.geometry import Point

    from app.context import usgs_gauges

    t = datetime.now(UTC).replace(second=0, microsecond=0).astimezone(timezone(timedelta(hours=-4)))
    df = pd.DataFrame([{"monitoring_location_id": "USGS-01302050", "geometry": Point(-73.76, 40.75),
                        "parameter_code": "00065", "value": 0.35, "time": pd.Timestamp(t)}])
    monkeypatch.setattr(wd, "get_latest_continuous", lambda **k: (df, None))
    monkeypatch.setattr(wd, "get_monitoring_locations", lambda **k: (
        pd.DataFrame([{"monitoring_location_name": "ALLEY CREEK NEAR OAKLAND GARDENS NY"}]), None))
    n = usgs_gauges.summary_for_point(40.75, -73.76)["narrative"]
    assert f"observed {t.astimezone(UTC):%Y-%m-%d %H:%M} UTC." in n
