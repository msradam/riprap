"""Build the static gallery: one briefing JSON per address in
scripts/gallery_addresses.json, written to web/sveltekit/src/lib/gallery/.
The SvelteKit app prerenders /gallery and /gallery/<slug> from these
files, so the gallery needs no backend (GitHub Pages).

    uv run python scripts/build_gallery.py          # no-LLM briefings
    RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 RIPRAP_LLM_MODEL=granite4:micro \\
        uv run python scripts/build_gallery.py      # LLM claims, verified

Each file carries the full result (the same shape as the SSE `final`
event, trace included), the deployment's stones and pebbles as
/api/pebbles serves them, and how and when it was generated.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "web" / "sveltekit" / "src" / "lib" / "gallery"


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
    index = []
    for a in addresses:
        t0 = time.time()
        final = run(a["address"])
        dep = deployment_by_name(final.get("deployment") or "nyc")
        stones = load_stones(dep.root)
        entry = {
            "slug": a["slug"],
            "neighborhood": a["neighborhood"],
            "address": a["address"],
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
            "riprap_commit": commit,
            "mode": (final.get("grounding") or {}).get("tier") or llm.tier(),
            "model": (final.get("grounding") or {}).get("model"),
            "deployment": {"name": dep.name, "city": stones.city, "hazard": stones.hazard},
            "pebbles": describe_deployment(stones, load_registry(dep.root)),
            "final": to_json_safe(final),
        }
        (OUT / f"{a['slug']}.json").write_text(json.dumps(entry, indent=1) + "\n")
        g = final.get("grounding") or {}
        index.append({k: entry[k] for k in ("slug", "neighborhood", "address", "generated_at", "mode")})
        print(f"{a['slug']:18s} {entry['mode']:7s} kept={len(g.get('claims') or [])} "
              f"dropped={len(g.get('dropped_claims') or [])} {time.time() - t0:.1f}s", flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
