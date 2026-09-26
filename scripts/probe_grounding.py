"""Grounding probe: run briefings in LLM mode and record, per address,
the claims kept, the claims dropped and why, and the claims that failed
the first attempt and were retried.

Needs an OpenAI-compatible endpoint (RIPRAP_LLM_BASE_URL and
RIPRAP_LLM_MODEL). Runs in process; no server needed.

    RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 RIPRAP_LLM_MODEL=granite4:micro \\
        uv run python scripts/probe_grounding.py

Writes tests/probe_grounding_results.json, or the path given as the
first argument.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from riprap.core import llm
    from riprap.core.burr.app import run

    if llm.tier() != "llm":
        print("No LLM endpoint configured (RIPRAP_LLM_BASE_URL / RIPRAP_LLM_MODEL).")
        return 2
    addresses = json.loads((ROOT / "scripts" / "gallery_addresses.json").read_text())
    rows = []
    for a in addresses:
        t0 = time.time()
        out = run(a["address"])
        g = out.get("grounding") or {}
        row = {
            "address": a["address"],
            "tier": g.get("tier"),
            "model": g.get("model"),
            "attempts": g.get("attempts"),
            "kept": len(g.get("claims") or []),
            "dropped": [{"text": d["text"], "reason": d["reason"]} for d in g.get("dropped_claims") or []],
            "retried": [{"text": d["text"], "reason": d["reason"]} for d in g.get("retried_claims") or []],
            "fallback_reason": g.get("fallback_reason"),
            "elapsed_s": round(time.time() - t0, 1),
        }
        rows.append(row)
        print(f"{a['slug']:18s} kept={row['kept']:3d} dropped={len(row['dropped'])} "
              f"retried={len(row['retried'])} attempts={row['attempts']} {row['elapsed_s']}s", flush=True)

    def reason_kind(r: str) -> str:
        return r.split(":", 1)[0]

    summary = {
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "endpoints": llm.describe()["endpoints"],
        "n_addresses": len(rows),
        "claims_kept": sum(r["kept"] for r in rows),
        "claims_dropped": sum(len(r["dropped"]) for r in rows),
        "claims_retried": sum(len(r["retried"]) for r in rows),
        "addresses_needing_retry": sum(1 for r in rows if r["attempts"] == 2),
        "drop_reasons": Counter(reason_kind(d["reason"]) for r in rows for d in r["dropped"]),
        "retry_reasons": Counter(reason_kind(d["reason"]) for r in rows for d in r["retried"]),
    }
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests" / "probe_grounding_results.json"
    out_path.write_text(json.dumps({"summary": summary, "results": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
