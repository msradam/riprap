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
    """get_briefing must trim the full Burr state dict (dozens of raw
    pebble payloads) down to the agent-facing shape: paragraph, citations,
    compliance — not the entire internal state."""
    stub_out = {
        "deployment": "nyc",
        "intent": "single_address",
        "paragraph": "Elevation 1.2 m [microtopo].",
        "citations": [{"doc_id": "microtopo", "source": "USGS 3DEP"}],
        "compliance": {"passed": True, "n_passed": 13, "n_total": 13},
        "sandy": {"inside": True},  # raw pebble payload — must NOT leak through
        "trace": [{"step": "geocode"}],
    }
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q: stub_out)

    out = get_briefing("189 Atlantic Ave, Brooklyn, NY")

    assert out["address"] == "189 Atlantic Ave, Brooklyn, NY"
    assert out["deployment"] == "nyc"
    assert out["paragraph"] == stub_out["paragraph"]
    assert out["citations"] == stub_out["citations"]
    assert out["compliance"] == stub_out["compliance"]
    assert "sandy" not in out
    assert "trace" not in out
