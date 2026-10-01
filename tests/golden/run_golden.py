"""Score a running Riprap against the independent keys.

    uv run python tests/golden/run_golden.py tests/golden/seen.json
    uv run python tests/golden/run_golden.py tests/golden/unseen.json --kinds question

Reads each entry, asks the app at --base for its briefing, computes the
keys at the point the app resolved, and writes one JSON result per entry
plus a summary table to stdout. Every fact is exact: a count is right or
wrong. The geocode distance between the city's geocoder and the app's is
reported separately so a different point is not scored as a wrong fact.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import keys  # noqa: E402

BOROUGH = {"MN": "MANHATTAN", "BX": "BRONX", "BK": "BROOKLYN", "QN": "QUEENS", "SI": "STATEN ISLAND"}


def app_json(base: str, path: str, q: str | None = None) -> dict:
    url = base + path + ("?" + urllib.parse.urlencode({"q": q}) if q else "")
    with urllib.request.urlopen(url, timeout=600) as r:
        return json.load(r)


def answer_text(out: dict) -> str:
    """The answer paragraph: the text under the first bold heading."""
    p = out.get("paragraph") or ""
    m = re.search(r"\*\*(?:Answer|In brief)\.\*\*\s*(.*?)(?:\n\n|\Z)", p, re.S)
    return (m.group(1) if m else p).strip()


def check(facts: list, name: str, got, want, ok=None) -> None:
    facts.append({"fact": name, "riprap": got, "key": want,
                  "ok": (got == want) if ok is None else ok})


def score_address(base: str, query: str) -> dict:
    out = app_json(base, "/api/agent", query)
    lat, lon = out.get("lat"), out.get("lon")
    res: dict = {"query": query, "intent": out.get("intent"),
                 "resolved": (out.get("geocode") or {}).get("address"),
                 "lat": lat, "lon": lon, "facts": []}
    if lat is None:
        res["error"] = "the app resolved no point"
        return res
    g = keys.geocode(query)
    res["geosearch"] = g
    res["geocode_distance_m"] = round(keys.haversine_m(lat, lon, g["lat"], g["lon"])) if g else None
    k = keys.all_keys(lat, lon)
    res["keys"] = k
    f = res["facts"]
    text = out.get("paragraph") or ""

    v = out.get("nyc311") or {}
    check(f, "311 count (200 m, 5 y)", v.get("n"), k["nyc311"]["n"])
    check(f, "311 by descriptor", v.get("by_descriptor"), k["nyc311"]["by_descriptor"])
    check(f, "311 count in text", None, k["nyc311"]["n"],
          ok=bool(re.search(rf"\b{k['nyc311']['n']} NYC 311", text)))

    v = out.get("floodnet") or {}
    check(f, "FloodNet sensors (600 m)", v.get("n_sensors"), k["floodnet"]["n_sensors"])
    check(f, "FloodNet events (3 y)", v.get("n_flood_events_3y"), k["floodnet"]["n_events"])
    peak = (v.get("peak_event") or {}).get("max_depth_mm")
    check(f, "FloodNet peak mm (good sensors)", peak, k["floodnet"]["peak_mm_good"])

    v = out.get("ida_hwm") or {}
    check(f, "Ida marks (800 m)", v.get("n_within_radius"), k["ida_hwm"]["n"])
    check(f, "Ida max height above ground ft", v.get("max_height_above_gnd_ft"),
          k["ida_hwm"]["max_height_above_gnd_ft"])
    check(f, "Ida max elevation ft", v.get("max_elev_ft"), k["ida_hwm"]["max_elev_ft"])
    near = v.get("nearest_dist_m")
    check(f, "Ida nearest mark m (within 5)", near, k["ida_hwm"]["nearest_m"],
          ok=near is not None and k["ida_hwm"]["nearest_m"] is not None
          and abs(near - k["ida_hwm"]["nearest_m"]) <= 5)

    v = out.get("fema_nfhl") or {}
    kf = k["fema_nfhl"] or {}
    check(f, "FEMA zone", v.get("fld_zone"), kf.get("zone"))
    check(f, "FEMA FIRM panel", v.get("firm_panel"), kf.get("panel"))
    check(f, "FEMA panel effective year", v.get("effective_year"), kf.get("effective_year"))

    v = out.get("fema_pfirm") or {}
    kp = k["fema_pfirm"] or {}
    check(f, "PFIRM zone", v.get("fld_zone"), kp.get("zone"))
    check(f, "PFIRM base flood elevation ft", v.get("static_bfe_ft"), kp.get("bfe_ft"))
    check(f, "PFIRM issue date", v.get("issue_date"), kp.get("issue_date"))

    check(f, "inside Sandy 2012 extent", (out.get("sandy") or {}).get("inside"), k["sandy_inside"])
    for s, cls in k["dep"].items():
        check(f, f"DEP class {s}", (out.get(s) or {}).get("depth_class"), cls)

    v = out.get("mta_entrances") or {}
    check(f, "MTA entrances (800 m)", v.get("n_entrances"), k["mta_entrances_800m"])
    return res


def score_district(base: str, code: str) -> dict:
    out = app_json(base, f"/api/district/{code}?no_llm=true")
    m = re.fullmatch(r"(MN|BX|BK|QN|SI)(\d\d)", code.upper())
    if not m:
        return {"query": code, "error": "not a district code", "facts": []}
    board = f"{m.group(2)} {BOROUGH[m.group(1)]}"
    v = out.get("nyc311_nta") or {}
    want = keys.nyc311_district(board, years=int(v.get("years") or 3))
    res = {"query": code, "intent": out.get("intent"), "facts": []}
    # Both count by the record's own community_board field, each with its own
    # definition of a flood descriptor and its own one-row-per-incident rule.
    got = v.get("n")
    check(res["facts"], f"311 count in {board} ({v.get('years')} y)", got, want)
    check(res["facts"], "311 sentence names the community board field", None, None,
          ok="community board field" in (out.get("paragraph") or ""))
    check(res["facts"], "311 count in text", got, want,
          ok=bool(re.search(rf"\b{got} NYC 311", out.get("paragraph") or "")))
    return res


_TWO_PARTS_RE = re.compile(r"(,|\band\b|\?)\s*(and\s+)?(did|was|were|has|have|had|is|are|how|which|what)\b", re.I)
_DISTRICT_RE = re.compile(r"\b(MN|BX|BK|QN|SI)\s?(\d\d)\b", re.I)


def expected_lead(question: str, k: dict) -> str:
    """The lead a past-event question should get from the keys: yes, no,
    other (the sources cannot settle it, so any yes or no is wrong), or
    unscored (a kind of question this runner has no independent rule for).
    Count questions return the count."""
    q = question.lower()
    fn, c = k["floodnet"], k["nyc311"]
    if _TWO_PARTS_RE.search(q.split(" ", 1)[-1]):
        return "unscored"  # two questions in one: the app answers part by part
    if "how many" in q:
        return str(c["n"])
    if not re.match(r"\W*(is|are|was|were|has|have|had|do|does|did)\b", q):
        return "unscored"  # "which schools ...", "what does the map show": no yes or no to check
    if "sandy" in q:
        # The mapped outline is not exact to a building: within 50 m of it,
        # on either side, the app states the distance and gives no flat yes or no.
        if k.get("sandy_edge_m") is not None and k["sandy_edge_m"] <= 50:
            return "other"
        return "yes" if k["sandy_inside"] else "no"
    # A yes rests on a sensor in good working order: events only at sensors
    # FloodNet flags for maintenance are quoted with the flag and no yes.
    if "sensor" in q:
        if fn["n_sensors"] == 0 or (fn["n_events"] and not fn["n_events_good"]):
            return "other"
        return "yes" if fn["n_events_good"] else "no"
    if "since" in q and "ida" in q:
        after = sum(n for y, n in c["by_year"].items() if int(y) > 2021)
        if fn["n_sensors"] and fn["n_events_good"]:
            return "yes"
        if after or fn["n_events"]:
            return "other"  # 311 requests alone are reports of trouble: they are quoted, with no flat yes
        if fn["n_sensors"]:
            return "no"
        return "other"
    return "unscored"


def score_question(base: str, question: str) -> dict:
    out = app_json(base, "/api/agent", question)
    lat, lon = out.get("lat"), out.get("lon")
    res: dict = {"query": question, "intent": out.get("intent"), "lat": lat, "lon": lon,
                 "answer": answer_text(out), "facts": []}
    if lat is None:
        res["error"] = "the app resolved no point"
        return res
    ans = res["answer"]
    d = _DISTRICT_RE.search(question)
    if d and out.get("intent") in ("neighborhood", "development_check"):
        # A question about a district: the one independent key is its 311 count.
        board = f"{d.group(2)} {BOROUGH[d.group(1).upper()]}"
        v = out.get("nyc311_nta") or {}
        if "how many" in question.lower() and "311" in question:
            want = keys.nyc311_district(board, years=int(v.get("years") or 3))
            got = re.search(r"\b(\d+) NYC 311", ans)
            check(res["facts"], f"311 count in {board} answered", int(got.group(1)) if got else None, want)
        return res
    k = keys.all_keys(lat, lon)
    res["keys"] = k
    want = expected_lead(question, k)
    lead = ans.split(".")[0].strip().lower() if ans else ""
    if want.isdigit():
        got = re.search(r"\b(\d+) NYC 311", ans)
        check(res["facts"], "count answered", got.group(1) if got else None, want)
    elif want != "unscored":
        got = "yes" if lead == "yes" else "no" if lead == "no" else "other"
        check(res["facts"], "answer lead", got, want)
    # Every number the answer quotes must be a key number for this point.
    quoted = {int(n) for n in re.findall(r"\b(\d+) (?:NYC 311|FloodNet|above-curb|Hurricane Ida high)", ans)}
    known = {k["nyc311"]["n"], k["floodnet"]["n_sensors"], k["floodnet"]["n_events"], k["ida_hwm"]["n"]}
    check(res["facts"], "numbers quoted are key numbers", sorted(quoted), sorted(known & quoted),
          ok=quoted <= known)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("set_file")
    ap.add_argument("--base", default="http://127.0.0.1:7860")
    ap.add_argument("--kinds", default="address,district,question")
    ap.add_argument("--ids", default=None, help="comma-separated entry ids to run")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pause", type=float, default=0, help="seconds between entries (the public APIs have quotas)")
    a = ap.parse_args()
    entries = json.load(open(a.set_file))
    kinds = set(a.kinds.split(","))
    results = []
    for e in entries:
        if e["kind"] not in kinds or (a.ids and e["id"] not in a.ids.split(",")):
            continue
        try:
            fn = {"address": score_address, "district": score_district, "question": score_question}[e["kind"]]
            r = fn(a.base, e["query"])
        except Exception as ex:  # noqa: BLE001
            r = {"query": e["query"], "error": repr(ex), "facts": []}
        r["id"], r["kind"] = e["id"], e["kind"]
        results.append(r)
        bad = [f for f in r["facts"] if not f["ok"]]
        print(f"{e['id']} {e['kind']:8} {len(r['facts']) - len(bad)}/{len(r['facts'])} ok"
              + (f"  geocode {r.get('geocode_distance_m')} m" if r.get("geocode_distance_m") is not None else "")
              + (f"  ERROR {r['error']}" if r.get("error") else ""))
        for f in bad:
            print(f"    MISS {f['fact']}: riprap={f['riprap']!r} key={f['key']!r}")
        time.sleep(a.pause)
    n_facts = sum(len(r["facts"]) for r in results)
    n_ok = sum(1 for r in results for f in r["facts"] if f["ok"])
    print(f"\n{n_ok}/{n_facts} facts agree, {len(results)} entries, {date.today()}")
    out = a.out or str(Path(a.set_file).with_suffix("")) + f"_results_{date.today()}.json"
    json.dump({"date": str(date.today()), "n_ok": n_ok, "n_facts": n_facts, "results": results},
              open(out, "w"), indent=1, default=str)
    print("wrote", out)
    return 0 if n_ok == n_facts else 1


if __name__ == "__main__":
    sys.exit(main())
