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
from riprap.core.burr import evidence
from riprap.core.burr.templated_reconciler import NON_SCOPE_FOOTER, _scope_header, compose_briefing

log = logging.getLogger("riprap.synthesis")

NO_EVIDENCE_LINE = "No grounded evidence for this section."
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


def verify(claims: list[dict], docs: list[Doc]) -> tuple[list[dict], list[dict]]:
    """Split claims into (kept, dropped); each dropped claim carries a
    `reason`."""
    by_id = {d.doc_id: d for d in docs}
    sections = {d.section for d in docs}
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
            stated = set(claim["numbers"]) | set(numbers_in(text))
            missing = sorted(n for n in stated
                             if n.lstrip("+-") not in _NOT_MEASUREMENTS
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


def _user_prompt(docs: list[Doc], sections: list[str]) -> str:
    lines = []
    for sec in sections:
        lines.append(f"## {sec}")
        lines += [f"[{d.doc_id}] {d.text}" for d in docs if d.section == sec]
        lines.append("")
    return "Documents, grouped by section:\n\n" + "\n".join(lines) + "\nReturn the claims as JSON."


def _render(kept: list[dict], docs: list[Doc], sections: list[str]) -> str:
    experimental = {d.doc_id for d in docs if d.experimental}
    parts = [_scope_header()]
    for sec in sections:
        sentences = []
        for c in kept:
            if c["section"] != sec:
                continue
            text = c["text"].rstrip(". ")
            if any(i in experimental for i in c["doc_ids"]) and "experimental" not in text.lower():
                text = f"Experimental: {text}"
            sentences.append(f"{text} {''.join(f'[{i}]' for i in c['doc_ids'])}.")
        parts.append(f"**{sec}.**\n" + (" ".join(sentences) or NO_EVIDENCE_LINE))
    parts.append(NON_SCOPE_FOOTER)
    return "\n\n".join(parts)


def synthesize(state) -> dict:
    """Run the claim loop. Returns paragraph, citations and a `grounding`
    record (kept claims, dropped claims with reasons, attempts, model).
    Falls back to the no-LLM briefing when no endpoint answers."""
    docs, items, _ = _documents(state)
    if not docs:
        return {"paragraph": "No grounded data available for this address.", "citations": {},
                "grounding": {"tier": "llm", "claims": [], "dropped_claims": [], "attempts": 0}}
    sections = list(dict.fromkeys(d.section for d in docs))
    schema = claims_schema(sorted({d.doc_id for d in docs}), sections)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(docs, sections)}]
    attempts, model, first_dropped = 0, None, []
    try:
        out, model = llm.chat_json(messages, schema, name="claims")
        attempts = 1
        kept, dropped = verify(out.get("claims") or [], docs)
        first_dropped = dropped
        if dropped:
            failures = "\n".join(f'- "{d["text"]}": {d["reason"]}' for d in dropped)
            messages += [
                {"role": "assistant", "content": json.dumps(out)},
                {"role": "user", "content": "These claims failed verification:\n" + failures +
                 "\nReturn the full claim list again. Fix these claims using only numbers "
                 "that appear in their cited documents, or leave them out."},
            ]
            out, model = llm.chat_json(messages, schema, name="claims")
            attempts = 2
            kept, dropped = verify(out.get("claims") or [], docs)
    except llm.LLMUnavailable as e:
        paragraph, cites = compose_briefing(state)
        return {"paragraph": paragraph, "citations": cites,
                "grounding": {"tier": "no_llm", "fallback_reason": f"LLM unavailable: {e}",
                              "claims": [], "dropped_claims": [], "attempts": attempts}}
    cited = {i for c in kept for i in c["doc_ids"]}
    return {
        "paragraph": _render(kept, docs, sections),
        "citations": {k: v for k, v in evidence.citations(items).items() if k in cited},
        "grounding": {"tier": "llm", "model": model, "attempts": attempts,
                      "claims": kept, "dropped_claims": dropped,
                      "retried_claims": first_dropped if attempts == 2 else [],
                      "n_kept": len(kept), "n_dropped": len(dropped)},
    }


@action(
    reads=["geocode", "intent", "deployment", "policy_corpus", *evidence.all_pebble_ids()],
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
