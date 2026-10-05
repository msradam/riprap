"""Bake the NYC Health Department's heat records for the app.

Data only. Reads three files of the Environment and Health Data Portal's
public repository (github.com/nychealth/EHDP-data, branch `production`) and
writes data/heat/dohmh_heat.json, which app/heat/dohmh.py reads:

  * the Heat Vulnerability Index by 2020 neighborhood tabulation area, with
    the inputs the department publishes beside it
    (key-topics/heat-vulnerability-index/hvi-nta-2020.csv);
  * the same index by community district (indicators/data/2191.json);
  * heat-stress emergency department visits by community district over five
    years: number, estimated annual rate and age-adjusted rate, with the
    department's suppression notes (indicators/data/2443.json).

Each block records the file's URL and the date of its last commit, which is
the record's vintage.

It also writes data/heat/parks_cooling.json: NYC Parks' spray showers
(NYC Open Data ckaz-6gaa) and pools (y5rm-wagw) as points, with each
dataset's own last-update date. Drinking fountains (qnv7-p7a2) are left
out: the table mixes fountains with sinks and was last updated in 2024.

    uv run python scripts/bake_heat_records.py
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "heat" / "dohmh_heat.json"
REPO = "nychealth/EHDP-data"
RAW = f"https://raw.githubusercontent.com/{REPO}/production/"
HVI_NTA = "key-topics/heat-vulnerability-index/hvi-nta-2020.csv"
HVI_CD = "indicators/data/2191.json"
ED = "indicators/data/2443.json"
GEO = "geography/GeoLookup.csv"  # the portal's own key to its ids
ABBR = {"Manhattan": "MN", "Bronx": "BX", "Brooklyn": "BK", "Queens": "QN", "Staten Island": "SI"}
ED_MEASURES = {1403: "n", 1404: "annual_rate", 1405: "age_adjusted_rate"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "riprap-heat-bake/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    time.sleep(1)
    return body


def _vintage(path: str) -> dict:
    commits = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits?path={path}&sha=production&per_page=1"))
    return {"source_url": RAW + path, "commit": commits[0]["sha"], "date_modified": commits[0]["commit"]["committer"]["date"][:10]}


def _rows(path: str) -> list[dict]:
    """An indicator file is one dict of equal-length columns."""
    cols = json.loads(_get(RAW + path))
    return [dict(zip(cols, vals, strict=True)) for vals in zip(*cols.values(), strict=True)]


def _boroughs() -> dict[tuple[str, int], str]:
    """(geography type, id) -> borough abbreviation, from the portal's lookup.
    Its ids follow three schemes: a borough row counts the boroughs in
    alphabetical order (1 is the Bronx), a community district id leads with
    the city's borough code (1 is Manhattan), and a 2020 tabulation area id
    leads with the county's FIPS code. Reading the lookup avoids all three."""
    rows = csv.DictReader(io.StringIO(_get(RAW + GEO).decode("utf-8-sig")))
    return {(r["GeoType"], int(r["GeoID"])): ABBR[r["Borough"]] for r in rows if r["Borough"] in ABBR}


SOCRATA = "https://data.cityofnewyork.us"


def parks_cooling() -> dict:
    """Spray showers and pools as [kind, park, lat, lon] rows."""
    from datetime import UTC, datetime

    sites, sources = [], {}
    for view, kind in (("ckaz-6gaa", "spray shower"), ("y5rm-wagw", "pool")):
        meta = json.loads(_get(f"{SOCRATA}/api/views/{view}.json"))
        sources[kind] = {"dataset": meta["name"], "id": view, "source_url": f"{SOCRATA}/d/{view}",
                         "date_modified": datetime.fromtimestamp(meta["rowsUpdatedAt"], UTC).strftime("%Y-%m-%d")}
        for r in json.loads(_get(f"{SOCRATA}/resource/{view}.json?$limit=5000")):
            if kind == "pool":
                ring = r["polygon"]["coordinates"][0]
                lon, lat = (sum(c[i] for c in ring) / len(ring) for i in (0, 1))
                # A wading pool is not a place to swim, so it is its own kind.
                kind_ = "wading pool" if r.get("pooltype") == "Wading" else f"{r['location'].lower()} pool"
                sites.append([kind_, r["name"], round(lat, 6), round(lon, 6)])
            elif r.get("point"):
                lon, lat = r["point"]["coordinates"]
                sites.append([kind, r.get("sitename") or r.get("propname") or "", round(lat, 6), round(lon, 6)])
    return {"retrieved_at": str(date.today()), "license": "NYC Open Data Terms of Use", "sources": sources,
            "columns": ["kind", "park", "lat", "lon"], "sites": sites}


def main() -> int:
    cooling = parks_cooling()
    (OUT.parent).mkdir(parents=True, exist_ok=True)
    (OUT.parent / "parks_cooling.json").write_text(json.dumps(cooling, separators=(",", ":")) + "\n")
    print(f"parks_cooling.json: {len(cooling['sites'])} sites")
    boro = _boroughs()
    nta = {}
    for r in csv.DictReader(io.StringIO(_get(RAW + HVI_NTA).decode("utf-8-sig"))):
        nta[r["NTACode"]] = {"name": r["GEONAME"], "district": r["CDTACode"], "hvi": int(r["HVI_RANK"]),
                             "surface_temp_f": round(float(r["SURFACE_TEMP"]), 1), "green_pct": round(float(r["GREENSPACE"]), 1),
                             "ac_pct": round(float(r["PCT_HOUSEHOLDS_AC"]), 1), "median_income": round(float(r["MEDIAN_INCOME"]))}
    cd_rows = _rows(HVI_CD)
    period = {r["TimePeriodID"] for r in cd_rows}
    if period != {298}:  # 2023 on the portal; a new release needs its year read from the metadata
        raise RuntimeError(f"HVI time period {period}, expected the 2023 release (298)")
    districts = {f"{boro['CDTA2020', r['GeoID']]}{r['GeoID'] % 100:02d}": int(r["Value"]) for r in cd_rows}
    visits: dict = {"district": {}, "borough": {}, "citywide": {}}
    for r in _rows(ED):
        key = ED_MEASURES[r["MeasureID"]]
        if r["GeoType"] == "CD":
            where = visits["district"].setdefault(f"{boro['CD', r['GeoID']]}{r['GeoID'] % 100:02d}", {})
        elif r["GeoType"] == "Borough":
            where = visits["borough"].setdefault(boro["Borough", r["GeoID"]], {})
        else:
            where = visits["citywide"]
        where[key] = r["Value"]
        if r["Note"]:
            where[f"{key}_note"] = r["Note"].lstrip("* ").strip()
    out = {
        "what": __doc__.split("\n\n")[0], "retrieved_at": str(date.today()),
        "license": "Apache-2.0 (nychealth/EHDP-data); source data NYC DOHMH and NYS SPARCS",
        "hvi": {"year": 2023, "nta": {**_vintage(HVI_NTA), "areas": nta}, "district": {**_vintage(HVI_CD), "areas": districts}},
        "ed_visits": {"period": "2018 to 2022", "months": "May to September", **_vintage(ED), **visits},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"{OUT}: {len(nta)} neighbourhoods, {len(districts)} districts, {len(visits['district'])} districts with visit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
