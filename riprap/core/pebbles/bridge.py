"""Bridge between the pebble registry and the legacy FSM.

Provides one helper, `fetch_pebble(pebble_id, lat, lon)`, that returns the
tuple `(value, trace_summary, err_msg)` matching the legacy FSM step
contract: a dict (or None) to write into state, a small renamed dict for
the SSE trace, and an error message if the fetch failed.

Registries load once per deployment directory (`get_registry`).
"""
from __future__ import annotations

import functools
import logging
import re
from pathlib import Path
from typing import Any

from riprap.core.pebbles import SpatialQuery, load_registry
from riprap.core.pebbles.deployments import deployment_root
from riprap.core.pebbles.registry import Registry

log = logging.getLogger("riprap.pebbles")


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


_STATUS_RE = re.compile(r"\b(?:HTTP|status(?: code)?|[Cc]lient error|[Ss]erver error)\D{0,3}([45]\d\d)\b|'([45]\d\d) ")


def plain_reason(err: str) -> str:
    """Why a source did not answer, for a reader: the briefing's "Not
    checked." section once printed "python_call: summary_for_point raised:
    HTTP 429 after 0/1 chunks; catch QuotaExhausted...". The raw text is
    logged by the caller; a message with no adapter prefix, status code or
    timeout in it (a manifest's own fallback sentence) passes through."""
    m = _STATUS_RE.search(err)
    code = int(m.group(1) or m.group(2)) if m else None
    if code == 429:
        return "the service refused the request: too many requests (HTTP 429)"
    if code and code >= 500:
        return f"the service reported an error of its own (HTTP {code})"
    if code:
        return f"the service refused the request (HTTP {code})"
    if re.search(r"timed? ?out|no answer within", err, re.I):
        return "the service did not answer in time"
    if re.search(r"connect|name resolution|unreachable|getaddrinfo", err, re.I):
        return "the service could not be reached"
    return re.sub(r"^[a-z_]+: (?:\w+ raised: |HTTP error: |\w+(?:Error|Exception): )?", "", err)


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
        if result.error:
            log.warning("pebble %s did not answer: %s", pebble_id, result.error)
        return None, {}, plain_reason(result.error) if result.error else "the source did not answer"
    if result.value is None:
        return None, {}, None  # the source ran and has nothing to say about this kind of place

    value = result.value
    # Some helpers catch their own fetch error and return it in the value
    # (nws_alerts, noaa_tides, nws_obs). That is a failed source, never a
    # reading of zero.
    if isinstance(value, dict) and value.get("error"):
        return None, {}, plain_reason(str(value["error"]))
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
