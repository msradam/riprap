"""Heat questions, answered from their own words like the flood ones.

`hazard_of(question)` says which briefing a query belongs to, and
`answer(question, texts, values)` is the heat half of
`rule_answer.answer`: it picks the lead and the facts from the heat
sources that returned a sentence. The facts are the sources' sentences
word for word; nothing here writes a fact.

The order of the rules:

  1. a score, rating or grade: Riprap computes none, and says so before
     the Health Department's own index;
  2. the temperature inside a building or on one block on a coming day: no
     source predicts that; the Weather Service's forecast for the area and
     the surface measurement follow;
  3. "right now", "today": the latest observation, any active heat alert
     and the forecast, with no yes or no;
  4. the coming days: the Weather Service's forecast and alerts, under a
     lead that says whose forecast it is;
  5. the coming decades: the NPCC4 projection;
  6. how many days reached 90 F: the station record;
  7. hotter or cooler than the city: the Landsat surface measurement, and
     a yes or no "at the surface" only when every image agrees;
  8. any source the question names (the index, emergency visits, tree
     canopy, places to cool off);
  9. any other heat question: the measurement, the index and the station.

The traps live in the sources' sentences (surface temperature is not air
temperature, the index is a rank, cooling centers open only in a heat
emergency), so an answer cannot quote a figure without its caveat.
"""

from __future__ import annotations

import re

# Outdoor heat. "Heath Avenue" and "heating" are not it, and neither is "hot
# water": a 311 "HEAT/HOT WATER" complaint is about a cold apartment in winter.
HEAT_RE = re.compile(
    r"\bheat(?:[- ]?waves?)?\b(?!\s*(?:and|&|/|or)\s*hot water)|\boverheat|\bhot(?:ter|test)?\b(?!\s+water)|\btemperatures?\b"
    r"|\bcooling (?:cent(?:er|re)s?|sites?)\b|\bcool (?:off|down)\b|\bspray showers?\b|\b(?:public|swimming) pools?\b"
    r"|\bswelter|\b(?:8[5-9]|9\d|1[01]\d)[- ]?(?:°|degrees?\b|deg\b)|\bair[- ]condition"
    r"|\bdays? (?:above|over|at or above) (?:8[5-9]|9\d|1[01]\d)\b|\b(?:cooler|coolest|warmer|warmest)\b"
    # Found by questions written without sight of these rules: "air temp", "will it be over 95", "hit 90 or
    # above", "forecast highs", "cool places", "what will summers be like".
    r"|\btemps?\b|\b(?:over|above|hit|hits|reach(?:es|ed)?|top(?:s|ped)?)\s+(?:8[5-9]|9\d|1[01]\d)\b|\bhighs\b"
    r"|\bcool (?:places?|spots?|spaces?)\b|\bstay(?:ing)? cool\b|\bsummers\b", re.I)
# A cold apartment: no heat, a radiator, the landlord. Not this briefing.
INDOOR_HEATING_RE = re.compile(
    r"\bheat\s*(?:and|&|/|or)\s*hot water|\bno heat\b|\bheat(?:ing)? (?:complaints?|violations?|season|is (?:off|out|broken))"
    r"|\b(?:radiators?|boilers?)\b|\bturn(?:ed|s)? (?:on|off) the heat|\bwithout heat\b|\bheat (?:in|for) (?:the )?winter", re.I)
INDOOR_HEATING = ("This reads as a question about indoor heating (no heat or hot water in a building). Riprap's heat "
                  "briefing covers outdoor summer heat only. Heating complaints go to 311 (portal.311.nyc.gov or call "
                  "311) and are enforced by the Department of Housing Preservation and Development.")

SURFACE = ("heat_surface", "heat_surface_nta")
HVI = ("hvi", "hvi_nta")
VISITS = ("heat_visits", "heat_visits_nta")
STATION = ("heat_station", "heat_station_nta")
FORECAST = ("nws_heat_forecast", "nws_heat_forecast_nta")
ALERTS = ("nws_heat_alerts", "nws_heat_alerts_nta")
NPCC4 = ("npcc4_heat", "npcc4_heat_nta")
COOLING = ("cool_features", "cool_features_nta")
COVER = ("city_landcover", "city_landcover_nta", "landcover", "landcover_nta")
OBS = ("heat_obs", "heat_obs_nta")
EXPERIMENTAL = ("landcover", "landcover_nta")

# Question words -> the source they name, most specific first.
TOPICS = (
    (re.compile(r"cooling (?:cent|site)|cool (?:off|down)|spray shower|\bpools?\b|sprinkler|where can (?:i|we|people|residents)", re.I),
     COOLING),
    (re.compile(r"emergency (?:room|department)|\b(?:er|ed) visits?\b|hospitali[sz]|heat (?:illness|stroke|exhaustion|stress)"
                r"|\bsick\b|\bhealth\b(?! department)", re.I), VISITS),
    (re.compile(r"vulnerab|\bhvi\b|\bindex\b", re.I), HVI),
    (re.compile(r"\btrees?\b|canopy|\bshade|\bpaved|\bpaving|pavement|impervious|green (?:space|cover)|vegetat", re.I), COVER),
    (re.compile(r"advisor(?:y|ies)|\bwarnings?\b|\balerts?\b|\bwatch\b", re.I), ALERTS),
    (re.compile(r"\bsurface\b|landsat|satellite|heat island|hot ?spots?|\b(?:run|runs|ran|get|gets|is|are) (?:the )?hottest\b"
                r"|\bhottest (?:parts?|blocks?|areas?|places?|spots?)\b|how hot (?:does|do) it get", re.I), SURFACE),
    (re.compile(r"\b(?:8[5-9]|9\d|1[01]\d)[- ]?(?:°|degrees?\b|deg\b)|\bhot days?\b|\brecord\b|hottest (?:day|it)"
                r"|how hot (?:did|was|has|does|do)|\b(?:this|last) (?:summer|year)\b|so far this"
                r"|\b(?:hit|reach(?:ed)?|top(?:ped)?|over|above) (?:8[5-9]|9\d|1[01]\d)\b", re.I), STATION),
)
# Heat deaths are published for the city as a whole only, so no source here holds them for a place.
_DEATHS_RE = re.compile(r"\bdeaths?\b|\bdied\b|\bmortality\b|\bfatalit", re.I)
_SCORE_RE = re.compile(r"\b(?:scores?|ratings?|rated|grades?|rank(?:ed|ing|s)?)\b", re.I)
# The inside of a building, or one block on a coming day: nobody forecasts that.
_INDOORS_RE = re.compile(r"\b(?:my|our|the|this) (?:apartment|unit|building|home|house|room|classroom|block|street|playground)\b"
                         r"|\bindoors?\b|\binside\b|\b(?:apartment|apt\.?) \w+\b|\bon my block\b", re.I)
# A calendar date ("on July 15", "the afternoon of 7/15"): beyond a seven-day forecast as a rule, and never forecast for one spot.
_DATE_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}\b|\b\d{1,2}/\d{1,2}\b", re.I)
_WILL_RE = re.compile(r"\b(?:will|going to|gonna|expected to|likely to)\b|\bhow hot will\b", re.I)
_TODAY_RE = re.compile(r"\b(?:today|this (?:morning|afternoon|evening)|outside now)\b", re.I)
_NEAR_RE = re.compile(r"\b(?:tomorrow|tonight|this (?:coming )?(?:week|weekend)|next (?:week|weekend|few days|couple of days)"
                      r"|(?:next|coming) (?:\w+ )?(?:hours|days)|forecast|on (?:mon|tues|wednes|thurs|fri|satur|sun)day"
                      r"|heat ?wave (?:coming|expected|on the way))\b", re.I)
_FAR_RE = re.compile(r"\b20[3-9]\ds?\b|\b2100\b|decades?|century|climate change|projections?|projected|in the future"
                     r"|by (?:the )?(?:middle|end) of the century|\b(?:next|coming) (?:\w+ )?years\b|\bwhen my kids\b"
                     r"|\bkeep getting (?:hotter|warmer)\b", re.I)
_COUNT_DAYS_RE = re.compile(r"\bhow many\b[^.?!]*\bdays?\b|\bnumber of\b[^.?!]*\bdays?\b|\bdays? (?:above|over|at or above)\b", re.I)
_COMPARE_CITY_RE = re.compile(r"\b(?:hott?er|warmer|cooler)\b[^.?!]*\bthan\b|\bthan (?:the )?(?:rest of the |city|average)"
                              r"|\bcompared? (?:to|with) (?:the )?(?:rest of the )?(?:city|average)|\bheat island\b"
                              r"|\b(?:hott?er|warmer|cooler) (?:here|there)\b", re.I)
# "Hotter than Riverdale" compares two places: the measurement here says nothing about there, so no yes or no.
_THAN_ELSEWHERE_RE = re.compile(r"\bthan\b(?!\s+(?:the\s+)?(?:rest|city|average|most|other|nyc|new york|normal|usual|it should))", re.I)
_YEAR_RE = re.compile(r"\b(?:in|during|for|of)\s+((?:19|20)\d\d)\b")


def hazard_of(question: str) -> str:
    """"heat" when the words are about outdoor heat and no part of the query
    is about flooding; "flood" otherwise. ("It gets hot here in the summer and
    the basement floods" is a flood question.)"""
    from riprap.core.burr import rule_answer

    q = question or ""
    if not HEAT_RE.search(q) or re.search(r"\bflood", q, re.I) or INDOOR_HEATING_RE.search(q):
        return "flood"
    # A preamble about the heat before a question about a flood record is a flood question.
    if any(rule_answer.names_flood(c) for c in rule_answer._clauses(q) if not HEAT_RE.search(c)):
        return "flood"
    return "heat"


def asks_something(text: str) -> bool:
    """Words beside a place that ask a heat question ("QN12 heat
    vulnerability index"). "Heat", "extreme heat" or "heat risk" alone ask
    for the heat briefing."""
    t = text or ""
    return bool(any(p.search(t) for p, _ in TOPICS) or _TODAY_RE.search(t) or _NEAR_RE.search(t) or _FAR_RE.search(t)
                or _SCORE_RE.search(t) or _COMPARE_CITY_RE.search(t) or _COUNT_DAYS_RE.search(t))


def named(question: str, texts: dict[str, str]) -> list[str]:
    """The sources the question's words name that returned a sentence."""
    out: list[str] = []
    for pattern, ids in TOPICS:
        if pattern.search(question or ""):
            out += [i for i in ids if texts.get(i) and i not in out]
    return out


def time_frame(question: str) -> str:
    from riprap.core.burr import rule_answer

    q = question or ""
    if _FAR_RE.search(q):
        return "future"
    if _NEAR_RE.search(q) or (_WILL_RE.search(q) and not _INDOORS_RE.search(q)):
        return "future"
    if rule_answer._NOW_RE.search(q) or _TODAY_RE.search(q):
        return "now"
    return "past" if re.search(r"\b(?:did|was|were|has|have|had)\b|\blast (?:summer|year)\b", q, re.I) else "any"


def year_sentence(question: str, facts: list[str], values: dict | None) -> str | None:
    """For "how hot did it get in June 2025": that year's highest reading
    and its date from the station's yearly record, as the lead. None when
    the question names no year, or asks for a count of days."""
    doc = next((d for d in STATION if d in facts), None)
    v = (values or {}).get(doc) if doc else None
    m = re.search(r"\b((?:19|20)\d\d)\b", question or "")
    if not m or not isinstance(v, dict) or _COUNT_DAYS_RE.search(question or "") or not re.search(r"how hot|hottest|highest|record", question or "", re.I):
        return None
    peak = (v.get("max_by_year") or {}).get(int(m.group(1)), (v.get("max_by_year") or {}).get(m.group(1)))
    return f"The highest reading at {v['station']} in {m.group(1)} was {peak[0]}°F on {peak[1]}." if peak else None


def count_sentence(question: str, facts: list[str], values: dict | None) -> str | None:
    """For "how many days reached 90 in 2023": that year's count from the
    station's own yearly record, as the count lead. None when the question
    names no year the record holds (the station sentence then answers)."""
    doc = next((d for d in STATION if d in facts), None)
    v = (values or {}).get(doc) if doc else None
    m = _YEAR_RE.search(question or "")
    if not m or not isinstance(v, dict) or not _COUNT_DAYS_RE.search(question or ""):
        return None
    n = (v.get("by_year") or {}).get(int(m.group(1)), (v.get("by_year") or {}).get(m.group(1)))
    if n is None:
        return None
    partial = f" through {v['through']}" if int(m.group(1)) == v.get("year") else ""
    return f"{n} day{'s' if n != 1 else ''} at or above 90°F at {v['station']} in {m.group(1)}{partial}."


def answer(question: str, texts: dict[str, str], values: dict | None = None) -> tuple[str, list[str]] | None:
    """(lead, facts) for a heat question, or None when no heat source
    answered. Leads: "facts", "count", "heat_forecast", "no_prediction_heat",
    "no_score", "surface_yes", "surface_no" (synthesis.LEAD_PHRASES)."""
    from riprap.core.burr import answer_checks as ac

    q = question or ""

    def have(*groups) -> list[str]:
        return [i for g in groups for i in g if texts.get(i)]

    subjects = named(q, texts)
    # The model's estimate follows the city's map, as in a flood answer.
    subjects = sorted(subjects, key=lambda d: d in EXPERIMENTAL)
    tf = time_frame(q)
    if _SCORE_RE.search(q):
        docs = have(HVI)
        return ("no_score", docs) if docs else None
    if (_INDOORS_RE.search(q) or _DATE_RE.search(q)) and (_WILL_RE.search(q) or _NEAR_RE.search(q)):
        docs = have(FORECAST, ALERTS, SURFACE)
        return ("no_prediction_heat", docs) if docs else None
    if _DEATHS_RE.search(q):
        return "cannot_answer", have(VISITS)
    if tf == "now":
        live = have(OBS, ALERTS, FORECAST)
        if any(d in COOLING for d in subjects) and not re.search(r"\bhot\b|temp|heat index|advisor|alert|warning", q, re.I):
            # "Is the pool open today": the list of places, which holds no hours, not the weather.
            return "facts", subjects[:4]
        # What the question names leads ("is there a heat advisory right now": the alert, then the reading).
        live = sorted(live, key=lambda d: d not in subjects)
        return ("facts", [*live, *(d for d in subjects if d not in live)][:6]) if live else None
    if tf == "future":
        if _FAR_RE.search(q):
            docs = have(NPCC4)
            return ("facts", [*docs, *(d for d in subjects if d not in docs)][:4]) if docs else None
        docs = have(FORECAST, ALERTS)
        return ("heat_forecast", docs) if docs else None
    if _COUNT_DAYS_RE.search(q) or (ac.is_count_question(q) and any(d in STATION for d in subjects)):
        docs = have(STATION)
        return ("count", docs) if docs else None
    if _COMPARE_CITY_RE.search(q) and not any(d in COVER or d in HVI for d in subjects):
        docs = have(SURFACE)
        v = (values or {}).get(docs[0]) if docs else None
        if docs and isinstance(v, dict) and ac.is_yes_no_question(q) and not _THAN_ELSEWHERE_RE.search(q):
            hotter = bool(re.search(r"\b(?:hott?er|warmer)\b|heat island", q, re.I))
            if v.get("warmer_in_every_image"):
                return ("surface_yes" if hotter else "surface_no"), docs
            if v.get("cooler_in_every_image"):
                return ("surface_no" if hotter else "surface_yes"), docs
        return ("facts", [*docs, *(d for d in subjects if d not in docs)][:4]) if docs else None
    if subjects:
        return ("count" if ac.is_count_question(q) and not any(d in COOLING for d in subjects) else "facts"), subjects[:4]
    docs = have(SURFACE, HVI, ("city_landcover", "city_landcover_nta"), STATION)
    return ("facts", docs[:4]) if docs else None
