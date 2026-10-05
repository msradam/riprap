"""The FloodNet sentence says what FloodNet's record says, in FloodNet's
terms: a count of the events a person verified, with their distinct UTC
days and the period the sensors could have recorded in; the highest depth,
said to be a verified event, with the status value the API lists for its
sensor (quoted, as of the read). Tide gauges in FloodNet's table are not
sensors. No per-sensor or per-event record leaves the server, and
FloodNet-derived output carries FloodNet's licence and credit. Offline: the
API calls are stubbed."""

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.context import floodnet
from app.context.floodnet import FloodEvent, Sensor

ROOT = Path(__file__).resolve().parent.parent
OLD = (datetime.now(UTC) - timedelta(days=365 * 5)).strftime("%Y-%m-%dT00:00:00")  # installed before the window
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")


def _stub(monkeypatch, status, other="good", installed=(OLD, OLD), extra=()):
    sensors = [Sensor("frank", "Q - 183rd St", "183rd St", "Queens", status, installed[0]),
               Sensor("other", "Q - 90th Ave", "90th Ave", "Queens", other, installed[1])]
    events = [FloodEvent("frank", "2026-05-20T23:21:49.842", None, 1172, "flood"),
              FloodEvent("other", "2025-07-14T10:00:00", None, 300, "flood"), *extra]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: events)


def test_the_highest_depth_is_stated_as_a_verified_event_with_its_sensors_status(monkeypatch):
    """The 46 in reading the press printed is in the city's table of verified
    events: the sentence says the event is verified, then quotes the status
    the API lists for its sensor today. No sentence sets it aside."""
    _stub(monkeypatch, "noisy")
    out = floodnet.summary_for_point(40.71, -73.78)
    n = out["narrative"]
    assert n.endswith(
        "The highest depth in FloodNet's record for these sensors in that period is 1172 mm (46.1 in) on 2026-05-20, "
        "in an event the API marks as verified by a person, "
        f"at a sensor listed as \"noisy\" in FloodNet's API when this was read ({TODAY}); that is the sensor's status "
        "now, which the API does not give for the day of the event. "
        "1 of the 2 sensors is listed with a status other than \"good\" in FloodNet's API when this was read "
        "(\"noisy\") and recorded 1 of the 2 events.")
    assert "Riprap, not FloodNet" not in n and "Among the sensors listed as good" not in n
    assert out["highest_event"] == {"max_depth_mm": 1172, "date": "2026-05-20"}
    assert out["peak_event"] == {"max_depth_mm": 300, "date": "2025-07-14"}
    assert out["other_status_peak_event"]["max_depth_mm"] == 1172 and "flagged_peak_event" not in out


def test_events_are_counted_with_their_days_and_years(monkeypatch):
    """Two sensors a block apart log one storm twice: the count carries its
    distinct UTC days, says once that dates are UTC, and gives each calendar
    year's count so a question about one year is not answered with the total."""
    storm = [FloodEvent("other", "2026-05-20T23:30:00", "2026-05-21T00:30:00", 815, "flood"),
             FloodEvent("frank", "2024-08-07T22:35:00", "2024-08-07T23:00:00", 40, "flood")]
    _stub(monkeypatch, "good", extra=storm)
    v = floodnet.summary_for_point(40.71, -73.78)
    assert v["narrative"].startswith(
        "2 FloodNet sensors within 600 m have recorded 4 flood events (each a series of depth readings above 10 mm at the "
        "sensor, FloodNet's definition) on 3 separate days in the last 3 years, the most recent starting 2026-05-20 23:30 UTC "
        "(every date here is a UTC day). By UTC calendar year: 1 in 2024, 1 in 2025 and 2 in 2026.")
    assert v["n_event_days"] == 3 and v["by_year"] == {"2024": 1, "2025": 1, "2026": 2}
    assert v["narrative"].count("UTC day") == 1


def test_tide_gauges_in_floodnets_table_are_not_counted_as_sensors(monkeypatch):
    """Ten rows of FloodNet's deployments table are NOAA and USGS tide
    gauges (deploy_type "tidal"). The Battery gauge once made "2 FloodNet
    sensors" near South Street, and a USGS gauge "1 FloodNet sensor ... 0
    flood events" for Great Kills."""
    from shapely.geometry import box

    rows = [{"deployment_id": "noaa-tidal-8518750", "name": "The Battery (8518750)", "deploy_type": "tidal",
             "sensor_status": "up", "date_deployed": "2022-11-13T03:38:37", "location": {"coordinates": [-73.95, 40.60]}},
            {"deployment_id": "real", "name": "BK - A St", "deploy_type": "coastal", "sensor_status": "good",
             "date_deployed": OLD, "location": {"coordinates": [-73.95, 40.60]}}]
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: {"deployments": rows, "deployments_within_radius": rows})
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: [])
    assert [s.deployment_id for s in floodnet.sensors_near(40.60, -73.95, 600)] == ["real"]
    assert floodnet.summary_for_polygon(box(-74.0, 40.55, -73.9, 40.65))["n_sensors"] == 1
    assert "deploy_type" in floodnet._NEAR_Q and "deploy_type" in floodnet._ALL_Q
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: {"deployments": rows[:1]})
    assert floodnet.summary_for_polygon(box(-74.0, 40.55, -73.9, 40.65))["narrative"] == "No FloodNet sensors are deployed inside this area."


def test_a_zero_count_quotes_the_statuses_of_sensors_not_listed_as_good(monkeypatch):
    """"0 flood events" from sensors listed as "low_charge" and "non-ota" is
    not the finding it is from sensors listed as good."""
    sensors = [Sensor("a", "BX - A", "A St", "Bronx", "low_charge", OLD), Sensor("b", "BX - B", "B St", "Bronx", "non-ota", OLD)]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: [])
    v = floodnet.summary_for_point(40.83, -73.89)
    assert v["narrative"] == (
        "2 FloodNet sensors within 600 m have recorded 0 flood events (each a series of depth readings above 10 mm at the "
        "sensor, FloodNet's definition) in the last 3 years. 2 of the 2 sensors are listed with a status other than \"good\" "
        "in FloodNet's API when this was read (\"low_charge\", \"non-ota\"); FloodNet notes that a sensor that is offline or "
        "awaiting repair may miss a flood.")
    assert v["n_sensors_not_good"] == 2


def test_the_wording_is_floodnets_own(monkeypatch):
    """No "above-curb", no "community", nothing FloodNet is said to have
    flagged: its definition of a flood event, and its status values quoted."""
    for status in ("signal", "low_charge", "removal_requested", "needs_driverail"):
        _stub(monkeypatch, status, other="non-ota")
        n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
        assert not re.search(r"above-curb|community|flagged|maintenance|working order", n), n
        assert f'listed as "{status}" in FloodNet\'s API when this was read' in n
        assert "flood events (each a series of depth readings above 10 mm at the sensor, FloodNet's definition)" in n
        assert "Riprap, not FloodNet, chooses" not in n  # a verified event counts whatever the sensor's status today
        assert "was open at" not in n  # events with no end: nothing is said about now


def test_good_variants_count_as_good(monkeypatch):
    _stub(monkeypatch, "good - fs")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("is 1172 mm (46.1 in) on 2026-05-20, in an event the API marks as verified by a person, at a sensor "
                      f"listed as \"good - fs\" in FloodNet's API when this was read ({TODAY}).")


def test_the_period_is_the_one_the_sensors_could_have_recorded_in(monkeypatch):
    """"In the last 3 years" only when a sensor is that old; else the install dates."""
    _stub(monkeypatch, "good")
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "FloodNet's definition) on 2 separate days in the last 3 years, the most recent" in v["narrative"]
    assert v["period_start"] == floodnet._window_start().date().isoformat()

    _stub(monkeypatch, "good", installed=("2025-10-17T12:00:00", "2026-06-12T16:52:00"))
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "last 3 years" not in v["narrative"]
    assert ("FloodNet's definition) on 2 separate days since 2025-10-17, the earliest install date among them (the latest is 2026-06-12), "
            "the most recent") in v["narrative"]
    assert v["period_start"] == "2025-10-17"

    _stub(monkeypatch, "good", installed=(OLD, "2026-06-12T16:52:00"))
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert "on 2 separate days in the last 3 years (1 of them installed during that period, the latest on 2026-06-12), the most recent" in n

    one = [Sensor("frank", "Q", "", "Queens", "retired", "2025-09-17T10:26:00", None, None, "2026-08-13T12:00:00")]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: one)
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    # Its own sentence, after the count: joined to it, the newest event read as the start of the outage.
    assert ("since it was installed on 2025-09-17, the most recent starting 2026-05-20 23:21 UTC (every date here is a UTC day). "
            "It is listed as down in FloodNet's API since 2026-08-13.") in n


def test_no_sensor_in_range_is_still_a_sentence(monkeypatch):
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: [])
    v = floodnet.summary_for_point(40.71, -73.78)
    assert v["narrative"] == "No FloodNet sensors deployed within 600 m of this address." and v["license"] == "CC BY-NC-SA 4.0"


def test_only_events_a_person_verified_are_counted(monkeypatch):
    """The API marks review state in annotated_by; "for-review" and
    unannotated events are named, not counted, and give no depth."""
    _stub(monkeypatch, "good", extra=(FloodEvent("other", "2026-09-01T00:00:00", "2026-09-01T01:00:00", 2000, "flood", "for-review"),
                                      FloodEvent("other", "2026-09-02T00:00:00", "2026-09-02T01:00:00", 40, "flood", None)))
    v = floodnet.summary_for_point(40.71, -73.78)
    assert (v["n_flood_events_3y"], v["n_events_unreviewed"], v["highest_event"]["max_depth_mm"]) == (2, 2, 1172)
    assert v["narrative"].startswith("2 FloodNet sensors within 600 m have recorded 2 flood events (")
    assert ("FloodNet's API lists 2 more events labelled flood here that are still to be verified by a person; "
            "Riprap counts verified events only.") in v["narrative"]
    assert "annotated_by" in floodnet._EVENTS_Q and "date_down" in floodnet._NEAR_Q and "date_down" in floodnet._ALL_Q


def test_the_first_sentence_reads_as_a_finding():
    """The lead rules read the first sentence: the definition in it must not turn events into an absence."""
    from riprap.core.burr.answer_checks import reports_result

    assert reports_result("2 FloodNet sensors within 600 m have recorded 14 flood events (each a series of depth readings "
                          "above 10 mm at the sensor, FloodNet's definition) since they were installed on 2023-10-26, "
                          "the most recent starting 2026-08-20 22:57 UTC. Riprap, not FloodNet, chooses.")


def test_every_floodnet_sentence_is_cited(monkeypatch):
    from riprap.core.burr.evidence import cite
    from riprap.core.compliance.predicates import _sentences

    _stub(monkeypatch, "noisy")
    cited = _sentences(cite(floodnet.summary_for_point(40.71, -73.78)["narrative"], "floodnet"))
    assert len(cited) == 4 and all(s.endswith("[floodnet].") for s in cited), cited


def test_floodnet_output_carries_its_licence_and_credit(monkeypatch):
    """The value, the citation record (which the JSON API, the MCP tools and
    the page's source list all read) and the manifests say the same."""
    from riprap.core.pebbles import load_registry
    from riprap.core.pebbles.deployments import deployment_root
    from riprap.core.pebbles.vintage import citation, license_notices

    _stub(monkeypatch, "good")
    v = floodnet.summary_for_point(40.71, -73.78)
    assert (v["license"], v["attribution"]) == ("CC BY-NC-SA 4.0", "FloodNet (New York University and The City University of New York)")
    registry = load_registry(deployment_root("nyc"))
    for pebble_id in ("floodnet", "floodnet_nta"):
        c = citation(registry.get(pebble_id).manifest)
        assert c["license"] == v["license"] and c["license_url"] == v["license_url"] == "https://creativecommons.org/licenses/by-nc-sa/4.0/"
        assert c["attribution"] == c["source"] == v["attribution"]
        assert "https://doi.org/10.1029/2023WR036806" in c["references"][0] and "e2023WR036806" in c["references"][0]
        assert "https://doi.org/10.1016/j.watres.2022.118648" in c["references"][1]
        assert "CC BY-NC-SA 4.0" in c["license_notice"] and "not covered by Riprap's Apache-2.0" in c["license_notice"]
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\dZ", c["retrieved_at"])  # the time stamp the licence asks for
        # The page's source list shows `source` and `title`: the licence and both papers are in them.
        assert all(t in c["title"] for t in ("CC BY-NC-SA 4.0", "10.1029/2023WR036806", "10.1016/j.watres.2022.118648", "10 mm"))
        assert not re.search(r"community|Brooklyn College|data-downloads", json.dumps(c))
        assert license_notices({"floodnet": c, "nyc311": {"license": "x"}})[0]["notice"] == c["license_notice"]
    notice = (ROOT / "NOTICE").read_text()
    assert "FloodNet-derived content" in notice and "CC BY-NC-SA 4.0" in notice and "10.1029/2023WR036806" in notice


RECORD_RE = re.compile(r"deployment_id|start_time|end_time|sensor_address|\"sensors\"|\"street\"|_rows|Q - 183rd St|Q - 90th Ave|frank")


def test_no_output_path_serves_a_floodnet_sensor_or_event_record(monkeypatch):
    """FloodNet's licence forbids reposting its data in part. The rows the
    answer rules need stay under the private key `_rows`; the JSON API, the
    stream, the district route, a comparison and the MCP tools serve
    sentences, counts and a depth with its date. There is no sensor map route."""
    from fastapi.testclient import TestClient

    from riprap.core.burr import app as burr_app
    from riprap.core.pebbles.bridge import public_value
    from riprap.mcp import server as mcp_server
    from web.main import app

    _stub(monkeypatch, "noisy")
    for s in floodnet.sensors_near():
        s.lat, s.lon, s.distance_m = 40.71, -73.78, 120.0
    v = floodnet.summary_for_point(40.71, -73.78)
    assert v["_rows"] == [{"distance_m": 120.0, "status": "noisy", "events": [{"max_depth_mm": 1172, "date": "2026-05-20"}]},
                          {"distance_m": 120.0, "status": "good", "events": [{"max_depth_mm": 300, "date": "2025-07-14"}]}]
    public = public_value(v)
    assert "_rows" not in public and not RECORD_RE.search(json.dumps(public)), json.dumps(public)
    assert {"license", "license_url", "attribution", "narrative", "n_sensors", "highest_event"} <= set(public)

    # Every result is built by _final from a run's state: a state that holds the private rows.
    state = {"query": "q", "intent": "single_address", "lat": 40.71, "lon": -73.78, "deployment": "nyc",
             "floodnet": v, "floodnet_nta": v, "paragraph": "", "trace": []}
    final = burr_app._final(state)
    assert final["floodnet"] == public and not RECORD_RE.search(json.dumps(final, default=str))
    monkeypatch.setattr(burr_app, "run", lambda *a, **k: dict(final))
    monkeypatch.setattr(burr_app, "district_summary", lambda *a, **k: dict(final))
    monkeypatch.setattr(burr_app, "plan_for", lambda q, **k: {"intent": "single_address"})
    monkeypatch.setattr(burr_app, "iter_steps", lambda q, plan=None: iter([{"kind": "final", **final}]))
    client = TestClient(app)
    served = [client.get("/api/agent", params={"q": "90-01 183rd Street, Queens"}).text,
              client.get("/api/agent/stream", params={"q": "90-01 183rd Street, Queens"}).text,
              client.get("/api/district/QN12").text,
              client.post("/api/agent/batch", json={"addresses": ["90-01 183rd Street, Queens"]}).text,
              json.dumps(mcp_server.get_evidence("90-01 183rd Street, Queens"), default=str),
              json.dumps(mcp_server.get_district_summary("QN12"), default=str),
              json.dumps(mcp_server.get_briefing("90-01 183rd Street, Queens"), default=str)]
    assert all("1172" in text for text in served[:-1])  # (get_briefing serves the paragraph, not the values)
    for text in served:
        assert not RECORD_RE.search(text), RECORD_RE.search(text)
    assert client.get("/api/floodnet_near", params={"lat": 40.71, "lon": -73.78}).status_code == 404


def test_no_tracked_data_file_holds_floodnet_event_rows():
    """FloodNet's licence agreement forbids reposting its data: no file
    under data/ in git holds a per-event or per-sensor row (an event's
    depth or times beside a sensor), and the path that once did is ignored."""
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "data"], capture_output=True, text=True, check=True).stdout.split()
    rows = re.compile(r"event_max_depth_mm|max_depth_proc_mm|max_depth_mm|event_start|deployment_id|\"sensor\":")
    held = [f for f in tracked if f.endswith((".json", ".geojson", ".csv", ".txt", ".yaml"))
            and (ROOT / f).is_file() and (ROOT / f).stat().st_size < 50_000_000
            and rows.search((ROOT / f).read_text(errors="ignore"))]
    assert not held, held
    assert "data/experimental/water_coastal_floodnet.json" not in tracked
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "data/experimental/water_coastal_floodnet.json"])
    assert ignored.returncode == 0


def test_a_baked_gallery_snapshot_holds_no_floodnet_sensor_or_event_record():
    """A baked snapshot is a repost. The gallery build strips FloodNet's
    per-sensor and per-event records and marks each file it writes; every
    marked snapshot is checked. A snapshot baked before the strip step has
    no mark and is skipped until it is rebuilt (scripts/build_gallery.py)."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_gallery import FLOODNET_STRIPPED, strip_floodnet

    event = {"deployment_id": "frank", "start_time": "2026-05-20T19:02:11", "end_time": "2026-05-20T20:00:00",
             "max_depth_mm": 1172, "label": "flood", "annotated_by": "human"}
    value = {"n_sensors": 1, "n_flood_events_3y": 6, "period_start": "2023-10-06", "narrative": "1 FloodNet sensor ...",
             "license": "CC BY-NC-SA 4.0", "highest_event": dict(event), "peak_event": None, "other_status_peak_event": dict(event), "_rows": [{"distance_m": 1.0}],
             "sensors": [{"deployment_id": "frank", "name": "QN - 183 St", "street": "183rd Street", "status": "noisy",
                          "deployed_at": "2022-01-01", "lat": 40.71, "lon": -73.77, "n_events": 6}]}
    final = {"floodnet": json.loads(json.dumps(value)), "citations": {"floodnet": {"license": "CC BY-NC-SA 4.0"}},
             "targets": [{"state": {"floodnet_nta": json.loads(json.dumps(value))}}]}
    for v in (strip_floodnet(final)["floodnet"], final["targets"][0]["state"]["floodnet_nta"]):
        assert v == {"n_sensors": 1, "n_flood_events_3y": 6, "period_start": "2023-10-06", "narrative": value["narrative"],
                     "license": "CC BY-NC-SA 4.0", "highest_event": {"max_depth_mm": 1172, "date": "2026-05-20"},
                     "peak_event": None, "other_status_peak_event": {"max_depth_mm": 1172, "date": "2026-05-20"}}
    assert final["citations"] == {"floodnet": {"license": "CC BY-NC-SA 4.0"}}

    def records(node) -> bool:
        """A sensor list or an event row left in a FloodNet value, at any depth."""
        if isinstance(node, list):
            return any(records(x) for x in node)
        if not isinstance(node, dict):
            return False
        return any(("sensors" in v or bool(re.search(r'"(deployment_id|start_time|lat|lon)"', json.dumps(v))))
                   if k in ("floodnet", "floodnet_nta") and isinstance(v, dict) else records(v) for k, v in node.items())

    assert records({"floodnet": value}) and not records(final)
    gallery = ROOT / "web" / "sveltekit" / "src" / "lib" / "gallery"
    baked = [(f, json.loads(f.read_text())) for f in sorted(gallery.glob("*.json")) if f.name != "index.json"]
    held = [f.name for f, d in baked if d.get(FLOODNET_STRIPPED) and records(d.get("final"))]
    assert not held, held


def test_events_are_asked_for_up_to_now(monkeypatch):
    """FloodNet's table holds events stamped 2080; the window closes at now."""
    seen = {}
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: seen.update(v) or {"sensor_events": []})
    floodnet.flood_events_for(["frank"])
    assert "_lte:$until" in floodnet._EVENTS_Q and seen["until"][:4] <= str(datetime.now(UTC).year + 1) and seen["since"] < seen["until"]
