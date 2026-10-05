"""Build the static gallery: one briefing JSON per address in
scripts/gallery_addresses.json, written to web/sveltekit/src/lib/gallery/.
The SvelteKit app prerenders /gallery and /gallery/<slug> from these
files, so the gallery needs no backend (GitHub Pages).

    uv run python scripts/build_gallery.py          # no model: rule answers
    GALLERY_ONLY=hollis-since-ida,homecrest-311 \\
    RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 \\
    RIPRAP_LLM_MODEL=hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M \\
        uv run python scripts/build_gallery.py      # those entries with a model configured

Entries with a `question` run the question; the rest run the bare place
(an address or a community district), as its flood briefing or, with
`"hazard": "heat"`, its heat briefing. Without a model a question is
answered by the rules. GALLERY_ONLY rebuilds just those slugs and keeps
every other file and index entry as it is.

Each file carries the full result (the same shape as the SSE `final`
event, trace included), the deployment's stones and pebbles as
/api/pebbles serves them, and how and when it was generated. FloodNet's
per-sensor and per-event records are taken out before a file is written
(`strip_floodnet`): its licence forbids reposting the data in part.

The landing's briefing preview is a screenshot of hollis-since-ida. After
rebuilding that entry, rebuild the frontend, serve it, and retake it:

    cd web/sveltekit && node scripts/capture-hero-preview.mjs http://127.0.0.1:7860
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "web" / "sveltekit" / "src" / "lib" / "gallery"


def _quant(model: str | None) -> str | None:
    """'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M' -> 'Q4_K_M'."""
    return model.rsplit(":", 1)[1] if model and ":" in model else None


FLOODNET_STRIPPED = "floodnet_records_stripped"  # set on every file baked since the strip step exists
_EVENTS = ("highest_event", "peak_event", "flagged_peak_event")


def strip_floodnet(node):
    """A result with FloodNet's records taken out, in place and at any depth
    (a comparison nests each place's result). FloodNet's Data Access
    License Agreement forbids reposting its data in part, and a baked
    snapshot is a repost. What stays: the sentences, the counts, each
    highest depth with its date, the licence fields and the citation. What
    goes: the list of sensors (deployment id, name, street, status, install
    date, coordinates, event count) and every field of an event row but its
    depth and date. The page then draws no sensor points and points to
    FloodNet's own dashboard (MapFigure.svelte)."""
    if isinstance(node, list):
        for x in node:
            strip_floodnet(x)
    elif isinstance(node, dict):
        for key, v in node.items():
            if key in ("floodnet", "floodnet_nta") and isinstance(v, dict) and "n_sensors" in v:
                v.pop("sensors", None)
                for k in _EVENTS:
                    if isinstance(v.get(k), dict):
                        v[k] = {"max_depth_mm": v[k].get("max_depth_mm"), "date": (v[k].get("start_time") or "")[:10] or None}
            else:
                strip_floodnet(v)
    return node


def main() -> int:
    from riprap.core import llm
    from riprap.core.burr.app import run
    from riprap.core.json_safe import to_json_safe
    from riprap.core.pebbles import load_registry
    from riprap.core.pebbles.deployments import deployment_by_name
    from riprap.core.pebbles.describe import describe_deployment
    from riprap.core.stones import load_stones

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or None
    OUT.mkdir(parents=True, exist_ok=True)
    addresses = json.loads((ROOT / "scripts" / "gallery_addresses.json").read_text())
    only = set(filter(None, os.environ.get("GALLERY_ONLY", "").split(",")))
    old_index = {e["slug"]: e for e in json.loads((OUT / "index.json").read_text())} \
        if (OUT / "index.json").exists() else {}
    index = []
    for a in addresses:
        if only and a["slug"] not in only:
            if a["slug"] in old_index:
                index.append(old_index[a["slug"]])
            continue
        t0 = time.time()
        # A heat entry with no question is the heat briefing for the place.
        final = run(a.get("question") or (f"heat {a['address']}" if a.get("hazard") == "heat" else a["address"]))
        dep = deployment_by_name(final.get("deployment") or "nyc")
        stones = load_stones(dep.root)
        entry = {
            "slug": a["slug"],
            "neighborhood": a["neighborhood"],
            "address": a["address"],
            "question": a.get("question"),
            "hazard": a.get("hazard", "flood"),
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
            "riprap_commit": commit,
            "mode": (final.get("grounding") or {}).get("tier") or llm.tier(),
            "model": (final.get("grounding") or {}).get("model"),
            "quantization": _quant((final.get("grounding") or {}).get("model")),
            "deployment": {"name": dep.name, "city": stones.city, "hazard": stones.hazard},
            "pebbles": describe_deployment(stones, load_registry(dep.root)),
            "final": strip_floodnet(to_json_safe(final)),
            FLOODNET_STRIPPED: True,
        }
        (OUT / f"{a['slug']}.json").write_text(json.dumps(entry, indent=1) + "\n")
        g = final.get("grounding") or {}
        index.append({k: entry[k] for k in ("slug", "neighborhood", "address", "question", "hazard",
                                            "generated_at", "mode", "model", "quantization")})
        print(f"{a['slug']:18s} {entry['mode']:7s} kept={len(g.get('claims') or [])} "
              f"dropped={len(g.get('dropped_claims') or [])} {time.time() - t0:.1f}s", flush=True)
        time.sleep(float(os.environ.get("GALLERY_PAUSE_S", "3")))  # the public APIs have quotas
    # Editorial fields come from the address list every run, so a kept entry
    # picks up a new reason or featured source without being regenerated.
    by_slug = {a["slug"]: a for a in addresses}
    for e in index:
        e["hazard"] = by_slug.get(e["slug"], {}).get("hazard", "flood")
        for k in ("reason", "feature_doc"):
            if by_slug.get(e["slug"], {}).get(k):
                e[k] = by_slug[e["slug"]][k]
            else:
                e.pop(k, None)
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
