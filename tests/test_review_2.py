"""Defects the second independent review found (2026-10-01), each as the
input the reviewer gave. Offline."""

import datetime

import pytest

from app.context import floodnet
from riprap.core.burr import answer_checks as ac
from riprap.core.burr import rule_answer as ra
from riprap.core.burr.intake import heuristic_plan
from riprap.core.burr.place import resolve_query

FLOODNET_QUIET = {"floodnet": "2 FloodNet sensors within 600 m have recorded 0 flood events in the "
                              "last 3 years.",
                  "nyc311": "0 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years."}
QUIET_VALUES = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 0, "n_flood_events_good_3y": 0},
                "nyc311": {"n": 0, "years": 5, "by_year": {}, "by_kind": {}}}


@pytest.mark.parametrize("question", [
    "Has it flooded at 100 Main St. since Sandy?",
    "Has it flooded on Ave. C since 2010?",
    "Has the block flooded near P.S. 90 since 2010?",
])
def test_an_abbreviation_does_not_end_the_question(question):
    # Neither source's window reaches back to the period asked, so no "No."
    lead, _ = ra.answer(question, FLOODNET_QUIET, QUIET_VALUES)
    assert lead == "cannot_answer"


def test_a_street_abbreviation_keeps_the_storm_in_the_clause():
    texts = {"sandy_inundation": "This address sits within the empirical 2012 Hurricane Sandy inundation footprint."}
    assert ra.answer("Did 80 Pioneer St. flood during Sandy?", texts, {"sandy_inundation": {"inside": True}}) == (
        "yes", ["sandy_inundation"])


IDA_FAR = {"ida_hwm": "USGS surveyed 3 Hurricane Ida high-water marks within 800 m of this address. Nearest mark: "
                      "Smith St (640 m away)."}
IDA_FAR_V = {"ida_hwm": {"n_within_radius": 3, "nearest_dist_m": 640}}


def test_marks_640_m_away_do_not_say_water_reached_the_address():
    lead, facts = ra.answer("Did any water reach 80 Pioneer Street during Ida?", IDA_FAR, IDA_FAR_V)
    assert lead == "facts" and facts == ["ida_hwm"]
    # The question about the marks themselves keeps its yes.
    assert ra.answer("Were any high-water marks surveyed near 80 Pioneer Street?", IDA_FAR, IDA_FAR_V)[0] == "yes"


def test_311_complaints_alone_do_not_say_a_street_floods():
    texts = {"nyc311": "14 NYC 311 flood-related complaints filed within 200 m in the last 5 years: 9 street flooding."}
    v = {"nyc311": {"n": 14, "years": 5, "by_kind": {"street flooding": 9}, "by_year": {"2025": 14}}}
    assert ra.answer("Does 80 Pioneer Street get any street flooding?", texts, v)[0] == "facts"
    assert ra.answer("Are there any street flooding complaints near 80 Pioneer Street?", texts, v)[0] == "yes"


@pytest.mark.parametrize("question", [
    "Are any schools near 80 Pioneer Street in the FEMA flood zone?",
    "Is the school at 80 Pioneer Street in the floodplain?",
])
def test_a_register_gives_no_yes_or_no_about_fema_zones(question):
    texts = {"doe_school_exposure": "2 flood-exposed NYC DOE schools within 1500 m: 0 inside the 2012 Sandy inundation "
                                    "extent and 0 inside the DEP extreme stormwater scenario (2080 sea-level rise)."}
    v = {"doe_school_exposure": {"n_schools": 2, "n_inside_sandy_2012": 0, "n_in_dep_extreme_2080": 0}}
    assert ra.answer(question, texts, v)[0] == "facts"


def test_a_verified_event_counts_whatever_the_sensors_status_is_today():
    """Review round 1 (A5): every counted event is one a person at FloodNet
    verified, and the status is of the sensor now, not of the event then. So
    events at a sensor listed "noisy" give a yes as events at a "good" one do
    (the highest reading in the city's own published table is such an event)."""
    texts = {"floodnet": "1 FloodNet sensor within 600 m has recorded 5 flood events in the last 3 "
                         "years. 1 of the 1 sensor is listed with a status other than \"good\"."}
    focus = {"time_frame": "past"}
    for good in (0, 5):
        v = {"floodnet": {"n_sensors": 1, "n_flood_events_3y": 5, "n_flood_events_good_3y": good}}
        assert ac.past_event_lead("Has 80 Pioneer Street flooded?", focus, ["floodnet"], texts, v)[0] == "yes"


def test_floodnet_counts_events_at_sensors_in_good_order(monkeypatch):
    sensors = [floodnet.Sensor("a", "A", "", "", "good", None, 40.7, -73.9),
               floodnet.Sensor("b", "B", "", "", "noisy", None, 40.7, -73.9)]
    events = [floodnet.FloodEvent("a", "2026-05-01T00:00:00", "2026-05-01T01:00:00", 100, "flood")] + [
        floodnet.FloodEvent("b", f"2026-05-{d:02d}T00:00:00", f"2026-05-{d:02d}T01:00:00", 900, "flood") for d in (2, 3)]
    monkeypatch.setattr(floodnet, "sensors_near", lambda *a, **k: sensors)
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: events)
    v = floodnet.summary_for_point(40.7, -73.9)
    assert (v["n_flood_events_3y"], v["n_flood_events_good_3y"]) == (3, 1)


def test_the_floodnet_event_query_is_not_cut_at_200():
    # City Island's sensors logged 436 events in three years and the app said 200.
    assert floodnet.EVENT_LIMIT >= 5000 and f"limit: {floodnet.EVENT_LIMIT}" in floodnet._EVENTS_Q


@pytest.mark.parametrize("question,share,lead", [
    ("Was QN12 inside the Sandy inundation zone?", 0.008, "partly"),
    ("Was any part of QN12 inside the Sandy inundation zone?", 0.008, "yes"),
    ("Was QN14 inside the Sandy inundation zone?", 0.97, "yes"),
    ("Was QN06 inside the Sandy inundation zone?", 0.0, "no"),
])
def test_a_small_sandy_share_is_in_part_not_yes(question, share, lead):
    texts = {"sandy_nta": f"{share * 100:.1f}% of this area lies inside the 2012 Hurricane Sandy inundation extent."}
    got, facts = ra.answer(question, texts, {"sandy_nta": {"fraction": share}})
    assert got == lead and facts == ["sandy_nta"]
    assert not [k for k, _ in ac.check_lead(got, facts, question, texts, {"sandy_nta": {"fraction": share}})]


@pytest.mark.parametrize("query,kind,text", [
    ("450 St. Nicholas Avenue, Manhattan", "address", "450 St. Nicholas Avenue, Manhattan"),
    ("Does 885 St. Johns Place flood?", "address", "885 St. Johns Place"),
    ("2302 Avenue U, Brooklyn", "address", "2302 Avenue U, Brooklyn"),
    ("Flushing Avenue, Brooklyn", "neighborhood", "Flushing Avenue"),      # the street, not Flushing in Queens
    ("Has Jamaica Avenue flooded since Ida?", "neighborhood", "Jamaica Avenue"),
    ("Is Jamaica Hospital in a flood zone?", "neighborhood", "Jamaica Hospital"),
    ("is coney island hospital in a flood zone", None, None),               # lower case: no neighbourhood guess
    ("is woodlawn chicago at risk of flooding", None, None),                # not Woodlawn in the Bronx
    ("has elmhurst illinois flooded", None, None),
    ("Is my place at Ocean Parkway going to flood?", "neighborhood", "Ocean Parkway"),  # not an intersection
    ("Does my street and the next street flood in Hollis?", "neighborhood", "Hollis"),
    ("Atlantic Avenue and Court Street, Brooklyn", "invalid", None),
    ("Flatbush Avenue and Avenue U, Brooklyn", "invalid", None),
    ("whats going on in hunts point", "neighborhood", "Hunts Point"),
])
def test_a_place_is_the_place_named(query, kind, text):
    got = resolve_query(query)
    assert (got["kind"], got["text"]) == (kind, text)


@pytest.mark.parametrize("query,target", [
    ("Has Jamaica Avenue flooded since Ida?", "Jamaica Avenue, New York, NY"),     # never the whole question
    ("Does Rockaway Boulevard flood?", "Rockaway Boulevard, New York, NY"),
    ("Is Pike Place Market in Seattle flooding right now?", "Pike Place Market, Seattle"),  # not ", New York, NY"
    ("Is Navy Pier in Chicago in a flood zone?", "Navy Pier, Chicago"),
    ("Ferry Building, San Francisco", "Ferry Building, San Francisco"),
])
def test_a_named_place_keeps_its_own_city(query, target):
    assert heuristic_plan(query)["targets"][0]["text"] == target


V311 = {"nyc311": {"n": 30, "years": 5, "by_year": {"2022": 4, "2023": 6, "2024": 9, "2025": 8, "2026": 3}, "by_kind": {}}}
T311 = {"nyc311": "30 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years."}
TODAY = datetime.date(2026, 10, 1)


def test_a_count_since_a_storm_is_not_the_windows_total():
    # The 5-year window starts a month after Ida: its total is not "since Ida".
    assert ac.count_lead("How many 311 flood complaints near here since Ida?", T311, V311, TODAY) == (None, True)


def test_a_count_since_a_year_sums_the_years_from_then():
    sentence, undetermined = ac.count_lead("How many 311 flood complaints near here since 2024?", T311, V311, TODAY)
    assert not undetermined and sentence.startswith("20 flood-related 311 complaints filed since the start of 2024")
    # A year the window does not reach back to cannot be summed.
    assert ac.count_lead("How many 311 flood complaints near here since 2019?", T311, V311, TODAY) == (None, True)


def test_an_offline_source_without_a_message_is_a_failure(monkeypatch):
    from riprap.core.pebbles import bridge
    from riprap.core.pebbles.base import PebbleResult

    class Offline:
        manifest = None

        def fetch(self, query):
            return PebbleResult(pebble_id="x", value=None, offline=True, error=None)

    monkeypatch.setattr(bridge, "get_registry", lambda deployment=None: type("R", (), {"get": lambda self, i: Offline()})())
    value, _, err = bridge.fetch_pebble("x", 40.7, -73.9)
    assert value is None and err


@pytest.mark.parametrize("text,sentences", [
    ("This address sits in FEMA flood zone X. 3 FloodNet sensors logged events.", 2),   # once joined into one
    ("The mark is on Water St. It may flood.", 2),
    ("Nearest school: P.S. 90 Horace Mann. It is outside.", 2),
    ("Intersection of 182nd St. and 90th Ave., Jamaica. Next.", 2),
    ("It covers Jamaica, St. Albans and Hollis. 2 marks.", 2),
])
def test_a_hedge_in_one_sentence_cannot_excuse_the_next(text, sentences):
    from riprap.core.compliance.predicates import _sentences

    assert len(_sentences(text)) == sentences


def test_the_same_incident_rule_is_not_quadratic():
    import time

    from app.context.nyc311 import Complaint, one_per_incident

    coded = [Complaint(str(i), "Sewer Backup (Use Comments) (SA)", f"2025-01-01T{i % 24:02d}:{i % 60:02d}:00", f"{i} A St",
                       "Closed", 40.7, -73.9) for i in range(4000)]
    plain = [Complaint(f"p{i}", "Backup", f"2025-01-01T{i % 24:02d}:{i % 60:02d}:30", f"{i} A St", "Closed", 40.7, -73.9)
             for i in range(4000)]
    t = time.time()
    kept = one_per_incident(coded + plain)
    assert len(kept) == 4000 and time.time() - t < 1.5  # every plain row has its coded twin; this took 3.4 s


def test_a_district_reads_the_sensors_inside_it(monkeypatch):
    from shapely.geometry import box

    rows = [{"deployment_id": "in", "name": "a", "sensor_address_street": "Dover Street", "sensor_address_borough": "BK",
             "sensor_status": "good", "date_deployed": None, "location": {"coordinates": [-73.95, 40.60]}},
            {"deployment_id": "out", "name": "b", "sensor_address_street": "Far Street", "sensor_address_borough": "BK",
             "sensor_status": "good", "date_deployed": None, "location": {"coordinates": [-73.80, 40.60]}}]
    monkeypatch.setattr(floodnet, "_gql", lambda q, v: {"deployments": rows})
    monkeypatch.setattr(floodnet, "flood_events_for", lambda ids: [
        floodnet.FloodEvent(i, "2026-05-01T00:00:00", "2026-05-01T01:00:00", 120, "flood") for i in ids])
    v = floodnet.summary_for_polygon(box(-74.0, 40.55, -73.9, 40.65))
    assert v["n_sensors"] == 1 and v["n_flood_events_3y"] == 1
    assert v["narrative"].startswith("1 FloodNet sensor inside this area has recorded 1 flood event")
    assert "Most events" not in v["narrative"] and "Dover Street" not in v["narrative"]  # no street beside a count
    empty = floodnet.summary_for_polygon(box(0, 0, 1, 1))
    assert empty["n_sensors"] == 0 and empty["narrative"] == "No FloodNet sensors are deployed inside this area."


@pytest.mark.parametrize("query,hazard", [
    # From the fourth unseen set: advice and another hazard, phrased as no rule expected.
    ("Thinking about renting a ground floor apt at 2636 East 14th St, Brooklyn 11235. should I take it or is the "
     "flood risk too high?", "flood"),
    ("is the smog bad around 104 W 136th St in Harlem in summer?", "air"),
])
def test_advice_and_other_hazards_are_declined_however_they_are_phrased(query, hazard):
    plan = heuristic_plan(query)
    assert plan["intent"] == "out_of_scope" and plan["focus"]["hazard"] == hazard
    # Heat was "another hazard" until the heat briefing (2026-10-02): the same unseen question is now routed to it.
    hot = heuristic_plan("which blocks around 104 W 136th St in Harlem get the hottest in summer?")
    assert hot["intent"] == "single_address" and hot["focus"]["hazard"] == "heat"
    # A question about the flood record that mentions summer is still answered.
    assert heuristic_plan("Did 80 Pioneer Street, Brooklyn flood last summer?")["intent"] == "single_address"
