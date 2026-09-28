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
from riprap.core.burr import answer_checks, entailment, evidence
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

EXTRACTIVE_RULES = """
A question was asked. Do not write claims in section "answer". Instead fill "answer": "lead" is one of yes, no, partly, count, cannot_answer, and "facts" lists the ids of one to four documents that support the lead, most relevant first. The reader sees a fixed phrase for the lead followed by those documents' text, word for word. Use "no" only when the facts report an absence (outside, none, zero). Use "partly" when some but not all of what was asked about is affected. Use "count" when the question asks how many or how much. Use "cannot_answer" with no facts when the documents do not answer the question. Then write the other sections as usual.
"""
GUARD_RULES = """
Answer claims are also checked in code. Do not say no, none or not when a cited document reports something. Do not write "all", "both" or "the <things> are" when a document counts fewer inside than in total; give the count ("3 of 5"). Do not join two documents with "which means", "indicating" or "therefore", and do not state a warning or forecast as something happening. State an elevation with its datum. Include the count or value that answers the question.
"""
LEADS = ("yes", "no", "partly", "count", "cannot_answer")
# The owner's decision after refactor 3: extractive cannot paraphrase, and
# it declines honestly when the evidence does not answer.
DEFAULT_ANSWER_MODE = "extractive"


def answer_mode() -> str:
    """RIPRAP_ANSWER_MODE: 'guarded' (model-written answer claims, checked
    by answer_checks) or 'extractive' (a lead plus template sentences)."""
    import os

    mode = os.environ.get("RIPRAP_ANSWER_MODE", DEFAULT_ANSWER_MODE).strip().lower()
    return mode if mode in ("guarded", "extractive") else DEFAULT_ANSWER_MODE


def _guard(kept: list[dict], dropped: list[dict], texts: dict[str, str],
           question: str, values: dict | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Guarded mode: an answer claim failing an answer check is dropped with
    the reason. An omitted count asks for a retry but drops nothing (the
    claims that were written are still true)."""
    out = []
    for c in kept:
        hits = answer_checks.check_claim(c["text"], c["doc_ids"], texts) if c["section"] == ANSWER_SECTION else []
        if hits:
            dropped = [*dropped, {**c, "reason": "answer check: " + "; ".join(f"{k}: {r}" for k, r in hits)}]
        else:
            out.append(c)
    notes = [f"the answer {r}" for _, r in answer_checks.check_answer(
        [c["text"] for c in out if c["section"] == ANSWER_SECTION], question, texts, values)]
    return out, dropped, notes


def _checks_run(mode: str | None, entail_info: dict) -> list[str]:
    """What was verified, in words, for the line at the end of the briefing."""
    checks = ["citations and numbers on every claim"]
    if mode == "guarded":
        checks.append("five answer rules on the answer")
        checks.append(f"{entail_info['label']} on the answer" if entail_info.get("ran")
                      else entail_info.get("reason", "entailment check not run"))
    elif mode == "extractive":
        checks.append("lead rules on the answer; no entailment check needed, since the answer is the "
                      "cited text word for word")
    return checks


def _extract(out: dict, question: str, texts: dict[str, str],
             values: dict | None = None) -> tuple[str, list[str], list[tuple[str, str]]]:
    a = out.get("answer") or {}
    lead = a.get("lead") if a.get("lead") in LEADS else "cannot_answer"
    facts = [f for f in dict.fromkeys(a.get("facts") or []) if f in texts]
    return lead, facts, answer_checks.check_lead(lead, facts, question, texts, values)
# "facts" is set only by code: the facts with no yes or no in front of them.
LEAD_PHRASES = {"yes": "Yes.", "no": "No.", "partly": "In part.", "count": "From the sources consulted:",
                "facts": "From the sources consulted:"}

ANSWER_RULES = """
A question was asked. First write one to three claims in section "answer" that answer it directly, using only the documents, with the same citation and number rules. Lead with the fact that answers the question. If the documents do not contain the answer, write no "answer" claims; do not guess. Then write the other sections as usual.
"""


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
            lead: str = "", empty: dict[str, list[str]] | None = None) -> str:
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
        return {"paragraph": "No grounded data available for this address.", "citations": {},
                "grounding": {"tier": "llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    plan = state.get("plan") or {}
    question, focus = plan.get("question") or "", plan.get("focus")
    mode = answer_mode() if question else None
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
    extra = (ANSWER_SECTION,) if mode == "guarded" else ()
    # Numbers the user typed (the question, the place) may be restated;
    # they are the user's words, not claims about the data.
    exempt = frozenset(numbers_in(f"{question} {state.get('query') or ''} "
                                  f"{(state.get('geocode') or {}).get('address') or ''}"))
    schema = claims_schema(sorted(texts), [*extra, *sections])
    if mode == "extractive":
        schema["properties"]["answer"] = {
            "type": "object", "additionalProperties": False, "required": ["lead", "facts"],
            "properties": {"lead": {"type": "string", "enum": list(LEADS)},
                           "facts": {"type": "array", "items": {"type": "string", "enum": sorted(texts)},
                                     "maxItems": 4}}}
        schema["required"] = [*schema["required"], "answer"]
    rules = {"guarded": ANSWER_RULES + GUARD_RULES, "extractive": EXTRACTIVE_RULES}.get(mode or "", "")
    messages = [{"role": "system", "content": SYSTEM_PROMPT + rules},
                {"role": "user", "content": _user_prompt(docs, sections, question, focus)}]

    entail_info: dict = {}

    def check(out: dict):
        nonlocal entail_info
        kept, dropped = verify(out.get("claims") or [], docs, extra, exempt)
        notes: list[str] = []
        lead, facts, lead_hits = "", [], []
        if mode == "guarded":
            kept, dropped, notes = _guard(kept, dropped, texts, question, values)
            kept, failed, entail_info = entailment.check(kept, texts)
            dropped = [*dropped, *failed]
        elif mode == "extractive":
            lead, facts, lead_hits = _extract(out, question, texts, values)
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
    lead_phrase, answer_flags, lead = "", notes, None
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
        kept = [*({"section": ANSWER_SECTION, "text": texts[f], "doc_ids": [f], "numbers": []} for f in facts),
                *kept]
        lead_phrase = LEAD_PHRASES.get(lead, "")
        if lead == "count" and rel in facts and (kl := answer_checks.kind_lead(question, texts, values)):
            lead_phrase = f"{kl} {lead_phrase}"
    checks = _checks_run(mode, entail_info)
    cited = {i for c in kept for i in c["doc_ids"]}
    return {
        "paragraph": _render(kept, docs, sections, question, lead_phrase, empty)
        + f"\n\nChecks run: {'; '.join(checks)}.",
        "citations": {k: v for k, v in evidence.citations(items).items() if k in cited},
        "grounding": {"tier": "llm", "model": model, "attempts": attempts,
                      "claims": kept, "dropped_claims": dropped,
                      "retried_claims": first_dropped if attempts == 2 else [],
                      "n_kept": len(kept), "n_dropped": len(dropped), "llm_calls": calls,
                      "question": question, "n_documents": len(docs), "answer_mode": mode,
                      "answer_lead": lead,
                      "answer_flags": answer_flags, "checks": checks, "entailment": entail_info,
                      "answered": any(c["section"] == ANSWER_SECTION for c in kept) if question else None},
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
