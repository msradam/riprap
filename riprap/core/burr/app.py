"""The briefing pipeline as one Burr application, for every intent.

  plan_intent / plan_heuristic
    ├─ not_implemented            -> reconcile (an honest "can't do that")
    ├─ neighborhood,
    │  development_check          -> resolve_area (NTA polygon)
    └─ single_address, live_now   -> geocode_target (point)
  select_deployment -> stones (parallel fan-out) -> assemble_legacy_state
    -> policy_corpus -> reconcile

`compare` runs the single_address graph once per target and merges the
two briefings (`run_compare`). The intent decides which pebbles the
Stones fan-out runs (see stones.py). `reconcile` is verified LLM claims
when an endpoint is configured, the no-LLM evidence briefing otherwise.

Burr's LocalTrackingClient is off unless RIPRAP_BURR_TRACKING=1, which
writes run logs to .burr/ for `burr` (the tracking UI) to read.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from pathlib import Path

from burr.core import ApplicationBuilder, State, expr
from burr.lifecycle import PostRunStepHook

from riprap.core.burr.capstone import assemble_legacy_state, step_policy_corpus
from riprap.core.burr.intake import (
    forecast_question,
    geocode_target,
    heuristic_plan,
    plan_heuristic,
    plan_intent,
    resolve_area,
    select_deployment,
    select_sources,
)
from riprap.core.burr.stones import POLYGON_INTENTS, StonesAction
from riprap.core.burr.templated_reconciler import reconcile_templated

log = logging.getLogger("riprap.burr.app")
_REPO = Path(__file__).resolve().parent.parent.parent.parent


class StepEventHook(PostRunStepHook):
    """Push each new trace record onto a queue after every action, so the
    SSE route can stream steps as they finish. queue=None is a no-op."""

    def __init__(self, q=None):
        self._q = q
        self._seen = 0

    def post_run_step(self, *, state: State, **_kw):
        if self._q is None:
            return
        trace = state.get("trace") or []
        for rec in trace[self._seen:]:
            self._q.put(("step", rec))
        self._seen = len(trace)


def _tier() -> str:
    from riprap.core import llm

    return llm.tier()


def _reconciler(no_llm: bool = False):
    from riprap.core.burr.synthesis import reconcile_claims

    return reconcile_templated if no_llm or _tier() == "no_llm" else reconcile_claims


def plan_for(query: str, *, no_llm: bool = False) -> dict:
    """The plan a query gets: the LLM planner in LLM mode, the regex
    planner otherwise (or when the LLM planner fails). LLM calls are
    listed under `llm_calls`."""
    if _tier() == "llm" and not no_llm:
        calls: list = []
        try:
            from app.planner import is_bare_place
            from app.planner import plan as run_planner
            from riprap.core.burr.synthesis import llm_bare

            guard = heuristic_plan(query)
            if guard["intent"] == "out_of_scope":  # the same fixed rules in both modes
                return guard
            if not llm_bare() and guard["intent"] != "not_implemented" and is_bare_place(query, guard["targets"]):
                return guard  # a bare place: the resolver finds it, and there is no question to plan
            p = run_planner(query, ledger=calls)
            intent, focus = p.intent, p.focus
            if forecast_question(query):
                # Decided in code: a forecast question is about what is coming,
                # so it runs the Lodestone's forecast pebbles, never live_now.
                intent = "single_address" if intent == "live_now" else intent
                focus = {**(focus or {}), "time_frame": "future"}
            return {"intent": intent, "targets": p.targets, "rationale": p.rationale,
                    "question": p.question, "focus": focus, "pebbles": p.pebbles,
                    "catalog": p.catalog, "llm_calls": calls}
        except Exception as e:  # noqa: BLE001 - fall back to the regex planner
            log.warning("LLM planner failed (%s); using the heuristic planner", e)
    return heuristic_plan(query)


def build_app(query: str, plan: dict | None = None, *, step_queue=None, no_llm: bool = False):
    """One briefing run. With `plan` given (the SSE route plans first so
    it can show the plan), the graph starts at the intake step for that
    intent; otherwise it starts by planning."""
    state = {"query": query, "trace": [], "nta": None, "polygon_wkt": None,
             "selected_pebbles": None, "consulted": None, "not_checked": None}
    if plan is None:
        entry = "plan_intent"
    else:
        target = (plan.get("targets") or [{}])[0]
        state.update(plan=plan, intent=plan["intent"],
                     first_target=target.get("text") or target.get("address") or query)
        entry = {"not_implemented": "reconcile", "out_of_scope": "reconcile"}.get(
            plan["intent"], "resolve_area" if plan["intent"] in POLYGON_INTENTS else "geocode_target")
    builder = (
        ApplicationBuilder()
        .with_state(**state)
        .with_entrypoint(entry)
        .with_hooks(StepEventHook(step_queue))
        .with_actions(
            plan_intent=plan_intent if _tier() == "llm" and not no_llm else plan_heuristic,
            geocode_target=geocode_target,
            resolve_area=resolve_area,
            select_deployment=select_deployment,
            select_sources=select_sources,
            stones=StonesAction(),
            assemble_legacy_state=assemble_legacy_state,
            policy_corpus=step_policy_corpus,
            reconcile=_reconciler(no_llm),
        )
        .with_transitions(
            ("plan_intent", "reconcile", expr("intent in ('not_implemented', 'out_of_scope')")),
            ("plan_intent", "resolve_area", expr(f"intent in {POLYGON_INTENTS!r}")),
            ("plan_intent", "geocode_target"),
            # No point resolved: nothing to run the sources on, so the
            # briefing says so instead of reporting every source as failed.
            ("resolve_area", "reconcile", expr("lat is None")),
            ("geocode_target", "reconcile", expr("lat is None")),
            ("resolve_area", "select_deployment"),
            ("geocode_target", "select_deployment"),
            ("select_deployment", "select_sources"),
            ("select_sources", "stones"),
            ("stones", "assemble_legacy_state"),
            ("assemble_legacy_state", "policy_corpus"),
            ("policy_corpus", "reconcile"),
        )
    )
    if os.environ.get("RIPRAP_BURR_TRACKING", "").lower() in ("1", "true", "yes"):
        from burr.tracking import LocalTrackingClient

        builder = builder.with_tracker(LocalTrackingClient(project="riprap",
                                                           storage_dir=str(_REPO / ".burr")))
    return builder.build()


_PIPELINE_KEYS = ("query", "intent", "plan", "geocode", "lat", "lon", "nta", "policy_corpus",
                  "dep", "paragraph", "audit", "grounding", "citations", "consulted", "not_checked")


def _final(state) -> dict:
    """The public result: pipeline fields, every pebble value the routed
    deployment produced, and the disclosure-check report."""
    out = {k: state.get(k) for k in _PIPELINE_KEYS}
    dep = state.get("deployment")
    out["deployment"] = None if dep == "__none__" else dep
    for k in state.keys():
        if k not in out and k not in ("trace", "first_target", "polygon_wkt", "deployment",
                                      "selected_pebbles"):
            v = state.get(k)
            if v is not None and not k.startswith("__"):
                out[k] = v
    out["trace"] = list(state.get("trace") or [])
    from app.models_info import for_briefing

    out["models"] = for_briefing(out)  # which models took part, where they ran, how long
    return attach_disclosure_checks(out)


def attach_disclosure_checks(out: dict) -> dict:
    """Run the disclosure checks (riprap/core/compliance, substring checks
    for scope, disclaimer and citation phrases) on the paragraph. The key
    stays `compliance` for API compatibility; it is not a quality score."""
    from riprap.core.compliance import check_briefing

    paragraph = out.get("paragraph") or ""
    if not paragraph or out.get("intent") in ("not_implemented", "out_of_scope") or out.get("lat") is None:
        out["compliance"] = {"passed": False, "n_passed": 0, "n_total": 0, "failed": [],
                             "note": "no briefing to check"}
        return out
    report = check_briefing(paragraph)
    out["compliance"] = {
        "passed": report.passed,
        "n_passed": len(report.passed_results),
        "n_total": len(report.results),
        "failed": [{"name": r.name, "rule": r.rule, "description": r.description,
                    "reason": r.reason, "evidence": r.evidence[:3]} for r in report.failed],
    }
    return out


def iter_steps(query: str, plan: dict | None = None):
    """Run one briefing on a worker thread and yield
    {"kind": "step", ...} per finished step, then {"kind": "final", ...}."""
    q: queue.Queue = queue.Queue()
    app = build_app(query, plan, step_queue=q)
    holder: dict = {}

    def _run():
        try:
            _, _, holder["state"] = app.run(halt_after=["reconcile"])
        except Exception as e:  # noqa: BLE001 - surfaced as an error event
            log.exception("briefing run failed")
            q.put(("error", {"err": f"{type(e).__name__}: {e}"}))
        finally:
            q.put(None)

    threading.Thread(target=_run, name="riprap-briefing", daemon=True).start()
    while (item := q.get()) is not None:
        kind, payload = item
        yield {"kind": kind, **payload}
    if "state" in holder:
        yield {"kind": "final", **_final(holder["state"])}


def district_summary(code: str, *, no_llm: bool = False) -> dict:
    """The neighbourhood evidence for a community district (QN12, BK06),
    run over the union of the district's NTAs."""
    plan = {"intent": "neighborhood", "targets": [{"type": "nta", "text": code}],
            "rationale": f"Community district summary: {code}."}
    return run(f"Community district {code}", plan, no_llm=no_llm)


def energy_summary(result: dict, plan: dict | None = None) -> dict:
    """The energy/token ledger for a briefing: planner plus synthesis
    LLM calls, each labelled measured, estimated or unknown."""
    from app.emissions import summarize

    calls = list((plan or {}).get("llm_calls") or [])
    calls += (result.get("grounding") or {}).get("llm_calls") or []
    return summarize(calls)


def run(query: str, plan: dict | None = None, *, no_llm: bool = False) -> dict:
    """Run to completion and return the result dict (with its energy
    ledger). Plans first, and runs `compare` as two briefings.
    `no_llm=True` forces the evidence briefing even with an endpoint set."""
    plan = plan or plan_for(query, no_llm=no_llm)
    if plan["intent"] == "compare":
        out = run_compare(query, plan, runner=lambda q, p: run(q, p, no_llm=no_llm))
    else:
        _, _, state = build_app(query, plan, no_llm=no_llm).run(halt_after=["reconcile"])
        out = _final(state)
    out["emissions"] = energy_summary(out, plan)
    return out


def run_compare(query: str, plan: dict, runner=None) -> dict:
    """Two single_address briefings, merged into one result labelled
    PLACE A and PLACE B. Falls back to one briefing when the plan has
    fewer than two targets. `runner(query, plan)` defaults to `run`."""
    runner = runner or (lambda q, p: run(q, p))
    targets = [t for t in plan.get("targets") or [] if t.get("text")][:2]
    if len(targets) < 2:
        return runner(query, {**plan, "intent": "single_address"})
    results = []
    for label, t in zip(("PLACE A", "PLACE B"), targets, strict=False):
        sub = {"intent": "single_address", "targets": [t], "rationale": plan.get("rationale")}
        results.append((label, t["text"], runner(t["text"], sub)))
    out = {**results[0][2]}
    out.update(
        intent="compare",
        plan=plan,
        paragraph="\n\n---\n\n".join(f"## {lab}: {addr}\n\n{(res.get('paragraph') or '').strip()}"
                                     for lab, addr, res in results),
        citations={k: v for _, _, res in results for k, v in (res.get("citations") or {}).items()},
        grounding={
            "tier": results[0][2].get("grounding", {}).get("tier"),
            "claims": [{**c, "place": lab} for lab, _, res in results
                       for c in (res.get("grounding") or {}).get("claims", [])],
            "dropped_claims": [{**c, "place": lab} for lab, _, res in results
                               for c in (res.get("grounding") or {}).get("dropped_claims", [])],
            "llm_calls": [c for _, _, res in results
                          for c in (res.get("grounding") or {}).get("llm_calls", [])],
        },
        targets=[{"label": lab, "address": addr, "state": res} for lab, addr, res in results],
    )
    return attach_disclosure_checks(out)
