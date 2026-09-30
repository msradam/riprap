"""Riprap query planner (LLM mode): turn a natural-language question into
a plan: intent, target place(s), the question and its focus, and the
pebbles needed to answer it, chosen from the deployment's catalog by
each manifest's `answers` line. `select_pebbles` (riprap/core/burr/
stones.py) adds the always-run floor. No-LLM mode uses the regex planner
in riprap/core/burr/intake.py and runs every pebble for the intent.

Output is a single JSON object with a fixed schema (see PLAN_SCHEMA).
The call passes plan_schema() as `response_format`, so the model
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
    "out_of_scope": (
        "Use when the question asks for something Riprap does not provide: "
        "advice on buying, renting or selling property, insurance prices, "
        "legal advice, a prediction for a specific future day, or a hazard "
        "other than flooding (heat, air quality, earthquakes). Still extract "
        "the place as a target and set focus.hazard."
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
    question: str = ""  # the question asked; "" when the input is only a place
    focus: dict | None = None  # {hazard, time_frame, assets}
    pebbles: list[str] | None = None  # sources chosen from the catalog
    catalog: list[str] | None = None  # ids that were offered


FOCUS_HAZARDS = ["flood", "heat", "air", "other"]
FOCUS_TIMES = ["past", "now", "future", "any"]
FOCUS_ASSETS = ["subway", "schools", "public_housing", "hospitals", "construction"]


PLAN_SCHEMA_DESC = """Return JSON with these keys:

  intent    one of the intents above
  targets   [{"type": "address", "text": ...}] for single_address, compare, live_now,
            out_of_scope; [{"type": "nta", "text": ...}] for neighborhood and
            development_check (a neighborhood name or a community district code such
            as QN12); compare has exactly two address targets
  focus     hazard (flood, heat, air, other), time_frame (past, now, future, any), and
            assets the question is about (subway, schools, public_housing, hospitals,
            construction), or [] for none
  pebbles   the few sources from the catalog needed to answer the question, usually
            one to five; [] when the input is only a place with no question
  rationale one short sentence
"""


SYSTEM_PROMPT = f"""You are Riprap's query planner. You read a flood-exposure question, decide which intent fits, which place it is about, and which of the listed data sources are needed to answer it. You do not have any data yet.

Intents:
{chr(10).join(f"  - {k}: {v}" for k, v in INTENTS.items())}

{PLAN_SCHEMA_DESC}
Choose sources whose description answers the question: history questions need past records, "right now" questions need live sources, scenario questions need the scenario layers, asset questions need that asset register. Use "point" sources for an address and "area" sources for a neighborhood or community district. Do not pick sources just in case."""


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
        "Riprap cannot say what it would have reported on a past date. It "
        "reports present flood exposure from today's sources; reconstructing "
        "an earlier date is on the roadmap but not yet available.",
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

def plan_schema(pebble_ids: list[str]) -> dict:
    """The plan's JSON schema; `pebbles` items are an enum of the ids the
    catalog offered, so the decoder cannot produce any other id."""
    return {
        "type": "object",
        "additionalProperties": False,
        # The question is the user's own text, set in code (_validate); the
        # model echoing it cost about 25 generated tokens, a second per query.
        "required": ["intent", "targets", "focus", "pebbles", "rationale"],
        "properties": {
            "intent": {"type": "string", "enum": sorted(INTENTS)},
            "targets": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["type", "text"],
                "properties": {"type": {"type": "string", "enum": ["address", "nta", "borough", "nyc"]},
                               "text": {"type": "string"}},
            }},
            "focus": {"type": "object", "additionalProperties": False,
                      "required": ["hazard", "time_frame", "assets"],
                      "properties": {
                          "hazard": {"type": "string", "enum": FOCUS_HAZARDS},
                          "time_frame": {"type": "string", "enum": FOCUS_TIMES},
                          "assets": {"type": "array", "items": {"type": "string", "enum": FOCUS_ASSETS}},
                      }},
            "pebbles": {"type": "array", "items": {"type": "string", "enum": pebble_ids}},
            "rationale": {"type": "string"},
        },
    }


def catalog(registry) -> list[dict]:
    """The sources the planner may choose from: id, stone, scope and the
    manifest's one-line `answers`. No evidence, so the prompt stays short."""
    return [{"id": p.id, "stone": p.stone,
             "scope": "area" if p.manifest.spatial.scope == "polygon" else "point",
             "answers": p.manifest.answers or p.manifest.title}
            for p in sorted(registry.all(), key=lambda p: (p.stone, p.id)) if p.stone != "capstone"]


def _catalog_registry():
    import os  # noqa: PLC0415

    from riprap.core.pebbles.bridge import get_registry  # noqa: PLC0415

    return get_registry(os.environ.get("RIPRAP_DEPLOYMENT", "nyc").rstrip("/").split("/")[-1])


def plan(query: str, on_token=None, ledger: list | None = None, registry=None) -> Plan:
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

    cat = catalog(registry or _catalog_registry())
    lines = "\n".join(f"  {c['id']} ({c['stone']}, {c['scope']}): {c['answers']}" for c in cat)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nData sources:\n" + lines},
        {"role": "user",   "content": query},
    ]
    from riprap.core import llm  # noqa: PLC0415

    ids = [c["id"] for c in cat]
    d, _model = llm.chat_json(messages, plan_schema(ids), name="plan", ledger=ledger)
    log.info("planner plan: %s", str(d)[:400])
    if on_token:
        on_token(json.dumps(d))
    return _validate(d, raw_query=query, catalog_ids=ids)


_QUESTION_WORDS = frozenset(
    "what whats how has have had is are was were will would does did do can could should "
    "which when where why who whom show tell list compare any many much".split())


def is_bare_place(raw_query: str, targets: list[dict[str, str]]) -> bool:
    """True when the input is only a place: no '?' and no question word
    once the target text is removed.

    ponytail: word list, so "flooding at 80 Pioneer Street" reads as bare
    and gets the full briefing (the safe side); a classifier if that bites."""
    if "?" in raw_query:
        return False
    rest = raw_query.lower()
    for t in targets:
        rest = rest.replace(t.get("text", "").lower(), " ")
    return not any(w in _QUESTION_WORDS for w in re.findall(r"[a-z]+", rest))


def _validate(d: dict[str, Any], raw_query: str, catalog_ids: list[str] | None = None) -> Plan:  # TODO(cleanup): cc-grade-D (23)
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

    if intent == "compare":
        # The planner can name one place twice; that is not a comparison.
        distinct = list({t["text"].lower().strip(" ,."): t for t in targets}.values())
        if len(distinct) < 2:
            intent, targets = "single_address", distinct[:1] or [{"type": "address", "text": raw_query}]
    rationale = (d.get("rationale") or "").strip()[:300] or "(no rationale provided)"
    # The question is the user's own text, decided in code: the model
    # echoes a bare address or invents "What is the flood risk for X?".
    question = "" if is_bare_place(raw_query, targets) else raw_query.strip()
    focus = d.get("focus") if isinstance(d.get("focus"), dict) else {}
    focus = {"hazard": focus.get("hazard") if focus.get("hazard") in FOCUS_HAZARDS else "flood",
             "time_frame": focus.get("time_frame") if focus.get("time_frame") in FOCUS_TIMES else "any",
             "assets": [a for a in focus.get("assets") or [] if a in FOCUS_ASSETS]}
    offered = set(catalog_ids or [])
    # The schema enum already restricts ids; validate anyway.
    pebbles = [p for p in dict.fromkeys(d.get("pebbles") or []) if p in offered]
    return Plan(intent=intent, targets=targets, rationale=rationale, question=question,
                focus=focus, pebbles=pebbles, catalog=catalog_ids)
