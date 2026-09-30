"""The extractive answer, on the refactor 2 failures (q05, q10, q12, q16,
q18, q19). The LLM is scripted."""

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
    def go(question, *outputs):
        replies = list(outputs)
        monkeypatch.setattr(syn, "_documents", lambda state: (DOCS, [], None))
        monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
        monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (replies.pop(0), "scripted"))
        out = syn.synthesize({"intent": "single_address", "plan": {"question": question}})
        assert not replies, "every scripted reply should be used"
        return out
    return go


def test_answer_is_lead_plus_template_verbatim(run):
    q = "Are the subway entrances near the address in a flood scenario?"
    out = run(q, {"claims": [], "answer": {"lead": "count", "facts": ["mta_entrance_exposure"]}})
    assert out["paragraph"].split("**Answer.**\n")[1].startswith(
        f"From the sources consulted: {MTA.rstrip('.')} [mta_entrance_exposure].")
    assert out["grounding"]["answer_lead"] == "count"
    assert out["paragraph"].endswith("Checks run: citations and numbers on every claim; lead rules on the "
                                     "answer, which is the cited text word for word.")


def test_q12_no_with_a_positive_fact_falls_back(run):
    bad = {"claims": [], "answer": {"lead": "no", "facts": ["nws_alerts"]}}
    out = run("Is it raining hard here?", bad, bad)
    g = out["grounding"]
    assert g["answer_lead"] == "cannot_answer" and "reports a result" in g["dropped_claims"][0]["reason"]
    assert CANNOT_ANSWER in out["paragraph"]


def test_q19_yes_over_a_partial_count_is_retried_to_partly(run):
    q = "Are the NYCHA developments near the address exposed to flooding?"
    out = run(q, {"claims": [], "answer": {"lead": "yes", "facts": ["nycha_development_exposure"]}},
              {"claims": [], "answer": {"lead": "partly", "facts": ["nycha_development_exposure"]}})
    assert out["grounding"]["answer_lead"] == "partly"
    assert "In part. 5 NYCHA developments" in out["paragraph"]


def test_q05_missing_source_is_appended(run):
    q = "Has the block flooded since Hurricane Ida?"
    reply = {"claims": [], "answer": {"lead": "no", "facts": ["sandy_inundation"]}}
    out = run(q, reply, reply)
    facts = [c["doc_ids"][0] for c in out["grounding"]["claims"] if c["section"] == "answer"]
    assert facts == ["sandy_inundation", "ida_hwm"]
    # "No." no longer fits once the Ida marks are appended, so the lead is dropped
    assert out["grounding"]["answer_lead"] == "facts"
    assert "**Answer.**\nFrom the sources consulted: " + SANDY.rstrip(".") in out["paragraph"]


# Refactor 4 lead rules (a04 and d01 from the refactor 3 held-out set)

HOSP = ("3 hospitals within 3000 m of this address: 0 inside the 2012 Sandy inundation extent "
        "and 0 inside the DEP extreme stormwater scenario (2080 sea-level rise).")
SANDY_IN = "This address sits within the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM)."
SHARE = ("DEP Moderate Stormwater (2.13 in/hr, 2050 SLR): 3.2% of this area is modeled to flood from rainfall, "
         "2.1% as nuisance flooding (4 in to under 1 ft) and 1.1% as deep and contiguous flooding (1 ft or more); "
         "0.0% is in the future high tide area (coastal tidal inundation projected for 2050).")


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


def test_d01_share_question_is_given_the_count_lead(run):
    q = "What share of community district QN04 is inside the DEP 2050 stormwater scenario?"
    reply = {"claims": [], "answer": {"lead": "partly", "facts": ["dep_moderate_2050_nta"]}}
    monkey_docs = [Doc("dep_moderate_2050_nta", "Hazard Reader", SHARE, False)]
    syn_docs = DOCS[:]
    DOCS[:] = monkey_docs
    try:
        out = run(q, reply, reply)
    finally:
        DOCS[:] = syn_docs
    assert out["grounding"]["answer_lead"] == "count"
    assert "In part." not in out["paragraph"]
