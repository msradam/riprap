"""MCP tool surface (`riprap.mcp.server`) — the agent-callable get_briefing
/ list_sources / get_citation tools. `list_sources` and `get_citation` hit
the real pebble registry (no network); `get_briefing` is checked for
correct output shaping against a stubbed Burr run — the run itself is
covered by the probe scripts.
"""

from __future__ import annotations

from riprap.mcp.server import get_briefing, get_citation, list_sources


def test_list_sources_known_deployment():
    out = list_sources("nyc")
    assert "error" not in out
    assert out["stones"]
    assert out["pebbles"]
    assert {"id", "type", "title", "stone", "provenance"} <= out["pebbles"][0].keys()


def test_list_sources_unknown_deployment():
    out = list_sources("atlantis")
    assert "error" in out


def test_get_citation_resolves_known_doc_id():
    doc_id = list_sources("nyc")["pebbles"][0]["provenance"]["doc_id"]
    cite = get_citation("nyc", doc_id)
    assert cite["doc_id"] == doc_id
    assert cite["source"]
    assert "error" not in cite


def test_get_citation_unknown_doc_id():
    cite = get_citation("nyc", "not_a_real_doc_id")
    assert "error" in cite


def test_get_briefing_shapes_burr_output(monkeypatch):
    """get_briefing trims the full result (dozens of raw pebble payloads)
    down to the agent-facing shape."""
    stub_out = {
        "deployment": "nyc",
        "intent": "single_address",
        "paragraph": "Elevation 1.2 m [microtopo].",
        "citations": {"microtopo": {"doc_id": "microtopo", "source": "USGS 3DEP"}},
        "compliance": {"passed": True, "n_passed": 13, "n_total": 13},
        "grounding": {"tier": "llm", "dropped_claims": [{"text": "x", "reason": "y"}]},
        "sandy": {"inside": True},  # raw pebble payload, must not leak through
        "trace": [{"step": "geocode"}],
    }
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q: stub_out)

    out = get_briefing("189 Atlantic Ave, Brooklyn, NY")

    assert out["paragraph"] == stub_out["paragraph"]
    assert out["citations"] == stub_out["citations"]
    assert out["disclosure_checks"] == stub_out["compliance"]
    assert out["mode"] == "llm" and out["dropped_claims"][0]["reason"] == "y"
    assert "sandy" not in out and "trace" not in out


def test_get_evidence_lists_manifest_sentences(monkeypatch):
    from riprap.mcp.server import get_evidence

    stub = {"deployment": "nyc", "intent": "single_address", "lat": 40.69, "lon": -73.99,
            "geocode": {"address": "189 ATLANTIC AVENUE"},
            "microtopo": {"narrative": "Elevation 16.89 m; HAND 16.76 m."}, "citations": {}}
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q, no_llm=False: stub)
    out = get_evidence("189 Atlantic Ave, Brooklyn, NY")
    assert out["place"] == "189 ATLANTIC AVENUE"
    assert {"doc_id": "microtopo", "stone": "Cornerstone", "text": "Elevation 16.89 m; HAND 16.76 m.",
            "maturity": "production"} in out["evidence"]


def test_server_imports_and_lists_tools():
    """Fresh-install guard: the server module imports on the pinned SDK
    and registers its tools."""
    import asyncio

    from riprap.mcp.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"get_briefing", "list_sources", "get_citation", "get_evidence",
            "get_district_summary", "nyc311_flood_requests"} <= names


def test_get_citation_never_returns_null_vintage(monkeypatch):
    """Every shipped NYC source reports a vintage (source date, Socrata
    metadata for live Socrata sources, or when our copy was retrieved)."""
    monkeypatch.setattr("riprap.core.pebbles.vintage.socrata_updated_at",
                        lambda domain, ds: "2026-09-26T01:38:37+0000")
    for pebble in list_sources("nyc")["pebbles"]:
        cite = get_citation("nyc", pebble["provenance"]["doc_id"])
        assert cite["vintage"], cite
