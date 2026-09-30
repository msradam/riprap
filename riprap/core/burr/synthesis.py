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
import re
import time
from dataclasses import dataclass

from burr.core import State, action

from riprap.core import llm
from riprap.core.burr import answer_checks, evidence
from riprap.core.burr.templated_reconciler import NON_SCOPE_FOOTER, _scope_header, compose_briefing

log = logging.getLogger("riprap.synthesis")

NO_EVIDENCE_LINE = "No grounded evidence for this section."
ANSWER_SECTION = "answer"
CANNOT_ANSWER = ("The sources consulted do not answer this question directly. "
                 "Here is what they show.")
POLICY_SECTION = "Policy context"

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


SYSTEM_PROMPT = """You write the body of a flood-exposure evidence briefing for one place, as JSON claims.

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
EXTRACTIVE_SYSTEM = """You answer a question about flood exposure at one place by choosing from numbered documents. You write no prose.

Return JSON with "answer": "lead" is one of yes, no, partly, count, cannot_answer, and "facts" lists the ids of one to four documents that support the lead, most relevant first. The reader sees a fixed phrase for the lead followed by those documents' text, word for word. Use "no" only when the facts report an absence (outside, none, zero). Use "partly" when some but not all of what was asked about is affected. Use "count" when the question asks how many or how much. Use "cannot_answer" with no facts when the documents do not answer the question. Use only ids from the list."""
LEADS = ("yes", "no", "partly", "count", "cannot_answer")
# The facts a forecast question is answered with, in order (refactor 8).
# What reports the present: a question about now quotes these, chosen in
# code (the model left out the sensors and the tide gauge).
LIVE_FACTS = ("nws_alerts", "floodnet", "noaa_tides", "usgs_gauges", "nws_obs")
FORECAST_FACTS = ("ttm_battery_surge", "ttm_311_forecast", "floodnet_forecast", "npcc4_slr",
                  "dep_moderate_2050", "dep_extreme_2080", "dep_moderate_2050_nta", "dep_extreme_2080_nta")
# The owner's decision after refactor 3: extractive cannot paraphrase, and
# it declines honestly when the evidence does not answer. The guarded mode
# it replaced (model-written answer claims, five answer rules and an
# entailment check) is kept at the git tag archive/guarded-answer-mode.
CHECKS_RUN = {
    "extractive": ["citations and numbers on every claim",
                   "lead rules on the answer, which is the cited text word for word"],
    None: ["citations and numbers on every claim"],
}


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
        return {"doc_id": doc, "in_lead": False} if doc else None
    if lead == "count":
        if kind_lead:
            return {"doc_id": rel, "in_lead": True} if rel else None
        doc = rel if rel in facts else next((f for f in facts if answer_checks.count_numbers(texts[f])), None)
        return {"doc_id": doc, "in_lead": False} if doc else None
    doc = answer_checks.past_event_source(question, focus, lead or "", texts, values)
    return {"doc_id": doc, "in_lead": False} if doc and doc in facts else None


def _extract(out: dict, question: str, texts: dict[str, str],
             values: dict | None = None, focus: dict | None = None) -> tuple[str, list[str], list[tuple[str, str]]]:
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
    return lead, facts, answer_checks.check_lead(lead, facts, question, texts, values)
# "facts" is set only by code: the facts with no yes or no in front of them.
LEAD_PHRASES = {"yes": "Yes.", "no": "No.", "partly": "In part.", "count": "From the sources consulted:",
                "facts": "From the sources consulted:"}


def _documents(state) -> tuple[list[Doc], list, object]:
    stones, registry = evidence.load(state.get("deployment"))
    heading = {s.id: evidence.stone_heading(s).rstrip(".") for s in stones.all()}
    items = evidence.collect(state, stones, registry) + evidence.policy_passages(state, registry)
    # Retrieved policy passages are verbatim quotes: their own section,
    # not labelled experimental (the retrieval summary sentence is).
    docs = [Doc(e.doc_id, POLICY_SECTION, e.text, False) if e.doc_id.startswith("rag_")
            else Doc(e.doc_id, heading.get(e.stone_id, e.stone_id), e.text, e.maturity == "experimental")
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


def _render(kept: list[dict], docs: list[Doc], sections: list[str], question: str = "",
            lead: str = "", empty: dict[str, list[str]] | None = None, brief: str | None = None) -> str:
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
        out = []
        for c in kept:
            if c["section"] != sec or restates(c):
                continue
            text = c["text"].rstrip(". ")
            if any(i in experimental for i in c["doc_ids"]) and "experimental" not in text.lower():
                text = f"Experimental: {text}"
            if len(c["doc_ids"]) == 1:  # a multi-sentence template fact: cite each numeric sentence
                out.append(evidence.cite(f"{text}.", c["doc_ids"][0]))
            else:
                out.append(f"{text} {''.join(f'[{i}]' for i in c['doc_ids'])}.")
        return " ".join(out)

    parts = [_scope_header()]
    if brief:
        parts.append(f"**In brief.**\n{brief}")
    if question:
        body = sentences(ANSWER_SECTION)
        parts.append("**Answer.**\n" + ((f"{lead} " if lead else "") + body if body else CANNOT_ANSWER))
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
                                          not in d.text.lower() else d.text, d.doc_id)
                            for d in docs if d.section == sec)
        parts.append(f"**{sec}.**\n" + (body or NO_EVIDENCE_LINE))
    parts.append(NON_SCOPE_FOOTER)
    return "\n\n".join(parts)


def synthesize(state) -> dict:
    """Run the claim loop. Returns paragraph, citations and a `grounding`
    record (kept claims, dropped claims with reasons, attempts, model).
    Falls back to the no-LLM briefing when no endpoint answers."""
    if state.get("intent") in ("not_implemented", "out_of_scope"):
        paragraph, _ = compose_briefing(state)
        return {"paragraph": paragraph, "citations": {},
                "grounding": {"tier": "llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    docs, items, stones = _documents(state)
    if not docs:
        from riprap.core.burr.templated_reconciler import nothing_built

        return {"paragraph": nothing_built(state), "citations": {},
                "grounding": {"tier": "llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    plan = state.get("plan") or {}
    question, focus = plan.get("question") or "", plan.get("focus")
    if not question and not llm_bare():
        paragraph, cites = compose_briefing(state)
        return {"paragraph": paragraph, "citations": cites,
                "grounding": {"tier": "no_llm", "claims": [], "dropped_claims": [], "attempts": 0,
                              "note": "No question was asked, so the cited evidence is shown without the LLM "
                                      "(RIPRAP_LLM_BARE=1 sends it to the LLM)."}}
    mode = "extractive" if question else None
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
    texts: dict[str, str] = {}
    for d in docs:
        texts[d.doc_id] = f"{texts.get(d.doc_id, '')} {d.text}".strip()
    # Numbers the user typed (the question, the place) may be restated;
    # they are the user's words, not claims about the data.
    exempt = frozenset(numbers_in(f"{question} {state.get('query') or ''} "
                                  f"{(state.get('geocode') or {}).get('address') or ''}"))
    schema = claims_schema(sorted(texts), sections)
    if mode == "extractive":
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
        if mode == "extractive":
            lead, facts, lead_hits = _extract(out, question, texts, values, focus)
            notes = [f"answer lead {lead!r}: {r}" for _, r in lead_hits]
        return kept, dropped, notes, (lead, facts, lead_hits)

    attempts, model, first_dropped, calls = 0, None, [], []
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
        paragraph, cites = compose_briefing(state)
        return {"paragraph": paragraph, "citations": cites,
                "grounding": {"tier": "no_llm", "fallback_reason": f"LLM unavailable: {e}",
                              "claims": [], "dropped_claims": [], "attempts": attempts,
                              "llm_calls": calls, "answer_mode": mode}}
    lead_phrase, answer_flags, lead, lead_fact = "", notes, None, None
    if mode == "extractive":
        lead, facts, lead_hits = answer
        rel = answer_checks.relevant_doc(question, texts)
        appended = bool(rel and rel not in facts and lead != "cannot_answer"
                        and any(k == "dropped_count" for k, _ in lead_hits))
        if appended:
            facts = [*facts, rel]  # the source the question is about, verbatim
        if (answer_checks.is_count_question(question) and lead not in ("count", "cannot_answer")
                and any(answer_checks.count_numbers(texts[f]) for f in facts)):
            lead = "count"  # a count or share question gets the number, not "In part."
        lead_hits = answer_checks.check_lead(lead, facts, question, texts, values)
        if appended and any(k != "dropped_count" for k, _ in lead_hits):
            lead, lead_hits = "facts", []  # the appended fact no longer fits the lead: drop the lead
        if any(k != "dropped_count" for k, _ in lead_hits):
            dropped = [*dropped, {"section": ANSWER_SECTION, "text": f"{lead}: {', '.join(facts)}",
                                  "doc_ids": facts, "numbers": [],
                                  "reason": "answer check: " + "; ".join(r for _, r in lead_hits)}]
            lead, facts = "cannot_answer", []
        if lead == "count" and rel in facts:
            facts = [rel]  # a count answers with the counted source alone, not unrelated facts
        experimental = frozenset(d.doc_id for d in docs if d.experimental)
        facts = sorted(facts, key=lambda f: f in experimental)  # experimental sources after all others
        kept = [*({"section": ANSWER_SECTION, "text": texts[f], "doc_ids": [f], "numbers": []} for f in facts),
                *kept]
        # Honest silence still shows what the sources say: facts under a
        # cannot-answer lead follow the silence line, with no key figure.
        lead_phrase = CANNOT_ANSWER if lead == "cannot_answer" and facts else LEAD_PHRASES.get(lead, "")
        if lead == "count" and rel in facts and (kl := answer_checks.kind_lead(question, texts, values)):
            lead_phrase = f"{kl} {lead_phrase}"
        lead_fact = _lead_fact(lead, facts, lead_phrase != LEAD_PHRASES.get(lead, ""), rel, question,
                               focus, texts, values, experimental)
    checks = CHECKS_RUN[mode]
    # A bare address opens with the same verified "In brief" lead as no-LLM mode.
    from riprap.core.burr.templated_reconciler import _lead

    brief = _lead(state, items) if not question and state.get("intent") == "single_address" else None
    paragraph = _render(kept, docs, sections, question, lead_phrase, empty, brief)
    # Every consulted source with a value is citable (its evidence row gets a
    # number), the ones the text cites first, in order of appearance, so the
    # numbering still starts with the answer. An uncited policy passage has
    # no row and is left out.
    cited = list(dict.fromkeys(re.findall(r"\[([a-z0-9_]+)\]", paragraph)))
    every = evidence.citations(items)
    citations = {k: every[k] for k in cited if k in every}
    citations.update({k: v for k, v in every.items() if k not in citations and not k.startswith("rag_")})
    return {
        "paragraph": paragraph + f"\n\nChecks run: {'; '.join(checks)}.",
        "citations": citations,
        "grounding": {"tier": "llm", "model": model, "attempts": attempts,
                      "claims": kept, "dropped_claims": dropped,
                      "retried_claims": first_dropped if attempts == 2 else [],
                      "n_kept": len(kept), "n_dropped": len(dropped), "llm_calls": calls,
                      "question": question, "n_documents": len(docs), "answer_mode": mode,
                      "answer_lead": lead, "lead_fact": lead_fact,
                      "answer_flags": answer_flags, "checks": checks,
                      "answered": (lead != "cannot_answer" and any(c["section"] == ANSWER_SECTION for c in kept))
                      if question else None},
    }


@action(
    reads=["geocode", "intent", "deployment", "plan", "policy_corpus", *evidence.all_pebble_ids()],
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
