"""POST /api/agent/batch — runs a list of addresses through the same
single-address pipeline as GET /api/agent, one request in, one JSON array
out. The biggest structural gap for a civic engineer or NGO checking a
portfolio of properties, since every other route takes one query at a
time. Validation logic tested directly against the route function with a
fake Request — no running server needed, and no need to invoke the real
Ollama/RAG stack for input-shape checks."""
from __future__ import annotations

import os

os.environ.setdefault("RIPRAP_DEPLOYMENT", "deployments/nyc")


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        if self._payload is _INVALID_JSON:
            raise ValueError("bad json")
        return self._payload


_INVALID_JSON = object()


async def _call(payload):
    from web.main import api_agent_batch
    return await api_agent_batch(_FakeRequest(payload))


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_rejects_invalid_json():
    resp = _run(_call(_INVALID_JSON))
    assert resp.status_code == 400


def test_rejects_missing_addresses_key():
    resp = _run(_call({}))
    assert resp.status_code == 400


def test_rejects_empty_addresses_list():
    resp = _run(_call({"addresses": []}))
    assert resp.status_code == 400


def test_rejects_non_list_addresses():
    resp = _run(_call({"addresses": "123 Main St"}))
    assert resp.status_code == 400


def test_rejects_non_string_entries():
    resp = _run(_call({"addresses": ["123 Main St", 42]}))
    assert resp.status_code == 400


def test_rejects_blank_entries():
    resp = _run(_call({"addresses": ["123 Main St", "   "]}))
    assert resp.status_code == 400


def test_rejects_batch_over_the_cap():
    from web.main import _BATCH_MAX_ADDRESSES
    resp = _run(_call({"addresses": [f"{i} Main St" for i in range(_BATCH_MAX_ADDRESSES + 1)]}))
    assert resp.status_code == 400


def test_runs_each_address_and_reports_per_address_failure(monkeypatch):
    """One address's failure shouldn't sink the whole batch — its slot
    carries an error instead of a briefing, other slots still succeed."""
    def fake_run(query):
        if "bad" in query:
            raise RuntimeError("boom")
        return {"query": query, "intent": "single_address", "paragraph": "ok"}

    monkeypatch.setattr("riprap.core.burr.app.run", fake_run)
    resp = _run(_call({"addresses": ["123 Main St", "bad address", "456 Oak Ave"]}))
    assert resp.status_code == 200
    body = json_body(resp)
    assert body["n"] == 3
    assert body["results"][0]["paragraph"] == "ok"
    assert "error" in body["results"][1]
    assert body["results"][2]["paragraph"] == "ok"


def json_body(resp):
    import json
    return json.loads(resp.body)
