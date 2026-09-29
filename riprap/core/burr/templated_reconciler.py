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
from riprap.core.pebbles.shapers.dep_scenario import PLAIN


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
        "live and precomputed data sources. It is informational only and not a "
        "substitute for a professional risk assessment."
    )


SCOPE_REFUSAL = (
    "Riprap does not answer this question. It reports public flood evidence for a "
    "place: flood maps, past flood records, live sensors and forecasts, each cited to "
    "its source. It does not give advice on buying, renting or insuring property, "
    "legal advice, or a prediction for a specific day. For those, consult a licensed "
    "professional; for a regulatory flood determination, use FEMA's Flood Map "
    "Service Center (msc.fema.gov)."
)
COVERAGE_REFUSAL = (
    "Riprap's New York City deployment covers flood evidence only. It has no {what} "
    "sources for this place, so it cannot answer this question. Ask about flooding "
    "at this address to see what it does cover."
)
_HAZARD_WORDS = {"heat": "heat", "air": "air-quality"}


def refusal(state) -> str:
    """Fixed text for queries Riprap does not answer; never model prose."""
    plan = state.get("plan") or {}
    if state.get("intent") == "not_implemented":
        return plan.get("rationale") or "Riprap cannot answer this query."
    hazard = (plan.get("focus") or {}).get("hazard", "flood")
    if hazard != "flood":
        return COVERAGE_REFUSAL.format(what=_HAZARD_WORDS.get(hazard, "non-flood"))
    return SCOPE_REFUSAL


NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing does not assess title, structural "
    "condition, or compliance with specific zoning rules. Where a probe "
    "was offline at run time, the relevant section omits that signal."
)


# The three point DEP scenarios, in time order, and the words for each.
# "2050 sea-level rise" (not "2050 sea level") is the phrase the disclosure
# check reads as a time horizon.
_DEP_POINT = {"dep_moderate_current": "current sea level with 2.13 in/hr of rain",
              "dep_moderate_2050": "2050 sea-level rise with 2.13 in/hr",
              "dep_extreme_2080": "2080 sea-level rise with 3.66 in/hr"}
_DEP_HORIZON = {"dep_moderate_current": "current", "dep_moderate_2050": "2050", "dep_extreme_2080": "2080"}


def _dep_sentence(state, items) -> str | None:
    """The DEP scenario sentences as one sentence naming each scenario's
    result, each part cited. None unless two or more scenarios ran."""
    parts = []
    for pid, words in _DEP_POINT.items():
        e = next((e for e in items if e.pebble_id == pid), None)
        v = state.get(pid) if e else None
        if isinstance(v, dict) and "depth_class" in v:
            result = ("outside the modeled flooding" if not v["depth_class"]
                      else PLAIN.get(v["depth_class"], f"{v['depth_label']} flooding"))
            parts.append(f"{words}, {result} [{e.doc_id}]")
    return f"NYC DEP stormwater scenarios at this address: {'; '.join(parts)}." if len(parts) >= 2 else None


def _lead(state, items) -> str | None:
    """A bare-address briefing's opening: the Sandy footprint, the FEMA
    zone, the DEP scenarios and the 311 count, each from its verified
    template sentence's value and cited, then checked by the claim
    verifier like any claim. Parts that fail the check are left out."""
    from riprap.core.burr.synthesis import Doc, verify

    by_pebble = {e.pebble_id: e for e in items}
    claims = []

    def add(pid: str, text: str, ids: list[str] | None = None):
        claims.append({"section": "lead", "text": text, "doc_ids": ids or [by_pebble[pid].doc_id]})

    if "sandy" in by_pebble and isinstance(state.get("sandy"), dict):
        add("sandy", f"{'inside' if state['sandy'].get('inside') else 'outside'} the 2012 Sandy inundation footprint")
    fema = state.get("fema_nfhl")
    if "fema_nfhl" in by_pebble and isinstance(fema, dict) and fema.get("fld_zone"):
        add("fema_nfhl", f"in FEMA flood zone {fema['fld_zone']}")
    dep = {p: state[p] for p in _DEP_POINT if p in by_pebble and isinstance(state.get(p), dict)}
    if dep:
        ids = [by_pebble[p].doc_id for p in dep]
        wet = [p for p, v in dep.items() if v.get("depth_class")]

        def horizons(ps) -> str:
            """'current, 2050 and 2080 sea-level rise': the disclosure check needs a horizon."""
            h = [_DEP_HORIZON[p] for p in ps]
            if h == ["current"]:
                return "current sea level (the near term)"
            return (h[0] if len(h) == 1 else f"{', '.join(h[:-1])} and {h[-1]}") + " sea-level rise"

        if not wet:
            add("", f"outside the modeled flooding in the DEP stormwater scenarios for {horizons(dep)}", ids)
        else:
            add("", f"inside the modeled flooding in the DEP stormwater scenario{'s' if len(wet) > 1 else ''} "
                    f"for {horizons(wet)}", [by_pebble[p].doc_id for p in wet])
    n311 = state.get("nyc311")
    if "nyc311" in by_pebble and isinstance(n311, dict) and "n" in n311:
        n = f"{'At least ' if n311.get('capped') else ''}{n311['n']}"
        add("nyc311", f"{n} flood-related 311 complaint{'s were' if n311['n'] != 1 else ' was'} filed within "
                      f"{n311['radius_m']:.0f} m in the last {n311['years']} years")
    docs = [Doc(e.doc_id, "lead", e.text, False) for e in items]
    kept, _ = verify(claims, docs)
    cited = [(c["doc_ids"], f"{c['text']} {''.join(f'[{i}]' for i in c['doc_ids'])}") for c in kept]
    where = [t for ids, t in cited if "nyc311" not in ids]
    count = [t for ids, t in cited if "nyc311" in ids]
    out = []
    if where:
        where = where if len(where) < 2 else [*where[:-1], f"and {where[-1]}"]
        out.append(f"This address is {(', ' if len(where) > 2 else ' ').join(where)}.")
    out += [f"{t}." for t in count]
    return " ".join(out) or None


def nothing_built(state) -> str:
    """The briefing when no source produced evidence: which sources failed
    to respond and which answered with nothing, not a bare "no data"."""
    ok = {t.get("step"): t.get("ok") for t in state.get("trace") or []}
    consulted = state.get("consulted") or []
    failed = [e["title"] for e in consulted if ok.get(e["id"]) is False]
    empty = [e["title"] for e in consulted if ok.get(e["id"]) is not False]
    out = [f"{_scope_header()}\n\nRiprap could not build this briefing: no source it consulted returned evidence "
           "for this place."]
    if failed:
        out.append(f"Failed to respond: {'; '.join(failed)}.")
    if empty:
        out.append(f"Answered with nothing for this place: {'; '.join(empty)}.")
    return " ".join(out)


def compose_briefing(state) -> tuple[str, dict[str, dict]]:
    """One section per Stone (stones.yaml order), one cited sentence per
    pebble with a value, the DEP scenarios merged into one sentence.
    A bare-address briefing opens with a short cited lead. Returns
    (paragraph, citations by doc_id). A not_implemented query gets the
    planner's explanation instead."""
    if state.get("intent") in ("not_implemented", "out_of_scope"):
        return refusal(state), {}
    stones, registry = evidence.load(state.get("deployment"))
    items = evidence.collect(state, stones, registry)
    sections = [_scope_header()]
    bare = state.get("intent") == "single_address" and not (state.get("plan") or {}).get("question")
    lead = _lead(state, items) if bare else None
    if lead:
        sections.append(f"**In brief.**\n{lead}")
    dep, dep_done = _dep_sentence(state, items), False
    for stone in stones.all():
        if stone.id == "capstone":
            continue  # Capstone is the synthesis output, not a data stone
        out = []
        for e in items:
            if e.stone_id != stone.id:
                continue
            if dep and e.pebble_id in _DEP_POINT:
                if not dep_done:  # the merged sentence goes where the first scenario was
                    out.append(dep)
                    dep_done = True
                continue
            out.append(evidence.cite(e.text, e.doc_id))
        body = " ".join(out)
        if body:
            sections.append(f"**{evidence.stone_heading(stone)}**\n{body}")
    if len(sections) == 1:
        return nothing_built(state), {}
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
