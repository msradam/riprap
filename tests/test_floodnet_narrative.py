"""The FloodNet sentence says what FloodNet's record says, in FloodNet's
terms: the highest depth in the record first, with the status value the
API lists for its sensor (quoted, as of the read), then the highest among
sensors listed as good; the period the sensors could have recorded in; a
count of the events a person verified. Setting sensors aside is Riprap's
choice and the sentence says so. FloodNet-derived output carries FloodNet's
licence and credit. Offline: the API calls are stubbed."""

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


def test_the_highest_depth_is_stated_with_its_sensors_listed_status(monkeypatch):
    """The 46 in reading the press printed leads, with the status value
    quoted; the highest among sensors listed as good follows."""
    _stub(monkeypatch, "noisy")
    out = floodnet.summary_for_point(40.71, -73.78)
    n = out["narrative"]
    assert n.endswith(
        "The highest depth in FloodNet's record for these sensors in that period is 1172 mm (46.1 in) on 2026-05-20, "
        f"at a sensor listed as \"noisy\" in FloodNet's API when this was read ({TODAY}); that is the sensor's status "
        "now, which the API does not give for the day of the event. "
        "Among the sensors listed as good, the highest depth is 300 mm (11.8 in) on 2025-07-14. "
        "1 sensor with a status other than good recorded 1 of the 2 events; Riprap, not FloodNet, chooses to rest "
        "a yes or no answer only on events from sensors listed as good.")
    assert n.index("1172 mm") < n.index("300 mm")
    assert out["highest_event"]["max_depth_mm"] == 1172
    assert out["peak_event"]["max_depth_mm"] == 300
    assert out["flagged_peak_event"]["max_depth_mm"] == 1172
    assert [s["status_words"] for s in out["sensors"]] == [
        "listed as \"noisy\" in FloodNet's API when this was read", "listed as \"good\" in FloodNet's API when this was read"]


def test_the_wording_is_floodnets_own(monkeypatch):
    """No "above-curb", no "community", nothing FloodNet is said to have
    flagged: its definition of a flood event, and its status values quoted."""
    for status in ("signal", "low_charge", "removal_requested", "needs_driverail"):
        _stub(monkeypatch, status, other="non-ota")
        n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
        assert not re.search(r"above-curb|community|flagged|maintenance|working order", n), n
        assert f'listed as "{status}" in FloodNet\'s API when this was read' in n
        assert "flood events (each a series of depth readings above 10 mm at the sensor, FloodNet's definition)" in n
        assert "Riprap, not FloodNet, chooses" in n
        assert "Among the sensors listed as good" not in n  # none is
        assert "no flood event under way" not in n  # events with no end: nothing is said about now


def test_good_variants_count_as_good(monkeypatch):
    _stub(monkeypatch, "good - fs")
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert n.endswith("is 1172 mm (46.1 in) on 2026-05-20, at a sensor listed as \"good - fs\" in FloodNet's API "
                      f"when this was read ({TODAY}).")


def test_the_period_is_the_one_the_sensors_could_have_recorded_in(monkeypatch):
    """"In the last 3 years" only when a sensor is that old; else the install dates."""
    _stub(monkeypatch, "good")
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "FloodNet's definition) in the last 3 years, the most recent" in v["narrative"]
    assert v["period_start"] == floodnet._window_start().date().isoformat()

    _stub(monkeypatch, "good", installed=("2025-10-17T12:00:00", "2026-06-12T16:52:00"))
    v = floodnet.summary_for_point(40.71, -73.78)
    assert "last 3 years" not in v["narrative"]
    assert ("FloodNet's definition) since 2025-10-17, the earliest install date among them (the latest is 2026-06-12), "
            "the most recent") in v["narrative"]
    assert v["period_start"] == "2025-10-17"

    _stub(monkeypatch, "good", installed=(OLD, "2026-06-12T16:52:00"))
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert "in the last 3 years (1 of them installed during that period, the latest on 2026-06-12), the most recent" in n

    one = [Sensor("frank", "Q", "", "Queens", "retired", "2025-09-17T10:26:00", None, None, "2026-08-13T12:00:00")]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: one)
    n = floodnet.summary_for_point(40.71, -73.78)["narrative"]
    assert "since it was installed on 2025-09-17; it is listed as down since 2026-08-13, the most recent" in n


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


def test_the_map_endpoint_carries_the_licence(monkeypatch):
    from fastapi.testclient import TestClient

    from web.main import app

    _stub(monkeypatch, "good", extra=(FloodEvent("other", "2026-09-01T00:00:00", None, 2000, "flood", "for-review"),))
    out = TestClient(app).get("/api/floodnet_near", params={"lat": 40.71, "lon": -73.78}).json()
    assert out["license"] == "CC BY-NC-SA 4.0" and out["attribution"].startswith("FloodNet (New York University")
    assert "Apache-2.0" in out["license_notice"]


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


def test_events_are_asked_for_up_to_now(monkeypatch):
    """FloodNet's table holds events stamped 2080; the window closes at now."""
    seen = {}
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: seen.update(v) or {"sensor_events": []})
    floodnet.flood_events_for(["frank"])
    assert "_lte:$until" in floodnet._EVENTS_Q and seen["until"][:4] <= str(datetime.now(UTC).year + 1) and seen["since"] < seen["until"]
