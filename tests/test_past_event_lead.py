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
    # The model's "partly" over two positive facts is replaced: the rule says yes, with the source
    # it relied on (FloodNet, the measured record) first and the model's order after it.
    assert past_event_lead(Q_IDA, PAST, ["ida_hwm", "nyc311"], TEXTS, HOLLIS, 2026) == \
        ("yes", ["floodnet", "ida_hwm", "nyc311"])


def test_yes_adds_the_positive_source_when_the_model_left_it_out():
    # The model's only fact (Sandy, not the storm asked about) is not evidence for "since Ida": the
    # answer is the source the rule relied on.
    assert past_event_lead(Q_IDA, PAST, ["sandy_inundation"], TEXTS, HOLLIS, 2026) == ("yes", ["floodnet"])


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
    # "During Ida" rests on the storm's own record; a 311 count is not quoted under that yes.
    assert past_event_lead(q, PAST, ["nyc311"], TEXTS, HOLLIS, 2026) == ("yes", ["ida_hwm"])
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



# Refactor 9: a "Yes." quotes only the evidence for yes. Map, scenario and terrain facts the model
# chose stay out of the answer (they remain in the evidence table).
COUNTER = {**TEXTS, "fema_nfhl": "This address sits in FEMA flood zone X (an area of minimal flood hazard).",
           "dep_moderate_2050": "This address is outside the modeled flooding in the NYC DEP stormwater scenario.",
           "microtopo": "Elevation 14.87 m; higher than 29% of the ground within 200 m."}


def test_yes_keeps_only_event_sources_with_the_relied_on_source_first():
    chosen = ["fema_nfhl", "nyc311", "dep_moderate_2050", "floodnet", "microtopo"]
    assert past_event_lead(Q_IDA, PAST, chosen, COUNTER, HOLLIS, 2026) == ("yes", ["floodnet", "nyc311"])


def test_yes_keeps_the_storm_record_when_it_reports_marks_nearby():
    chosen = ["ida_hwm", "fema_nfhl", "floodnet", "nyc311"]
    assert past_event_lead(Q_IDA, PAST, chosen, COUNTER, HOLLIS, 2026) == ("yes", ["floodnet", "ida_hwm", "nyc311"])
    no_marks = {**HOLLIS, "ida_hwm": {"n_within_radius": 0}}
    assert past_event_lead(Q_IDA, PAST, chosen, COUNTER, no_marks, 2026) == ("yes", ["floodnet", "nyc311"])


def test_yes_with_no_event_source_chosen_adds_the_relied_on_one():
    chosen = ["fema_nfhl", "dep_moderate_2050", "microtopo"]
    assert past_event_lead(Q_IDA, PAST, chosen, COUNTER, HOLLIS, 2026) == ("yes", ["floodnet"])


def test_count_answer_quotes_only_the_counted_source(monkeypatch):
    # Refactor 9, point 4: a count lead does not carry facts from unrelated sources.
    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import Doc

    n311 = "34 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years."
    fema = "This address sits in FEMA flood zone X (an area of minimal flood hazard)."
    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("fema_nfhl", "Hazard reader", fema, False), Doc("nyc311", "Live observer", n311, False)], [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "count", "facts": ["fema_nfhl", "nyc311"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address", "plan": {
        "question": "How many flooding complaints have people near 2017 East 17th Street, Brooklyn made to 311?"}})
    answer = [c["doc_ids"][0] for c in out["grounding"]["claims"] if c["section"] == "answer"]
    assert answer == ["nyc311"], out["paragraph"]


def test_a_qualifying_sentence_does_not_turn_events_into_an_absence():
    """'Have street flood sensors recorded flooding near 214 3rd Street?' got
    cannot_answer: a 'not' in a later FloodNet sentence read as an absence
    and the rule's 'yes' was thrown out."""
    from riprap.core.burr.answer_checks import reports_result

    doc = ("5 FloodNet sensors within 600 m have recorded 28 flood events in the last "
           "3 years. Among the sensors listed as good, the highest depth is 715 mm on 2026-08-23. 1 sensor "
           "with a status other than good recorded 3 of the 28 events; Riprap, not FloodNet, chooses to rest a yes "
           "or no answer only on events from sensors listed as good.")
    assert reports_result(doc)
    assert not reports_result("1 FloodNet sensor within 600 m has recorded 0 flood events "
                              "in the last 3 years.")
    assert not reports_result("No FloodNet sensors deployed within 600 m of this address.")


def test_since_ida_with_no_mark_nearby_keeps_the_rules_yes():
    """41-17 Main Street, Flushing: one sensor with 8 events and 17
    complaints since 2021, no Ida high-water mark within 800 m. "since Ida"
    names the period, so the Ida record is not the source the question is
    about, and its "none within 800 m" cannot turn the rule's yes into
    silence."""
    from riprap.core.burr.answer_checks import check_lead

    q = "Has the block around 41-17 Main Street, Queens flooded since Hurricane Ida?"
    texts = {"floodnet": "1 FloodNet sensor within 600 m has recorded 8 flood events in the last 3 years.",
             "nyc311": "18 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years.",
             "ida_hwm": "No Hurricane Ida (Sept 2021) high-water marks were surveyed within 800 m of this address."}
    values = {"ida_hwm": {"n_within_radius": 0}}
    # The Ida record is still appended (the reader sees it), but its "none" is no contradiction.
    assert [k for k, _ in check_lead("yes", ["floodnet", "nyc311"], q, texts, values)] == ["dropped_count"]
    assert check_lead("yes", ["floodnet", "nyc311", "ida_hwm"], q, texts, values) == []
    # A question about the storm itself keeps the marks as its subject.
    during = "Did Hurricane Ida flood the block around 41-17 Main Street, Queens?"
    assert [k for k, _ in check_lead("yes", ["floodnet", "ida_hwm"], during, texts, values)] == ["absence"]


def test_a_no_from_the_sensors_covers_only_the_period_they_could_record(monkeypatch):
    """A sensor installed last month with no events said "No." to "has it
    flooded since 2025?". The value's period_start is the day its record
    starts: a no is given only for a period that starts on or after it, and
    a no to a question that names no period says the day."""
    from riprap.core.burr.answer_checks import no_period

    q = "Have street flood sensors recorded flooding near 1 East 161st Street, Bronx"
    new = {"floodnet": {"n_sensors": 1, "n_flood_events_3y": 0, "period_start": "2026-09-03"}}
    assert past_event_lead(f"{q} since 2025?", PAST, [], TEXTS, new, 2026) == ("cannot_answer", ["floodnet"])
    old = {"floodnet": {"n_sensors": 1, "n_flood_events_3y": 0, "period_start": "2024-06-01"}}
    assert past_event_lead(f"{q} since 2025?", PAST, [], TEXTS, old, 2026) == ("no", ["floodnet"])
    # Events in a record that starts before the asked period may predate it: no yes.
    events = {"floodnet": {"n_sensors": 1, "n_flood_events_3y": 3, "period_start": "2024-06-01"}}
    assert past_event_lead(f"{q} since 2025?", PAST, [], TEXTS, events, 2026)[0] == "cannot_answer"
    assert past_event_lead(f"{q}?", PAST, [], TEXTS, new, 2026) == ("no", ["floodnet"])
    assert no_period("no", "floodnet", f"{q}?", new) == (
        "The sensors' record quoted here starts on 2026-09-03, so this is a no for the time since then only.")
    assert no_period("no", "floodnet", f"{q} since 2025?", old) == ""  # the question's own period is covered
    assert no_period("yes", "floodnet", f"{q}?", new) == "" and no_period("no", "nyc311", f"{q}?", new) == ""
    docs = [Doc("floodnet", "Live Observer", "1 FloodNet sensor within 600 m has recorded 0 flood events.", False)]
    items = [SimpleNamespace(doc_id="floodnet", pebble_id="floodnet")]
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    out = syn.synthesize({"intent": "single_address", **new, "plan": {"question": f"{q}?"}}, use_llm=False)
    assert "**Answer.**\nNo. The sensors' record quoted here starts on 2026-09-03" in out["paragraph"]
