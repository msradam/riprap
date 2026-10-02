"""Score a running Riprap heat briefing against the independent heat keys.

    uv run python tests/golden/run_golden_heat.py
    uv run python tests/golden/run_golden_heat.py --ids h01,d01 --base http://127.0.0.1:7861

Reads tests/golden/heat_seen.json, asks the app for each entry's heat
briefing, computes the keys at the point the app resolved (or over the
district outline), and writes tests/golden/results/heat_seen_<date>.json
with every fact as {fact, riprap, key, ok, note}, plus a table to stdout.
A fact with ok null was not scored (a forecast reissued between the two
fetches). Tolerances are stated in keys_heat.py and repeated in each note.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import keys_heat as kh  # noqa: E402
from run_golden import app_json, check  # noqa: E402

RECORD = True  # score the station's all-time record: needs NCEI's whole record, tens of minutes the first time
LANDCOVER = ("built_pct", "green_pct", "tree_canopy_pct", "water_pct", "bare_pct")
UNSCORED = "unscored"


def fact(facts: list, name: str, got, want, ok=None, note: str = "") -> None:
    check(facts, name, got, want, ok)
    if facts[-1]["ok"] == UNSCORED:
        facts[-1]["ok"] = None
    facts[-1]["note"] = note


def near(facts: list, name: str, got, want, tol: float, why: str) -> None:
    ok = got is not None and want is not None and abs(got - want) <= tol + 1e-9
    diff = f"{got - want:+.2f}" if got is not None and want is not None else "n/a"
    fact(facts, name, got, want, ok, f"difference {diff}, tolerance {tol:.2f} ({why})")


def score_surface(f: list, v: dict, k: dict, pre: str) -> None:
    counts = (f"images with at least half the place clear {k.get('n_images')}, with all of it clear "
              f"{k.get('n_images_all_clear')}, with any of it clear {k.get('n_images_any_clear')}")
    # The brief sets no rule for a place that is partly clear, so the count is right anywhere between the two extremes.
    n = v.get("n_images")
    fact(f, f"{pre}.n_images", n, k.get("n_images"), note=counts,
         ok=n is not None and k.get("n_images_all_clear", 0) <= n <= k.get("n_images_any_clear", -1))
    for name in ("first", "last"):
        fact(f, f"{pre}.{name}", v.get(name), k.get(name))
    geo = k.get("geometry_f", {})

    def wide(name: str) -> str:
        moved = (k.get("half_pixel_south_east_f") or {}).get(name)
        return f"; the same circle 15 m east and 15 m south gives {moved}" if moved is not None else ""

    for name in ("mean_diff_f", "min_diff_f", "max_diff_f"):
        near(f, f"{pre}.{name}", v.get(name), k.get(name), geo.get(name, 0) + kh.CITY_TOL_F + 0.1,
             f"90 m cell alignment {geo.get(name, 0):.2f}, city mean {kh.CITY_TOL_F}, rounding 0.1" + wide(name))
    near(f, f"{pre}.latest_surface_f", v.get("latest_surface_f"), k.get("latest_surface_f"),
         geo.get("latest_surface_f", 0) + 0.1,
         f"90 m cell alignment {geo.get('latest_surface_f', 0):.2f}, rounding 0.1" + wide("latest_surface_f"))
    near(f, f"{pre}.latest_city_mean_f", v.get("latest_city_mean_f"), k.get("latest_city_mean_f"), kh.CITY_TOL_F,
         "land mask definition")
    # "In every image" turns on the sign of the closest image: agree, or the key's closest image is within tolerance of zero.
    for name, edge in (("warmer_in_every_image", "min_diff_f"), ("cooler_in_every_image", "max_diff_f")):
        tol = geo.get(edge, 0) + kh.CITY_TOL_F + 0.1
        same = v.get(name) == k.get(name)
        fact(f, f"{pre}.{name}", v.get(name), k.get(name), ok=same or abs(k.get(edge, 99)) <= tol,
             note="" if same else f"the key's {edge} is {k.get(edge)}, within {tol:.2f} of zero")


def score_visits(f: list, v: dict | None, k: dict | None, pre: str) -> None:
    if k is None:
        fact(f, f"{pre}.no community district here", v, None, ok=not v or not v.get("available", True),
             note="the point's tabulation area belongs to no community district (a park, airport or island)")
        return
    v = v or {}
    for name in ("district", "n", "suppressed", "age_adjusted_rate", "citywide_age_adjusted_rate"):
        got = v.get(name)
        if name == "citywide_age_adjusted_rate" and k["suppressed"] and got is None:
            continue  # the app quotes the city rate only beside a district rate
        fact(f, f"{pre}.{name}", got, k[name])
    if k["suppressed"]:
        why = (k["note"] or "").lstrip("* ")
        fact(f, f"{pre}.suppression reason as the portal words it", None, why, ok=why in (v.get("narrative") or ""))


def score_station(f: list, v: dict, k: dict, pre: str) -> None:
    fact(f, f"{pre}.station", v.get("station"), k["station"], ok=k["station"] in (v.get("station") or ""),
         note=f"nearest by haversine to NCEI's coordinates: {k['station']} {k['distance_km']} km, "
         f"then {k['runner_up']} {k['runner_up_km']} km")
    near(f, f"{pre}.distance_km", v.get("distance_km"), k["distance_km"], 0.2, "two roundings to 0.1 km, and sources give station coordinates to different precision")
    note = f"NCEI holds days through {k['through']}; the app says through {v.get('through')}"
    for name in ("days_ge_90", "days_ge_90_last_year", "max_f"):
        fact(f, f"{pre}.{name}", v.get(name), k[name], note=note)
    fact(f, f"{pre}.normal_days_ge_90", v.get("normal_days_ge_90"), k["normal_days_ge_90"],
         note=f"1991 to 2020 mean is {k['normal_exact']}")
    fact(f, f"{pre}.max_date", v.get("max_date"), k["max_dates"], ok=v.get("max_date") in k["max_dates"])
    tops = v.get("max_by_year") or {}
    wrong = {y: (tops.get(y), want) for y, want in k["max_by_year"].items()
             if not tops.get(y) or tops[y][0] != want[0] or tops[y][1] not in want[1]}
    fact(f, f"{pre}.max_by_year", {y: a for y, (a, _) in wrong.items()}, {y: b for y, (_, b) in wrong.items()},
         ok=not wrong, note=f"{len(k['max_by_year'])} years compared: the high, and its date among the days that reached it")
    if "record_f" in k:  # absent under --no-record
        fact(f, f"{pre}.record_f", v.get("record_f"), k["record_f"], note=f"NCEI holds this station from {k['record_since']}")
        fact(f, f"{pre}.record_date", v.get("record_date"), k["record_dates"], ok=v.get("record_date") in k["record_dates"])
        fact(f, f"{pre}.record_since", v.get("record_since"), k["record_since"])
    by = {str(y): n for y, n in (v.get("by_year") or {}).items()}
    wrong = {y: (by.get(y), n) for y, n in k["by_year"].items() if by.get(y) != n}
    fact(f, f"{pre}.by_year", wrong and {y: a for y, (a, _) in wrong.items()}, wrong and {y: b for y, (_, b) in wrong.items()},
         ok=not wrong, note=f"{len(k['by_year'])} years compared; NCEI days missing in a year: {k['days_missing'] or 'none'}")


def score_forecast(f: list, v: dict, k: dict, pre: str) -> None:
    if v.get("issued") != k["issued"]:
        for name in ("highs", "max_high_f", "max_apparent_f"):
            fact(f, f"{pre}.{name}", v.get(name), k.get(name), ok=UNSCORED,
                 note=f"not scored: the app's forecast was issued {v.get('issued')}, the key's {k['issued']}")
        return
    note = f"both issued {k['issued']} Eastern, grid {k['office']} {k['grid']} (app {v.get('office')} {v.get('grid')})"
    fact(f, f"{pre}.highs", v.get("highs"), k["highs"], note=note)
    fact(f, f"{pre}.max_high_f", v.get("max_high_f"), k["max_high_f"], note=note)
    near(f, f"{pre}.max_apparent_f", v.get("max_apparent_f"), k["max_apparent_f"], 1.0, "stated tolerance of 1 F")


def score_cool(f: list, v: dict, k: dict, pre: str) -> None:
    note = f"{k['n_spray_shower_rows']} spray shower rows on {k['n_spray_shower_properties']} properties"
    for name in ("n_spray_shower_sites", "n_outdoor_pools", "n_indoor_pools"):
        fact(f, f"{pre}.{name}", v.get(name), k[name], note=note if "spray" in name else "")
    got = sorted(s.casefold() for s in v.get("spray_shower_sites") or [])
    if len(got) == v.get("n_spray_shower_sites"):  # the app may list only some names of a long list
        fact(f, f"{pre}.spray shower site names", got, k["spray_shower_sites"])


def score_npcc4(f: list, v: dict, table: dict, pre: str) -> None:
    """The value table against the paper's Table 4, then the sentence: each
    claim the brief lists must be there as the paper has it, and the sentence
    may hold no number that is not in the table's heat rows."""
    wrong = []
    for period, rows in table.items():
        for row, vals in rows.items():
            for col, n in vals.items():
                got = (v.get("baseline") or {}).get(row) if col == "baseline" else ((v.get(period) or {}).get(row) or {}).get(col)
                if got != n:
                    wrong.append(f"{period} {row} {col}: app {got}, paper {n}")
    text = v.get("narrative") or ""
    t50, t80 = table["2050s"], table["2080s"]
    d90, e90, d95, hw = t50["days_ge_90"], t80["days_ge_90"], t50["days_ge_95"], t50["heat_waves"]
    for claim in (f"{d90['25']} to {d90['75']} days a year at or above 90°F", f"{e90['25']} to {e90['75']} by the 2080s",
                  f"against {d90['baseline']} a year", f"90th percentile is {d90['90']} days by the 2050s and {e90['90']} by the 2080s",
                  f"95°F go from {d95['baseline']} a year to {d95['25']} to {d95['75']} by the 2050s",
                  f"heat waves from {hw['baseline']} a year to {hw['25']} to {hw['75']}"):
        if claim not in text:
            wrong.append(f"sentence lacks: {claim}")
    known = {n for t in (t50, t80) for vals in t.values() for n in vals.values()} | {16}  # 16 climate models: the paper's text
    plain = re.sub(r"NPCC4|\(2024\)|SSP\d-\d\.\d|\d+°F|\d+(?:st|nd|rd|th)\b|\d{4}s|\d{4}-\d{4}", " ", text)
    stray = sorted({int(n) for n in re.findall(r"\d+", plain)} - known)
    if stray:
        wrong.append(f"numbers not in the table's heat rows: {stray}")
    fact(f, f"{pre}.table and sentence against Table 4", wrong, [], ok=not wrong,
         note="value table exact; six claims matched as phrases; every other number must be a 2050s or 2080s table value")


def score_address(base: str, query: str) -> dict:
    out = app_json(base, "/api/agent", query)
    lat, lon = out.get("lat"), out.get("lon")
    res: dict = {"query": query, "resolved": (out.get("geocode") or {}).get("address"), "lat": lat, "lon": lon, "facts": []}
    if lat is None or "heat_surface" not in out:
        res["error"] = "the app returned no heat briefing for a point"
        return res
    k = kh.all_heat_keys(lat, lon, RECORD)  # the forecast is fetched first, seconds after the app's
    res["keys"] = k
    f = res["facts"]
    score_surface(f, out.get("heat_surface") or {}, k["heat_surface"], "heat_surface")

    v, kv = out.get("hvi") or {}, k["hvi"]
    fact(f, "hvi.hvi", v.get("hvi"), kv["hvi"], note=kv["why"] or f"portal id {kv['geo_id']}")
    fact(f, "hvi.area", v.get("area"), kv["area"])
    if kv["hvi"] is not None:
        fact(f, "hvi.area_code", v.get("area_code"), kv["area_code"])
        ac, vals = v.get("ac_pct"), k["hvi_ac_values"]
        fact(f, "hvi.ac_pct", ac, vals, ok=ac is not None and vals[0] <= ac <= vals[-1],
             note="a bound only: " + ("equal to one of" if ac in vals else "between the lowest and highest of")
             + " the borough's 2017 survey area figures in indicator 2185")
        lc = k["nta_landcover"]
        near(f, "hvi.green_pct", v.get("green_pct"), lc["green_pct"], 2.0,
             f"recount of the 2017 raster over the NTA polygon; {lc['green_pct_of_land']} if water is left out")

    score_visits(f, out.get("heat_visits"), k["heat_visits"], "heat_visits")
    score_station(f, out.get("heat_station") or {}, k["heat_station"], "heat_station")
    score_forecast(f, out.get("nws_heat_forecast") or {}, k["nws_heat_forecast"], "nws_heat_forecast")

    v = out.get("city_landcover") or {}
    fact(f, "city_landcover.radius_m", v.get("radius_m"), 500)
    for name in LANDCOVER:
        near(f, f"city_landcover.{name}", v.get(name), k["city_landcover"][name], 1.5, "30 m cells against 6 inch pixels at the circle's edge")
    v = out.get("cool_features") or {}
    fact(f, "cool_features.radius_m", v.get("radius_m"), 800)
    score_cool(f, v, k["cool_features"], "cool_features")
    score_npcc4(f, out.get("npcc4_heat") or {}, k["npcc4"], "npcc4_heat")
    return res


def score_district(base: str, code: str) -> dict:
    out = app_json(base, f"/api/district/{code}?no_llm=true&hazard=heat")
    lat, lon = out.get("lat"), out.get("lon")
    forecast = kh.nws_heat_forecast(lat, lon)  # at the point the app used, seconds after the app
    k = kh.all_heat_district_keys(code)
    res: dict = {"query": code, "lat": lat, "lon": lon, "keys": k, "facts": []}
    f = res["facts"]
    score_surface(f, out.get("heat_surface_nta") or {}, k["heat_surface"], "heat_surface_nta")
    v = out.get("hvi_nta") or {}
    fact(f, "hvi_nta.hvi", v.get("hvi"), k["hvi"]["hvi"], note=f"portal id {k['hvi']['geo_id']}")
    fact(f, "hvi_nta.neighbourhoods", {h["name"]: h["hvi"] for h in v.get("neighbourhoods") or []}, k["hvi"]["neighbourhoods"])
    score_visits(f, out.get("heat_visits_nta"), k["heat_visits"], "heat_visits_nta")
    score_station(f, out.get("heat_station_nta") or {}, kh.heat_station(lat, lon, RECORD), "heat_station_nta")
    score_forecast(f, out.get("nws_heat_forecast_nta") or {}, forecast, "nws_heat_forecast_nta")
    v = out.get("city_landcover_nta") or {}
    for name in LANDCOVER:
        near(f, f"city_landcover_nta.{name}", v.get(name), k["city_landcover"][name], 0.5, "30 m cells against every 8th 6 inch pixel")
    near(f, "city_landcover_nta.green_pct against the Health portal's vegetative cover (2143)", v.get("green_pct"),
         k["vegetative_cover_2143"], 3.0, "an outside figure for the true community district, not its NTA approximation")
    score_cool(f, out.get("cool_features_nta") or {}, k["cool_features"], "cool_features_nta")
    score_npcc4(f, out.get("npcc4_heat_nta") or {}, k["npcc4"], "npcc4_heat_nta")
    return res


def score_sweep(base: str, _query: str) -> dict:
    """Heat visits and the district index for every community district, through the district endpoint."""
    res: dict = {"query": "all 59 community districts", "facts": []}
    codes = sorted(c for c in set(kh._ntas()["cdta2020"]) if kh.heat_visits(c))
    for code in codes:
        out = app_json(base, f"/api/district/{code}?no_llm=true&hazard=heat")
        score_visits(res["facts"], out.get("heat_visits_nta"), kh.heat_visits(code), f"heat_visits_nta[{code}]")
        kv = kh.hvi_district(code)
        v = out.get("hvi_nta") or {}
        fact(res["facts"], f"hvi_nta[{code}].hvi", v.get("hvi"), kv["hvi"])
        fact(res["facts"], f"hvi_nta[{code}].neighbourhoods", {h["name"]: h["hvi"] for h in v.get("neighbourhoods") or []},
             kv["neighbourhoods"])
        time.sleep(2)
    res["n_districts"] = len(codes)
    return res


def score_selection(_base: str, _query: str) -> dict:
    """The app's list of kept and skipped Landsat images against its own stated rule, recomputed."""
    res: dict = {"query": "Landsat image selection", "facts": []}
    for s in kh.landsat_selection():
        fact(res["facts"], f"landsat_selection[{s['id']}]", "kept" if s["app_keeps"] else "skipped",
             "kept" if s["key_keeps"] else "skipped",
             note=f"tier {s['tier']}, scene cloud {s['scene_cloud_pct']}%, {s['clear_land_pct']}% of NTA pixels clear")
    lists = kh.landsat_lists()
    listed = set(lists["kept"] + lists["skipped"])
    left_out = [c["id"] for c in kh.landsat_candidates() if c["scene_cloud_pct"] <= 20 and c["id"] not in listed]
    fact(res["facts"], "landsat_selection.every image under 20% scene cloud is listed", left_out, [])
    return res


KINDS = {"heat_address": score_address, "heat_district": score_district, "heat_sweep": score_sweep,
         "heat_selection": score_selection}


def group(name: str) -> str:
    return re.split(r"[.\[]", name)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("set_file", nargs="?", default=str(HERE / "heat_seen.json"))
    ap.add_argument("--base", default="http://127.0.0.1:7861")
    ap.add_argument("--ids", default=None, help="comma-separated entry ids to run")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pause", type=float, default=2, help="seconds between entries")
    ap.add_argument("--fit-shift", action="store_true", help="also fit where the app's surface raster sits (a diagnosis; minutes)")
    ap.add_argument("--no-record", action="store_true", help="skip the station's all-time record (a slow first fetch)")
    a = ap.parse_args()
    global RECORD
    RECORD = not a.no_record
    results = []
    for e in json.load(open(a.set_file)):
        if a.ids and e["id"] not in a.ids.split(","):
            continue
        try:
            r = KINDS[e["kind"]](a.base, e["query"])
        except Exception as ex:  # noqa: BLE001
            r = {"query": e["query"], "error": repr(ex), "facts": []}
        r["id"], r["kind"] = e["id"], e["kind"]
        results.append(r)
        bad = [f for f in r["facts"] if f["ok"] is False]
        skipped = sum(f["ok"] is None for f in r["facts"])
        print(f"{e['id']} {e['kind']:14} {sum(f['ok'] is True for f in r['facts'])}/{len(r['facts']) - skipped} ok"
              + (f", {skipped} unscored" if skipped else "") + f"  {e['query']}"
              + (f"  ERROR {r['error']}" if r.get("error") else ""), flush=True)
        for f in bad:
            print(f"    MISS {f['fact']}: riprap={f['riprap']!r} key={f['key']!r}  {f['note']}", flush=True)
        time.sleep(a.pause)

    tally: dict[str, Counter] = {}
    for r in results:
        for f in r["facts"]:
            tally.setdefault(group(f["fact"]), Counter())[{True: "ok", False: "miss", None: "unscored"}[f["ok"]]] += 1
    print(f"\n{'source':24} {'ok':>5} {'miss':>5} {'unscored':>9}")
    for g, c in tally.items():
        print(f"{g:24} {c['ok']:5} {c['miss']:5} {c['unscored']:9}")
    fit = None
    if a.fit_shift:
        app = [{"lat": r["lat"], "lon": r["lon"], **{f["fact"].split(".")[1]: f["riprap"] for f in r["facts"]
                                                     if f["fact"].startswith("heat_surface.")}}
               for r in results if r["kind"] == "heat_address" and r["facts"]]
        fit = kh.surface_shift_fit(app)
        print(f"\nsurface raster register, {len(app)} addresses: best fit {fit[0][1]} m east, {fit[0][2]} m north "
              f"(mean difference {fit[0][0]} F); unshifted {[e for e, dx, dy in fit if (dx, dy) == (0, 0)][0]} F")
    n_ok = sum(c["ok"] for c in tally.values())
    n_miss = sum(c["miss"] for c in tally.values())
    n_un = sum(c["unscored"] for c in tally.values())
    print(f"{'total':24} {n_ok:5} {n_miss:5} {n_un:9}")
    print(f"\n{n_ok}/{n_ok + n_miss} scored facts agree, {n_un} unscored, {len(results)} entries, {date.today()}")
    out = a.out or str(HERE / "results" / f"heat_seen_{date.today()}.json")
    json.dump({"date": str(date.today()), "base": a.base, "n_ok": n_ok, "n_miss": n_miss, "n_unscored": n_un,
               "by_source": {g: dict(c) for g, c in tally.items()}, "surface_shift_fit": fit, "results": results}, open(out, "w"), indent=1, default=str)
    print("wrote", out)
    return 0 if n_miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
