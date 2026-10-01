"""Energy and token ledger for the LLM calls in one briefing.

Every call record says how its energy figure was obtained:

  measured   Apple Silicon SoC energy read through zeus-apple-silicon
             (the optional `energy` extra) for a call to a local
             endpoint. It is whole-chip energy during the call, so it
             includes other processes.
  estimated  RIPRAP_ENERGY_WATTS (a sustained power you declare for the
             local machine) times the call's duration, for a local
             endpoint.
  unknown    everything else. Hosted endpoints never get a figure: they
             report no energy, and power times duration on shared
             hardware would be invented.

The LLM is the only model Riprap runs, so the ledger covers every model
call in a briefing.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "ollama"}


def _is_local(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "") in _LOCAL_HOSTS


def _zeus():
    try:
        from zeus_apple_silicon import AppleEnergyMonitor  # noqa: PLC0415

        return AppleEnergyMonitor()
    except Exception:  # noqa: BLE001 - the energy extra is optional
        return None


@contextmanager
def measure_call(base_url: str, model: str):
    """Wrap one LLM call; yields the record to fill with token counts.
    Energy fields are set on exit."""
    rec: dict[str, Any] = {"kind": "llm", "model": model, "endpoint": urlparse(base_url).netloc,
                           "prompt_tokens": None, "completion_tokens": None}
    local = _is_local(base_url)
    monitor = _zeus() if local else None
    if monitor:
        monitor.begin_window("llm")
    t0 = time.time()
    try:
        yield rec
    finally:
        rec["duration_s"] = round(time.time() - t0, 3)
        rec.update(energy_status="unknown", wh=None,
                   energy_note="hosted endpoint: no energy reported" if not local
                   else "no energy source configured")
        if monitor:
            m = monitor.end_window("llm")
            mj = sum(v or 0 for v in (m.cpu_total_mj, m.gpu_mj, m.dram_mj, m.ane_mj))
            # zeus-apple-silicon 1.1 reads 0 mJ of CPU energy on some chips
            # (seen on an Apple M5); a zero CPU reading over a real call is
            # a broken counter, not a free call.
            if m.cpu_total_mj and rec["duration_s"] > 0.5:
                rec.update(energy_status="measured", wh=round(mj / 3.6e6, 5),
                           energy_note="Apple SoC energy (CPU+GPU+DRAM+ANE) during the call, "
                                       "includes other processes")
            else:
                rec["energy_note"] = "energy counters returned no CPU energy on this chip"
        watts = os.environ.get("RIPRAP_ENERGY_WATTS")
        if local and rec["energy_status"] == "unknown" and watts:
            rec.update(energy_status="estimated",
                       wh=round(float(watts) * rec["duration_s"] / 3600, 5),
                       energy_note=f"declared {watts} W times duration")


def summarize(calls: list[dict]) -> dict[str, Any]:
    """Totals for a briefing. total_wh is reported only when every call
    has a measured or estimated figure; otherwise it is None."""
    known = [c for c in calls if c.get("wh") is not None]
    statuses = sorted({c.get("energy_status", "unknown") for c in calls})
    prompt = sum(c.get("prompt_tokens") or 0 for c in calls)
    completion = sum(c.get("completion_tokens") or 0 for c in calls)
    return {
        "n_calls": len(calls),
        "n_measured": sum(1 for c in calls if c.get("energy_status") == "measured"),
        "energy_status": statuses[0] if len(statuses) == 1 else ("mixed" if statuses else "none"),
        "total_wh": round(sum(c["wh"] for c in known), 5) if calls and len(known) == len(calls) else None,
        "total_duration_s": round(sum(c.get("duration_s") or 0 for c in calls), 3),
        "tokens": {"prompt": prompt or None, "completion": completion or None,
                   "total": (prompt + completion) or None},
        "calls": calls,
        "method": ("Each LLM call is labelled measured (Apple SoC counters), estimated "
                   "(declared watts times duration) or unknown; hosted endpoints are always "
                   "unknown. See app/emissions.py."),
    }
