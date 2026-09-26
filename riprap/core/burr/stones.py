"""The four data Stones as one parallel Burr fan-out.

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

from collections.abc import Generator, Iterable
from typing import Any

from burr.core import State
from burr.core.application import ApplicationContext
from burr.core.parallelism import MapActions

from riprap.core.burr.pebble import pebble_action
from riprap.core.pebbles import load_registry

DATA_STONES = ("cornerstone", "touchstone", "keystone", "lodestone")
POLYGON_INTENTS = ("neighborhood", "development_check")


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
    import os
    from pathlib import Path

    from riprap.core.pebbles.deployments import deployment_by_name

    if deployment == "__none__":
        deployment = "federal"
    if deployment is None:
        deployment = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    dep = deployment_by_name(deployment)
    if dep is not None:
        root, bbox = dep.root, dep.bbox
    else:
        root, bbox = Path(deployment), None
        if not root.is_absolute():
            root = Path(__file__).resolve().parent.parent.parent.parent / deployment
    if not (root / "manifests").is_dir():
        return []
    order = {s: i for i, s in enumerate(DATA_STONES)}
    pebbles = [p for p in load_registry(root).all()
               if p.stone in order and p.id != "policy_corpus" and _wants(p.manifest, intent)]
    if lat is not None and lon is not None:
        pebbles = [p for p in pebbles if p.fires_at(lat, lon, bbox)]
    pebbles.sort(key=lambda p: (order[p.stone],
                                p.manifest.display.order if p.manifest.display.order is not None else 999,
                                p.id))
    return [p.id for p in pebbles]


def _all_data_pebble_ids() -> list[str]:
    """Union of data-Stone pebble ids across every deployment. Burr needs
    `writes` before any query arrives; the reducer fills keys the routed
    deployment did not run with None."""
    from riprap.core.pebbles.deployments import discover_deployments

    ids: set[str] = set()
    for dep in discover_deployments():
        try:
            reg = load_registry(dep.root)
        except Exception:  # noqa: BLE001 - one malformed deployment must not break the rest
            continue
        ids.update(p.id for p in reg.all() if p.stone in DATA_STONES and p.id != "policy_corpus")
    return sorted(ids)


class StonesAction(MapActions):
    """Every data-Stone pebble for the query, run concurrently."""

    @property
    def reads(self) -> list[str]:
        return ["lat", "lon", "deployment", "intent", "polygon_wkt"]

    @property
    def writes(self) -> list[str]:
        return [*_all_data_pebble_ids(), "trace"]

    def actions(self, state: State, inputs: dict[str, Any],  # noqa: ARG002 - Burr API
                context: ApplicationContext) -> Generator[Any, None, None]:  # noqa: ARG002
        for pid in pebbles_for(state.get("deployment"), state.get("lat"), state.get("lon"),
                               state.get("intent")):
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
                elif k not in ("lat", "lon", "deployment", "intent", "polygon_wkt"):
                    updates[k] = s[k]
        for declared in self.writes:
            if declared != "trace" and declared not in updates and state.get(declared) is None:
                updates[declared] = None
        order = {pid: i for i, pid in enumerate(pebbles_for(
            state.get("deployment"), state.get("lat"), state.get("lon"), state.get("intent")))}
        new = sorted(trace[len(state.get("trace", [])):], key=lambda r: order.get(r.get("step"), 999))
        return state.update(trace=[*state.get("trace", []), *new], **updates)
