"""The NYC Health Department's heat records at a place.

Reads data/heat/dohmh_heat.json (scripts/bake_heat_records.py, from the
Environment and Health Data Portal's public repository):

  * the Heat Vulnerability Index, 1 (lowest risk) to 5 (highest), for the
    2020 neighborhood tabulation area around an address, or for a community
    district with its neighbourhoods;
  * heat-stress emergency department visits by residents of a community
    district, May to September over five years.

The traps the sentences carry:

  * the index is a rank among neighbourhoods from a model of heat deaths,
    not a measurement of heat at an address, and the department says every
    neighbourhood has residents at risk whatever its score;
  * parks, airports and cemeteries have no index;
  * visits are counted by where the patient lives, only when diagnosed as
    heat illness, and small counts are suppressed. A suppressed count is
    not a zero.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "heat" / "dohmh_heat.json"
BOROUGH = {"MN": "Manhattan", "BX": "the Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}
RANK_TRAP = ("The index ranks neighbourhoods against each other by a model of heat deaths, from surface temperature, "
             "green space, air conditioning, income and the share of Black residents; it is not a measurement of heat "
             "at an address, and the department notes that every neighbourhood has residents at risk, whatever its score.")
GROUP = {1: "the lowest risk group", 5: "the highest risk group"}


@lru_cache(maxsize=1)
def _data() -> dict | None:
    return json.loads(PATH.read_text()) if PATH.exists() else None


def _nta_at(lat: float, lon: float) -> dict | None:
    """The 2020 neighborhood tabulation area containing a point."""
    from shapely.geometry import Point

    from app.areas import nta

    g = nta.load()
    hit = g[g.contains(Point(lon, lat))]
    return None if hit.empty else {"code": hit.iloc[0]["nta2020"], "name": hit.iloc[0]["ntaname"],
                                   "district": hit.iloc[0]["cdta2020"]}


def _district_words(code: str) -> str:
    return f"{BOROUGH[code[:2]]} community district {int(code[2:])}"


def _score(n: int) -> str:
    return f"at {n} out of 5" + (f", {GROUP[n]}" if n in GROUP else "")


def _hvi_nta(code: str, name: str, where: str) -> dict | None:
    d = _data()
    if d is None:
        return None
    year = d["hvi"]["year"]
    a = d["hvi"]["nta"]["areas"].get(code)
    if a is None:
        return {"available": False, "area": name, "year": year,
                "narrative": f"The NYC Health Department publishes no Heat Vulnerability Index for {name}: the {year} index "
                             "covers residential neighbourhoods and leaves out parks, airports and cemeteries."}
    narrative = (f"The NYC Health Department's Heat Vulnerability Index ({year}, from 2016 to 2020 data) scores "
                 f"{name}{where} {_score(a['hvi'])}. "
                 f"{RANK_TRAP} For {name} the department lists {a['ac_pct']}% of households with air conditioning and "
                 f"{a['green_pct']}% green space.")
    return {"available": True, "hvi": a["hvi"], "area": name, "area_code": code, "year": year, "ac_pct": a["ac_pct"],
            "green_pct": a["green_pct"], "median_income": a["median_income"], "narrative": narrative,
            "headline_value": f"{a['hvi']} of 5 ({name})"}


def hvi_for_point(lat: float, lon: float) -> dict | None:
    area = _nta_at(lat, lon)
    return area and _hvi_nta(area["code"], area["name"], ", the neighbourhood around this address,")


def hvi_for_area(query) -> dict | None:
    """A neighbourhood (its own score) or a community district (its score and
    each of its neighbourhoods')."""
    from app.areas import nta

    code = ((query.extras.get("area_code") if query else None) or "").upper().replace(" ", "")
    d = _data()
    if d is None or not code:
        return None
    if not re.fullmatch(r"(MN|BX|BK|QN|SI)\d\d", code):
        row = nta.by_code(code)
        return row and _hvi_nta(code, row["nta_name"], "")
    score = d["hvi"]["district"]["areas"].get(code)
    if score is None:
        return None
    parts = sorted(((a["name"], a["hvi"]) for a in d["hvi"]["nta"]["areas"].values() if a["district"] == code),
                   key=lambda p: (-p[1], p[0]))
    year = d["hvi"]["year"]
    narrative = (f"The NYC Health Department's Heat Vulnerability Index ({year}, from 2016 to 2020 data) scores "
                 f"{_district_words(code)} "
                 f"{_score(score)}; its neighbourhoods score {', '.join(f'{n} {s}' for n, s in parts)}. {RANK_TRAP}")
    return {"available": True, "hvi": score, "area": code, "area_code": code, "year": year,
            "neighbourhoods": [{"name": n, "hvi": s} for n, s in parts], "narrative": narrative,
            "headline_value": f"{score} of 5 ({code})"}


def _visits(code: str) -> dict | None:
    d = _data()
    v = d and d["ed_visits"]["district"].get(code)
    if v is None:
        return None
    e, where = d["ed_visits"], _district_words(code)
    when = f"{e['months']} of {e['period']}"
    if v.get("n") is None:
        return {"available": True, "suppressed": True, "district": code, "period": e["period"], "n": None,
                "narrative": f"The NYC Health Department withholds the number of emergency department visits for heat "
                             f"illness by residents of {where} in {when}. {v.get('n_note', 'The count is suppressed.')} "
                             "A withheld count is not a zero."}
    city = e["citywide"]
    narrative = (f"Residents of {where} made {v['n']} emergency department visits for heat illness in {when}, an "
                 f"age-adjusted rate of {v['age_adjusted_rate']:.1f} per 100,000 a year against {city['age_adjusted_rate']:.1f} "
                 f"citywide (NYC Health Department, from state hospital records). Visits are counted by where the "
                 f"patient lives, and only when diagnosed as heat illness.")
    return {"available": True, "suppressed": False, "district": code, "period": e["period"], "n": v["n"],
            "age_adjusted_rate": v["age_adjusted_rate"], "citywide_age_adjusted_rate": city["age_adjusted_rate"],
            "narrative": narrative, "headline_value": f"{v['n']} visits, {v['age_adjusted_rate']:.1f} per 100,000 a year"}


def visits_for_point(lat: float, lon: float) -> dict | None:
    area = _nta_at(lat, lon)
    return area and _visits(area["district"])


def visits_for_area(query) -> dict | None:
    from app.areas import nta

    code = ((query.extras.get("area_code") if query else None) or "").upper().replace(" ", "")
    if code and not re.fullmatch(r"(MN|BX|BK|QN|SI)\d\d", code):
        g = nta.load()
        hit = g[g["nta2020"] == code]
        code = "" if hit.empty else hit.iloc[0]["cdta2020"]
    return _visits(code) if code else None
