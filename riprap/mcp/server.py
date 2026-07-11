"""Riprap MCP server — exposes Riprap as three agent-callable tools
instead of a full 1:1 wrap of the HTTP API.

Deliberately small surface. An audit of 116 production MCP servers found
the well-designed ones expose a median of ~19% of the wrapped API's
operations through curation, not mirroring (arxiv.org/html/2507.16044);
Riprap's HTTP surface has ~20 routes (layer tiles, SSE streams, PDF
render, debug endpoints) that make no sense as a single agent tool call.
These three do:

  get_briefing(address)            run a full cited flood briefing
  list_sources(deployment)         the stones + pebbles a deployment fires
  get_citation(deployment, doc_id) provenance for one cited source

Run standalone (stdio transport, for Claude Desktop / any local MCP
client config)::

    .venv/bin/python -m riprap.mcp.server

Or as a network service (streamable-http, for a remote agent)::

    .venv/bin/python -m riprap.mcp.server --http --port 8765
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "riprap",
    instructions=(
        "Riprap composes public-record flood data (FEMA, NOAA, USGS, NWS, "
        "city 311) into a citation-grounded flood-exposure briefing for a "
        "US street address. Every numeric claim in a briefing carries an "
        "inline [doc_id] citation resolvable via get_citation. Riprap is "
        "an informational reference dossier, not a FEMA flood zone "
        "determination, a professional engineering opinion, or a "
        "substitute for the NFIP appeal process."
    ),
)


@mcp.tool()
def get_briefing(address: str) -> dict:
    """Run a full flood-exposure briefing for a US street address.

    Returns the cited prose plus a structured citation list and the
    deterministic compliance-predicate summary. Deployment routing is
    automatic — the address is geocoded and matched to whichever shipped
    deployment's bounding box contains it (nyc, chicago, seattle, sf,
    boston, albany, ...); no deployment argument needed.
    """
    from riprap.core.burr.app import run as _run_briefing

    out = _run_briefing(address)
    return {
        "address": address,
        "deployment": out.get("deployment"),
        "intent": out.get("intent"),
        "paragraph": out.get("paragraph"),
        "citations": out.get("citations") or [],
        "compliance": out.get("compliance"),
    }


def _resolve_deployment_root(deployment: str):
    from pathlib import Path

    from riprap.core.pebbles.deployments import deployment_by_name

    dep = deployment_by_name(deployment)
    if dep is not None:
        return dep.root
    repo_root = Path(__file__).resolve().parent.parent.parent
    p = Path(deployment)
    if not p.is_absolute():
        p = repo_root / "deployments" / deployment
    return p if p.is_dir() else None


@mcp.tool()
def list_sources(deployment: str = "nyc") -> dict:
    """List the stones (role groups) and pebbles (data sources) a Riprap
    deployment fires, with each source's provenance and citation doc_id.

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
    """Resolve one [doc_id] citation from a briefing to its source
    provenance: publisher, URL, license, and data vintage.

    `doc_id` is the bracketed id a briefing sentence cites, e.g. the
    `[nyc311]` in "34 complaints filed within 200 m [nyc311]." Matches a
    pebble's `provenance.doc_id` first, falling back to its pebble id.
    """
    from riprap.core.pebbles import load_registry

    root = _resolve_deployment_root(deployment)
    if root is None:
        return {"error": f"unknown deployment {deployment!r}"}
    registry = load_registry(root)
    for pebble in registry.all():
        prov = pebble.manifest.provenance
        if (prov.doc_id or pebble.id) == doc_id:
            return {
                "doc_id": doc_id,
                "source": prov.source_name,
                "title": prov.citation or pebble.manifest.title,
                "url": prov.source_url,
                "license": prov.license,
                "vintage": prov.last_updated.isoformat() if prov.last_updated else None,
            }
    return {"error": f"no source with doc_id {doc_id!r} in deployment {deployment!r}"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--http", action="store_true", help="serve streamable-http instead of stdio")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.http:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
