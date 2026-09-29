"""Capstone inputs: the DEP fan-in and the policy-corpus pebble.

  assemble_legacy_state -> fold the three DEP scenario pebbles into one
                           `dep` dict (read by step_policy_corpus).
  policy_corpus         -> retrieval + NER over the policy PDFs.

The terminal `reconcile` action is `synthesis.reconcile_claims` (LLM)
or `templated_reconciler.reconcile_templated` (no LLM).
"""
from __future__ import annotations

import time
from typing import Any

from burr.core import State, action

from riprap.core.burr.pebble import trace_rec_for


@action(
    reads=["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"],
    writes=["dep", "trace"],
)
def assemble_legacy_state(state: State) -> State:
    """Compose the three DEP scenario pebble values into the legacy `dep`
    compound dict that step_policy_corpus + step_reconcile read.

    All other pebbles (sandy, ida_hwm, floodnet, etc.) already write the
    legacy state keys directly via their shapers — no other compounding
    needed in v1.
    """
    trace = list(state.get("trace", []))
    rec = trace_rec_for("assemble_legacy_state")
    dep: dict[str, Any] = {}
    for scen in ("dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"):
        v = state.get(scen)
        if v is not None:
            dep[scen] = v
    rec["ok"] = True
    rec["result"] = {"scenarios": sorted(dep.keys())}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)
    trace.append(rec)
    return state.update(dep=dep, trace=trace)


@action(
    reads=["lat", "lon", "geocode", "sandy", "dep", "intent", "selected_pebbles"],
    writes=["policy_corpus", "trace"],
)
def step_policy_corpus(state: State) -> State:
    """Run the policy_corpus pebble: retrieve + NER in one pebble call.

    Builds the search query from state (geocode + flood signals), then
    delegates to the pebble registry.
    """
    import time

    from riprap.core.pebbles.bridge import fetch_pebble

    trace = list(state.get("trace", []))
    rec = trace_rec_for("policy_corpus")
    selected = state.get("selected_pebbles")
    if selected is not None and "policy_corpus" not in selected:
        return state.update(policy_corpus=None, trace=trace)  # listed as not checked
    try:
        geo = state.get("geocode") or {}

        # No real address resolved (geocode failed, or the point is out
        # of coverage) means no legitimate location to search policy
        # documents *about*. Without this gate the query below still
        # runs on its generic "flood resilience plan, vulnerability,
        # hardening, mitigation" tail alone, pulls back real PDF chunks
        # by topic-similarity with zero place relevance, and the
        # reconciler cites them as if they grounded an answer for
        # whatever address was actually asked about — a real production
        # case: a London query with no NYC geocode still got NYCHA/DEP/
        # Con Edison citations synthesized into a confident paragraph.
        if not geo.get("address") and state.get("lat") is None:
            rec["ok"] = True
            rec["result"] = {"skipped": "no geocode — nothing to search policy documents about"}
            rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
            trace.append(rec)
            return state.update(policy_corpus=None, trace=trace)

        sandy = state.get("sandy")
        dep = state.get("dep") or {}

        # Build a context-rich query so retrieval pulls policy paragraphs
        # relevant to *this* address, not generic flood text.
        bits: list[str] = []
        if geo.get("address"):
            bits.append(f"address {geo['address']}")
        if geo.get("borough"):
            bits.append(f"in {geo['borough']}")
        if sandy:
            bits.append("inside Hurricane Sandy 2012 inundation zone")
        for v in (dep or {}).values():
            if isinstance(v, dict) and (v.get("depth_class") or 0) > 0:
                bits.append(f"DEP stormwater scenario: {v.get('depth_label', '?')}")
        bits.append("flood resilience plan, vulnerability, hardening, mitigation")
        query_str = "; ".join(bits)

        value, trace_summary, err = fetch_pebble(
            "policy_corpus",
            state.get("lat") or 0.0,
            state.get("lon") or 0.0,
            extras={"query": query_str},
        )
        if value is None:
            rec["ok"] = False
            rec["err"] = err or "policy_corpus unavailable"
            trace.append(rec)
            return state.update(policy_corpus=None, trace=trace)

        rec["ok"] = True
        rec["result"] = trace_summary
        trace.append(rec)

        return state.update(policy_corpus=value, trace=trace)
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(policy_corpus=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)


__all__ = ["assemble_legacy_state", "step_policy_corpus"]
