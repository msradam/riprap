"""No-LLM place resolution accuracy on tests/place_resolution_cases.yaml.

    uv run python scripts/place_eval.py [label]

Runs each input through the no-LLM planner and the same resolve_area /
geocode_target actions the app uses, then checks the resolved place:
an address within 150 m of the expected address's geocode, a district
code, a neighbourhood name containing the expected words, or a refusal.
Writes tests/place_resolution_<label>.json (label defaults to "run").
Needs the network for geocoding (NYC Geosearch, Nominatim).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CASES = ROOT / "tests" / "place_resolution_cases.yaml"


def _metres(a, b) -> float:
    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def resolve(query: str) -> dict:
    """The place the no-LLM path resolves for a query."""
    from burr.core import State

    from riprap.core.burr.intake import geocode_target, heuristic_plan, resolve_area

    plan = heuristic_plan(query)
    intent = plan["intent"]
    if intent in ("out_of_scope", "not_implemented"):
        return {"kind": "refused", "intent": intent, "message": plan.get("rationale")}
    target = (plan.get("targets") or [{}])[0].get("text") or ""
    state = State({"query": query, "first_target": target, "trace": [], "plan": plan})
    if intent in ("neighborhood", "development_check"):
        out = resolve_area(state)
        nta = out.get("nta") or {}
        return {"kind": "area", "intent": intent, "target": target, "code": nta.get("nta_code"),
                "name": nta.get("nta_name"), "match": (out.get("geocode") or {}).get("match")}
    out = geocode_target(state)
    g = out.get("geocode") or {}
    return {"kind": "point", "intent": intent, "target": target, "address": g.get("address"),
            "lat": g.get("lat"), "lon": g.get("lon"), "match": g.get("match")}


def main() -> None:
    from app.geocode import geocode_one

    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    cases = yaml.safe_load(CASES.read_text())
    expected_pts: dict[str, tuple[float, float]] = {}
    rows, ok = [], 0
    for c in cases:
        got = resolve(c["input"])
        if "address" in c:
            if c["address"] not in expected_pts:
                h = geocode_one(c["address"])
                expected_pts[c["address"]] = (h.lat, h.lon)
            exp = expected_pts[c["address"]]
            d = _metres(exp, (got["lat"], got["lon"])) if got.get("lat") is not None else None
            passed = d is not None and d <= 150
            detail = f"{d:.0f} m" if d is not None else "no point"
        elif "district" in c:
            passed = got.get("code") == c["district"]
            detail = got.get("code")
        elif "neighborhood" in c:
            passed = c["neighborhood"].lower() in (got.get("name") or "").lower()
            detail = got.get("name")
        else:
            passed = got["kind"] == "refused" and c["refuse"].split()[0].lower() in (got.get("message") or "").lower()
            detail = got.get("message")
        ok += passed
        rows.append({**c, "got": got, "passed": passed, "detail": detail})
        print(("PASS" if passed else "FAIL"), "|", c["input"][:70], "|", detail, flush=True)
    out = {"label": label, "n": len(cases), "passed": ok, "accuracy": round(ok / len(cases), 3), "rows": rows}
    (ROOT / "tests" / f"place_resolution_{label}.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"{label}: {ok}/{len(cases)} = {out['accuracy']}")


if __name__ == "__main__":
    main()
