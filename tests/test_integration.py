"""End-to-end tests against a running server (skipped without one).

Hits `/api/agent/stream` over SSE for three NYC addresses (Brighton
Beach, Hollis, Hunts Point) and checks the trace, the cited paragraph
and the grounding record. Works in either mode: no-LLM by default, LLM
claims when the server has RIPRAP_LLM_BASE_URL and RIPRAP_LLM_MODEL.

    uv run uvicorn web.main:app --port 7860 &
    uv run pytest tests/test_integration.py -v
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

BASE = os.environ.get("RIPRAP_TEST_BASE", "http://127.0.0.1:7860")


def _server_up() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(f"{BASE}/api/deployment", timeout=2)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _server_up(), reason=f"no Riprap server at {BASE}")
TIMEOUT_S = float(os.environ.get("RIPRAP_TEST_TIMEOUT", "300"))

@dataclass
class StreamResult:
    events: list[tuple[str, dict]]
    plan: dict | None
    final: dict | None
    errors: list[dict]
    trace_steps: list[str]
    elapsed_s: float


def _stream(query: str, timeout: float = TIMEOUT_S) -> StreamResult:
    """Hit /api/agent/stream and return a parsed StreamResult."""
    url = f"{BASE}/api/agent/stream?q={urllib.parse.quote(query)}"
    t0 = time.time()
    events: list[tuple[str, dict]] = []
    plan = None
    final = None
    errors: list[dict] = []
    trace_steps: list[str] = []

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ev_name = None
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line.startswith("event:"):
                ev_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and ev_name is not None:
                try:
                    payload = json.loads(line.split(":", 1)[1].strip())
                except Exception:
                    payload = {"_raw": line}
                events.append((ev_name, payload))
                if ev_name == "plan":
                    plan = payload
                elif ev_name == "final":
                    final = payload
                elif ev_name == "step":
                    trace_steps.append(payload.get("step", ""))
                elif ev_name == "error":
                    errors.append(payload)
                elif ev_name == "done":
                    break
                ev_name = None
    return StreamResult(events=events, plan=plan, final=final,
                        errors=errors, trace_steps=trace_steps,
                        elapsed_s=time.time() - t0)


def _backend() -> dict:
    with urllib.request.urlopen(f"{BASE}/api/backend", timeout=10) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

ADDRESSES = [
    pytest.param("2940 Brighton 3rd St, Brooklyn", id="brighton"),
    pytest.param("Hollis",                          id="hollis"),
    pytest.param("Hunts Point",                     id="hunts"),
]


# Steps every linear single_address run must hit, regardless of intent.
# Steps every NYC single-address run reports (ok or not). The reconcile
# step is reconcile_templated (no LLM) or reconcile_claims (LLM).
EXPECTED_STEPS = [
    "geocode",
    "select_deployment",
    "sandy",
    "dep_extreme_2080",
    "floodnet",
    "nyc311",
    "noaa_tides",
    "nws_alerts",
    "nws_obs",
    "microtopo",
    "ida_hwm",
]


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def backend_info() -> dict:
    return _backend()


def test_backend_endpoint_reachable(backend_info):
    assert backend_info.get("tier") in ("llm", "no_llm")
    if backend_info["tier"] == "llm":
        assert backend_info.get("reachable") is True, (
            f"Configured LLM endpoint is not reachable: {backend_info}"
        )


# ---------------------------------------------------------------------------
# Per-address single_address E2E
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", params=ADDRESSES)
def streamed(request) -> StreamResult:
    """Run the SSE stream once per address, share across assertions."""
    return _stream(request.param)


def test_no_error_events(streamed: StreamResult):
    assert not streamed.errors, (
        f"stream emitted {len(streamed.errors)} error events: "
        f"{streamed.errors[:3]}"
    )


def test_planner_emitted(streamed: StreamResult):
    assert streamed.plan is not None, "no plan event in stream"
    assert streamed.plan.get("intent") in (
        "single_address", "live_now", "neighborhood", "development_check"
    ), f"unknown intent: {streamed.plan.get('intent')}"


def test_expected_steps_fired(streamed: StreamResult):
    if streamed.plan and streamed.plan.get("intent") != "single_address":
        pytest.skip(
            f"intent={streamed.plan['intent']}; non-linear FSM has its own "
            "step list — see TestNeighborhood/TestLiveNow if added"
        )
    fired = set(streamed.trace_steps)
    missing = [s for s in EXPECTED_STEPS if s not in fired]
    assert not missing, (
        f"expected steps did not fire: {missing} "
        f"(actually fired: {sorted(fired)})"
    )


def test_final_paragraph_present(streamed: StreamResult):
    assert streamed.final is not None, "no final event"
    para = streamed.final.get("paragraph") or ""
    assert len(para) >= 100, (
        f"final paragraph too short ({len(para)} chars): {para!r}"
    )


def test_paragraph_has_citations(streamed: StreamResult):
    if streamed.final is None:
        pytest.skip("no final event")
    import re
    para = streamed.final.get("paragraph", "")
    cites = re.findall(r"\[([a-z][a-z0-9_]*)\]", para)
    assert len(cites) >= 3, (
        f"paragraph has {len(cites)} citations; expected ≥3.\n"
        f"paragraph: {para!r}"
    )


def test_grounding_reported(streamed: StreamResult):
    """Every final carries a grounding record; in LLM mode, dropped
    claims never appear in the paragraph."""
    if streamed.final is None:
        pytest.skip("no final event")
    g = streamed.final.get("grounding") or {}
    assert g.get("tier") in ("llm", "no_llm")
    para = streamed.final.get("paragraph", "")
    for d in g.get("dropped_claims") or []:
        assert d["text"] not in para, f"dropped claim rendered: {d}"


# ---------------------------------------------------------------------------
# Iterator test — used to spot-check cli-style consumers
# ---------------------------------------------------------------------------

def _iter_events(query: str) -> Iterator[tuple[str, dict]]:
    """Useful in REPL — yields (event_name, payload) lazily."""
    yield from _stream(query).events
