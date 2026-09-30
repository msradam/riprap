"""Riprap MCP server: a small set of agent-callable tools, not a 1:1 wrap
of the HTTP API.

Deliberately small surface. An audit of 116 production MCP servers found
the well-designed ones expose a median of ~19% of the wrapped API's
operations through curation, not mirroring (arxiv.org/html/2507.16044).

  list_sources(deployment)            the stones and pebbles a deployment runs
  get_evidence(address)               cited evidence for an address, no LLM
  get_district_summary(code)          the same for an NYC community district
  get_citation(deployment, doc_id)    provenance and vintage for one source
  nyc311_flood_requests(...)          311 flood requests near a point or in a district
  plan_query(question, address)       how a question would be routed, without running it
  get_briefing(address, question)     the briefing, answering the question when given

Every tool except get_briefing works without an LLM. Run over stdio (for a
local MCP client config) or streamable HTTP:

    uv run riprap-mcp                     # or: uv run python -m riprap.mcp.server
    uv run riprap-mcp --http --port 8765
"""

from __future__ import annotations

import argparse

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "riprap",
    instructions=(
        "Riprap composes public-record flood data (FEMA, NOAA, USGS, NWS, "
        "NYC 311, NYC DEP, FloodNet) into cited evidence for a US street "
        "address. Every evidence sentence carries a doc_id resolvable via "
        "get_citation. Sentences marked 'Experimental:' come from model "
        "layers without an evaluation that supports them as evidence. Riprap "
        "is an informational reference, not a FEMA flood zone determination, "
        "a professional engineering opinion, or a substitute for the NFIP "
        "appeal process. Start with get_evidence (an address) or "
        "get_district_summary (an NYC community district): both return cited "
        "sentences without a language model. plan_query shows how a question "
        "would be routed without fetching anything. get_briefing returns the "
        "same evidence as a briefing and, only when the server has an LLM "
        "endpoint configured, an answer to the question whose every claim is "
        "checked against its cited source. Every result carries a record "
        "block (query, time, code version, digest) and names the sources that "
        "failed to respond."
    ),
)


def _commit() -> str | None:
    """The git commit the server runs from, when it runs from a checkout."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip() or None
    except Exception:  # noqa: BLE001 - not a checkout, or no git
        return None


def _record(out: dict, body: dict) -> dict:
    """What a reader needs to reproduce or verify a result: the query, when
    it ran, the code version and commit, and a digest of the body."""
    import hashlib
    import json
    from datetime import UTC, datetime
    from importlib.metadata import version

    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return {"query": out.get("query"), "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "riprap_version": version("riprap"), "commit": _commit(), "sha256": digest}


def _failed(out: dict) -> list[dict]:
    """Sources the run consulted that did not answer, by name and reason."""
    trace = {t.get("step"): t for t in out.get("trace") or []}
    return [{"id": c["id"], "title": c.get("title"), "reason": trace[c["id"]].get("err")}
            for c in out.get("consulted") or [] if trace.get(c["id"], {}).get("ok") is False]


def _place_match(out: dict) -> str | None:
    """"exact" when the place resolved is the one asked for, "closest" for
    a nearby, similar or neighbourhood-level match that a reader should
    check before relying on the briefing."""
    return (out.get("geocode") or {}).get("match")


def _evidence_payload(out: dict) -> dict:
    from riprap.core.burr import evidence

    stones, registry = evidence.load(out.get("deployment") or "nyc")
    items = evidence.collect(out, stones, registry)
    heading = {s.id: s.name for s in stones.all()}
    if not items:  # say why, rather than hand back an empty list
        text = (out.get("paragraph") or "").split("\n\n")
        return {"place": None, "error": text[1] if len(text) > 1 else text[0], "evidence": [],
                "failed": _failed(out)}
    body = {
        "place": (out.get("geocode") or {}).get("address"),
        "place_match": _place_match(out),
        "lat": out.get("lat"),
        "lon": out.get("lon"),
        "deployment": out.get("deployment"),
        "intent": out.get("intent"),
        "evidence": [{"doc_id": e.doc_id, "stone": heading.get(e.stone_id, e.stone_id),
                      "text": e.text, "maturity": e.maturity} for e in items],
        "citations": out.get("citations") or {},
        "failed": _failed(out),
    }
    return {**body, "record": _record(out, body)}


@mcp.tool()
def get_evidence(address: str) -> dict:
    """Cited flood evidence for a US street address, without an LLM.

    Geocodes the address, routes it to the deployment covering it, runs
    every data source for that place and returns one entry per source
    that had data: {doc_id, stone, text, maturity}, plus citations with
    source URL and vintage. Deterministic: the text is each source's
    manifest template filled from the fetched values.
    """
    from riprap.core.burr.app import run

    return _evidence_payload(run(address, no_llm=True))


@mcp.tool()
def get_district_summary(community_district: str) -> dict:
    """The same evidence for an NYC community district, such as QN12
    (Jamaica, St. Albans, Hollis) or BK15 (Sheepshead Bay, Homecrest):
    shares of the district in the Sandy and DEP extents, terrain, 311 flood
    complaints and DOB permits, without an LLM."""
    from riprap.core.burr.app import district_summary

    return _evidence_payload(district_summary(community_district, no_llm=True))


@mcp.tool()
def nyc311_flood_requests(address: str | None = None, lat: float | None = None,
                          lon: float | None = None, radius_m: float = 200,
                          community_district: str | None = None, days: int = 365) -> dict:
    """Flood-related NYC 311 requests (street flooding, sewer backup, catch
    basin, manhole overflow) over the last `days`, either within `radius_m`
    of a point (give lat/lon or an address) or inside a community district
    (e.g. QN12). Returns exact counts by descriptor and by month and the
    ten most recent requests. Source: NYC Open Data erm2-nwe9."""
    from app.context.nyc311 import flood_requests

    if address and (lat is None or lon is None) and not community_district:
        from app.geocode import geocode_one

        hit = geocode_one(address)
        if hit is None:
            return {"error": f"could not geocode {address!r}"}
        lat, lon = hit.lat, hit.lon
    return flood_requests(lat=lat, lon=lon, radius_m=radius_m,
                          community_district=community_district, days=days)


def _query(address: str, question: str | None) -> str:
    if not question:
        return address
    return question if address.lower() in question.lower() else f"{question} ({address})"


@mcp.tool()
def plan_query(question: str, address: str | None = None) -> dict:
    """How Riprap would route a question, without running it: intent,
    targets, the question and its focus, the pebbles the planner chose,
    the always-run floor, and the final selection for the deployment the
    place routes to. Uses the LLM planner when configured, else the regex
    planner (which selects every pebble for the intent)."""
    from app.geocode import geocode_one
    from riprap.core.burr.app import plan_for
    from riprap.core.burr.stones import floor_for, select_pebbles
    from riprap.core.pebbles.bridge import get_registry
    from riprap.core.pebbles.deployments import pick_deployment

    plan = plan_for(_query(address or "", question) if address else question)
    target = (plan.get("targets") or [{}])[0].get("text") or question
    hit = geocode_one(target) if plan["intent"] not in ("neighborhood", "development_check") else None
    dep = pick_deployment(hit.lat, hit.lon) if hit else None
    deployment = dep.name if dep else "nyc"
    return {
        "intent": plan["intent"], "targets": plan.get("targets"), "place": plan.get("place"),
        "question": plan.get("question"),
        "focus": plan.get("focus"), "chosen": plan.get("pebbles"),
        "floor": sorted(floor_for(plan)), "deployment": deployment,
        "selected": select_pebbles(plan, get_registry(deployment)),
        "rationale": plan.get("rationale"),
    }


@mcp.tool()
def get_briefing(address: str, question: str | None = None) -> dict:
    """The flood-exposure briefing for a US street address, optionally
    answering a question about it ("Has this block flooded since Ida?").
    Works without an LLM: the briefing is then the cited evidence and
    `mode` is "no_llm". With an LLM endpoint configured on the server
    (RIPRAP_LLM_BASE_URL and RIPRAP_LLM_MODEL), the planner picks the
    sources the question needs and the answer is the lead plus cited
    sentences the model chose, each checked in code (failed claims are
    listed under dropped_claims, not shown). `consulted`, `not_checked`
    and `failed` list the sources."""
    from riprap.core.burr.app import run

    out = run(_query(address, question))
    g = out.get("grounding") or {}
    body = {
        "address": address,
        "question": question,
        "place": (out.get("geocode") or {}).get("address"),
        "place_match": _place_match(out),
        "deployment": out.get("deployment"),
        "intent": out.get("intent"),
        "paragraph": out.get("paragraph"),
        "mode": g.get("tier"),
        "dropped_claims": g.get("dropped_claims") or [],
        "citations": out.get("citations") or {},
        "consulted": out.get("consulted") or [],
        "not_checked": out.get("not_checked") or [],
        "failed": _failed(out),
        "disclosure_checks": out.get("compliance"),
    }
    return {**body, "record": _record(out, body)}


def _resolve_deployment_root(deployment: str):
    from riprap.core.pebbles.deployments import deployment_root

    root = deployment_root(deployment)
    return root if (root / "manifests").is_dir() else None


@mcp.tool()
def list_sources(deployment: str = "nyc") -> dict:
    """List the stones (role groups) and pebbles (data sources) a Riprap
    deployment runs, with each source's provenance, vintage, citation
    doc_id and maturity (production or experimental).

    `deployment` is a shipped deployment directory name (nyc, chicago,
    seattle, sf, boston, albany, ...).
    """
    from riprap.core.pebbles import load_registry
    from riprap.core.pebbles.describe import describe_deployment
    from riprap.core.stones import load_stones

    root = _resolve_deployment_root(deployment)
    if root is None:
        return {"error": f"unknown deployment {deployment!r}"}
    return describe_deployment(load_stones(root), load_registry(root))


@mcp.tool()
def get_citation(deployment: str, doc_id: str) -> dict:
    """Resolve one doc_id to its source: publisher, URL, license, the
    source's own date_modified, when our copy was retrieved, and a
    `vintage` display string. Live Socrata sources report their current
    dataUpdatedAt; other live sources report "live".
    """
    from riprap.core.pebbles import load_registry
    from riprap.core.pebbles.vintage import citation

    root = _resolve_deployment_root(deployment)
    if root is None:
        return {"error": f"unknown deployment {deployment!r}"}
    registry = load_registry(root)
    for pebble in registry.all():
        if (pebble.manifest.provenance.doc_id or pebble.id) == doc_id:
            return citation(pebble.manifest, fetched=False)
    return {"error": f"no source with doc_id {doc_id!r} in deployment {deployment!r}"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--http", action="store_true", help="serve streamable-http instead of stdio")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.http:
        mcp.run(transport="streamable-http", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
