"""Check every source link in the deployment manifests with a real request.

    uv run python scripts/check_links.py [deployment ...] [--json out.json]

Collects each manifest's provenance.source_url and any URL in its
provenance.citation, requests each once (GET, redirects followed, no
cache) and prints one line per link: status, deployment, manifest, URL.
With no deployment names it checks all of them. Exits 1 when any link
answers 4xx or 5xx or cannot be reached.

Needs the network, so it is not part of the pytest suite; run it before a
release or after editing a manifest. Some portals answer 403 to scripted
requests while serving browsers; the script reports what it got and says
nothing about why.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
_URL = re.compile(r"https?://[^\s\"'<>)]+")
UA = "Riprap link check (+https://github.com/msradam/riprap)"


def links(deployments: list[str]) -> list[tuple[str, str, str]]:
    """(deployment, manifest, url) for every provenance link."""
    out = []
    for path in sorted(ROOT.glob("deployments/*/manifests/*.yaml")):
        dep = path.parent.parent.name
        if deployments and dep not in deployments:
            continue
        prov = (yaml.safe_load(path.read_text()) or {}).get("provenance") or {}
        urls = [prov.get("source_url") or ""] + _URL.findall(str(prov.get("citation") or ""))
        for u in dict.fromkeys(u.rstrip(".,") for u in urls if u):
            out.append((dep, path.stem, u))
    return out


def status(client: httpx.Client, url: str) -> str:
    try:
        with client.stream("GET", url) as r:
            return str(r.status_code)
    except httpx.HTTPError as e:
        return type(e).__name__


def main() -> int:
    args = sys.argv[1:]
    out_json = args[args.index("--json") + 1] if "--json" in args else None
    deps = [a for a in args if not a.startswith("--") and a != out_json]
    rows, bad = [], 0
    with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": UA}) as client:
        for dep, manifest, url in links(deps):
            s = status(client, url)
            bad += not s.startswith(("2", "3"))
            rows.append({"deployment": dep, "manifest": manifest, "url": url, "status": s})
            print(f"{s:>6}  {dep:<8} {manifest:<32} {url}", flush=True)
    print(f"{len(rows)} links, {bad} not OK")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
