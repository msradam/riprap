"""Which models took part in a briefing, and which are loaded now (refactor 8).

`for_briefing(final)` reads the trace and the LLM call records of one
result and lists each model that ran: its name and Hugging Face repo (or
the LLM endpoint's model id), where it ran, whether it was loaded in
process or read from a precomputed batch output, and its latency for this
briefing. `loaded()` backs /api/models: the models this process has in
memory now. `warm()` loads them at startup when RIPRAP_WARM=1.
"""

from __future__ import annotations

import logging

log = logging.getLogger("riprap.models")

# pebble id -> the models it runs. "where" is where the model itself runs.
PEBBLE_MODELS: dict[str, list[dict]] = {
    "ttm_battery_surge": [{"name": "Granite TTM r2, Battery surge fine-tune",
                           "repo": "msradam/Granite-TTM-r2-Battery-Surge", "where": "CPU", "how": "loaded"}],
    "ttm_311_forecast": [{"name": "Granite TTM r2", "repo": "ibm-granite/granite-timeseries-ttm-r2",
                          "where": "CPU", "how": "loaded"}],
    "floodnet_forecast": [{"name": "Granite TTM r2", "repo": "ibm-granite/granite-timeseries-ttm-r2",
                           "where": "CPU", "how": "loaded"}],
    "policy_corpus": [{"name": "Granite Embedding 278M", "repo": "ibm-granite/granite-embedding-278m-multilingual",
                       "where": "CPU", "how": "loaded"},
                      {"name": "Flair NER (OntoNotes, fast)", "repo": "flair/ner-english-ontonotes-fast",
                       "where": "CPU", "how": "loaded"}],
    "prithvi_water": [{"name": "Prithvi-EO 2.0, NYC pluvial fine-tune", "repo": "msradam/Prithvi-EO-2.0-NYC-Pluvial",
                       "where": "Apple GPU (MPS), in the batch run", "how": "precomputed"}],
    "prithvi_water_nta": [{"name": "Prithvi-EO 2.0, NYC pluvial fine-tune",
                           "repo": "msradam/Prithvi-EO-2.0-NYC-Pluvial",
                           "where": "Apple GPU (MPS), in the batch run", "how": "precomputed"}],
}


def _prithvi_detail(value: dict | None) -> str:
    if not isinstance(value, dict):
        return ""
    return (f"batch output for the {value.get('rain_date', '')} event; post scenes "
            f"{value.get('post_scene', '')}; pre scenes {value.get('pre_scene', '')}; "
            f"batch run {value.get('batch_run', 'date not recorded')}")


def for_briefing(final: dict) -> list[dict]:
    """The models that ran for one result, in trace order, then the LLM."""
    out: list[dict] = []
    for t in final.get("trace") or []:
        step = t.get("step")
        res = t.get("result") if isinstance(t.get("result"), dict) else {}
        if step not in PEBBLE_MODELS or not t.get("ok") or res.get("skipped") or final.get(step) is None:
            continue
        for m in PEBBLE_MODELS[step]:
            row = {**m, "pebble": step, "latency_s": t.get("elapsed_s")}
            if m["how"] == "precomputed":
                row["detail"] = _prithvi_detail(final.get(step))
            out.append(row)
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
    ent = (final.get("grounding") or {}).get("entailment") or {}
    if ent.get("ran"):
        out.append({"name": f"Entailment check ({ent.get('label', '')})".replace(" ()", ""),
                    "repo": "knowledgator/gliclass-large-v3.0" if ent.get("backend") == "gliclass" else ent.get("backend"),
                    "where": "CPU", "how": "loaded", "latency_s": ent.get("seconds")})
    return out + list(by_model.values())


def _where(endpoint: str) -> str:
    local = endpoint.startswith(("localhost", "127.0.0.1"))
    if local and endpoint.endswith(":11434"):
        return f"Ollama on this machine ({endpoint})"
    return f"LLM endpoint {endpoint}" if endpoint else "LLM endpoint"


def loaded() -> dict:
    """What this process has in memory now, and the LLM endpoint configured."""
    import sys

    def attr(mod: str, name: str):
        m = sys.modules.get(mod)
        return getattr(m, name, None) if m else None

    from riprap.core import llm

    return {
        "in_process": {
            "msradam/Granite-TTM-r2-Battery-Surge": attr("app.live.ttm_battery_surge", "_MODEL") is not None,
            "ibm-granite/granite-timeseries-ttm-r2": bool(attr("app.live.ttm_forecast", "_MODELS")),
            "ibm-granite/granite-embedding-278m-multilingual": attr("app.rag", "_MODEL") is not None,
            "flair/ner-english-ontonotes-fast": bool(attr("app.context.entity_extract", "_TAGGER")),
        },
        "precomputed": {"msradam/Prithvi-EO-2.0-NYC-Pluvial": _prithvi_available()},
        "llm_endpoints": [{"model": e.model, "base_url": e.base_url} for e in llm.endpoints()],
    }


def _prithvi_available() -> bool:
    from app.flood_layers import prithvi_water

    return prithvi_water._paths()[0].exists()


def warm() -> dict:
    """Load the in-process models and send one tiny request to the LLM, so
    the first query is not the cold one. Each step is optional: a missing
    extra or an unreachable endpoint is logged and skipped. Returns the
    seconds each step took."""
    import time

    took: dict[str, float] = {}

    def step(name, fn):
        t0 = time.perf_counter()
        try:
            fn()
            took[name] = round(time.perf_counter() - t0, 1)
        except Exception as e:  # noqa: BLE001 - warming is best effort
            log.warning("warm %s skipped: %s", name, e)
            took[name] = -1.0

    from app import rag
    from app.context import entity_extract
    from app.live import ttm_battery_surge, ttm_forecast

    step("granite-embedding", rag.warm)
    step("flair-ner", entity_extract.warm)
    step("ttm-battery-surge", ttm_battery_surge.warm)
    step("ttm-r2", ttm_forecast._load_model)
    step("llm", _ping_llm)
    return took


def _ping_llm() -> None:
    from riprap.core import llm

    if not llm.endpoints():
        raise RuntimeError("no LLM endpoint configured")
    from openai import OpenAI

    ep = llm.endpoints()[0]
    OpenAI(base_url=ep.base_url, api_key=ep.api_key, timeout=120, max_retries=0).chat.completions.create(
        model=ep.model, messages=[{"role": "user", "content": "ok"}], max_tokens=1)
