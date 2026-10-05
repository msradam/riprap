"""The answer names the fact its lead rests on (`lead_fact`), so the page can
set that sentence as the key figure (design pass 2, closing round).
Offline fixtures."""

from riprap.core.burr.answer_checks import past_event_source
from riprap.core.burr.synthesis import _lead_fact

PAST = {"hazard": "flood", "time_frame": "past", "assets": []}
Q_IDA = "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
Q_SENSOR = "Have the FloodNet sensors near 80 Pioneer Street recorded flooding?"
TEXTS = {"nyc311": "82 NYC 311 flood-related complaints filed within 200 m in the last 5 years.",
         "floodnet": "2 FloodNet sensors within 600 m have recorded 14 flood events.",
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
    # "since Ida": the measured FloodNet record comes first in the rule's precedence and reports events.
    assert past_event_source(Q_IDA, PAST, "yes", TEXTS, HOLLIS, 2026) == "floodnet"
    assert _lead_fact("yes", ["ida_hwm", "floodnet", "nyc311"], False, None, Q_IDA, PAST, TEXTS, HOLLIS) == \
        {"doc_id": "floodnet", "in_lead": False}
    # Without a FloodNet event the proxy 311 record carries the yes.
    only_311 = {**HOLLIS, "floodnet": {"n_sensors": 2, "n_flood_events_3y": 0}}
    assert past_event_source(Q_IDA, PAST, "yes", TEXTS, only_311, 2026) == "nyc311"


def test_rule_set_no_rests_on_the_source_the_question_names():
    assert past_event_source(Q_SENSOR, PAST, "no", TEXTS, NONE, 2026) == "floodnet"


def test_other_leads_single_out_nothing():
    assert _lead_fact("partly", ["nyc311", "floodnet"], False, None, "Is this block at risk?", None, TEXTS, HOLLIS) is None
    assert _lead_fact("facts", ["nyc311"], False, None, "What do the forecasts show?", {"time_frame": "future"},
                      TEXTS, HOLLIS) is None
    # A yes the rule did not set (not a past-event question) has no key fact either.
    assert past_event_source("Is 80 Pioneer Street in a flood zone?", None, "yes", TEXTS, HOLLIS, 2026) is None


# An experimental source never leads the answer and is never the key fact.

def test_experimental_source_is_never_the_key_fact():
    exp = frozenset({"floodnet"})
    assert _lead_fact("count", ["floodnet", "nyc311"], False, None, "How many flood events?", None, TEXTS, {},
                      exp) == {"doc_id": "nyc311", "in_lead": False}
    assert _lead_fact("count", ["floodnet"], False, "floodnet", "How many flood events?", None, TEXTS, {}, exp) is None
    assert _lead_fact("no", ["floodnet"], False, None, Q_SENSOR, PAST, TEXTS, NONE, exp) is None


def test_extractive_answer_puts_experimental_facts_after_the_others(monkeypatch):
    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import Doc

    sandy = "This address sits inside the 2012 Hurricane Sandy inundation footprint (NYC OEM)."
    layer = ("Experimental: satellite-detected surface water about 14 hours after Hurricane Ida: "
               "3 water polygons within 500 m of this address.")
    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("experimental_layer", "Hazard reader", layer, True),
         Doc("sandy_inundation", "Hazard reader", sandy, False)], [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "yes", "facts": ["experimental_layer", "sandy_inundation"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address",
                          "plan": {"question": "Did this address flood in Hurricane Sandy?"}})
    answer = [c["doc_ids"][0] for c in out["grounding"]["claims"] if c["section"] == "answer"]
    assert answer == ["sandy_inundation", "experimental_layer"], out["paragraph"]
    assert (out["grounding"]["lead_fact"] or {}).get("doc_id") != "experimental_layer"


# A future scenario question keeps its neutral lead and names its key fact.

Q_2050 = "What does the 2050 stormwater scenario show at 400 Carroll Street, Brooklyn?"
FUTURE = {"hazard": "flood", "time_frame": "future", "assets": []}
GOWANUS = {
    "dep_moderate_2050": "The NYC DEP stormwater scenario (2.13 in/hr, 2050 SLR) models deep and contiguous "
                         "flooding (1 ft or more) from rainfall at this address.",
    "dep_extreme_2080": "The NYC DEP stormwater scenario (3.66 in/hr, 2080 SLR) models deep and contiguous "
                        "flooding (1 ft or more) from rainfall at this address.",
    "fema_nfhl": "This address sits in FEMA flood zone AE (a Special Flood Hazard Area), per NFHL FIRM panel "
                 "3604970211F, effective 2007.",
    "sandy_inundation": "This address sits within the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM).",
}


def test_dep_scenario_asked():
    from riprap.core.burr.answer_checks import dep_scenario_asked

    assert dep_scenario_asked(Q_2050) == "dep_moderate_2050"
    assert dep_scenario_asked("What does the DEP 2080 scenario show here?") == "dep_extreme_2080"
    assert dep_scenario_asked("What does the current stormwater scenario show?") == "dep_moderate_current"
    assert dep_scenario_asked("How do the 2050 and 2080 stormwater scenarios compare?") is None
    assert dep_scenario_asked("What sea level does the 2050 scenario project?") is None
    assert dep_scenario_asked("Will this block flood in 2050?") is None


def test_scenario_question_key_fact_is_the_scenario_it_names():
    facts = ["dep_moderate_2050", "fema_nfhl", "sandy_inundation"]
    assert _lead_fact("facts", facts, False, None, Q_2050, FUTURE, GOWANUS, {}) == \
        {"doc_id": "dep_moderate_2050", "in_lead": False}
    assert _lead_fact("facts", ["fema_nfhl"], False, None, Q_2050, FUTURE, GOWANUS, {}) is None


def test_scenario_question_drops_the_dep_scenarios_it_did_not_ask_about():
    from riprap.core.burr.synthesis import _extract

    out = {"answer": {"lead": "yes", "facts": ["dep_moderate_2050", "dep_extreme_2080", "fema_nfhl",
                                              "sandy_inundation"]}}
    lead, facts, hits = _extract(out, Q_2050, GOWANUS, {}, FUTURE)
    assert lead == "facts" and facts == ["dep_moderate_2050", "fema_nfhl", "sandy_inundation"] and not hits
    # The scenario asked about is not among the facts: nothing is dropped.
    out = {"answer": {"lead": "yes", "facts": ["dep_extreme_2080", "fema_nfhl"]}}
    assert _extract(out, Q_2050, GOWANUS, {}, FUTURE)[1] == ["dep_extreme_2080", "fema_nfhl"]


def test_since_ida_needs_a_window_that_starts_on_or_before_ida():
    from riprap.core.burr.answer_checks import past_event_lead

    q = "Have people near 355 Food Center Drive, Bronx reported flooding to 311 since Hurricane Ida?"
    # A 4-year window read in 2026 starts in 2022, after Ida: it cannot say "no".
    zero4 = {"nyc311": {"n": 0, "years": 4, "by_year": {}}}
    assert past_event_lead(q, PAST, [], {"nyc311": "0 complaints."}, zero4, 2026)[0] == "cannot_answer"
    zero = {"nyc311": {"n": 0, "years": 5, "by_year": {}}}
    # "since 2022" starts inside the window: every source answered none, so the answer is no.
    q22 = q.replace("since Hurricane Ida", "since 2022")
    assert past_event_lead(q22, PAST, [], {"nyc311": "0 complaints."}, zero, 2026)[0] == "no"
