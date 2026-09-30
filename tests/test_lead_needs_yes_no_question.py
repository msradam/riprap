"""A yes, no or partly lead needs a yes-or-no question, and never a question
about now. The model once answered "What is the FEMA flood zone at 1310
Surf Avenue?" with "Yes.", and "Is it flooding right now near Hollis?"
with "No." on the strength of no active NWS alert."""
from riprap.core.burr import answer_checks
from riprap.core.burr.synthesis import _extract

TEXTS = {"fema_nfhl": "This address sits in FEMA flood zone AE (a Special Flood Hazard Area), per NFHL FIRM panel 3604970353F, effective 2007.",
         "nws_alerts": "No active NWS flood, coastal or wind alerts at this point, checked 2026-09-30 15:12 UTC."}


def test_yes_no_questions_open_with_a_verb():
    assert answer_checks.is_yes_no_question("Has the block around 80 Pioneer Street flooded since Ida?")
    assert answer_checks.is_yes_no_question("Is 350 5th Avenue at risk of flooding?")
    assert not answer_checks.is_yes_no_question("What is the FEMA flood zone at 1310 Surf Avenue?")
    assert not answer_checks.is_yes_no_question("How many complaints were filed near 200 Water Street?")


def test_a_what_question_keeps_the_facts_without_a_yes():
    out = {"answer": {"lead": "yes", "facts": ["fema_nfhl"]}}
    lead, facts, _ = _extract(out, "What is the FEMA flood zone at 1310 Surf Avenue, Brooklyn?", TEXTS,
                              focus={"time_frame": "any"})
    assert (lead, facts) == ("facts", ["fema_nfhl"])


def test_a_question_about_now_gets_no_yes_or_no():
    out = {"answer": {"lead": "no", "facts": ["nws_alerts"]}}
    lead, facts, _ = _extract(out, "Is it flooding right now near 90-01 183rd Street, Queens?", TEXTS,
                              focus={"time_frame": "now"})
    assert (lead, facts) == ("facts", ["nws_alerts"])


def test_a_zone_answer_quotes_both_fema_maps():
    texts = {**TEXTS, "fema_pfirm": "FEMA's preliminary flood map (PFIRM issued 2015-01-30, community 360497) places this address in zone AE (a Special Flood Hazard Area); a preliminary map is not the effective map and does not set flood insurance."}
    out = {"answer": {"lead": "facts", "facts": ["fema_nfhl"]}}
    _, facts, _ = _extract(out, "What is the FEMA flood zone at 1310 Surf Avenue, Brooklyn?", texts,
                           focus={"time_frame": "any"})
    assert facts == ["fema_nfhl", "fema_pfirm"]
