"""Which model took part in a briefing.

`for_briefing(final)` reads the LLM call records of one result and lists
each model that ran: the endpoint's model id, where it ran and its latency
for this briefing. A briefing made without a language model lists nothing:
no other model runs. `loaded()` backs /api/models; `warm()` pings the LLM
at startup when RIPRAP_WARM=1.
"""

from __future__ import annotations

import logging

log = logging.getLogger("riprap.models")


def for_briefing(final: dict) -> list[dict]:
    """The LLM endpoints that answered for one result, with calls and time."""
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
    return list(by_model.values())


def _where(endpoint: str) -> str:
    local = endpoint.startswith(("localhost", "127.0.0.1"))
    if local and endpoint.endswith(":11434"):
        return f"Ollama on this machine ({endpoint})"
    return f"LLM endpoint {endpoint}" if endpoint else "LLM endpoint"


def loaded() -> dict:
    """The LLM endpoint configured, if any. No model runs in this process."""
    from riprap.core import llm

    return {"in_process": {}, "llm_endpoints": [{"model": e.model, "base_url": e.base_url} for e in llm.endpoints()]}


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
