"""Deployment description — the stones+pebbles summary shared by the
HTTP `/api/pebbles` route and the MCP `list_sources` tool, so both
surfaces describe a deployment identically.
"""

from __future__ import annotations

from riprap.core.pebbles.registry import Registry
from riprap.core.pebbles.vintage import resolve
from riprap.core.stones import StoneRegistry


def describe_deployment(stones_reg: StoneRegistry, pebble_reg: Registry) -> dict:
    """A deployment's stones + pebbles, manifest guts stripped.

    Per-pebble payload keeps just the parts a caller needs to draw a card
    or cite a source: id/type/title/stone/tier, display hints, narration,
    provenance, and offline-fallback behavior. Drops `config` / `shaper` /
    `trace_summary` / `spatial.crs`, which are adapter implementation
    detail no external caller needs.
    """
    stones = [
        {
            "id": s.id,
            "name": s.name,
            "tagline": s.tagline,
            "description": s.description,
            "order": s.order,
        }
        for s in stones_reg.all()
    ]
    pebbles = []
    for p in pebble_reg.all():
        m = p.manifest
        pebbles.append(
            {
                "id": m.id,
                "type": m.type,
                "title": m.title,
                "stone": m.stone,
                "hazard": m.hazard,  # flood, heat, or any (runs in both briefings)
                "tier": m.tier,
                "maturity": m.maturity,
                # point pebbles run for address intents, polygon pebbles
                # for neighborhood / development intents.
                "scope": m.spatial.scope,
                "display": {
                    "order": m.display.order,
                    "kind": m.display.kind,
                    "variant": m.display.variant,
                    "map_layer": m.display.map_layer,
                    "icon": m.display.icon,
                },
                "narration": {
                    "short": m.narration.short,
                    "template": m.narration.template,
                },
                "provenance": {
                    "source_name": m.provenance.source_name,
                    "source_url": m.provenance.source_url,
                    "license": m.provenance.license,
                    "citation": m.provenance.citation,
                    "doc_id": m.provenance.doc_id,
                    **resolve(m.provenance, fetched=False),
                },
                "fallback": {
                    "on_offline": m.fallback.on_offline,
                    "message": m.fallback.message,
                },
            }
        )
    pebbles.sort(
        key=lambda x: (
            stones_reg.get(x["stone"]).order if x["stone"] in stones_reg else 99,
            x["display"]["order"] if x["display"]["order"] is not None else 999,
            x["id"],
        )
    )
    return {"stones": stones, "pebbles": pebbles}
