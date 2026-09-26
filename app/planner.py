"""Riprap query planner (LLM mode): route a natural-language query to an
intent and its target place(s). The Burr app then runs the pebbles for
that intent. No-LLM mode uses the regex planner in
riprap/core/burr/intake.py instead.

Output is a single JSON object with a fixed schema (see PLAN_SCHEMA).
The call passes PLAN_JSON_SCHEMA as `response_format`, so the model
cannot emit malformed structure. A deterministic post-validator
sanity-checks the plan against the supported intents.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("riprap.planner")

# ---- Plan schema -----------------------------------------------------------
#
# The set of intents Riprap currently supports. Every plan picks exactly
# one; riprap/core/burr/app.py maps the intent to its graph branch.

INTENTS = {
    "single_address": (
        "Use when the query refers to a SPECIFIC LOCATABLE POINT — either "
        "(a) a street address with house number + street name (e.g. "
        "'116-50 Sutphin Blvd', '350 5th Ave Manhattan'), or (b) a named "
        "development, complex, or housing project that geocodes to a single "
        "location (e.g. 'Coney Island I Houses', 'Carleton Manor Houses', "
        "'Vladeck Houses'). If the query names only a general neighborhood "
        "or borough with no specific address or named building, use "
        "'neighborhood'."
    ),
    "neighborhood": (
        "Use when the query names a NEIGHBORHOOD or BOROUGH with no "
        "specific street address (e.g. 'Brighton Beach', 'Carroll "
        "Gardens', 'Brooklyn', 'is Red Hook at risk?', 'show me Hollis "
        "flooding'). Skip geocoding; resolve to NTA polygon(s) and run "
        "polygon-level evidence."
    ),
    "live_now": (
        "User asked about CURRENT CONDITIONS in NYC (e.g. 'is there "
        "flooding right now', 'what's the surge tonight'). Skip historic "
        "and modeled layers; focus on live sources."
    ),
    "development_check": (
        "User asked about CURRENT/IN-PROGRESS CONSTRUCTION OR DEVELOPMENT "
        "in a place, with implicit interest in flood risk for those projects "
        "(e.g. 'what are they building in Gowanus and is it risky?', "
        "'show me new construction in flood zones', 'are there projects "
        "underway in Red Hook?'). Resolve target to NTA polygon, pull active "
        "DOB construction permits inside it, cross-reference each project "
        "with Sandy + DEP flood layers, return a flagged-projects list."
    ),
    "compare": (
        "Use ONLY when the query explicitly compares TWO specific street "
        "ADDRESSES (e.g. 'compare 80 Pioneer St Brooklyn to 100 Gold St "
        "Manhattan', 'which is riskier: X or Y?', 'X vs Y flood risk'). "
        "Extract BOTH full street addresses into targets as two separate "
        "{type: 'address', text: ...} objects."
    ),
}

@dataclass
class Plan:
    intent: str
    targets: list[dict[str, str]]
    rationale: str


PLAN_SCHEMA_DESC = """Return JSON with exactly these keys:

{
  "intent": one of the intents above,
  "targets": [
    {"type": "address", "text": "<address text>"}    for single_address, compare, live_now
    {"type": "nta",     "text": "<neighborhood>"}    for neighborhood, development_check
    {"type": "borough", "text": "<borough>"}         for a whole borough
    {"type": "nyc",     "text": "NYC"}               for live_now with no specific place
  ],
  "rationale": "<one short sentence>"
}

Rules:
- Pick ONE intent.
- compare: exactly two targets, both type "address".
- Extract place names from the query text: "in Gowanus" gives {"type": "nta", "text": "Gowanus"}.
"""


SYSTEM_PROMPT = f"""You are Riprap's query planner. You read a flood-exposure question and decide which intent fits and which place or places it is about. You do not have any data.

Intents:
{chr(10).join(f"  - {k}: {v}" for k, v in INTENTS.items())}

{PLAN_SCHEMA_DESC}"""


# ---- Not-implemented short-circuits ----------------------------------------
#
# These patterns are well-defined feature gaps. Returning a graceful message
# is better than routing them into an intent that silently fails.

_RETROSPECTIVE_RE = re.compile(
    r"(?:what\s+would\s+(?:riprap|you|it)\s+have\s+said"
    r"|what\s+(?:was|were)\s+(?:the\s+)?(?:flood|risk|status)"
    r"|(?:as\s+of|on)\s+(?:august|september|october|november|december|january|"
    r"february|march|april|may|june|july)\s+\d"
    r"|on\s+(?:the\s+date\s+of|hurricane\s+ida|hurricane\s+sandy)"
    r"|(?:september|august|october)\s+\d{1,2},?\s+20\d{2}"
    r")",
    re.IGNORECASE,
)

_RANKING_RE = re.compile(
    r"(?:rank\s+(?:the\s+)?top\s+\d"
    r"|top\s+\d+\s+\w+\s+by\s+flood"
    r"|intersect(?:ed)?\s+with\s+(?:dac|ejnyc|social\s+vulnerability)"
    r"|sort(?:ed)?\s+by\s+(?:flood\s+)?(?:exposure|risk|score)"
    r")",
    re.IGNORECASE,
)

NOT_IMPLEMENTED_INTENTS = {
    "retrospective": (
        _RETROSPECTIVE_RE,
        "Historical-date mode (\"what would Riprap have said on [date]\") "
        "is on the roadmap but not yet available. Riprap currently reports "
        "present-state flood exposure; past-state reconstruction is planned "
        "for a future release.",
    ),
    "ranking": (
        _RANKING_RE,
        "Cross-development ranking queries (\"rank top N by flood exposure\", "
        "\"intersect with DAC designation\") require a cross-register join "
        "that is on the roadmap but not yet available. Try a specific address "
        "or neighborhood instead.",
    ),
}


def _not_implemented_message(query: str) -> str | None:
    """Return a user-facing message if the query matches a known feature gap,
    else None."""
    for _name, (pattern, message) in NOT_IMPLEMENTED_INTENTS.items():
        if pattern.search(query):
            return message
    return None


# ---- Planner call ----------------------------------------------------------

PLAN_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "targets", "rationale"],
    "properties": {
        "intent": {"type": "string", "enum": sorted(INTENTS)},
        "targets": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["type", "text"],
            "properties": {"type": {"type": "string", "enum": ["address", "nta", "borough", "nyc"]},
                           "text": {"type": "string"}},
        }},
        "rationale": {"type": "string"},
    },
}


def plan(query: str, on_token=None, ledger: list | None = None) -> Plan:
    """Ask Granite 4.1 to plan a query. Returns a validated Plan.

    If on_token is provided, the planner runs in streaming mode and
    on_token(delta) is called for each chunk of the JSON output as
    Granite generates. The streaming endpoint uses this to show the
    agent's reasoning forming live in the UI.
    """
    msg = _not_implemented_message(query)
    if msg:
        log.info("planner: short-circuit not_implemented for query %r", query[:80])
        if on_token:
            on_token(json.dumps({"intent": "not_implemented", "message": msg}))
        return Plan(intent="not_implemented", targets=[], rationale=msg)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": query},
    ]
    from riprap.core import llm  # noqa: PLC0415

    d, _model = llm.chat_json(messages, PLAN_JSON_SCHEMA, name="plan", ledger=ledger)
    log.info("planner plan: %s", str(d)[:400])
    if on_token:
        on_token(json.dumps(d))
    return _validate(d, raw_query=query)


def _validate(d: dict[str, Any], raw_query: str) -> Plan:  # TODO(cleanup): cc-grade-D (23)
    """Defensive parse + sanitize. The model might pick an invalid intent
    or no usable target; fall back to single_address
    with the raw query as the address (the most common case)."""
    intent = d.get("intent")
    if intent not in INTENTS:
        log.warning("planner picked invalid intent %r; defaulting to single_address", intent)
        intent = "single_address"

    raw_targets = d.get("targets") or []
    targets: list[dict[str, str]] = []
    for t in raw_targets:
        if not isinstance(t, dict):
            continue
        t_type = t.get("type")
        t_text = (t.get("text") or "").strip()
        if not t_text or t_type not in ("address", "nta", "borough", "nyc"):
            continue
        targets.append({"type": t_type, "text": t_text})
    if not targets:
        # Reasonable fallback: assume the raw query IS the target
        if intent == "single_address":
            targets = [{"type": "address", "text": raw_query}]
        elif intent == "neighborhood":
            targets = [{"type": "nta", "text": raw_query}]
        elif intent == "compare":
            # Planner failed to extract two addresses — treat whole query as
            # single address so the caller gets at least one result rather
            # than a confusing empty response.
            log.warning("compare intent but no valid targets extracted; "
                        "falling back to single raw query")
            targets = [{"type": "address", "text": raw_query}]
        else:
            targets = [{"type": "nyc", "text": "NYC"}]

    rationale = (d.get("rationale") or "").strip()[:300] or "(no rationale provided)"
    return Plan(intent=intent, targets=targets, rationale=rationale)
