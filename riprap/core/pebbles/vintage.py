"""Resolve a manifest's provenance vintage and build its citation.

Manifests carry `date_modified` (the source's own vintage) and
`retrieved_at` (when our copy was made). Baked sources set both to fixed
dates. Live sources set `at_fetch`: `retrieved_at` becomes the read time,
and `date_modified` comes from Socrata's metadata API (`dataUpdatedAt`)
when the source is a Socrata dataset, or equals the read time otherwise.

Every citation Riprap emits (briefing, /api/pebbles, MCP get_citation) is
built here, so there is one source of provenance: the manifests.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from riprap.core import http
from riprap.core.pebbles.schema import Provenance

log = logging.getLogger("riprap.vintage")

AT_FETCH = "at_fetch"
_SOCRATA_ID_RE = re.compile(r"([a-z0-9]{4}-[a-z0-9]{4})(\.\w+)?")


def socrata_dataset(url: str | None) -> tuple[str, str] | None:
    """(domain, dataset_id) when `url` names a Socrata dataset: a path
    segment that is a 4x4 id such as erm2-nwe9 or 4mhf-duep.geojson."""
    if not url:
        return None
    parsed = urlparse(url)
    for segment in reversed(parsed.path.split("/")):
        m = _SOCRATA_ID_RE.fullmatch(segment)
        if m:
            return parsed.netloc, m.group(1)
    return None


def socrata_updated_at(domain: str, dataset_id: str) -> str | None:
    """The dataset's `dataUpdatedAt`, cached for an hour by the shared client."""
    try:
        r = http.get(f"https://{domain}/api/views/metadata/v1/{dataset_id}", timeout=10, ttl_s=3600)
        r.raise_for_status()
        return r.json().get("dataUpdatedAt")
    except Exception as e:  # noqa: BLE001 - vintage is best-effort metadata
        log.warning("Socrata metadata for %s/%s failed: %r", domain, dataset_id, e)
        return None


def resolve(prov: Provenance, *, fetched: bool = True) -> dict[str, str | None]:
    """Concrete `date_modified` / `retrieved_at` for one source.

    `fetched=False` is for callers outside a briefing (MCP get_citation,
    /api/pebbles): a live source then reports its Socrata vintage if it
    has one, and "live" otherwise, instead of pretending a read happened.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
    retrieved = prov.retrieved_at
    if retrieved == AT_FETCH:
        retrieved = now if fetched else "live"
    modified = prov.date_modified
    if modified == AT_FETCH:
        ds = socrata_dataset(prov.source_url)
        modified = socrata_updated_at(*ds) if ds else None
        if modified is None:
            modified = now if fetched else "live"
    return {"date_modified": modified, "retrieved_at": retrieved}


def citation(manifest, *, fetched: bool = True, doc_id: str | None = None,
             title: str | None = None) -> dict:
    """The citation record for one pebble, in the shape the frontend
    `Citation` type and MCP clients read. `vintage` is the display string:
    the source's date_modified, else when our copy was retrieved."""
    prov = manifest.provenance
    v = resolve(prov, fetched=fetched)
    vintage = v["date_modified"] or (f"retrieved {v['retrieved_at']}" if v["retrieved_at"] else None)
    return {
        "doc_id": doc_id or prov.doc_id or manifest.id,
        "source": prov.source_name,
        "title": title or prov.citation or manifest.title,
        "url": prov.source_url,
        "license": prov.license,
        "date_modified": v["date_modified"],
        "retrieved_at": v["retrieved_at"],
        "vintage": vintage,
        "maturity": manifest.maturity,
    }
