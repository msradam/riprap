"""Capstone input: the DEP fan-in.

  assemble_legacy_state -> fold the three DEP scenario pebbles into one
                           `dep` dict (part of the public result).

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
    compound dict the public result carries.

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


__all__ = ["assemble_legacy_state"]
