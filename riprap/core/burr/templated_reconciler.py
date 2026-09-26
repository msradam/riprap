"""Templated reconciler: the no-LLM Capstone.

In no-LLM mode the Burr app ends with `reconcile_templated` instead of
the LLM synthesis. The result is a deterministic briefing built from
each pebble's `narration.template` filled from its value dict (see
`evidence.py`).

Why this exists:
  * NGO / Pi-class deployments without a GPU or even a CPU LLM
  * Civic-tech audit: every claim is traceable to a manifest entry by
    construction, with no hallucination surface
  * Latency: sub-second briefing prose. The whole `/api/agent` round
    trip lands in under 30 s end-to-end, dominated by live HTTP probes
  * A baseline that the LLM tier can be compared against

The output shape (paragraph, audit, grounding, citations) matches the
LLM tier, so the frontend renders both the same way.
"""

from __future__ import annotations

import time

from burr.core import State, action

from riprap.core.burr import evidence


def _scope_header() -> str:
    """Hazard-agnostic scope declaration. Riprap-flood ships with the
    canonical flood phrasing; other deployments can override the wording
    by setting RIPRAP_BRIEFING_SCOPE (e.g. "automated heat-exposure
    briefing"). Defaults to the safe generic "hazard-exposure briefing."
    """
    import os

    scope_kind = os.environ.get("RIPRAP_BRIEFING_SCOPE", "hazard-exposure")
    return (
        f"This is an automated {scope_kind} briefing produced by Riprap from "
        "live and baked data sources. It is informational only and not a "
        "substitute for a professional risk assessment."
    )


NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing does not assess title, structural "
    "condition, or compliance with specific zoning rules. Where a probe "
    "was offline at run time, the relevant section omits that signal."
)


def compose_briefing(state) -> tuple[str, dict[str, dict]]:
    """One section per Stone (stones.yaml order), one cited sentence per
    pebble with a value. Returns (paragraph, citations by doc_id). A
    not_implemented query gets the planner's explanation instead."""
    if state.get("intent") == "not_implemented":
        return (state.get("plan") or {}).get("rationale") or "Riprap cannot answer this query.", {}
    stones, registry = evidence.load(state.get("deployment"))
    items = evidence.collect(state, stones, registry)
    sections = [_scope_header()]
    for stone in stones.all():
        if stone.id == "capstone":
            continue  # Capstone is the synthesis output, not a data stone
        body = " ".join(evidence.cite(e.text, e.doc_id) for e in items if e.stone_id == stone.id)
        if body:
            sections.append(f"**{evidence.stone_heading(stone)}**\n{body}")
    if len(sections) == 1:
        return "No grounded data available for this address.", {}
    sections.append(NON_SCOPE_FOOTER)
    return "\n\n".join(sections), evidence.citations(items)


@action(
    reads=["geocode", "intent", "deployment", "policy_corpus", *evidence.all_pebble_ids()],
    writes=["paragraph", "audit", "grounding", "citations", "trace"],
)
def reconcile_templated(state: State) -> State:
    """Burr action: the no-LLM briefing. No model call; every sentence is
    a manifest template filled from a pebble value."""
    trace = list(state.get("trace", []))
    rec = {"step": "reconcile_templated", "started_at": time.time(), "ok": True,
           "result": None, "err": None, "elapsed_s": 0.0}
    try:
        paragraph, cites = compose_briefing(state)
        rec["result"] = {"n_chars": len(paragraph), "n_citations": len(cites), "tier": "no_llm"}
    except Exception as e:  # noqa: BLE001 - surfaced via trace
        rec["ok"], rec["err"] = False, str(e)
        paragraph, cites = "", {}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
    trace.append(rec)
    return state.update(
        paragraph=paragraph,
        audit={"raw": paragraph, "dropped": [], "tier": "no_llm"},
        grounding={"tier": "no_llm", "claims": [], "dropped_claims": []},
        citations=cites,
        trace=trace,
    )
