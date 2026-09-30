"""One LLM client: the `openai` SDK against any OpenAI-compatible endpoint.

Settings are read at call time, never frozen at import:

  RIPRAP_LLM_BASE_URL   e.g. http://localhost:11434/v1 (Ollama), a vLLM
                        server, or a hosted provider
  RIPRAP_LLM_MODEL      model name at that endpoint, e.g. granite4:micro
  RIPRAP_LLM_API_KEY    optional; local servers ignore it

  RIPRAP_LLM_FALLBACK_BASE_URL / _MODEL / _API_KEY
                        optional second endpoint, tried when the first
                        fails to answer

With no base URL and model set, Riprap runs in no-LLM mode: the
deterministic evidence briefing. RIPRAP_RECONCILER_TIER=no_llm forces
that mode even when an endpoint is configured.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("riprap.llm")


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    model: str
    api_key: str


def endpoints() -> list[Endpoint]:
    # ponytail: primary plus one fallback; make it a list in the env if a
    # deployment ever needs three.
    out = []
    for prefix in ("RIPRAP_LLM_", "RIPRAP_LLM_FALLBACK_"):
        base, model = os.environ.get(prefix + "BASE_URL"), os.environ.get(prefix + "MODEL")
        if base and model:
            out.append(Endpoint(base.rstrip("/"), model, os.environ.get(prefix + "API_KEY") or "none"))
    return out


def tier() -> str:
    """`llm` when an endpoint is configured, else `no_llm`."""
    forced = os.environ.get("RIPRAP_RECONCILER_TIER", "").lower()
    if forced in ("no_llm", "templated"):
        return "no_llm"
    return "llm" if endpoints() else "no_llm"


class LLMUnavailable(RuntimeError):
    pass


def chat_json(messages: list[dict], schema: dict, *, name: str = "output",
              temperature: float = 0.0, timeout_s: float | None = None,
              ledger: list | None = None) -> tuple[dict, str]:
    """One JSON-schema-constrained completion. Returns (parsed JSON, the
    model that answered). Tries each endpoint in order; raises
    LLMUnavailable when none answers with valid JSON. Each attempt is
    appended to `ledger` (tokens, duration, energy status)."""
    from openai import OpenAI  # noqa: PLC0415

    from app.emissions import measure_call  # noqa: PLC0415

    timeout_s = timeout_s or float(os.environ.get("RIPRAP_LLM_TIMEOUT_S", "300"))
    errors = []
    for ep in endpoints():
        try:
            client = OpenAI(base_url=ep.base_url, api_key=ep.api_key, timeout=timeout_s, max_retries=0)
            with measure_call(ep.base_url, ep.model) as rec:
                if ledger is not None:
                    ledger.append(rec)
                resp = client.chat.completions.create(
                    model=ep.model, messages=messages, temperature=temperature,
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": name, "schema": schema, "strict": True}},
                )
                if resp.usage:
                    rec.update(prompt_tokens=resp.usage.prompt_tokens,
                               completion_tokens=resp.usage.completion_tokens)
            return json.loads(resp.choices[0].message.content or ""), ep.model
        except Exception as e:  # noqa: BLE001 - try the next endpoint, report all at the end
            log.warning("LLM endpoint %s (%s) failed: %r", ep.base_url, ep.model, e)
            errors.append(f"{ep.base_url} ({ep.model}): {type(e).__name__}: {e}")
    raise LLMUnavailable("; ".join(errors) or "no LLM endpoint configured")


def describe() -> dict:
    """What the UI's backend badge shows. No secrets."""
    eps = endpoints()
    return {
        "tier": tier(),
        "endpoints": [{"base_url": e.base_url, "model": e.model} for e in eps],
    }
