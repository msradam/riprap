"""Bridge between the pebble registry and the legacy FSM.

Provides one helper, `fetch_pebble(pebble_id, lat, lon)`, that returns the
tuple `(value, trace_summary, err_msg)` matching the legacy FSM step
contract: a dict (or None) to write into state, a small renamed dict for
the SSE trace, and an error message if the fetch failed.

Registries load once per deployment directory (`get_registry`).
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

from riprap.core.pebbles import SpatialQuery, load_registry
from riprap.core.pebbles.deployments import deployment_root
from riprap.core.pebbles.registry import Registry


@functools.cache
def _registry_at(root: Path) -> Registry:
    return load_registry(root)


def get_registry(deployment: str | None = None) -> Registry:
    """The pebble registry for a deployment name ('chicago'), loaded once
    per directory and shared by every caller, so a run never sees two
    views of the same deployment. None means the server's default."""
    return _registry_at(deployment_root(deployment))


def public_value(value: Any) -> Any:
    """A pebble value as it may leave the process: without its private keys
    (those starting with an underscore). FloodNet's value keeps per-sensor
    rows under `_rows` for the answer rules, and FloodNet's licence does not
    let Riprap repost them; `riprap.core.burr.app._final` passes every value
    through here, so the JSON API, the stream, the MCP tools and the gallery
    bake never hold one."""
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if not str(k).startswith("_")}
    return value


def fetch_pebble(pebble_id: str, lat: float, lon: float,
                 extras: dict | None = None,
                 deployment: str | None = None,
                 geometry_wkt: str | None = None) -> tuple[Any, dict, str | None]:
    """Run one pebble. Return (value_dict_for_state, trace_summary, err_msg).

    `value_dict_for_state` is None if the pebble was offline or errored.
    `trace_summary` is built from the manifest's `trace_summary:` block
    (empty dict if not declared). `err_msg` is set when an error or
    offline-fallback occurred.

    `extras` are passed into SpatialQuery.extras for adapters that need
    more context than lat/lon — text-mining pebbles need a search query
    string, dependent pebbles need an upstream pebble's value, etc.

    `deployment` is the short name from per-query routing (e.g.
    `'chicago'`). When set, the pebble is looked up in that deployment's
    registry, so a Chicago run finds `chicago_311` even when the server's
    env var defaults to `nyc`.
    """
    reg = get_registry(deployment)
    pebble = reg.get(pebble_id)
    result = pebble.fetch(SpatialQuery(lat=lat, lon=lon, geometry_wkt=geometry_wkt,
                                       extras=extras or {}))

    if result.error is not None or result.offline:
        return None, {}, result.error or "the source did not answer"
    if result.value is None:
        return None, {}, None  # the source ran and has nothing to say about this kind of place

    value = result.value
    # Some helpers catch their own fetch error and return it in the value
    # (nws_alerts, noaa_tides, nws_obs). That is a failed source, never a
    # reading of zero.
    if isinstance(value, dict) and value.get("error"):
        return None, {}, str(value["error"])
    trace_map = pebble.manifest.trace_summary or {}
    trace_summary: dict = {}
    for tk, vk in trace_map.items():
        if vk == "__value__":
            trace_summary[tk] = value
        elif isinstance(value, dict):
            trace_summary[tk] = value.get(vk)
        else:
            trace_summary[tk] = None  # value isn't a dict; skip this lookup
    return value, trace_summary, None
