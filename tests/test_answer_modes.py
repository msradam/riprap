"""Guarded and extractive answer modes, on the refactor 2 failures
(q05, q10, q12, q16, q18, q19). The LLM is scripted."""

import pytest

from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import CANNOT_ANSWER, Doc

ALERTS = "There are 3 active NWS alerts at this point: Coastal Flood Warning (Severe), High Surf Advisory (Minor)."
OBS = "The latest METAR observation at JFK Airport reports a temperature of 15.0°C."
MTA = ("8 MTA subway entrances within 800 m of this address: 0 inside the 2012 Sandy inundation extent "
       "and 8 inside the DEP extreme stormwater scenario (2080 sea-level rise).")
NYCHA = ("5 NYCHA developments within 2000 m of this address: 3 inside the 2012 Sandy inundation extent "
         "and 2 inside the DEP extreme stormwater scenario (2080 sea-level rise).")
IDA = "USGS surveyed 2 Hurricane Ida high-water mark(s) within 800 m of this address; the highest observed water elevation was 48.2 ft."
SANDY = "This address sits outside the empirical 2012 Hurricane Sandy inundation footprint."
SLR = "NPCC4 (2024) projects 0.38 m of sea-level rise at the Battery by 2050."
DEP = "This address is outside the modeled flooding in the NYC DEP stormwater scenario (2.13 in/hr, 2050 SLR)."
DOCS = [Doc("nws_alerts", "Projector", ALERTS, False), Doc("nws_obs", "Live Observer", OBS, False),
        Doc("mta_entrance_exposure", "Asset Register", MTA, False),
        Doc("nycha_development_exposure", "Asset Register", NYCHA, False),
        Doc("ida_hwm", "Hazard Reader", IDA, False), Doc("sandy_inundation", "Hazard Reader", SANDY, False),
        Doc("npcc4_slr", "Projector", SLR, False), Doc("dep_moderate_2050", "Hazard Reader", DEP, False)]


@pytest.fixture
def run(monkeypatch):
    def go(mode, question, *outputs):
        replies = list(outputs)
        monkeypatch.setenv("RIPRAP_ANSWER_MODE", mode)
        monkeypatch.setattr(syn, "_documents", lambda state: (DOCS, [], None))
        monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
        monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (replies.pop(0), "scripted"))
        out = syn.synthesize({"intent": "single_address", "plan": {"question": question}})
        assert not replies, "every scripted reply should be used"
        return out
    return go


def claim(text, *ids, section="answer"):
    return {"section": section, "text": text, "doc_ids": list(ids), "numbers": []}


# Guarded mode

def test_guarded_q12_absence_is_dropped_then_fixed(run):
    bad = claim("No active flood alerts indicate heavy rain near the address.", "nws_alerts")
    good = claim("There are 3 active NWS alerts, including a Coastal Flood Warning.", "nws_alerts")
    out = run("guarded", "Is it raining hard here?", {"claims": [bad]}, {"claims": [good]})
    g = out["grounding"]
    assert g["attempts"] == 2 and "absence" in g["retried_claims"][0]["reason"]
    assert out["paragraph"].split("**Answer.**\n")[1].startswith("There are 3 active NWS alerts")


@pytest.mark.parametrize("text,ids,cls", [
    ("The NYCHA developments near the address are mapped within the 2012 Sandy inundation extent.",
     ["nycha_development_exposure"], "universal"),                                          # q19
    ("A Coastal Flood Warning is active, indicating flooding is currently occurring.", ["nws_alerts"], "inference"),  # q10
    ("NPCC4 projects 0.38 m of sea-level rise by 2050, which means the address is outside the DEP scenario.",
     ["npcc4_slr", "dep_moderate_2050"], "inference"),                                       # q16
    ("The highest observed water elevation was 48.2 ft.", ["ida_hwm"], "datum"),             # q05
])
def test_guarded_failures_are_dropped_after_one_retry(run, text, ids, cls):
    out = run("guarded", "Question?", {"claims": [claim(text, *ids)]}, {"claims": [claim(text, *ids)]})
    g = out["grounding"]
    assert g["attempts"] == 2 and not g["claims"]
    assert cls in g["dropped_claims"][0]["reason"]
    assert CANNOT_ANSWER in out["paragraph"]


def test_guarded_q18_dropped_count_retries_but_keeps_true_claims(run):
    text = "The subway entrances near the address are inside the DEP extreme stormwater scenario."
    q = "Are the subway entrances near the address in a flood scenario?"
    out = run("guarded", q, {"claims": [claim(text, "mta_entrance_exposure")]},
              {"claims": [claim(text, "mta_entrance_exposure")]})
    g = out["grounding"]
    assert g["attempts"] == 2 and len(g["claims"]) == 1
    assert "mta_entrance_exposure (8)" in g["answer_flags"][0]


def test_guarded_number_words_are_checked(run):
    bad = claim("Four NYCHA developments are inside the 2012 Sandy extent.", "nycha_development_exposure")
    out = run("guarded", "How many NYCHA developments were in the Sandy extent?", {"claims": [bad]}, {"claims": [bad]})
    assert "numbers not found" in out["grounding"]["dropped_claims"][0]["reason"]


# Extractive mode

def test_extractive_answer_is_lead_plus_template_verbatim(run):
    q = "Are the subway entrances near the address in a flood scenario?"
    out = run("extractive", q, {"claims": [], "answer": {"lead": "count", "facts": ["mta_entrance_exposure"]}})
    assert out["paragraph"].split("**Answer.**\n")[1].startswith(
        f"From the sources consulted: {MTA.rstrip('.')} [mta_entrance_exposure].")
    assert out["grounding"]["answer_lead"] == "count"


def test_extractive_q12_no_with_a_positive_fact_falls_back(run):
    bad = {"claims": [], "answer": {"lead": "no", "facts": ["nws_alerts"]}}
    out = run("extractive", "Is it raining hard here?", bad, bad)
    g = out["grounding"]
    assert g["answer_lead"] == "cannot_answer" and "reports a result" in g["dropped_claims"][0]["reason"]
    assert CANNOT_ANSWER in out["paragraph"]


def test_extractive_q19_yes_over_a_partial_count_is_retried_to_partly(run):
    q = "Are the NYCHA developments near the address exposed to flooding?"
    out = run("extractive", q, {"claims": [], "answer": {"lead": "yes", "facts": ["nycha_development_exposure"]}},
              {"claims": [], "answer": {"lead": "partly", "facts": ["nycha_development_exposure"]}})
    assert out["grounding"]["answer_lead"] == "partly"
    assert "In part. 5 NYCHA developments" in out["paragraph"]


def test_extractive_q05_missing_source_is_appended(run):
    q = "Has the block flooded since Hurricane Ida?"
    reply = {"claims": [], "answer": {"lead": "no", "facts": ["sandy_inundation"]}}
    out = run("extractive", q, reply, reply)
    facts = [c["doc_ids"][0] for c in out["grounding"]["claims"] if c["section"] == "answer"]
    assert facts == ["sandy_inundation", "ida_hwm"]
    # "No." no longer fits once the Ida marks are appended, so the lead is dropped
    assert out["grounding"]["answer_lead"] == "facts"
    assert "**Answer.**\nFrom the sources consulted: " + SANDY.rstrip(".") in out["paragraph"]


# Refactor 4 lead rules (a04 and d01 from the refactor 3 held-out set)

HOSP = ("3 hospitals within 3000 m of this address: 0 inside the 2012 Sandy inundation extent "
        "and 0 inside the DEP extreme stormwater scenario (2080 sea-level rise).")
SANDY_IN = "This address sits within the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM)."
SHARE = ("DEP Moderate Stormwater (2.13 in/hr, 2050 SLR): 3.1% of this area is modeled to flood "
         "(2.1% nuisance, over 4 in to 1 ft; 1.1% 1 to 4 ft; 0.0% over 4 ft).")


def test_a04_partly_is_invalid_when_the_asked_source_reports_none():
    from riprap.core.burr.answer_checks import check_lead

    docs = {"sandy_inundation": SANDY_IN, "doh_hospital_exposure": HOSP}
    q = "Are any hospitals near 200 Water Street, Manhattan in a flood scenario?"
    hits = check_lead("partly", ["sandy_inundation", "doh_hospital_exposure"], q, docs)
    assert any("reports none" in r for _, r in hits)
    assert not check_lead("no", ["doh_hospital_exposure"], q, docs)


def test_d01_share_question_needs_the_count_lead():
    from riprap.core.burr.answer_checks import check_lead

    docs = {"dep_moderate_2050_nta": SHARE}
    q = "What share of community district QN04 is inside the DEP 2050 stormwater scenario?"
    assert any("count or share question" in r for _, r in check_lead("partly", ["dep_moderate_2050_nta"], q, docs))
    assert not check_lead("count", ["dep_moderate_2050_nta"], q, docs)


def test_partly_needs_a_positive_and_a_negative_or_partial_fact():
    from riprap.core.burr.answer_checks import check_lead

    q = "Are the NYCHA developments near the address exposed to flooding?"
    assert not check_lead("partly", ["nycha_development_exposure"], q, {"nycha_development_exposure": NYCHA})
    only_positive = {"sandy_inundation": SANDY_IN}
    assert check_lead("partly", ["sandy_inundation"], "Did Sandy flood it?", only_positive)


def test_register_with_one_inside_is_a_result():
    from riprap.core.burr.answer_checks import reports_result

    assert reports_result("3 hospitals within 3000 m of this address: 0 inside the 2012 Sandy inundation "
                          "extent and 1 inside the DEP extreme stormwater scenario.")
    assert not reports_result(HOSP)


def test_extractive_is_the_default(monkeypatch):
    monkeypatch.delenv("RIPRAP_ANSWER_MODE", raising=False)
    assert syn.answer_mode() == "extractive"


def test_d01_share_question_is_given_the_count_lead(run):
    q = "What share of community district QN04 is inside the DEP 2050 stormwater scenario?"
    reply = {"claims": [], "answer": {"lead": "partly", "facts": ["dep_moderate_2050_nta"]}}
    monkey_docs = [Doc("dep_moderate_2050_nta", "Hazard Reader", SHARE, False)]
    syn_docs = DOCS[:]
    DOCS[:] = monkey_docs
    try:
        out = run("extractive", q, reply, reply)
    finally:
        DOCS[:] = syn_docs
    assert out["grounding"]["answer_lead"] == "count"
    assert "In part." not in out["paragraph"]
