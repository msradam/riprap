"""Evidence: pebble values rendered through their manifests.

One path turns state into citable evidence for every consumer:

  * the no-LLM briefing (`templated_reconciler`) prints the sentences;
  * the LLM briefing passes the same sentences as documents, so the model
    can only restate what the no-LLM briefing already shows;
  * citations come from each manifest's provenance (`vintage.citation`).

A sentence is the pebble's `narration.template` filled from its value.
If the template names a field the value lacks, the pebble says nothing
(silence over a hollow sentence). Pebbles without a template fall back
to `narration.short`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from riprap.core.compliance.predicates import _CITATION_RE, _NUM_TOKEN_RE, _sentences
from riprap.core.pebbles import load_registry
from riprap.core.pebbles.registry import Registry
from riprap.core.pebbles.vintage import citation
from riprap.core.stones import StoneRegistry, load_stones

_REPO = Path(__file__).resolve().parent.parent.parent.parent


@dataclass
class Evidence:
    doc_id: str
    pebble_id: str
    stone_id: str
    text: str  # plain sentence(s), no citation markers
    maturity: str
    manifest: Any


def deployment_root(deployment: str | None) -> Path:
    """Root of the routed deployment. Out-of-coverage (`__none__`) falls
    back to the federal deployment so NWS/FEMA pebbles still narrate."""
    import os

    from riprap.core.pebbles.deployments import deployment_by_name

    name = "federal" if deployment == "__none__" else deployment
    if name:
        dep = deployment_by_name(name)
        if dep is not None:
            return dep.root
    p = Path(os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc"))
    return p if p.is_absolute() else _REPO / p


def load(deployment: str | None) -> tuple[StoneRegistry, Registry]:
    root = deployment_root(deployment)
    return load_stones(root), load_registry(root)


class _MissingField(KeyError):
    pass


def _format(template: str, value: dict[str, Any]) -> str:
    """Strict {field} substitution: a missing or None field raises instead
    of printing 'None' into the briefing."""

    class _Strict(dict):
        def __missing__(self, key):
            raise _MissingField(key)

        def __getitem__(self, key):
            v = super().__getitem__(key)
            if v is None:
                raise _MissingField(key)
            return v

    return template.format_map(_Strict(value))


def sentence_for(value: Any, manifest) -> str | None:
    """Plain evidence text for one pebble value, or None."""
    if value is None:
        return None
    template, short = manifest.narration.template, manifest.narration.short
    if template:
        if not isinstance(value, dict):
            return None
        v = dict(value)
        # A capped query reports "200+" rather than a count that is
        # really the LIMIT.
        if v.get("n_truncated") is True and isinstance(v.get("n_records"), int):
            v["n_records"] = f"{v['n_records']}+"
        try:
            body = _format(template, v).strip()
        except (_MissingField, IndexError, ValueError):
            return None
    else:
        body = (short or "").strip()
    if not body:
        return None
    if manifest.maturity == "experimental" and not body.lower().startswith("experimental"):
        body = f"Experimental: {body}"
    return body if body[-1] in ".!?" else body + "."


def cite(text: str, doc_id: str) -> str:
    """Append [doc_id] to every sentence that states a number (the
    per-sentence rule `every_numeric_claim_cited` audits), and to the
    last sentence in any case."""
    marker = f"[{doc_id}]"
    out = []
    for s in _sentences(text):
        if _NUM_TOKEN_RE.search(s) and not _CITATION_RE.search(s):
            s = f"{s[:-1].rstrip()} {marker}{s[-1]}" if s[-1] in ".!?" else f"{s} {marker}"
        out.append(s)
    body = " ".join(out)
    if marker not in body:
        body = f"{body[:-1].rstrip()} {marker}{body[-1]}" if body[-1] in ".!?" else f"{body} {marker}"
    return body


def collect(state, stones: StoneRegistry, registry: Registry) -> list[Evidence]:
    """Evidence for every pebble with a value, in Stone order, then by
    each manifest's display.order."""
    stone_order = {s.id: i for i, s in enumerate(stones.all())}
    pebbles = sorted(
        registry.all(),
        key=lambda p: (stone_order.get(p.stone, 99),
                       p.manifest.display.order if p.manifest.display.order is not None else 999,
                       p.id),
    )
    out: list[Evidence] = []
    for p in pebbles:
        text = sentence_for(state.get(p.id), p.manifest)
        if text:
            out.append(Evidence(
                doc_id=p.manifest.provenance.doc_id or p.id, pebble_id=p.id,
                stone_id=p.stone, text=text, maturity=p.manifest.maturity,
                manifest=p.manifest,
            ))
    return out


def policy_passages(state, registry: Registry, limit: int = 3) -> list[Evidence]:
    """Retrieved policy-corpus passages as their own documents (rag_*),
    for the LLM path. Citations resolve to the policy_corpus manifest."""
    value = state.get("policy_corpus") or {}
    if "policy_corpus" not in registry.ids():
        return []
    manifest = registry.get("policy_corpus").manifest
    out = []
    for hit in (value.get("rag_hits") or [])[:limit]:
        text = " ".join((hit.get("text") or "").split())[:400]
        if text:
            out.append(Evidence(
                doc_id=hit["doc_id"], pebble_id="policy_corpus", stone_id=manifest.stone,
                text=f"{hit.get('title', '')}, page {hit.get('page', '?')}: {text}",
                maturity=manifest.maturity, manifest=manifest,
            ))
    return out


def citations(items: list[Evidence]) -> dict[str, dict]:
    """doc_id -> citation record, from manifest provenance only."""
    out: dict[str, dict] = {}
    for e in items:
        if e.doc_id in out:
            continue
        title = e.text.split(":", 1)[0] if e.doc_id.startswith("rag_") else None
        out[e.doc_id] = citation(e.manifest, doc_id=e.doc_id, title=title)
    return out


def stone_heading(stone) -> str:
    """'the hazard reader' -> 'Hazard reader.'"""
    tag = (stone.tagline or stone.name).strip()
    if tag.lower().startswith("the "):
        tag = tag[4:]
    return f"{tag[0].upper()}{tag[1:]}."


def all_pebble_ids() -> list[str]:
    """Every pebble id across the shipped deployments. Burr actions that
    read pebble values declare these as reads, since which pebbles hold
    values depends on where the query routed."""
    from riprap.core.pebbles.deployments import discover_deployments

    ids: set[str] = set()
    for dep in discover_deployments():
        try:
            ids.update(load_registry(dep.root).ids())
        except Exception:  # noqa: BLE001 - one malformed deployment must not break the rest
            continue
    return sorted(ids)
