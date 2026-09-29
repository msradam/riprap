"""Yes or no questions about past flooding get their lead from a rule
(refactor 6, phase 4). The model still picks the facts. Offline fixtures."""

from types import SimpleNamespace

from riprap.core.burr import synthesis as syn
from riprap.core.burr.answer_checks import past_event_lead
from riprap.core.burr.synthesis import CANNOT_ANSWER, Doc

PAST = {"hazard": "flood", "time_frame": "past", "assets": []}
Q_IDA = "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
Q = "Has 80 Pioneer Street flooded?"
TEXTS = {"nyc311": "82 NYC 311 flood-related complaints ...", "floodnet": "2 FloodNet sensors ...",
         "ida_hwm": "USGS surveyed 2 Hurricane Ida high-water marks ...",
         "sandy_inundation": "This address sits outside the 2012 Sandy footprint."}
HOLLIS = {"nyc311": {"n": 82, "years": 5, "by_year": {"2021": 7, "2022": 6, "2025": 28}},
          "floodnet": {"n_flood_events_3y": 14}, "ida_hwm": {"n_within_radius": 2},
          "sandy_inundation": {"inside": False}}
NONE = {"nyc311": {"n": 0, "years": 5, "by_year": {}}, "floodnet": {"n_sensors": 1, "n_flood_events_3y": 0},
        "ida_hwm": {"n_within_radius": 0}}


def test_yes_when_an_observed_source_reports_an_event_in_the_period():
    # The model's "partly" over two positive facts is replaced: the rule says yes.
    assert past_event_lead(Q_IDA, PAST, ["ida_hwm", "nyc311"], TEXTS, HOLLIS, 2026) == ("yes", ["ida_hwm", "nyc311"])


def test_yes_adds_the_positive_source_when_the_model_left_it_out():
    # FloodNet, the measured record, comes first in the rule's precedence.
    assert past_event_lead(Q_IDA, PAST, ["sandy_inundation"], TEXTS, HOLLIS, 2026) == \
        ("yes", ["sandy_inundation", "floodnet"])


def test_no_only_when_every_relevant_source_answered_none():
    lead, facts = past_event_lead(Q, PAST, [], TEXTS, NONE, 2026)
    assert lead == "no" and set(facts) == {"nyc311", "floodnet"}


def test_cannot_answer_when_a_relevant_source_is_missing_or_unavailable():
    # The facts under the silence line are the relevant sources that did answer.
    partial = {"nyc311": NONE["nyc311"]}  # FloodNet did not answer
    assert past_event_lead(Q, PAST, [], TEXTS, partial, 2026) == ("cannot_answer", ["nyc311"])
    down = {**NONE, "floodnet": {"n_flood_events_3y": 0, "error": "HTTP 503"}}
    assert past_event_lead(Q, PAST, [], TEXTS, down, 2026) == ("cannot_answer", ["nyc311"])


def test_zero_in_a_window_that_misses_part_of_the_period_is_not_no():
    # "since Ida": FloodNet's 3-year window starts in 2023, so 0 events cannot rule out 2021 to 2023.
    zero = {"nyc311": {"n": 0, "years": 5, "by_year": {}}, "floodnet": {"n_flood_events_3y": 0},
            "ida_hwm": {"n_within_radius": 0}}
    assert past_event_lead(Q_IDA, PAST, [], TEXTS, zero, 2026)[0] == "cannot_answer"


def test_a_storm_question_is_judged_by_that_storm_record():
    q = "Did the area around 79-01 Broadway, Queens flood during Hurricane Ida?"
    assert past_event_lead(q, PAST, ["nyc311"], TEXTS, HOLLIS, 2026) == ("yes", ["nyc311", "ida_hwm"])
    q = "Was 1310 Surf Avenue, Brooklyn inside the area Hurricane Sandy flooded?"
    assert past_event_lead(q, PAST, [], TEXTS, HOLLIS, 2026) == ("no", ["sandy_inundation"])


def test_a_named_source_is_the_only_relevant_one():
    q = "Have street flood sensors recorded flooding near 1 East 161st Street, Bronx?"
    zero = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 0}, "nyc311": HOLLIS["nyc311"]}
    # The model's positive 311 fact is about something else and is not shown under "No."
    assert past_event_lead(q, PAST, ["nyc311", "floodnet"], TEXTS, zero, 2026) == ("no", ["floodnet"])
    no_sensor = {"floodnet": {"n_sensors": 0, "n_flood_events_3y": 0}}
    assert past_event_lead(q, PAST, [], TEXTS, no_sensor, 2026) == ("cannot_answer", ["floodnet"])


def test_no_ida_mark_nearby_does_not_mean_it_stayed_dry():
    q = "Did the area around 79-01 Broadway, Queens flood during Hurricane Ida?"
    assert past_event_lead(q, PAST, [], TEXTS, {"ida_hwm": {"n_within_radius": 0}}, 2026) == \
        ("cannot_answer", ["ida_hwm"])


def test_other_questions_are_left_to_the_model():
    assert past_event_lead("How many 311 complaints near here?", PAST, [], TEXTS, HOLLIS, 2026) is None
    assert past_event_lead(Q, {"time_frame": "future"}, [], TEXTS, HOLLIS, 2026) is None
    assert past_event_lead("What is the flood zone?", PAST, [], TEXTS, HOLLIS, 2026) is None


def test_extractive_answer_uses_the_rule_lead(monkeypatch):
    monkeypatch.setenv("RIPRAP_ANSWER_MODE", "extractive")
    docs = [Doc(i, "Live Observer" if i in ("nyc311", "floodnet") else "Hazard Reader", t, False)
            for i, t in TEXTS.items()]
    items = [SimpleNamespace(doc_id=i, pebble_id={"sandy_inundation": "sandy"}.get(i, i)) for i in TEXTS]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"claims": [], "answer": {"lead": "partly", "facts": ["ida_hwm", "nyc311"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    state = {"intent": "single_address", "plan": {"question": Q_IDA, "focus": PAST},
             "nyc311": HOLLIS["nyc311"], "floodnet": HOLLIS["floodnet"], "ida_hwm": HOLLIS["ida_hwm"],
             "sandy": HOLLIS["sandy_inundation"]}
    out = syn.synthesize(state)
    assert out["grounding"]["answer_lead"] == "yes" and "**Answer.**\nYes. " in out["paragraph"]
    assert out["grounding"]["attempts"] == 1  # no retry: the rule, not the model, set the lead
    assert CANNOT_ANSWER not in out["paragraph"]


def test_honest_silence_shows_the_sources_that_answered(monkeypatch):
    # A sensor question with no sensor in range: the silence line, then FloodNet's own sentence, cited.
    monkeypatch.setenv("RIPRAP_ANSWER_MODE", "extractive")
    q = "Have street flood sensors recorded flooding near 1 East 161st Street, Bronx?"
    texts = {"floodnet": "No FloodNet sensors deployed within 600 m of this address.",
             "nyc311": "82 NYC 311 flood-related complaints filed within 200 m in the last 5 years."}
    docs = [Doc(i, "Live Observer", t, False) for i, t in texts.items()]
    items = [SimpleNamespace(doc_id=i, pebble_id=i) for i in texts]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {e.doc_id: {} for e in items})
    reply = {"answer": {"lead": "no", "facts": ["floodnet"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    state = {"intent": "single_address", "plan": {"question": q, "focus": PAST},
             "floodnet": {"n_sensors": 0, "n_flood_events_3y": 0}, "nyc311": HOLLIS["nyc311"]}
    out = syn.synthesize(state)
    g = out["grounding"]
    assert g["answer_lead"] == "cannot_answer" and g["lead_fact"] is None and g["answered"] is False
    assert (f"**Answer.**\n{CANNOT_ANSWER} No FloodNet sensors deployed within 600 m of this address "
            "[floodnet].") in out["paragraph"]
    assert "82 NYC 311" not in out["paragraph"].split("**Answer.**")[1].split("\n\n")[0]
    assert not g["dropped_claims"]
