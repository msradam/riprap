"""Capstone LLM synthesis: structured claims, verified in code.

The model never writes free prose. It returns JSON: a list of claims,
each with `section`, `text`, `doc_ids` and the `numbers` it states. The
JSON schema restricts `doc_ids` to an enum of the documents actually
passed in for this request, and `section` to the sections that have
evidence. Code then checks every claim:

  1. every cited doc_id was passed to the model;
  2. every number in the claim (its `numbers` field and any number in its
     text) matches a number in the cited documents, allowing for rounding
     to the claim's precision and for m/ft and m/km conversion;
  3. the text holds no template placeholders.

Claims that fail are sent back once with the reasons. Whatever still
fails is dropped and returned in `dropped_claims` with its reason, never
rendered. A section with evidence but no surviving claim gets the line
"No grounded evidence for this section." Non-numeric wording is checked
only for its citations, not for semantic support.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

from burr.core import State, action

from riprap.core import llm
from riprap.core.burr import answer_checks, evidence, heat_answer, rule_answer
from riprap.core.burr.templated_reconciler import (
    HEAT_NON_SCOPE_FOOTER,
    NON_SCOPE_FOOTER,
    _scope_header,
    compose_briefing,
    with_place_notes,
)

log = logging.getLogger("riprap.synthesis")

NO_EVIDENCE_LINE = "No grounded evidence for this section."
ANSWER_SECTION = "answer"
CANNOT_ANSWER = ("The sources consulted do not answer this question directly. "
                 "Here is what they show.")
# With nothing to show, the line must not promise it ("Here is what they show." once ended an answer).
NOTHING_TO_SHOW = ("The sources consulted do not answer this question directly, and none of them returned a record "
                   "that bears on it for this place.")
# Insurance, price, buying, renting, safety: said first, before the one record that bears on insurance.
NO_ADVICE = ("Riprap reports public records about a place. It does not price flood insurance, value property or give "
             "advice on buying, renting or whether a home is safe.")
ADVICE_POINTER = ("For flood insurance questions, NYC Emergency Management points to FloodHelpNY "
                  "(https://www.floodhelpny.org).")
# Beside it for a question about safety or a basement. The name is Notify NYC's own (its FAQ: "Basement Alerts:
# Notifications specifically designed to alert those living in basement apartment about life-threatening weather
# conditions").
SAFETY_POINTER = ("Notify NYC (https://a858-nycnotify.nyc.gov) is the city's emergency notification program; one of "
                  "its notification types is Basement Alerts, for people who live in basement apartments.")
# An unanswered question says so in the text itself, where the answer would be: the text is what people print
# and what the MCP tools return, and only the page used to say it.
# Where help is, apart from the "Out of scope" note: a life-safety line does not belong under that heading.
WHERE_TO_TURN = "**Where to turn.**"
NO_PREDICTION = "Riprap cannot predict whether a particular place floods on a given day: no source or model here does that."
_BASEMENT_RE = re.compile(r"\bbasements?\b|\bcellars?\b", re.I)
NOT_RECOGNISED = "Riprap's rules did not recognise what this question asks, so it is not answered."
RECORDS_FOLLOW = "The public records for this place follow; none of them is an answer to the question."
_STORM_NAMES = {"ida": "Hurricane Ida", "sandy": "Hurricane Sandy"}

# A number is not preceded by a letter, digit or '.', so 'Extreme-2080'
# gives 2080 and a FIRM panel '3604970203F' gives 3604970203.
_NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")
_PLACEHOLDER_RE = re.compile(r"<[^>]*>|\[doc_id\]|\{[a-z_]+\}|\bTODO\b", re.IGNORECASE)
_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]")
# Service names, not measurements.
_NOT_MEASUREMENTS = {"311", "911"}
_M_PER_FT = 0.3048


def _parse(num: str) -> tuple[float, int] | None:
    s = num.replace(",", "").lstrip("+")
    try:
        value = float(s)
    except ValueError:
        return None
    decimals = len(s.split(".", 1)[1]) if "." in s else 0
    return value, decimals


def numbers_in(text: str) -> list[str]:
    return [n for n in _NUM_RE.findall(_BRACKET_RE.sub("", text)) if n.lstrip("+-") not in _NOT_MEASUREMENTS]


def number_supported(claimed: str, evidence_numbers: list[float]) -> bool:
    """True when `claimed` equals an evidence number, the evidence number
    rounded to the claim's precision, or the same after converting
    metres to feet (or back) or metres to kilometres (or back)."""
    parsed = _parse(claimed)
    if parsed is None:
        return False
    value, decimals = parsed
    tol = 0.5 * 10 ** -decimals + 1e-9
    for e in evidence_numbers:
        for cand in (e, e / _M_PER_FT, e * _M_PER_FT, e / 1000, e * 1000):
            if abs(abs(value) - abs(cand)) <= tol:
                return True
    return False


@dataclass
class Doc:
    doc_id: str
    section: str
    text: str
    experimental: bool


def verify(claims: list[dict], docs: list[Doc], extra_sections: tuple[str, ...] = (),
           exempt: frozenset[str] = frozenset()) -> tuple[list[dict], list[dict]]:
    """Split claims into (kept, dropped); each dropped claim carries a
    `reason`."""
    by_id = {d.doc_id: d for d in docs}
    sections = {d.section for d in docs} | set(extra_sections)
    kept, dropped = [], []
    for c in claims:
        text = _BRACKET_RE.sub("", str(c.get("text", ""))).strip()
        ids = [i for i in (c.get("doc_ids") or []) if isinstance(i, str)]
        claim = {"section": c.get("section"), "text": text, "doc_ids": ids,
                 "numbers": [str(n) for n in (c.get("numbers") or [])]}
        unknown = [i for i in ids if i not in by_id]
        if not text:
            reason = "empty claim"
        elif not ids:
            reason = "no citation"
        elif claim["section"] not in sections:
            reason = f"unknown section: {claim['section']}"
        elif unknown:
            reason = f"cites doc_ids that were not provided: {', '.join(unknown)}"
        elif _PLACEHOLDER_RE.search(text):
            reason = "contains a template placeholder"
        else:
            evidence_numbers = [p[0] for n in numbers_in(" ".join(by_id[i].text for i in ids))
                                if (p := _parse(n))]
            # Listed "numbers" can be identifiers or dates ("3604970203F",
            # "2021-09-02"); tokenize them exactly as the evidence is.
            stated = (set(numbers_in(answer_checks.words_to_digits(text)))
                      | {t for n in claim["numbers"] for t in numbers_in(n)})
            missing = sorted(n for n in stated
                             if n.lstrip("+-") not in _NOT_MEASUREMENTS and n not in exempt
                             and not number_supported(n, evidence_numbers))
            reason = (f"numbers not found in the cited documents: {', '.join(missing)}"
                      if missing else None)
        if reason:
            dropped.append({**claim, "reason": reason})
        else:
            kept.append(claim)
    return kept, dropped


def claims_schema(doc_ids: list[str], sections: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {"claims": {"type": "array", "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["section", "text", "doc_ids", "numbers"],
            "properties": {
                "section": {"type": "string", "enum": sections},
                "text": {"type": "string"},
                "doc_ids": {"type": "array", "minItems": 1,
                            "items": {"type": "string", "enum": doc_ids}},
                "numbers": {"type": "array", "items": {"type": "string"}},
            },
        }}},
    }


SYSTEM_PROMPT = """You write the body of a flood or heat exposure evidence briefing for one place, as JSON claims.

Rules:
- Use only the documents given. Each claim is one plain-language sentence that restates what its cited documents say.
- Put each claim in the section its documents are listed under. Write one to three claims per section.
- `doc_ids` lists every document the sentence relies on. Cite only ids from the list.
- Copy numbers from the cited documents. You may round them, but do not compute new ones (no sums, differences or percentages the documents do not state).
- `numbers` lists every number that appears in the sentence, as written.
- If a document starts with "Experimental:", a claim citing it must say the result is experimental.
- Do not write citation brackets in `text`; citations go in `doc_ids`.
- Never say a place "will flood", is "safe", or has "no risk". Say "is mapped within", "was recorded", "is modeled to".
"""

# The answer is extractive (refactor 8): the model returns a lead and
# the ids of the facts. The reader sees those facts word for word, and a
# question page shows no model-written section claims, so asking for them
# only cost generation time (about 1,100 tokens, over a minute on a laptop).
EXTRACTIVE_SYSTEM = """You answer a question about flood or heat exposure at one place by choosing from numbered documents. You write no prose.

Return JSON with "answer": "lead" is one of yes, no, partly, count, cannot_answer, and "facts" lists the ids of one to four documents that support the lead, most relevant first. The reader sees a fixed phrase for the lead followed by those documents' text, word for word. Use "no" only when the facts report an absence (outside, none, zero). Use "partly" when some but not all of what was asked about is affected. Use "count" when the question asks how many or how much. Use "cannot_answer" with no facts when the documents do not answer the question. Use only ids from the list."""
LEADS = ("yes", "no", "partly", "count", "cannot_answer")
# What reports the present, and what a forecast question is answered with:
# chosen in code in both paths (the model left out the sensors and the tide
# gauge, and picked the flood zone for a forecast question).
LIVE_FACTS, FORECAST_FACTS = rule_answer.LIVE_FACTS, rule_answer.FORECAST_FACTS
# When True (the default), a question the rules recognise is answered by the
# rules even with a model configured, and the model is asked only for the
# rest (riprap/core/burr/rule_answer.py). Without a model the rules always
# answer. On 130 questions written by agents that could not read the
# repository, judged blind, the rule answers were preferred to the model's on
# 54 and the model's on 21, at about 2 s against 10 s (docs/GROUNDING.md). RIPRAP_RULES_FIRST=0 puts the
# model first again.
RULES_FIRST = os.environ.get("RIPRAP_RULES_FIRST", "1") != "0"
# The owner's decision after refactor 3: extractive cannot paraphrase, and
# it declines honestly when the evidence does not answer. The guarded mode
# it replaced (model-written answer claims, five answer rules and an
# entailment check) is kept at the git tag archive/guarded-answer-mode.

def llm_bare() -> bool:
    """RIPRAP_LLM_BARE=1: send a bare address or district (no question) to
    the LLM to rewrite its evidence as claims. Off by default: with no
    question there is nothing to answer, and the claims only restated the
    cited sentences at a minute or more per briefing."""
    import os

    return os.environ.get("RIPRAP_LLM_BARE", "").lower() in ("1", "true", "yes")


def _lead_fact(lead: str | None, facts: list[str], kind_lead: bool, rel: str | None, question: str,
               focus: dict | None, texts: dict[str, str], values: dict | None,
               experimental: frozenset[str] = frozenset()) -> dict | None:
    """Which fact the lead rests on, so the page can set that sentence as the
    key figure. A count lead: the counted kind's lead sentence itself
    (`in_lead`), else the source the question is about, else the first fact
    with a count. A yes or no set by the past-event rule: the source the rule
    relied on. A future scenario question's neutral lead: the source the
    question is about. Any other lead: None (no sentence is singled out). An
    experimental source is never the key fact."""
    facts = [f for f in facts if f not in experimental]
    if rel in experimental:
        rel = None
    if lead == "facts" and (focus or {}).get("time_frame") == "future":
        # A scenario question keeps its neutral lead; the key fact is the source
        # it is about (the DEP scenario it names), when that is among the facts.
        asked = answer_checks.dep_scenario_asked(question)
        doc = rel if rel in facts else next((f for f in facts if asked and f.startswith(asked)), None)
        if "nws_water_forecast" in facts and rule_answer._NEAR_RE.search(question or ""):
            doc = "nws_water_forecast"  # the days ahead: the Weather Service's forecast, not the last reading
        return {"doc_id": doc, "in_lead": False} if doc else None
    if lead == "count":
        if kind_lead:
            return {"doc_id": rel, "in_lead": True} if rel else None
        doc = rel if rel in facts else next((f for f in facts if answer_checks.count_numbers(texts[f])), None)
        return {"doc_id": doc, "in_lead": False} if doc else None
    doc = answer_checks.past_event_source(question, focus, lead or "", texts, values)
    return {"doc_id": doc, "in_lead": False} if doc and doc in facts else None


def _extract(out: dict, question: str, texts: dict[str, str], values: dict | None = None, focus: dict | None = None,
             experimental: frozenset[str] = frozenset()) -> tuple[str, list[str], list[tuple[str, str]]]:
    a = out.get("answer") or {}
    lead = a.get("lead") if a.get("lead") in LEADS else "cannot_answer"
    facts = [f for f in dict.fromkeys(a.get("facts") or []) if f in texts]
    # A yes or no question about past flooding: the rule sets the lead.
    rule = answer_checks.past_event_lead(question, focus, facts, texts, values)
    if rule:
        lead, facts = rule
    # A yes, no or partly lead needs a yes-or-no question ("What is the FEMA
    # flood zone" once got "Yes."), and never a question about now: no active
    # alert is not an observation that nothing is flooding.
    # A count question keeps its own rule (check_lead asks the model again for the count lead).
    if lead in ("yes", "no", "partly") and not answer_checks.is_count_question(question) and (
            not answer_checks.is_yes_no_question(question) or (focus or {}).get("time_frame") == "now"):
        lead = "facts"
    # The two FEMA maps go together: a zone answer that quotes the 2007
    # effective FIRM also quotes the 2015 preliminary map when it ran.
    if "fema_nfhl" in facts and "fema_pfirm" not in facts and texts.get("fema_pfirm"):
        facts = [*facts, "fema_pfirm"]
    if (focus or {}).get("time_frame") == "now":
        live = [i for i in LIVE_FACTS if texts.get(i)]
        if live:
            lead, facts = "facts", live
    if (focus or {}).get("time_frame") == "future":
        # A forecast question: the facts are the forecasts and projections themselves,
        # chosen in code (the model tended to pick the flood zone), and the lead is
        # neutral, since a forecast is not an observation.
        from riprap.core.burr.intake import forecast_question

        forecasts = [i for i in FORECAST_FACTS if texts.get(i)]
        if forecasts and forecast_question(question):
            lead, facts = "facts", forecasts[:4]
        elif lead in ("yes", "no", "partly"):
            lead = "facts"  # a scenario question ("what does the 2050 scenario show"): the model's facts, neutral lead
        # A question naming one DEP scenario: the other DEP scenarios were not asked
        # about, so they leave the answer when the one asked about is among the facts.
        asked = answer_checks.dep_scenario_asked(question)
        if lead == "facts" and asked and any(f.startswith(asked) for f in facts):
            facts = [f for f in facts if not f.startswith("dep_") or f.startswith(asked)]
    lead = rule_answer.soften(lead, facts, values)
    # A yes or no is checked against the measured facts only: a model's
    # output neither supports nor contradicts one, and alone it gets no lead.
    measured = [f for f in facts if f not in experimental]
    if lead in ("yes", "no", "partly") and not measured:
        lead = "facts"
    return lead, facts, answer_checks.check_lead(lead, measured if lead in ("yes", "no", "partly") else facts,
                                                 question, texts, values)
# "facts" is set only by code: the facts with no yes or no in front of them.
# "experimental" and "no_prediction" are set only by rule_answer: an answer
# formed by an experimental model alone, and "will it flood" at a place.
LEAD_PHRASES = {"yes": "Yes.", "no": "No.", "partly": "In part.", "count": "From the sources consulted:",
                "facts": "From the sources consulted:",
                "experimental": "From an experimental model, not a measurement:",
                "no_prediction": f"{NO_PREDICTION} What the Weather Service expects, and what the maps show:",
                "no_satellite": "Riprap quotes no satellite imagery of flooding: the satellite water layer it carried was "
                                "retired after two tests in which it found recorded floods no more often than chance. "
                                "What was surveyed and recorded here:",
                # Heat (heat_answer.py).
                "heat_forecast": "From the National Weather Service, as issued for the next 7 days; Riprap predicts "
                                 "nothing itself:",
                "no_prediction_heat": "Riprap cannot predict what will happen in one building, on one block or on a "
                                      "named day: no source here does that. What the Weather Service expects for the "
                                      "area over the next 7 days, and what has been measured here:",
                "no_advice": f"{NO_ADVICE} The FEMA flood zone here, from the effective map (the one FEMA uses "
                             "for the National Flood Insurance Program) first:",  # as ADVICE_THEN[False]
                "needs_address": "Riprap read this question for the neighbourhood or district as a whole, because it "
                                 "names no house number, and the USGS high-water marks surveyed after Hurricane Ida "
                                 "are read around a street address. Type the address with its house number, such as "
                                 "90-01 183rd Street, Queens, to get the marks near it.",
                "no_change_record": "Riprap has no like-for-like record of change in land cover here.",
                "no_ranking": "Riprap does not rank places against each other or single out one part of a place. The "
                              "record below is for the whole of the place named; ask about one neighbourhood or "
                              "community district for its own:",
                "no_prediction_far": "Riprap cannot predict what will happen in one building, on one block or on a "
                                     "named day: no source here does that, and the Weather Service's forecast runs "
                                     "7 days ahead. What has been measured here:",
                "no_deaths": "Heat deaths are published for the city as a whole only, so no source here holds them for "
                             "a place. What the Health Department publishes by district is emergency visits for heat "
                             "illness:",
                "cooling_centers": "The city opens cooling centers only during a heat emergency and lists them then at "
                                   "finder.nyc.gov/coolingcenters, so none are listed here. What NYC Parks lists:",
                "no_score": "Riprap computes no score or rating of its own. The Health Department publishes an index "
                            "for the neighbourhood, quoted here with what it is and is not:",
                "surface_yes": "At the surface, yes.", "surface_no": "At the surface, no.",
                "no_prediction_register": "Riprap cannot predict which places will flood: no source or model here "
                                          "does that. What the register lists is which of them sit inside a mapped "
                                          "flood extent:",
                "no_advice_heat": f"{NO_ADVICE} No source here measures the temperature inside a building. What was "
                                  "measured outdoors and published for this place:",
                "no_depth": "Riprap gives no flood depth for a place: no source here predicts one, and the city says "
                            "its stormwater flood map \"does not provide the exact depth of flooding at any "
                            "location\". What the maps show at the point mapped:",
                "area_zone": "FEMA flood zones are read at a street address, not for an area as a whole: type an "
                             "address to get its zone. What is counted and mapped for this area:",
                "no_area_zone": "FEMA flood zones are read at a street address, not for an area as a whole, so this "
                                "is not answered for the area: type an address to get its zone. What is mapped for "
                                "this area:",
                "no_rating_heat": "Riprap gives no rating of a place and does not say whether one is safe in the "
                                  "heat. The Health Department's "
                                  "index is a rank among neighbourhoods and not a measurement, and the department "
                                  "says \"All neighborhoods have residents at risk for heat illness and death\". "
                                  "What was measured and published for this place:",
                "no_air_temp": "Riprap has no air temperature at an address: the air readings it quotes come from "
                               "the weather stations named below, and Landsat measures the temperature of surfaces, "
                               "not of the air. What those show:"}
# no_advice opens the same way for every such question; what follows it depends on which records come first.
ADVICE_THEN = {True: "What has been recorded and mapped for this place, the observed record first:",
               False: "The FEMA flood zone here, from the effective map (the one FEMA uses for the National Flood "
                      "Insurance Program) first:"}


def _documents(state) -> tuple[list[Doc], list, object]:
    stones, registry = evidence.load(state.get("deployment"))
    heading = {s.id: evidence.stone_heading(s).rstrip(".") for s in stones.all()}
    items = evidence.collect(state, stones, registry)
    docs = [Doc(e.doc_id, heading.get(e.stone_id, e.stone_id), e.text, e.maturity == "experimental")
            for e in items]
    return docs, items, stones


def _user_prompt(docs: list[Doc], sections: list[str], question: str = "", focus: dict | None = None) -> str:
    lines = []
    if question:
        f = focus or {}
        lines += [f"Question: {question}",
                  f"Focus: hazard {f.get('hazard', 'flood')}, time frame {f.get('time_frame', 'any')}"
                  + (f", assets {', '.join(f['assets'])}" if f.get("assets") else ""), ""]
    for sec in sections:
        lines.append(f"## {sec}")
        lines += [f"[{d.doc_id}] {d.text}" for d in docs if d.section == sec]
        lines.append("")
    return "Documents, grouped by section:\n\n" + "\n".join(lines) + "\nReturn the claims as JSON."


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


# A "right now" answer says where the live picture is: the public tools are
# better at that job than a briefing built from records.
LIVE_POINTER = ("Riprap reads records, not the street. For a live depth reading use the FloodNet dashboard "
                "(dataviz.floodnet.nyc); official warnings come from the National Weather Service "
                "(weather.gov) and Notify NYC.")
BOTH_HAZARDS = ("This question names flooding and heat. Riprap keeps them as separate briefings and does not weigh one "
                "against the other: this is the flood record, and asking about heat alone at this place gives the heat record.")


def _change_lead(facts: list[str], values: dict | None) -> str:
    """The lead of a change-over-time question about land cover: the two
    figures are two methods, said before either is printed, and whether
    their difference is inside what the model was off by when tested (the
    gap figures come from the model's own result file)."""
    from app import experimental

    lead = LEAD_PHRASES["no_change_record"]
    city = next(((values or {}).get(f) for f in facts if f.startswith("city_landcover")), None)
    model = next(((values or {}).get(f) for f in facts if f.startswith("landcover")), None)
    if not (isinstance(city, dict) and isinstance(model, dict) and model.get("built_pct") is not None
            and city.get("built_pct") is not None):
        return f"{lead} What the sources below show is one year each, not a change:"
    lead += (f" The two figures below come from different methods: the city's {city.get('year', 2017)} map, surveyed "
             f"from LiDAR and aerial imagery, and an experimental model reading {model.get('year')} satellite images.")
    gap, tested = abs(model["built_pct"] - city["built_pct"]), experimental.evaluation("landcover") or {}
    typical, most = tested.get("district_paved_gap_points_median_abs"), tested.get("district_paved_gap_points_max")
    if typical is not None and most is not None and gap <= most:
        return (f"{lead} Their paved shares differ by {gap:.1f} points, which is within what the model was off by "
                f"when tested against the city's 2021 map (typically {typical} points for a district, at most {most}), "
                "so the difference is not a measured change:")
    return f"{lead} The difference between them is not a measured change:"


HEAT_LIVE_POINTER = ("Riprap reads records, not the street. Official heat warnings come from the National Weather "
                     "Service (weather.gov/okx) and Notify NYC; during a heat emergency the city lists its cooling "
                     "centers at finder.nyc.gov/coolingcenters.")


def _render(kept: list[dict], docs: list[Doc], sections: list[str], question: str = "",
            lead: str = "", empty: dict[str, list[str]] | None = None, brief: str | None = None,
            now: bool = False, place: str = "", advice: str = "", closing: str = "") -> str:
    """Scope header, then the answer (when a question was asked), then one
    section per Stone that ran, then the footer. Only verified claims.

    A question page says each thing once: a claim that only restates the
    answer (the same sources, no number the answer lacks) is left out, and
    a Stone section left with nothing is hidden, since its facts are in the
    evidence cards. `empty` maps a Stone heading to the sources it consulted
    that returned nothing; such a Stone says so instead of the generic line."""
    experimental = {d.doc_id for d in docs if d.experimental}
    answer = [c for c in kept if c["section"] == ANSWER_SECTION]
    answer_ids = {i for c in answer for i in c["doc_ids"]}
    answer_nums = set(numbers_in(" ".join(c["text"] for c in answer)))

    def restates(c: dict) -> bool:
        return (bool(answer) and c["section"] != ANSWER_SECTION and set(c["doc_ids"]) <= answer_ids
                and set(numbers_in(c["text"])) <= answer_nums)

    def sentences(sec: str) -> str:
        out: list = []  # a finished sentence, or a (text, doc_id, every) fact still to cite
        for c in kept:
            if c["section"] != sec or restates(c):
                continue
            text = c["text"].rstrip(". ")
            if any(i in experimental for i in c["doc_ids"]) and "experimental" not in text.lower():
                text = f"Experimental: {text}"
            if len(c["doc_ids"]) == 1:  # a multi-sentence template fact: cite each numeric sentence
                out.append((f"{text}.", c["doc_ids"][0], c["doc_ids"][0] in experimental))
            else:
                out.append(f"{text} {''.join(f'[{i}]' for i in c['doc_ids'])}.")
        # Cited together, so a closing sentence several facts share is printed once, after the last of them.
        cited = iter(evidence.cite_each([f for f in out if not isinstance(f, str)]))
        return " ".join(filter(None, (f if isinstance(f, str) else next(cited) for f in out)))

    parts = [_scope_header()]
    if brief:
        parts.append(f"**In brief.**\n{brief}")
    if question:
        body = sentences(ANSWER_SECTION)
        # With no fact to quote, the lead's own statement stands alone, or the line that says nothing is shown.
        # `closing` is what the rules add after the quoted facts (rule_answer.closing).
        body = f"{body} {closing}" if body and closing else body
        parts.append("**Answer.**\n" + ((f"{lead} " if lead else "") + body if body else lead or NOTHING_TO_SHOW))
    for sec in sections:
        body = sentences(sec)
        if not body and question and sec in (empty or {}):
            parts.append(f"**{sec}.**\nConsulted {_and(empty[sec])}; "
                         f"{'it' if len(empty[sec]) == 1 else 'they'} returned nothing for this place.")
            continue
        if not body and question:
            continue  # its facts are in the answer or the evidence cards; the section would only say so
        if not body:
            # The model wrote no claim here, but the section has evidence: show the
            # sources' own template sentences (cited, correct by construction),
            # never "no evidence" over a section that has some.
            body = " ".join(evidence.cite(f"Experimental: {d.text}" if d.experimental and "experimental"
                                          not in d.text.lower() else d.text, d.doc_id, every=d.experimental)
                            for d in docs if d.section == sec)
        parts.append(f"**{sec}.**\n" + (body or NO_EVIDENCE_LINE))
    heat = heat_answer.hazard_of(question) == "heat"
    pointer = HEAT_LIVE_POINTER if heat else LIVE_POINTER
    footer = HEAT_NON_SCOPE_FOOTER if heat else NON_SCOPE_FOOTER
    footer = footer.replace("**Out of scope.** ", f"**Out of scope.** {pointer} ", 1) if now else footer
    if advice:  # the pointers a declined question gets, as plain links, under their own heading
        parts.append(f"{WHERE_TO_TURN}\n{advice}")
    footer = with_place_notes(footer, question, place, heat)
    if question and re.search(r"\bflood", question, re.I) and re.search(r"\bheat\b|\bhott?(?:er|est)?\b", question, re.I) \
            and not heat_answer.INDOOR_HEATING_RE.search(question):
        # "Which is the bigger problem here, flooding or heat?" got the flood record and no word about heat.
        footer = footer.replace("**Out of scope.** ", f"**Out of scope.** {BOTH_HAZARDS} ", 1)
    parts.append(footer)
    return "\n\n".join(parts)


def _days_311(question: str, texts: dict[str, str], values: dict) -> str:
    """What a question about Hurricane Ida, the time since it, or a named
    day older than the 311 window is told about 311: the complaints filed
    near the address on those days, fetched for them alone (the address
    count covers the last 5 years, which now begins five weeks after Ida),
    or, for an area or when that fetch fails, that the count quoted starts
    after the days asked about. Empty for any other question."""
    import datetime

    from app.context import nyc311

    doc = next((d for d in ("nyc311", "nyc311_nta") if texts.get(d) and isinstance(values.get(d), dict)), None)
    since = answer_checks._iso_date(values[doc].get("since")) if doc else None
    if not since or heat_answer.hazard_of(question) == "heat":
        return ""
    day = answer_checks.named_day(question)
    if re.search(r"\bida\b", question, re.I) or answer_checks.storm_of_day(question) == "ida":
        first, last, what = *nyc311.IDA_DAYS, "the days of Hurricane Ida"
    elif day and day < since:
        first, last, what = day.isoformat(), day.isoformat(), "the day asked about"
    else:
        return ""
    if datetime.date.fromisoformat(first) >= since:
        return ""  # the window quoted already holds those days
    point = values.get("_point")
    if doc == "nyc311" and point:
        try:
            return f"{nyc311.days_sentence(point[0], point[1], values[doc].get('radius_m') or 200, first, last, what)[:-1]} [{doc}]."
        except Exception as e:  # noqa: BLE001 - the fallback sentence says what is missing
            log.warning("311 for %s to %s could not be read: %s", first, last, e)
    return (f"The 311 count quoted here starts on {since.isoformat()}, after {what} ({first}"
            f"{'' if first == last else ' to ' + last}), so it holds no complaint from then [{doc}].")


def _unanswered(state, statement: str, grounding: dict) -> dict:
    """The result for a question that is not answered: the statement of
    why where the answer would be, then the evidence briefing for the place.
    `grounding.answered` is False, and the text says so itself. A question
    that mentions a basement gets the city's basement alerts under "Where
    to turn"."""
    paragraph, cites = compose_briefing(state)
    head, block = _scope_header(state), f"**Answer.**\n{statement} {RECORDS_FOLLOW}"
    if _BASEMENT_RE.search((state.get("plan") or {}).get("question") or ""):
        block = f"{block}\n\n{WHERE_TO_TURN}\n{SAFETY_POINTER}"
    paragraph = paragraph.replace(head, f"{head}\n\n{block}", 1) if head in paragraph else f"{block}\n\n{paragraph}"
    return {"paragraph": paragraph, "citations": cites,
            "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": 0, "llm_calls": [],
                          "question": (state.get("plan") or {}).get("question") or "", "answered": False, **grounding}}


def synthesize(state, use_llm: bool = True) -> dict:
    """The briefing for a state. `grounding.tier` is "llm" when a model was
    called here and "no_llm" when none was. A question is answered by the rules of
    rule_answer (always when `use_llm` is False; first when RULES_FIRST) or
    by the model's choice of lead and facts, checked by the lead rules.
    Returns paragraph, citations and a `grounding` record (the answer's
    facts as claims, dropped claims with reasons, attempts, model). Falls
    back to the rules, then to the evidence briefing, when no endpoint
    answers."""
    if state.get("intent") in ("not_implemented", "out_of_scope"):
        paragraph, _ = compose_briefing(state)
        return {"paragraph": paragraph, "citations": {},
                "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    docs, items, stones = _documents(state)
    if not docs:
        from riprap.core.burr.templated_reconciler import nothing_built

        return {"paragraph": nothing_built(state), "citations": {},
                "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    plan = state.get("plan") or {}
    question, focus = rule_answer.spelled(plan.get("question") or ""), plan.get("focus")
    if not question and not (use_llm and llm_bare()):
        paragraph, cites = compose_briefing(state)
        return {"paragraph": paragraph, "citations": cites,
                "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": 0,
                              "note": "No question was asked, so the cited evidence is shown without the LLM "
                                      "(RIPRAP_LLM_BARE=1 sends it to the LLM)."}}
    # Stones whose consulted sources all returned nothing: named on a question page.
    empty: dict[str, list[str]] = {}
    if question and stones is not None:
        heading = {s.id: evidence.stone_heading(s).rstrip(".") for s in stones.all() if s.id != "capstone"}
        with_docs = {d.section for d in docs}
        for e in state.get("consulted") or []:
            h = heading.get(e.get("stone"))
            if h and h not in with_docs:
                empty.setdefault(h, []).append(e["title"])
    order = list(heading.values()) if empty else []
    sections = list(dict.fromkeys([*(h for h in order if h in empty or h in {d.section for d in docs}),
                                   *(d.section for d in docs)]))
    # Structured pebble values by doc_id, for the headline figure checks.
    values = {e.doc_id: state.get(e.pebble_id) for e in items if isinstance(state.get(e.pebble_id), dict)}
    if not state.get("nta") and state.get("lat") is not None:
        # The queried address, for the rules that ask how far a record is from it (answer_checks.BLOCK_M).
        values["_point"] = (state["lat"], state["lon"])
    texts: dict[str, str] = {}
    for d in docs:
        texts[d.doc_id] = f"{texts.get(d.doc_id, '')} {d.text}".strip()
    # Numbers the user typed (the question, the place) may be restated;
    # they are the user's words, not claims about the data.
    exempt = frozenset(numbers_in(f"{question} {state.get('query') or ''} "
                                  f"{(state.get('geocode') or {}).get('address') or ''}"))
    schema = claims_schema(sorted(texts), sections)
    if question:
        # The answer only: no section claims (see EXTRACTIVE_SYSTEM).
        schema = {"type": "object", "additionalProperties": False, "required": ["answer"], "properties": {
            "answer": {"type": "object", "additionalProperties": False, "required": ["lead", "facts"],
                       "properties": {"lead": {"type": "string", "enum": list(LEADS)},
                                      "facts": {"type": "array", "items": {"type": "string", "enum": sorted(texts)},
                                                "maxItems": 4}}}}}
        system = EXTRACTIVE_SYSTEM
    else:
        system = SYSTEM_PROMPT
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": _user_prompt(docs, sections, question, focus)}]

    def check(out: dict):
        kept, dropped = verify(out.get("claims") or [], docs, exempt=exempt)
        notes: list[str] = []
        lead, facts, lead_hits = "", [], []
        if question:
            lead, facts, lead_hits = _extract(out, question, texts, values, focus,
                                              frozenset(d.doc_id for d in docs if d.experimental))
            notes = [f"answer lead {lead!r}: {r}" for _, r in lead_hits]
        return kept, dropped, notes, (lead, facts, lead_hits)

    attempts, model, first_dropped, calls, fallback_reason = 0, None, [], [], None
    kept, dropped, notes, answer = [], [], [], ("", [], [])
    # The rules answer from the sources that answered: one that was
    # unavailable is not a fact ("NWS alerts unavailable" is not "no alerts").
    answered = {d: t for d, t in texts.items() if not answer_checks.unavailable(d, texts, values)}
    ruled = rule_answer.answer(question, answered, values) if question and (RULES_FIRST or not use_llm) else None
    if ruled is None and use_llm:
        try:
            out, model = llm.chat_json(messages, schema, name="claims", ledger=calls)
            attempts = 1
            kept, dropped, notes, answer = check(out)
            first_dropped = dropped
            if dropped or notes:
                failures = "\n".join([f'- "{d["text"]}": {d["reason"]}' for d in dropped] + [f"- {n}" for n in notes])
                messages += [
                    {"role": "assistant", "content": json.dumps(out)},
                    {"role": "user", "content": "These failed verification:\n" + failures +
                     "\nReturn the full output again. Fix these using only what their cited documents "
                     "say, or leave them out."},
                ]
                out, model = llm.chat_json(messages, schema, name="claims", ledger=calls)
                attempts = 2
                kept, dropped, notes, answer = check(out)
        except llm.LLMUnavailable as e:
            # The question stays a question: the rules answer it if they can.
            fallback_reason = f"LLM unavailable: {e}"
            ruled = rule_answer.answer(question, answered, values) if question else None
            kept, dropped, notes = [], [], []
    if ruled is None and (fallback_reason or not use_llm):
        # No rule names what the question asks and no model answered: the
        # evidence for the place, and the page says it was not answered.
        if not question:
            paragraph, cites = compose_briefing(state)
            return {"paragraph": paragraph, "citations": cites,
                    "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": attempts,
                                  "llm_calls": calls, "question": question, "answered": None, "answer_mode": None}}
        # Nothing answered: neither a rule nor the model.
        return _unanswered(state, NOT_RECOGNISED, {
            "attempts": attempts, "llm_calls": calls, "answer_mode": None, "answer_lead": "not_recognised",
            **({"fallback_reason": fallback_reason} if fallback_reason else {})})
    if ruled is not None and ruled[0] in ("not_held", "not_english"):
        # A rule read the question and what it asks for is not here: said first, then the place's records.
        topic, statement = rule_answer.not_held(question) or ("language", rule_answer.ENGLISH_ONLY)
        if ruled[0] == "not_english":
            topic, statement = "language", rule_answer.ENGLISH_ONLY
        elif rule_answer._WILL_FLOOD_RE.search(question) and heat_answer.hazard_of(question) != "heat":
            statement = f"{statement} {NO_PREDICTION}"  # "Will my basement flood?": that too is not said
        return _unanswered(state, statement, {"attempts": attempts, "llm_calls": calls, "answer_mode": "rules",
                                              "answer_lead": ruled[0], "not_held": topic})
    if ruled is not None:
        focus = {"time_frame": rule_answer.time_frame(question)}
        lead, facts = ruled
        absent = {d: t for d, t in texts.items() if isinstance(values.get(d), dict) and values[d].get("installed") is False}
        # The lead is checked against the measured facts only: a model's
        # sentence, or its "not available", neither supports nor undoes one.
        models = {d.doc_id for d in docs if d.experimental}
        measured = [f for f in facts if f not in models] if lead in ("yes", "no", "partly") else facts
        if any(k != "dropped_count" for k, _ in answer_checks.check_lead(lead, measured, question, texts, values)):
            lead = "facts"  # the facts stand; a lead that fails the lead rules does not
        if lead in ("facts", "experimental") and focus["time_frame"] != "past":
            # The question asks what an experimental model answers and this
            # server cannot run it: its "not available" sentence closes the
            # answer. Never under a yes, a no or a count, and never for the past.
            facts = [*facts, *(d for d in rule_answer.experimental(question, texts)[1] if d in absent and d not in facts)]
        answer = (rule_answer.soften(lead, facts, values), facts, [])
    lead_phrase, answer_flags, lead, lead_fact = "", notes, None, None
    record_lead = False
    if question and ruled is not None:
        lead, facts, _ = answer
        rel = answer_checks.relevant_doc(question, texts)
        experimental = frozenset(d.doc_id for d in docs if d.experimental)
        facts = sorted(facts, key=lambda f: f in experimental)  # the rule's order, experimental sources last
        kept = [{"section": ANSWER_SECTION, "text": texts[f], "doc_ids": [f], "numbers": []} for f in facts]
        lead_phrase = CANNOT_ANSWER if lead == "cannot_answer" and facts else LEAD_PHRASES.get(lead, "")
        if lead == "no_advice":
            # With no record for this place: the statement alone, and the pointers below.
            lead_phrase = f"{NO_ADVICE} {ADVICE_THEN[facts[0] not in rule_answer.ADVICE_FACTS]}" if facts else NO_ADVICE
        since = answer_checks._period_start_date(question)
        if lead == "near":
            # The nearest record of any kind among the sources that put flooding near the address.
            verdict = answer_checks._past_event_verdict(question, texts, values)[1]
            nearby = [f for f in facts if verdict.get(f) == answer_checks.NEAR] or facts[:1]
            mark = (values.get("ida_hwm") or {}).get("nearest_dist_m") if "ida_hwm" in facts else None
            if mark is not None and mark > answer_checks.BLOCK_M and "ida_hwm" not in nearby:
                nearby = [*nearby, "ida_hwm"]  # "since Ida": a mark nearer than the sensor is the nearest record
            lead_phrase = answer_checks.near_lead(nearby, values, since) if facts else ""
        if lead == "day":
            lead_phrase = (answer_checks.day_lead(question, texts, values) or ("", "", []))[1]
        if period := answer_checks.period_lead(question, texts, values) if rule_answer._happened_clause(question) else None:
            if lead in ("period", "cannot_answer") and facts == period[2]:
                lead_phrase = period[1]  # a named year, season or month: what the records dated in it hold
        if lead == "yes" and state.get("nta"):
            # A yes about an area names the area: "Has Gowanus flooded?" is answered for a tabulation
            # area four neighbourhoods wide, and a bare "Yes." read as a yes about Gowanus alone.
            lead_phrase = f"Yes, in {state['nta'].get('nta_name') or 'this area'}:"
        if lead == "cannot_answer" and state.get("deployment") == "__none__":
            # "Has 1 Washington Street, Hoboken, NJ flooded?": the reason there is nothing to quote.
            lead_phrase = ("This place is outside the cities Riprap covers, so Riprap holds no local record of past "
                           "flooding, complaints or sensors for it and cannot answer this question."
                           + (" What the federal sources it read show:" if facts else ""))
        if lead in ("yes", "near", "cannot_answer") and (storm := answer_checks.storm_of_day(question)):
            day = answer_checks.named_day(question)
            lead_phrase = (f"{lead_phrase} {day.isoformat()} is a day of {_STORM_NAMES[storm]}'s flooding in the "
                           "city, so this is read from the record of that storm.")
        if lead == "no_change_record":
            lead_phrase = _change_lead(facts, values)
        if lead == "count" and rel in facts:
            sentence, undetermined = answer_checks.count_lead(question, texts, values)
            if undetermined:  # the period asked is not the source's window: no count as the answer
                lead, lead_phrase = "facts", LEAD_PHRASES["facts"]
            elif sentence:
                lead_phrase = f"{sentence} {lead_phrase}"
        if lead == "count" and (days := heat_answer.count_sentence(question, facts, values)
                                or heat_answer.trend_sentence(question, facts, values)):
            lead_phrase = f"{days} {lead_phrase}"  # "how many days reached 90 in 2023": that year, from the station's record
            record_lead = True
        elif lead == "facts" and (peak := heat_answer.year_sentence(question, facts, values)
                                  or heat_answer.record_sentence(question, facts, values)
                                  or heat_answer.trend_sentence(question, facts, values)):
            lead_phrase = f"{peak} {lead_phrase}"  # "how hot did it get in 2025", "the hottest day on record"
            record_lead = True
        lead_fact = _lead_fact(lead, facts, lead_phrase != LEAD_PHRASES.get(lead, ""), rel, question,
                               focus, texts, values, experimental)
        if period := answer_checks.no_period(lead, (lead_fact or {}).get("doc_id"), question, values):
            lead_phrase = f"{lead_phrase} {period}"  # a "No." says the period the sensors could have recorded
        if lead == "yes" and not state.get("nta") and (rests := answer_checks.yes_lead((lead_fact or {}).get("doc_id"), values, since)):
            lead_phrase = f"{lead_phrase} {rests}"  # a "Yes." about an address says how far its record is
        deepest = (values.get("floodnet") or {}).get("highest_event") if "floodnet" in facts else None
        if lead == "facts" and deepest and deepest.get("max_depth_mm") is not None and re.search(
                r"\bhow deep\b|\bdeepest\b|\bhighest depth\b", question, re.I):
            # "How deep was the worst flood FloodNet measured in Hollis?": the reading itself, before the counts.
            mm = deepest["max_depth_mm"]
            lead_phrase = (f"The highest depth in FloodNet's verified record for the sensors read here is {mm} mm "
                           f"({mm / 25.4:.1f} in), on {deepest['date']} (UTC) [floodnet]. {lead_phrase}")
        hvi = next((values[f] for f in facts if f in heat_answer.HVI and isinstance(values.get(f), dict)), None)
        if lead in ("count", "facts") and hvi and hvi.get("ac_pct") is not None and re.search(r"\bair[- ]?condition|\ba/c\b", question, re.I):
            # "How many households in East Harlem have air conditioning?": the share itself, before the index
            # sentence that holds it (the department publishes a share, not a count of households).
            doc = next(f for f in facts if f in heat_answer.HVI)
            lead_phrase = (f"The Health Department's file gives {hvi['ac_pct']}% of households with air conditioning in "
                           f"{hvi.get('area') or 'this neighbourhood'}, a survey estimate and a share, not a count of "
                           f"households [{doc}]. {lead_phrase}")
        if (unplaced := (state.get("geocode") or {}).get("unplaced")) and state.get("nta"):
            # "Has the block around La Marqueta, East Harlem flooded?": the landmark was not found, so no yes or
            # no about its block; what follows is the wider area's record, said first.
            lead = "facts" if lead in ("yes", "no", "partly", "near") else lead
            lead_phrase = (f"Riprap could not locate \"{unplaced}\", so it gives no yes or no about that spot: what "
                           f"follows is the record for the wider area, {state['nta'].get('nta_name') or 'named above'}."
                           + ("" if lead == "facts" else f" {lead_phrase}"))
    elif question:
        lead, facts, lead_hits = answer
        rel = answer_checks.relevant_doc(question, texts)
        appended = bool(rel and rel not in facts and lead != "cannot_answer"
                        and any(k == "dropped_count" for k, _ in lead_hits))
        if appended:
            facts = [*facts, rel]  # the source the question is about, verbatim
        if (answer_checks.is_count_question(question) and lead not in ("count", "cannot_answer")
                and any(answer_checks.count_numbers(texts[f]) for f in facts)):
            lead = "count"  # a count or share question gets the number, not "In part."
        experimental = frozenset(d.doc_id for d in docs if d.experimental)
        measured = [f for f in facts if f not in experimental]
        if lead in ("yes", "no", "partly") and not measured:
            lead = "facts"  # the model chose only an experimental source: that is not a measurement
        lead_hits = answer_checks.check_lead(lead, measured if lead in ("yes", "no", "partly") else facts,
                                             question, texts, values)
        if appended and any(k != "dropped_count" for k, _ in lead_hits):
            lead, lead_hits = "facts", []  # the appended fact no longer fits the lead: drop the lead
        if any(k != "dropped_count" for k, _ in lead_hits):
            dropped = [*dropped, {"section": ANSWER_SECTION, "text": f"{lead}: {', '.join(facts)}",
                                  "doc_ids": facts, "numbers": [],
                                  "reason": "answer check: " + "; ".join(r for _, r in lead_hits)}]
            lead, facts = "cannot_answer", []
        if lead == "count" and rel in facts:
            facts = [rel]  # a count answers with the counted source alone, not unrelated facts
        # The source the question is about leads the facts when the model
        # chose it ("Are the schools ... exposed?" opened with the FEMA zone
        # of the address, and the school register came fourth). A record
        # appended by rule keeps its place, and so does a named storm's own
        # record ("since Ida" names the period, and the sensors and 311 say
        # what happened since). Experimental sources come last.
        # A METAR with no precipitation reading says nothing about flooding:
        # "Is there flooding ... right now?" once cited "21.1°C at Central Park".
        facts = [f for f in facts if f != "nws_obs" or "precip" in texts.get(f, "").lower()]
        subject = None if appended or rel == answer_checks._storm_record(question) else rel
        facts = sorted(facts, key=lambda f: (f in experimental, f != subject))
        kept = [*({"section": ANSWER_SECTION, "text": texts[f], "doc_ids": [f], "numbers": []} for f in facts),
                *kept]
        # Honest silence still shows what the sources say: facts under a
        # cannot-answer lead follow the silence line, with no key figure.
        lead_phrase = CANNOT_ANSWER if lead == "cannot_answer" and facts else LEAD_PHRASES.get(lead, "")
        if lead == "count" and rel in facts:
            sentence, undetermined = answer_checks.count_lead(question, texts, values)
            if undetermined:  # the period asked is not the source's window: no count as the answer
                lead, lead_phrase = "facts", LEAD_PHRASES["facts"]
            elif sentence:
                lead_phrase = f"{sentence} {lead_phrase}"
        lead_fact = _lead_fact(lead, facts, lead_phrase != LEAD_PHRASES.get(lead, ""), rel, question,
                               focus, texts, values, experimental)
        if period := answer_checks.no_period(lead, (lead_fact or {}).get("doc_id"), question, values):
            lead_phrase = f"{lead_phrase} {period}"  # a "No." says the period the sensors could have recorded
    checks = ["citations and numbers on every claim"]
    if question:
        quoted = any(c["section"] == ANSWER_SECTION for c in kept)  # an answer with no fact quotes nothing
        checks.append("lead rules on the answer" + (", which is the cited text word for word" if quoted else "")
                      + ("; its first sentence is read from the same station's yearly record" if record_lead else ""))
    # A bare address opens with the same verified "In brief" lead as no-LLM mode.
    from riprap.core.burr.stones import hazard_of
    from riprap.core.burr.templated_reconciler import _heat_lead, _lead

    brief = None
    if not question and state.get("intent") == "single_address":
        brief = _heat_lead(state, items, area=False) if hazard_of(plan) == "heat" else _lead(state, items)
    pointers = ADVICE_POINTER if lead == "no_advice" else ""
    if (lead in ("no_advice", "no_advice_heat") and rule_answer._SAFETY_RE.search(question)) or _BASEMENT_RE.search(question):
        pointers = f"{SAFETY_POINTER} {pointers}".strip()  # every question that mentions a basement carries it
    closing = rule_answer.closing(question, lead or "", [c["doc_ids"][0] for c in kept if c["section"] == ANSWER_SECTION
                                                         and len(c["doc_ids"]) == 1], values, texts) if question else ""
    if question and ruled is not None and (days := _days_311(question, texts, values)):
        closing = f"{closing} {days}".strip()
    paragraph = _render(kept, docs, sections, question, lead_phrase, empty, brief,
                        now=bool(question) and (focus or {}).get("time_frame") == "now",
                        place=(state.get("geocode") or {}).get("address") or "", advice=pointers, closing=closing)
    paragraph = paragraph.replace(_scope_header(), _scope_header(state), 1)  # outside every city: say what was not read
    # Every consulted source with a value is citable (its evidence row gets a
    # number), the ones the text cites first, in order of appearance, so the
    # numbering still starts with the answer.
    cited = list(dict.fromkeys(re.findall(r"\[([a-z0-9_]+)\]", paragraph)))
    every = evidence.citations(items)
    citations = {k: every[k] for k in cited if k in every}
    citations.update({k: v for k, v in every.items() if k not in citations})
    return {
        "paragraph": paragraph + f"\n\nChecks run: {'; '.join(checks)}.",
        "citations": citations,
        "grounding": {"tier": "llm" if attempts else "no_llm", "model": model, "attempts": attempts,
                      "claims": kept, "dropped_claims": dropped,
                      "retried_claims": first_dropped if attempts == 2 else [],
                      "n_kept": len(kept), "n_dropped": len(dropped), "llm_calls": calls,
                      "question": question, "n_documents": len(docs),
                      # "rules": lead and facts chosen by rule_answer; "extractive": by the model.
                      "answer_mode": "rules" if ruled is not None else "extractive",
                      **({"fallback_reason": fallback_reason} if fallback_reason else {}),
                      "answer_lead": lead, "lead_fact": lead_fact,
                      "answer_flags": answer_flags, "checks": checks,
                      "answered": (lead not in answer_checks.UNANSWERED_LEADS
                                   and any(c["section"] == ANSWER_SECTION for c in kept))
                      if question else None},
    }


@action(
    reads=["geocode", "intent", "deployment", "plan", *evidence.all_pebble_ids()],
    writes=["paragraph", "audit", "grounding", "citations", "trace"],
)
def reconcile_claims(state: State) -> State:
    """Burr action: LLM synthesis as verified structured claims."""
    trace = list(state.get("trace", []))
    rec = {"step": "reconcile_claims", "started_at": time.time(), "ok": True,
           "result": None, "err": None, "elapsed_s": 0.0}
    try:
        out = synthesize(state)
        g = out["grounding"]
        rec["result"] = {"tier": g["tier"], "model": g.get("model"), "attempts": g.get("attempts"),
                         "kept": len(g["claims"]), "dropped": len(g["dropped_claims"])}
    except Exception as e:  # noqa: BLE001 - surfaced via trace
        log.exception("claim synthesis failed")
        rec["ok"], rec["err"] = False, str(e)
        out = {"paragraph": "", "citations": {},
               "grounding": {"tier": "llm", "claims": [], "dropped_claims": [], "error": str(e)}}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)
    trace.append(rec)
    return state.update(
        paragraph=out["paragraph"],
        audit={"raw": out["paragraph"], "dropped": out["grounding"]["dropped_claims"],
               "tier": out["grounding"]["tier"]},
        grounding=out["grounding"], citations=out["citations"], trace=trace,
    )
