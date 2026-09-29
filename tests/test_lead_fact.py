"""The answer names the fact its lead rests on (`lead_fact`), so the page can
set that sentence as the key figure (design pass 2, closing round).
Offline fixtures."""

from riprap.core.burr.answer_checks import past_event_source
from riprap.core.burr.synthesis import _lead_fact

PAST = {"hazard": "flood", "time_frame": "past", "assets": []}
Q_IDA = "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
Q_SENSOR = "Have the FloodNet sensors near 80 Pioneer Street recorded flooding?"
TEXTS = {"nyc311": "82 NYC 311 flood-related complaints filed within 200 m in the last 5 years.",
         "floodnet": "2 FloodNet community sensors within 600 m have logged 14 above-curb flood events.",
         "ida_hwm": "USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address.",
         "nyc311_nta": "4273 NYC 311 flood-related complaints filed inside this area in the last 3 years."}
HOLLIS = {"nyc311": {"n": 82, "years": 5, "by_year": {"2021": 7, "2022": 6, "2025": 28}},
          "floodnet": {"n_sensors": 2, "n_flood_events_3y": 14}, "ida_hwm": {"n_within_radius": 2}}
NONE = {"nyc311": {"n": 0, "years": 5, "by_year": {}}, "floodnet": {"n_sensors": 1, "n_flood_events_3y": 0}}


def test_count_lead_built_from_the_counted_kind_is_the_key_sentence():
    # QN12: "533 street flooding complaints ..." is the lead sentence; the 4273 total supports it.
    assert _lead_fact("count", ["nyc311_nta"], True, "nyc311_nta", "How many street flooding complaints has QN12 had?",
                      None, TEXTS, {}) == {"doc_id": "nyc311_nta", "in_lead": True}


def test_count_lead_without_a_kind_rests_on_the_source_the_question_is_about():
    assert _lead_fact("count", ["ida_hwm", "nyc311"], False, "nyc311", "How many flood complaints near here?",
                      None, TEXTS, {}) == {"doc_id": "nyc311", "in_lead": False}


def test_count_lead_falls_back_to_the_first_fact_with_a_count():
    assert _lead_fact("count", ["floodnet"], False, None, "How many flood events?", None, TEXTS, {}) == \
        {"doc_id": "floodnet", "in_lead": False}


def test_rule_set_yes_rests_on_the_first_relevant_source_reporting_an_event():
    # "since Ida": complaints come first in the rule's precedence and report events after 2021.
    assert past_event_source(Q_IDA, PAST, "yes", TEXTS, HOLLIS, 2026) == "nyc311"
    assert _lead_fact("yes", ["ida_hwm", "floodnet", "nyc311"], False, None, Q_IDA, PAST, TEXTS, HOLLIS) == \
        {"doc_id": "nyc311", "in_lead": False}


def test_rule_set_no_rests_on_the_source_the_question_names():
    assert past_event_source(Q_SENSOR, PAST, "no", TEXTS, NONE, 2026) == "floodnet"


def test_other_leads_single_out_nothing():
    assert _lead_fact("partly", ["nyc311", "floodnet"], False, None, "Is this block at risk?", None, TEXTS, HOLLIS) is None
    assert _lead_fact("facts", ["nyc311"], False, None, "What do the forecasts show?", {"time_frame": "future"},
                      TEXTS, HOLLIS) is None
    # A yes the rule did not set (not a past-event question) has no key fact either.
    assert past_event_source("Is 80 Pioneer Street in a flood zone?", None, "yes", TEXTS, HOLLIS, 2026) is None
