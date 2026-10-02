"""Which models took part in a briefing.

`for_briefing(final)` lists each model behind one result: the experimental
models whose sources returned a value (the surge forecast runs in this
process; the satellite models ran earlier, in a batch, and their saved
output is read), then the LLM endpoint with its calls and latency. A
briefing made with none of them lists nothing. `loaded()` backs
/api/models; `warm()` pings the LLM at startup when RIPRAP_WARM=1.
"""

from __future__ import annotations

import logging

from app import experimental

log = logging.getLogger("riprap.models")

# source id -> (the experimental model behind it, where it ran, how).
SOURCES = {
    "ttm_battery_surge": ("surge", "CPU, in this server", "loaded"),
    **{s: ("landcover", "an earlier batch run; its saved output is read", "precomputed")
       for s in ("landcover", "landcover_nta")},
}


def for_briefing(final: dict) -> list[dict]:
    """The models behind one result: experimental models in trace order,
    each once, then the LLM endpoints that answered."""
    out: dict[str, dict] = {}
    for t in final.get("trace") or []:
        step, value = t.get("step"), final.get(t.get("step"))
        if step not in SOURCES or not isinstance(value, dict) or value.get("available") is False:
            continue
        key, where, how = SOURCES[step]
        m = experimental.MODELS[key]
        out.setdefault(m.repo or m.name, {"name": f"{m.name} (experimental)", "repo": m.repo, "where": where, "how": how,
                                "latency_s": t.get("elapsed_s") if how == "loaded" else None})
    calls = [*((final.get("plan") or {}).get("llm_calls") or []),
             *((final.get("grounding") or {}).get("llm_calls") or [])]
    by_model: dict[str, dict] = {}
    for c in calls:
        key = f"{c.get('model')}@{c.get('endpoint')}"
        row = by_model.setdefault(key, {"name": "LLM", "repo": c.get("model"),
                                        "where": _where(c.get("endpoint") or ""), "how": "endpoint",
                                        "latency_s": 0.0, "calls": 0})
        row["latency_s"] = round(row["latency_s"] + float(c.get("duration_s") or 0), 2)
        row["calls"] += 1
    return [*out.values(), *by_model.values()]


def _where(endpoint: str) -> str:
    local = endpoint.startswith(("localhost", "127.0.0.1"))
    if local and endpoint.endswith(":11434"):
        return f"Ollama on this machine ({endpoint})"
    return f"LLM endpoint {endpoint}" if endpoint else "LLM endpoint"


def loaded() -> dict:
    """The experimental models this server can use, and the LLM endpoint
    configured. `in_process`: the surge model, true once loaded.
    `precomputed`: whether each batch model's saved output is on disk.
    `installed`: whether the optional extras are."""
    import importlib.util
    import sys

    from app.eo import landcover
    from riprap.core import llm

    surge = sys.modules.get("app.live.ttm_battery_surge")
    m = experimental.MODELS
    return {
        "in_process": {m["surge"].repo: bool(surge and surge._MODEL is not None)},
        "precomputed": {m["landcover"].name: bool(landcover.years())},
        "installed": {"ml": bool(importlib.util.find_spec("tsfm_public")),
                      "eo": bool(importlib.util.find_spec("terratorch"))},
        "llm_endpoints": [{"model": e.model, "base_url": e.base_url} for e in llm.endpoints()],
    }


def warm() -> dict:
    """Send one tiny request to the LLM, so the first question is not the
    cold one. An unreachable endpoint is logged and skipped. Returns the
    seconds it took (-1 when skipped)."""
    import time

    t0 = time.perf_counter()
    try:
        _ping_llm()
        return {"llm": round(time.perf_counter() - t0, 1)}
    except Exception as e:  # noqa: BLE001 - warming is best effort
        log.warning("warm llm skipped: %s", e)
        return {"llm": -1.0}


def _ping_llm() -> None:
    from riprap.core import llm

    if not llm.endpoints():
        raise RuntimeError("no LLM endpoint configured")
    from openai import OpenAI

    ep = llm.endpoints()[0]
    OpenAI(base_url=ep.base_url, api_key=ep.api_key, timeout=120, max_retries=0).chat.completions.create(
        model=ep.model, messages=[{"role": "user", "content": "ok"}], max_tokens=1)
