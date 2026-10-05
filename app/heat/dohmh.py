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
# The index in the department's own words (NYC Health Department, Interactive Heat Vulnerability Index,
# a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/, read 2026-10-05). The page lists four factors and
# explains race under its own heading, "Racial inequities in heat impacts"; it once stood here as a fifth input,
# "the share of Black residents", with none of that explanation.
RANK_TRAP = ("The index ranks neighbourhoods against each other: the department says it \"uses a statistical model to "
             "summarize the most important factors of neighborhood heat risk: surface temperature, green space, home "
             "air conditioning, and income\". It is not a measurement of heat at an address, and the department "
             "says \"All neighborhoods have residents at risk for heat illness and death\".")
# Carried wherever a score of 4 or 5 is stated: a high score beside a neighbourhood's name reads as a fact about
# its residents unless the department's own account of the cause comes with it.
RACISM = ("Of who heat harms most, the department writes that Black New Yorkers suffer disproportionate health "
          "impacts from heat \"due to social and economic disparities\", and that \"These disparities stem from "
          "structural racism, which includes neighborhood disinvestment, racist housing policies, fewer job "
          "opportunities and lower pay, and less access to high-quality education and health care\" (NYC Health "
          "Department, Interactive Heat Vulnerability Index).")
# The department scores its own neighbourhoods, which are City Planning's tabulation areas and not the
# neighbourhood names City Planning's geocoder returns for an address ("Hollis" in the place line, "Jamaica" here).
OWN_AREAS = ("The area is the 2020 Neighborhood Tabulation Area the index is published for, which can carry "
             "another name than the neighbourhood in the address above.")
PUBLIC_HOUSING = ("This address is in or beside the public housing development {name} (NYCHA's map of its "
                  "developments): the neighbourhood's figures, its air conditioning share especially, are not the "
                  "development's.")
_NEAR_DEVELOPMENT_M = 100
GROUP = {1: "the lowest risk group", 5: "the highest risk group"}
DISTRICT_MISMATCH = ("The count and the rate are separate figures in the department's file: for most community "
                     "districts the count divided by residents and years does not give the printed rate, the file "
                     "does not say why, and both are printed here as published.")


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


@lru_cache(maxsize=1)
def _developments():
    """NYCHA's development outlines in a metric projection, or None when the file is not there."""
    import geopandas as gpd

    path = PATH.parents[1] / "nycha.geojson"
    return gpd.read_file(path).to_crs(2263) if path.exists() else None


def _development_at(lat: float, lon: float) -> str | None:
    """The public housing development an address is in or within 100 m of."""
    import geopandas as gpd
    from shapely.geometry import Point

    g = _developments()
    if g is None:
        return None
    pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(2263).iloc[0]
    near = g[g.distance(pt) <= _NEAR_DEVELOPMENT_M / 0.3048]  # the projection is in feet
    return None if near.empty else str(near.iloc[0]["developmen"]).title()


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
                 f"{RANK_TRAP} For {name} the department's file gives {a['ac_pct']}% of households with air conditioning (a "
                 f"survey estimate it shares across neighbouring neighbourhoods) and {a['green_pct']}% green space.")
    if "-" in name:
        narrative += f" The index scores {name} as one area: no one of the neighbourhoods in its name has a score of its own."
    if where:
        narrative += f" {OWN_AREAS}"
    if a["hvi"] >= 4:
        narrative += f" {RACISM}"
    return {"available": True, "hvi": a["hvi"], "area": name, "area_code": code, "year": year, "ac_pct": a["ac_pct"],
            "green_pct": a["green_pct"], "narrative": narrative,
            "headline_value": f"{a['hvi']} of 5 ({name})"}


def hvi_for_point(lat: float, lon: float) -> dict | None:
    area = _nta_at(lat, lon)
    out = area and _hvi_nta(area["code"], area["name"], ", the neighbourhood around this address,")
    if out and out.get("available") and (name := _development_at(lat, lon)):
        out = {**out, "public_housing": name, "narrative": f"{out['narrative']} {PUBLIC_HOUSING.format(name=name)}"}
    return out


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
                 f"{_score(score)}; its neighbourhoods score {', '.join(f'{n} {s}' for n, s in parts)}. {RANK_TRAP}"
                 + (f" {RACISM}" if max([score, *(s for _, s in parts)]) >= 4 else ""))
    return {"available": True, "hvi": score, "area": code, "area_code": code, "year": year,
            "neighbourhoods": [{"name": n, "hvi": s} for n, s in parts], "narrative": narrative,
            "headline_value": f"{score} of 5 ({code})"}


def _visits(code: str) -> dict | None:
    """Visits for a community district ('QN12'), a borough ('QN') or the city ('NYC')."""
    d = _data()
    if d is None:
        return None
    e = d["ed_visits"]
    v = e["citywide"] if code == "NYC" else e["borough"].get(code) if len(code) == 2 else e["district"].get(code)
    if v is None:
        return None
    where = "New York City" if code == "NYC" else BOROUGH[code] if len(code) == 2 else _district_words(code)
    when = f"{e['months']} of {e['period']}"
    if v.get("n") is None:
        return {"available": True, "suppressed": True, "district": code, "period": e["period"], "n": None,
                "narrative": f"The NYC Health Department withholds the number of emergency department visits for heat "
                             f"illness by residents of {where} in {when}. {v.get('n_note', 'The count is suppressed.')} "
                             "A withheld count is not a zero."}
    city = e["citywide"]
    # The count is the file's five-year total and the rate its average annual
    # age-adjusted rate. For most community districts the two do not
    # reconcile and the portal's metadata does not say why, so the sentence
    # says what each is and that they are printed as published.
    narrative = (f"Residents of {where} made {v['n']} emergency department visits for heat illness in {when} (the "
                 f"five-year total), and the NYC Health Department gives an average annual age-adjusted rate of "
                 f"{v['age_adjusted_rate']:.1f} per 100,000 residents"
                 + ("" if code == "NYC" else f" against {city['age_adjusted_rate']:.1f} citywide")
                 + " (from state hospital records). "
                 + (DISTRICT_MISMATCH + " " if len(code) == 4 else "")
                 + "Visits are counted by where the patient lives, and only when diagnosed as heat illness.")
    return {"available": True, "suppressed": False, "district": code, "period": e["period"], "n": v["n"],
            "age_adjusted_rate": v["age_adjusted_rate"], "citywide_age_adjusted_rate": city["age_adjusted_rate"],
            "narrative": narrative, "headline_value": f"{v['n']} visits, {v['age_adjusted_rate']:.1f} per 100,000 a year"}


def visits_for_point(lat: float, lon: float) -> dict | None:
    area = _nta_at(lat, lon)
    return area and _visits(area["district"])


def visits_for_area(query) -> dict | None:
    from app.areas import nta

    code = ((query.extras.get("area_code") if query else None) or "").upper().replace(" ", "")
    if code and not re.fullmatch(r"(MN|BX|BK|QN|SI)(\d\d)?|NYC", code):
        g = nta.load()
        hit = g[g["nta2020"] == code]
        code = "" if hit.empty else hit.iloc[0]["cdta2020"]
    return _visits(code) if code else None
