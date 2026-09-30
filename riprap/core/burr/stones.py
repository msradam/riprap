"""The four data Stones as one parallel Burr fan-out, over the pebbles
`select_pebbles` chose for the question.

Cornerstone, Touchstone, Keystone and Lodestone pebbles do not depend on
each other, so a single `MapActions` runs every pebble for the query
concurrently (Burr's thread pool) and reduces the results back into one
state. The Stone a pebble belongs to is still its manifest's `stone:`
field; the UI and the briefing group by it.

Which pebbles run depends on the intent:

  single_address, compare   point pebbles
  live_now                  point pebbles of `type: live`
  neighborhood,
  development_check         polygon pebbles (spatial.scope: polygon)

`policy_corpus` is excluded here; the Capstone runs it with a query built
from the other evidence.
"""
from __future__ import annotations

import functools
import re
from collections.abc import Generator, Iterable
from typing import Any

from burr.core import State
from burr.core.application import ApplicationContext
from burr.core.parallelism import MapActions

from riprap.core.burr.pebble import pebble_action

DATA_STONES = ("cornerstone", "touchstone", "keystone", "lodestone")
POLYGON_INTENTS = ("neighborhood", "development_check")

# Always run for a question, whatever the planner chose: the regulatory
# flood zone and the modeled flood layers a flood answer should never
# skip. Geocoding always runs; it is not a pebble.
FLOOR = {
    "single_address": ("fema_nfhl", "sandy", "dep_moderate_2050"),
    "compare": ("fema_nfhl", "sandy", "dep_moderate_2050"),
    "live_now": ("nws_alerts",),
    "neighborhood": ("area_boundary", "sandy_nta", "dep_moderate_2050_nta"),
    "development_check": ("area_boundary", "sandy_nta", "dep_moderate_2050_nta", "dob_permits_nta"),
}

# What an analyst checks for a question's focus, whatever the planner
# chose: the record of past floods, the live signals, the asset register.
# Ids outside the intent's scope (point vs area) are ignored.
FOCUS_FLOOR = {
    ("time_frame", "past"): ("nyc311", "floodnet", "ida_hwm", "sandy", "nyc311_nta", "sandy_nta"),
    ("time_frame", "now"): ("nws_alerts", "nws_obs", "floodnet", "noaa_tides"),
    # Refactor 8: a forecast question runs every forecast and projection.
    ("time_frame", "future"): ("npcc4_slr", "ttm_battery_surge", "floodnet_forecast", "ttm_311_forecast",
                               "dep_moderate_2050", "dep_extreme_2080",
                               "dep_moderate_2050_nta", "dep_extreme_2080_nta"),
    ("assets", "subway"): ("mta_entrances",),
    ("assets", "schools"): ("doe_schools",),
    ("assets", "public_housing"): ("nycha_developments",),
    ("assets", "hospitals"): ("doh_hospitals",),
    ("assets", "construction"): ("dob_permits_nta",),
}


# A question about the DEP stormwater scenarios runs all of them.
_DEP_RE = re.compile(r"\b(dep|stormwater)\b", re.IGNORECASE)
DEP_FLOOR = ("dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080",
             "dep_moderate_current_nta", "dep_moderate_2050_nta", "dep_extreme_2080_nta")


def floor_for(plan: dict) -> set[str]:
    focus = plan.get("focus") or {}
    keys = [("time_frame", focus.get("time_frame")), *(("assets", a) for a in focus.get("assets") or [])]
    floor = set(FLOOR.get(plan.get("intent"), ())).union(*(FOCUS_FLOOR.get(k, ()) for k in keys))
    return floor | set(DEP_FLOOR) if _DEP_RE.search(plan.get("question") or "") else floor


def select_pebbles(plan: dict | None, registry) -> list[str]:
    """The pebbles to run for a plan, in registry order: the planner's
    choice plus the intent's FLOOR and the focus floor. A bare place (no question), no-LLM
    mode (no choice), or a plan made against another deployment's catalog
    gets every pebble for the intent. One plain function so another
    selector (a small classifier) can replace the planner's choice."""
    plan = plan or {}
    intent = plan.get("intent")
    ids = [p.id for p in registry.all() if p.stone != "capstone" and _wants(p.manifest, intent)]
    chosen = plan.get("pebbles")
    if not plan.get("question") or chosen is None:
        return ids
    if not set(plan.get("catalog") or []).issuperset(ids):
        return ids  # e.g. planned with the NYC catalog, routed to Chicago
    keep = set(chosen) | floor_for(plan)
    return [i for i in ids if i in keep]


def _wants(manifest, intent: str | None) -> bool:
    scope = "polygon" if intent in POLYGON_INTENTS else "point"
    if manifest.spatial.scope != scope:
        return False
    return intent != "live_now" or manifest.type == "live"


def pebbles_for(deployment: str | None, lat: float | None = None, lon: float | None = None,
                intent: str | None = None) -> list[str]:
    """Pebble ids to run for a query, in Stone then display order.

    `deployment` is a deployment name, or "__none__" when no city covers
    the point (federal pebbles still run). Pebbles whose `coverage` does
    not contain the point are skipped."""
    from riprap.core.pebbles.bridge import get_registry
    from riprap.core.pebbles.deployments import deployment_by_name, deployment_root

    if not (deployment_root(deployment) / "manifests").is_dir():
        return []
    dep = deployment_by_name("federal" if deployment == "__none__" else deployment or "")
    bbox = dep.bbox if dep is not None else None
    order = {s: i for i, s in enumerate(DATA_STONES)}
    pebbles = [p for p in get_registry(deployment).all()
               if p.stone in order and p.id != "policy_corpus" and _wants(p.manifest, intent)]
    if lat is not None and lon is not None:
        pebbles = [p for p in pebbles if p.fires_at(lat, lon, bbox)]
    pebbles.sort(key=lambda p: (order[p.stone],
                                p.manifest.display.order if p.manifest.display.order is not None else 999,
                                p.id))
    return [p.id for p in pebbles]


@functools.cache
def _import_ml_stacks() -> None:
    """Import transformers and tsfm_public once, on the thread that
    starts the fan-out. Their lazy module loaders are not thread-safe on
    first import ("cannot import name 'PreTrainedModel'"), and the TTM
    pebbles run on worker threads. A no-op when they are not installed."""
    try:
        from transformers import PreTrainedModel  # noqa: F401
        from tsfm_public import TinyTimeMixerForPrediction  # noqa: F401
    except Exception:  # noqa: BLE001 - the ml extra is optional
        pass


def _all_data_pebble_ids() -> list[str]:
    """Union of data-Stone pebble ids across every deployment. Burr needs
    `writes` before any query arrives; the reducer fills keys the routed
    deployment did not run with None."""
    from riprap.core.pebbles.bridge import get_registry
    from riprap.core.pebbles.deployments import discover_deployments

    ids: set[str] = set()
    for dep in discover_deployments():
        try:
            reg = get_registry(dep.name)
        except Exception:  # noqa: BLE001 - one malformed deployment must not break the rest
            continue
        ids.update(p.id for p in reg.all() if p.stone in DATA_STONES and p.id != "policy_corpus")
    return sorted(ids)


def _to_run(state) -> list[str]:
    """Pebbles the fan-out runs: those covering the point, restricted to
    the selection when there is one."""
    ids = pebbles_for(state.get("deployment"), state.get("lat"), state.get("lon"), state.get("intent"))
    selected = state.get("selected_pebbles")
    return ids if selected is None else [i for i in ids if i in selected]


class StonesAction(MapActions):
    """Every data-Stone pebble for the query, run concurrently."""

    @property
    def reads(self) -> list[str]:
        return ["lat", "lon", "deployment", "intent", "polygon_wkt", "selected_pebbles"]

    @property
    def writes(self) -> list[str]:
        return [*_all_data_pebble_ids(), "trace"]

    def actions(self, state: State, inputs: dict[str, Any],  # noqa: ARG002 - Burr API
                context: ApplicationContext) -> Generator[Any, None, None]:  # noqa: ARG002
        _import_ml_stacks()
        for pid in _to_run(state):
            yield pebble_action(pid)

    def state(self, state: State, inputs: dict[str, Any]) -> State:  # noqa: ARG002 - Burr API
        return state.update(trace=[])

    def reduce(self, state: State, states: Iterable[State]) -> State:
        trace = list(state.get("trace", []))
        updates: dict[str, Any] = {}
        for s in states:
            for k in s.keys():
                if k == "trace":
                    trace.extend(s["trace"])
                elif k not in ("lat", "lon", "deployment", "intent", "polygon_wkt", "selected_pebbles"):
                    updates[k] = s[k]
        for declared in self.writes:
            if declared != "trace" and declared not in updates and state.get(declared) is None:
                updates[declared] = None
        order = {pid: i for i, pid in enumerate(_to_run(state))}
        new = sorted(trace[len(state.get("trace", [])):], key=lambda r: order.get(r.get("step"), 999))
        return state.update(trace=[*state.get("trace", []), *new], **updates)
