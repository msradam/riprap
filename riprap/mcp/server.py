"""Riprap MCP server: a small set of agent-callable tools, not a 1:1 wrap
of the HTTP API.

Deliberately small surface. An audit of 116 production MCP servers found
the well-designed ones expose a median of ~19% of the wrapped API's
operations through curation, not mirroring (arxiv.org/html/2507.16044).

  list_sources(deployment)            the stones and pebbles a deployment runs
  get_evidence(address, hazard)       cited evidence for an address, no model called (flood, or heat in NYC)
  get_district_summary(code, hazard)  the same for an NYC community district
  get_citation(deployment, doc_id)    provenance and vintage for one source
  nyc311_flood_requests(...)          311 flood requests near a point or in a district
  plan_query(question, address)       how a question would be routed, without running it
  get_briefing(address, question)     the briefing, answering the question when given

Every tool works with no language model, and that is the default. Rules
answer first: every sentence is a source's template filled from the
fetched record, and a question is answered by fixed rules over its words.
A server may configure an optional open model (IBM Granite by default).
It is then asked only about a question the rules do not match: it may
route the question (intent, time frame, which extra sources run) and
propose a lead (yes, no, partly, count, cannot answer) with up to four of
the existing cited sentences. Rules check the lead against those sentences
and drop it if it fails. The model writes no sentence of a briefing or an
answer. (The one exception is a server started with RIPRAP_LLM_BARE=1, off
by default, which has the model restate a bare place's evidence as claims
checked for their citations and numbers.) Run over stdio (for a local MCP client config) or
streamable HTTP:

    uv run riprap-mcp                     # or: uv run python -m riprap.mcp.server
    uv run riprap-mcp --http --port 8765
"""

from __future__ import annotations

import argparse
import functools

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "riprap",
    instructions=(
        "Riprap composes public-record flood data (FEMA, NOAA, USGS, NWS, "
        "NYC 311, NYC DEP, FloodNet) into cited evidence for a US street "
        "address, and for New York City public-record heat data as well "
        "(Landsat surface temperature, the Health Department's index and heat "
        "illness visits, station records, the Weather Service's forecast, "
        "NPCC4): pass hazard='heat', or ask get_briefing a heat question. "
        "Every evidence item carries its sentence, the source's own "
        "figures (value), its source URL and data vintage, and a doc_id "
        "resolvable via get_citation. FloodNet-derived items are licensed "
        "CC BY-NC-SA 4.0, not Apache-2.0: results that include them carry "
        "license_notices. Riprap "
        "is an informational reference, not a FEMA flood zone determination, "
        "a professional engineering opinion, or a substitute for the NFIP "
        "appeal process. Start with get_evidence (an address) or "
        "get_district_summary (an NYC community district): both return cited "
        "sentences and never call a language model. plan_query shows how a question "
        "would be routed without running the sources. get_briefing returns the "
        "same evidence as a briefing and answers a question by fixed rules over "
        "the question's words. Rules answer first. If the server has an optional "
        "open language model configured, it is asked only about a question the "
        "rules do not match: it may route the question and propose a lead (yes, "
        "no, partly, count, cannot answer) with up to four of the existing cited "
        "sentences; rules check that lead against the sentences and drop it if it "
        "fails. By default the model never writes a sentence. answer_path says which path "
        "produced a result (rules or llm). Evidence and briefing results carry "
        "a record block (query, time, code version, digest) and name the "
        "sources that failed to respond."
    ),
)


@functools.cache
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
    it ran, the code version and commit, and a digest of the body (SHA-256
    of the body as JSON with sorted keys and Python's default separators)."""
    import hashlib
    import json
    from datetime import UTC, datetime
    from importlib.metadata import version

    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return {"query": out.get("query"), "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "riprap_version": version("riprap"), "commit": _commit(), "sha256": digest}


def _failed(out: dict) -> list[dict]:
    """Sources the run consulted that did not answer, by name and reason
    (the HTTP result's `failed`; computed here for a result that has none)."""
    from riprap.core.burr.templated_reconciler import failed_sources

    return out["failed"] if "failed" in out else failed_sources(out)


def _place_match(out: dict) -> str | None:
    """"exact" when the place resolved is the one asked for, "closest" for
    a nearby, similar or neighbourhood-level match that a reader should
    check before relying on the briefing."""
    return (out.get("geocode") or {}).get("match")


# Fields a pebble value carries for the page (a sentence, a chart, a map
# shape), not for a program.
_PRESENTATION = {"narrative", "geojson", "headline_value", "citation", "inside_or_outside"}


def _value(v) -> dict | None:
    """The source's own figures for one evidence item, so a program reads
    numbers and names, not a sentence."""
    if not isinstance(v, dict):
        return None
    return {k: x for k, x in v.items() if k not in _PRESENTATION and not k.endswith(("_phrasing", "_note"))}


def _evidence_payload(out: dict) -> dict:
    from riprap.core.burr import evidence
    from riprap.core.pebbles.vintage import license_notices

    # A place outside every city ran the federal sources: `deployment` is null.
    stones, registry = evidence.load(out.get("deployment") or "__none__")
    items = evidence.collect(out, stones, registry)
    heading = {s.id: s.name for s in stones.all()}
    if not items:  # say why, rather than hand back an empty list
        text = (out.get("paragraph") or "").split("\n\n")
        body = {"place": None, "error": text[1] if len(text) > 1 else text[0], "evidence": [],
                "failed": _failed(out)}
        return {**body, "record": _record(out, body)}
    cites = out.get("citations") or {}
    body = {
        "place": (out.get("geocode") or {}).get("address"),
        "place_match": _place_match(out),
        "place_note": (out.get("geocode") or {}).get("note"),  # which area or borough was chosen, and the others
        "lat": out.get("lat"),
        "lon": out.get("lon"),
        "deployment": out.get("deployment"),
        "intent": out.get("intent"),
        "evidence": [{"doc_id": e.doc_id, "stone": heading.get(e.stone_id, e.stone_id),
                      "text": e.text, "value": _value(e.value), "maturity": e.maturity,
                      "source_url": (cites.get(e.doc_id) or {}).get("url"),
                      "vintage": (cites.get(e.doc_id) or {}).get("vintage"),
                      # Only where the source's licence binds this item (FloodNet).
                      **({"license": cites[e.doc_id].get("license")}
                         if (cites.get(e.doc_id) or {}).get("license_notice") else {})} for e in items],
        "citations": cites,
        "license_notices": license_notices(cites),
        "failed": _failed(out),
    }
    return {**body, "record": _record(out, body)}


def _heat_plan(place: str) -> dict:
    """The plan for a bare place's heat briefing."""
    from riprap.core.burr.app import plan_for

    plan = plan_for(place, no_llm=True)
    if plan["intent"] not in ("not_implemented", "out_of_scope"):
        plan["focus"] = {"hazard": "heat", "time_frame": "any", "assets": []}
    return plan


@mcp.tool()
def get_evidence(address: str, hazard: str = "flood") -> dict:
    """Cited flood evidence for a US street address. No language model is
    called, whatever the server has configured. With hazard="heat", the heat evidence for a New York City address (measured
    surface temperature, the Health Department's vulnerability index and
    heat illness visits, the station record, the Weather Service's forecast
    and alerts, NPCC4 projections, NYC Parks cooling features).

    Geocodes the address, routes it to the deployment covering it, runs
    every data source for that place and returns one entry per source
    that had data: {doc_id, stone, text, value, maturity, source_url,
    vintage}. `text` is the cited sentence and `value` the source's own
    figures (counts, zones, names, readings), so a program need not parse
    the sentence; `citations` has each source's full provenance.
    Deterministic: the text is each source's manifest template filled
    from the fetched values.
    """
    from riprap.core.burr.app import run

    if hazard not in ("flood", "heat"):
        return {"error": f"hazard must be 'flood' or 'heat', not {hazard!r}"}
    if hazard == "heat":
        return _evidence_payload(run(address, _heat_plan(address), no_llm=True))
    return _evidence_payload(run(address, no_llm=True))


@mcp.tool()
def get_district_summary(community_district: str, hazard: str = "flood") -> dict:
    """The same evidence for an NYC community district, such as QN12
    (Jamaica, St. Albans, Hollis) or BK15 (Sheepshead Bay, Homecrest):
    shares of the district in the Sandy and DEP extents, terrain, 311 flood
    complaints, the exposed subway entrances, schools, NYCHA developments
    and hospitals and NYC Planning's floodplain counts. No language model
    is called, whatever the server has configured. With hazard="heat": the district's surface temperature against
    the city's, its Heat Vulnerability Index and heat illness visits, tree
    canopy, the station record, the forecast and NYC Parks cooling features."""
    from riprap.core.burr.app import district_summary
    from riprap.core.burr.place import parse_district

    if hazard not in ("flood", "heat"):
        return {"error": f"hazard must be 'flood' or 'heat', not {hazard!r}"}
    # The check the HTTP route makes: "QN99" once came back as a full briefing for the
    # nearest name match, Astoria (North)-Ditmars-Steinway.
    found, refusal = parse_district(community_district)
    if not found:
        return {"error": refusal or f"{community_district!r} is not a community district code such as QN12"}
    return _evidence_payload(district_summary(found, no_llm=True, hazard=hazard))


@mcp.tool()
def nyc311_flood_requests(address: str | None = None, lat: float | None = None,
                          lon: float | None = None, radius_m: float = 200,
                          community_district: str | None = None, days: int = 365) -> dict:
    """Flood-related NYC 311 requests (street flooding, sewer backup, catch
    basin, manhole overflow) over the last `days`, either within `radius_m`
    of a point (give lat/lon or an address) or inside a community district
    (e.g. QN12). Returns exact counts by descriptor and by month, the ten
    most recent requests (each at its block: street and cross streets,
    never a house number) and the exact query as `query_url`. Source: NYC
    Open Data erm2-nwe9."""
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
    """How Riprap would route a question, without running the sources
    (it geocodes the place): intent, targets, the question and its focus,
    the pebbles the planner chose, the always-run floor, and the final
    selection for the deployment the place routes to. `planner` says
    which planner ran: "regex", the fixed rules, which choose no pebbles
    (`chosen` is null) so `selected` is every pebble for the intent; or
    "llm" when the server has the optional model configured and the rules
    did not match the question. The rules route first: a bare place, a
    refusal, a comparison and any question the answer rules recognise never
    reach the model. When it is asked, the model may set the intent, the
    time frame and assets of the focus, and which sources run beyond the
    fixed floor; the hazard and the question text are set in code."""
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
        "planner": "llm" if plan.get("llm_calls") else "regex",
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
    A question about outdoor heat ("Is this block hotter than the rest of
    the city?", "Will it be dangerously hot this week?") gets the heat
    briefing's answer instead, for New York City addresses.
    Rules answer first, and with no model configured they are the only
    path: the briefing is the cited evidence, a question is answered by
    fixed rules over its words, and `mode` is "no_llm" (the HTTP API calls
    the same value `grounding.tier`).
    A server may configure an optional open language model
    (RIPRAP_LLM_BASE_URL and RIPRAP_LLM_MODEL; IBM Granite by default). It
    is asked only about a question the rules do not match. It may route
    the question (intent, time frame, which extra sources run) and propose
    a lead (yes, no, partly, count or cannot answer) with up to four of the
    existing cited sentences. The lead is printed as a fixed phrase and is
    checked by rules against those sentences: one that fails is sent back
    once, then dropped, and the answer says the sources do not answer
    (the dropped choice is listed under dropped_claims, not shown). The
    model never writes a sentence, unless the server was started with
    RIPRAP_LLM_BARE=1 (off by default), which has it restate the evidence
    for a bare place as claims checked for their citations and numbers.
    `answer_path` is "llm" when a model was
    called for the result and "rules" when none was; `answer_mode` is
    "rules" or "extractive" (the model's choice). `consulted`,
    `not_checked` and `failed` list the sources."""
    from riprap.core.burr.app import run
    from riprap.core.pebbles.vintage import license_notices

    out = run(_query(address, question))
    g = out.get("grounding") or {}
    body = {
        "address": address,
        "question": question,
        "place": (out.get("geocode") or {}).get("address"),
        "place_match": _place_match(out),
        "place_note": (out.get("geocode") or {}).get("note"),  # which area or borough was chosen, and the others
        "deployment": out.get("deployment"),
        "intent": out.get("intent"),
        "paragraph": out.get("paragraph"),
        "mode": g.get("tier"),
        # Whether the question was answered, by what ("rules" or "extractive",
        # the model's choice) and with which lead (yes, no, partly, count,
        # facts, experimental, no_prediction, cannot_answer).
        "answered": g.get("answered"),
        "answer_mode": g.get("answer_mode"),
        "answer_lead": g.get("answer_lead"),
        # Which path produced this result, refusals and bare briefings included: "rules" (no language model
        # was called) or "llm" (a model planned the query or chose the answer's sentences).
        "answer_path": out.get("answer_path"),
        "dropped_claims": g.get("dropped_claims") or [],
        "citations": out.get("citations") or {},
        "license_notices": license_notices(out.get("citations")),
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
    seattle, albany or federal).
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
