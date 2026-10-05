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
            "microtopo": {"narrative": "Elevation 16.89 m; HAND 16.76 m.", "point_elev_m": 16.89, "hand_m": 16.76},
            "citations": {"microtopo": {"url": "https://www.usgs.gov/3dep", "vintage": "2018"}}}
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q, no_llm=False: stub)
    out = get_evidence("189 Atlantic Ave, Brooklyn, NY")
    assert out["place"] == "189 ATLANTIC AVENUE"
    # The sentence, and beside it the figures and the source a program needs:
    # no parsing of prose, no second call for provenance.
    assert {"doc_id": "microtopo", "stone": "Cornerstone", "text": "Elevation 16.89 m; HAND 16.76 m.",
            "value": {"point_elev_m": 16.89, "hand_m": 16.76}, "maturity": "production",
            "source_url": "https://www.usgs.gov/3dep", "vintage": "2018"} in out["evidence"]


def test_floodnet_content_is_labelled_in_every_tool_result(monkeypatch):
    """FloodNet-derived content is CC BY-NC-SA 4.0, not Apache-2.0: a client
    that reads only one tool result sees the licence, the credit, the
    papers to cite, the retrieval time and the notice."""
    from riprap.core.burr import evidence
    from riprap.mcp.server import get_district_summary, get_evidence

    _, registry = evidence.load("nyc")
    cite = evidence.citation(registry.get("floodnet").manifest)
    stub = {"deployment": "nyc", "intent": "single_address", "geocode": {"address": "90-11 183 STREET"},
            "paragraph": "2 FloodNet sensors within 600 m have recorded 6 flood events [floodnet].",
            "floodnet": {"narrative": "2 FloodNet sensors within 600 m have recorded 6 flood events.", "n_sensors": 2,
                         "license": "CC BY-NC-SA 4.0"},
            "citations": {"floodnet": cite, "microtopo": {"url": "https://www.usgs.gov/3dep", "license": "public domain"}}}
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q, *a, **k: stub)
    monkeypatch.setattr("riprap.core.burr.app.district_summary", lambda code, **k: stub)
    for out in (get_evidence("90-11 183 St, Queens"), get_district_summary("QN12"), get_briefing("90-11 183 St, Queens")):
        (notice,) = out["license_notices"]
        assert notice["doc_id"] == "floodnet" and notice["license"] == "CC BY-NC-SA 4.0"
        assert notice["license_url"] == "https://creativecommons.org/licenses/by-nc-sa/4.0/"
        assert notice["attribution"] == "FloodNet (New York University and The City University of New York)"
        assert "10.1029/2023WR036806" in notice["references"][0] and "10.1016/j.watres.2022.118648" in notice["references"][1]
        assert "not covered by Riprap's Apache-2.0" in notice["notice"] and notice["retrieved_at"]
        assert out["citations"]["floodnet"]["license_notice"] == notice["notice"]
    item = next(e for e in get_evidence("90-11 183 St, Queens")["evidence"] if e["doc_id"] == "floodnet")
    assert item["license"] == "CC BY-NC-SA 4.0" and item["value"]["license"] == "CC BY-NC-SA 4.0"
    assert get_citation("nyc", "floodnet")["license_notice"] == cite["license_notice"]
    # A result with no FloodNet content carries no notice.
    monkeypatch.setattr("riprap.core.burr.app.run", lambda q, *a, **k: {**stub, "floodnet": None, "citations": {}})
    assert get_briefing("90-11 183 St, Queens")["license_notices"] == []


def test_server_imports_and_lists_tools():
    """Fresh-install guard: the server module imports on the pinned SDK
    and registers its tools."""
    import asyncio

    from riprap.mcp.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"get_briefing", "list_sources", "get_citation", "get_evidence",
            "get_district_summary", "nyc311_flood_requests", "plan_query"} <= names


def test_get_citation_never_returns_null_vintage(monkeypatch):
    """Every shipped NYC source reports a vintage (source date, Socrata
    metadata for live Socrata sources, or when our copy was retrieved)."""
    monkeypatch.setattr("riprap.core.pebbles.vintage.socrata_updated_at",
                        lambda domain, ds: "2026-09-26T01:38:37+0000")
    for pebble in list_sources("nyc")["pebbles"]:
        cite = get_citation("nyc", pebble["provenance"]["doc_id"])
        assert cite["vintage"], cite
