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

from riprap.core.burr.place import _STREET_WORD, _SUFFIX

# Outdoor heat. "Heath Avenue" and "heating" are not it, and neither is "hot
# water": a 311 "HEAT/HOT WATER" complaint is about a cold apartment in winter.
HEAT_RE = re.compile(
    r"\bheat(?:[- ]?waves?)?\b(?!\s*(?:and|&|/|or)\s*hot water)|\boverheat|\bhot(?:ter|test)?\b(?!\s+water)|\btemperatures?\b"
    r"|\bcooling (?:cent(?:er|re)s?|sites?)\b|\bcool (?:off|down)\b|\bspray showers?\b|\b(?:public|swimming) pools?\b"
    r"|\bswelter|\bscorch|\b(?:8[5-9]|9\d|1[01]\d)[- ]?(?:°|degrees?\b|deg\b|f\b)|\bair[- ]condition"
    r"|\bdays? (?:above|over|at or above) (?:8[5-9]|9\d|1[01]\d)\b|\b(?:cooler|coolest|warmer|warmest)\b"
    # Found by questions written without sight of these rules: "air temp", "will it be over 95", "hit 90 or
    # above", "forecast highs", "cool places", "what will summers be like".
    r"|\btemps?\b|\b(?:over|above|hit|hits|reach(?:es|ed)?|top(?:s|ped)?)\s+(?:8[5-9]|9\d|1[01]\d)f?\b|\bhighs\b"
    r"|\bcool (?:places?|spots?|spaces?)\b|\bstay(?:ing)? cool\b|\bsummers\b"
    r"|\brecord highs?\b(?!\s+(?:tide|water|surge|rain))"
    # Trees and shade are asked about for heat; paving alone stays with the flood briefing.
    r"|\b(?:tree )?canopy\b|\btree cover\b|\bstreet trees\b|\bshad(?:e|ed|y)\b"
    r"|\bsprinklers?\b|\b(?:a|the|any|nearest|closest|outdoor|indoor|city|kiddie) pools?\b|\bpools? (?:and|or|near|nearby|open)\b", re.I)
# A cold apartment: no heat, a radiator, the landlord. Not this briefing.
INDOOR_HEATING_RE = re.compile(
    r"\bheat\s*(?:and|&|/|or)\s*hot water|\bno heat\b|\bheat(?:ing)? (?:complaints?|violations?|season|is (?:off|out|broken))"
    r"|\b(?:radiators?|boilers?)\b|\bturn(?:ed|s)? (?:on|off) the heat|\bwithout heat\b|\bheat (?:in|for) (?:the )?winter", re.I)
INDOOR_HEATING = ("This reads as a question about indoor heating (no heat or hot water in a building). Riprap's heat "
                  "briefing covers outdoor summer heat only. Heating complaints go to 311 (portal.311.nyc.gov or call "
                  "311) and are enforced by the Department of Housing Preservation and Development.")

# The basketball team: "what time is the Heat game at Barclays Center".
_TEAMS = r"(?:knicks|nets|celtics|lakers|bulls|sixers|76ers|nba|playoffs?)"
# The basketball team, and "hot" as fashionable ("hottest new restaurants"). Not "hot spots": those can be heat.
# ponytail: a word list; a classifier is the upgrade if real questions keep slipping past it.
SPORT_RE = re.compile(r"\bmiami heat\b|\bheat (?:game|tickets?)\b|\bthe Heat\b(?-i:(?<=Heat))(?= (?:game|play|are|vs|beat|lost|won))"
                      rf"|\bheat\b[^.?!]*\b{_TEAMS}\b|\b{_TEAMS}\b[^.?!]*\bheat\b"
                      r"|\bhot(?:test)?\s+(?:new\s+)?(?:restaurants?|bars?|clubs?|tickets?|takes?|deals?|sauce|dogs?|tubs?|yoga|pot"
                      r"|wings|chicken|stocks?|real estate)\b", re.I)
NOT_WEATHER = ("This does not read as a question about hot weather. Riprap reports flood and heat records "
               "for New York City places, each cited to its source.")

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
    (re.compile(r"emergency (?:room|department|visits?)|\b(?:go|goes|went|going|sent|end(?:s|ed)? up) (?:to|in|at) (?:the |a )?(?:hospital|er|emergency)\b|\bhospital visits?\b|\b(?:er|ed) visits?\b|hospitali[sz]|heat (?:illness|stroke|exhaustion|stress)"
                r"|\bsick\b|\bhealth\b(?! department)", re.I), VISITS),
    (re.compile(r"vulnerab|\bhvi\b|(?<!heat )\bindex\b|\bat risk\b", re.I), HVI),
    (re.compile(r"\bheat index\b|\bfeels? like\b|\bhumid", re.I), OBS),
    (re.compile(r"\btrees?\b|canopy|\bshade|\bpaved|\bpaving|pavement|impervious|green (?:space|cover)|vegetat", re.I), COVER),
    (re.compile(r"advisor(?:y|ies)|\bwarnings?\b|\balerts?\b|\bwatch\b", re.I), ALERTS),
    (re.compile(r"\bsurface\b|landsat|satellite|heat island|hot ?spots?|\b(?:run|runs|ran|get|gets|is|are) (?:the )?hottest\b"
                r"|\bhottest (?:parts?|blocks?|areas?|places?|spots?)\b|how hot (?:does|do) .{0,40}?\bget\b", re.I), SURFACE),
    (re.compile(r"\b(?:8[5-9]|9\d|1[01]\d)[- ]?(?:°|degrees?\b|deg\b)|\bhot days?\b|\brecord\b|hottest (?:day|it)"
                r"|how hot (?:did|was|has|does|do)|\b(?:this|last) (?:summer|year)\b|so far this|scorcher|\bthe records\b|\bused to\b"
                r"|\bover the years\b|\b(?:gone|going|went) up\b|\btrend|\bincreas|\b(?:gotten|got) (?:worse|hotter|warmer)\b"
                r"|\bsince (?:19|20)\d\d\b"
                r"|\b(?:hit|reach(?:ed)?|top(?:ped)?|over|above) (?:8[5-9]|9\d|1[01]\d)\b", re.I), STATION),
)
# Heat deaths are published for the city as a whole only, so no source here holds them for a place.
_DEATHS_RE = re.compile(r"\bdeaths?\b|\bdied\b|\bmortality\b|\bfatalit", re.I)
_SCORE_RE = re.compile(r"\b(?:scores?|ratings?|rated|grades?|rank(?:ed|ing|s)?)\b|^\s*rate\b|\byou rate\b|\bon a scale\b|\bscale of \d", re.I)
# The inside of a building, or one block on a coming day: nobody forecasts that.
_INDOORS_RE = re.compile(r"\b(?:my|our|the|this) (?:apartment|unit|building|home|house|room|classroom|block|street|playground)\b"
                         r"|\bindoors?\b|\binside\b|\b(?:apartment|apt\.?) \w+\b|\bon my block\b", re.I)
# A calendar date ("on July 15", "the afternoon of 7/15"): beyond a seven-day forecast as a rule, and never forecast for one spot.
_DATE_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?\b|\b\d{1,2}/\d{1,2}\b"
                      r"|\b(?:labor|memorial|independence) day\b|\b(?:fourth|4th) of july\b|\bjuly fourth\b|\bjuneteenth\b", re.I)
_WILL_RE = re.compile(r"\b(?:will|going to|gonna|expected to|likely to)\b|\bhow hot will\b", re.I)
_TODAY_RE = re.compile(r"\b(?:today|this (?:morning|afternoon|evening)|outside now|current(?:ly)?)\b", re.I)
_NEAR_RE = re.compile(r"\b(?:tomorrow|tonight|this (?:coming )?(?:week|weekend)|next (?:week|weekend|few days|couple of days)"
                      r"|(?:next|coming) (?:\w+ )?(?:hours|days)|forecast|on (?:mon|tues|wednes|thurs|fri|satur|sun)day"
                      r"|heat ?wave (?:coming|expected|on the way))\b", re.I)
_FAR_RE = re.compile(r"\b20[3-9]\ds?\b|\b2100\b|decades?|century|climate change|projections?|projected|in the future"
                     r"|by (?:the )?(?:middle|end) of the century|\b(?:next|coming) (?:\w+ )?years\b|\bwhen my kids\b"
                     r"|\bkeep getting (?:hotter|warmer)\b", re.I)
_COUNT_DAYS_RE = re.compile(r"\bhow many\b[^.?!]*\bdays?\b|\bnumber of\b[^.?!]*\bdays?\b|\bdays? (?:above|over|at or above)\b", re.I)
# People the index and the visits file do not break out, and climate measures Table 4 does not hold.
_GROUP_RE = re.compile(r"\b(?:kids?|child(?:ren)?|infants?|bab(?:y|ies)|seniors?|elderly|older (?:adults|people|residents)|"
                       r"by age|age groups?|outdoor workers|pregnan\w+)\b", re.I)
_NOT_IN_TABLE_RE = re.compile(r"\b(?:mean|average) (?:annual |summer )?temperatures?\b|\bdegrees? (?:of )?warming\b|\bhumidity\b", re.I)
_COMPARE_CITY_RE = re.compile(r"\b(?:hott?er|warmer|cooler)\b[^.?!]*\bthan\b|\bthan (?:the )?(?:rest of the |city|average)"
                              r"|\bcompared? (?:to|with) (?:the )?(?:rest of the )?(?:city|average)|\bheat island\b"
                              r"|\b(?:hott?er|warmer|cooler) (?:here|there)\b", re.I)
# The measurement is a difference from the city's land average, so it gives a yes or no only against the city:
# "hotter than Riverdale", "than the rest of Queens" and "than usual" are other comparisons.
_CITY = r"(?:the )?(?:rest of (?:the )?)?(?:city|nyc|new york(?: city)?|citywide|average|city'?s? average|city as a whole)\b(?! of)"
_VS_CITY_RE = re.compile(rf"\bthan {_CITY}|\bcompared? (?:to|with) {_CITY}|\bheat island\b", re.I)
_HOTTER_RE = re.compile(r"\b(?:hott?er|warmer|hot|higher|above)\b|heat island", re.I)
_COOLER_RE = re.compile(r"\b(?:cooler|colder|cool|lower|below)\b", re.I)
_YEAR_RE = re.compile(r"\b((?:19|20)\d\d)\b(?!s)")
# A span of years ("since 2020", "from 2019 to 2024") is not one year.
_SPAN_RE = re.compile(r"\b(?:since|from|between|after|before|over the (?:last|past))\b", re.I)
_DEGREES_RE = re.compile(r"\b(8[5-9]|9\d|1[01]\d)\b(?!\s*(?:days?|years?|%|percent|m\b|km\b))")
# A house number is not a year or a temperature ("near 2020 Grand Concourse", "Did Sandy hit 89-11 Merrick
# Boulevard"): capitalised words up to a street word, or any words after "at" or "near". As rule_answer._HOUSE_YEAR_RE.
_HOUSE_RE = re.compile(rf"(?:(?<!\bin )(?<!\bby )(?<!\bthe )(?<!\bsince )\b\d{{1,5}}(?:-\d{{1,4}})?(?=\s+(?:(?-i:[A-Z])[\w'.]*\s+){{0,3}}?{_SUFFIX}\b)"
                       rf"|(?:(?<=\bat )|(?<=\bnear )|(?<=\baround )|(?<=\boutside ))\d{{1,5}}(?:-\d{{1,4}})?(?=\s+(?:{_STREET_WORD}\s+){{0,3}}?{_SUFFIX}\b))",
                       re.I)


def _sans_house(question: str) -> str:
    return _HOUSE_RE.sub(" ", question or "")


def hazard_of(question: str) -> str:
    """"heat" when the words are about outdoor heat and no part of the query
    is about flooding; "flood" otherwise. ("It gets hot here in the summer and
    the basement floods" is a flood question.)"""
    from riprap.core.burr import rule_answer

    q = _sans_house(question)
    if not HEAT_RE.search(q) or re.search(r"\bflood", q, re.I) or INDOOR_HEATING_RE.search(q):
        return "flood"
    # "Summers" alone is a weak heat word: beside water it is the season a street floods in.
    if all(m.group(0).lower() == "summers" for m in HEAT_RE.finditer(q)) and re.search(
            r"\b(?:water|rain\w*|storm\w*|sewer\w*|wet|damp|leak\w*|drain\w*)\b", q, re.I):
        return "flood"
    # A preamble about the heat before a question about a flood record is a flood question, and so is a clause
    # that names a flood source beside a heat word ("a hot spot for sewer backups"). Harbor is in place names.
    if any(rule_answer.names_flood(re.sub(r"\bharbor\b", " ", c, flags=re.I) if HEAT_RE.search(c) else c)
           for c in rule_answer._clauses(q)):
        return "flood"
    return "heat"


def asks_something(text: str) -> bool:
    """Words beside a place that ask a heat question ("QN12 heat
    vulnerability index"). "Heat", "extreme heat" or "heat risk" alone ask
    for the heat briefing."""
    t = text or ""
    return bool(any(p.search(t) for p, _ in TOPICS) or _TODAY_RE.search(t) or _NEAR_RE.search(t) or _FAR_RE.search(t) or _RANK_RE.search(t) or _DEATHS_RE.search(t) or _GROUP_RE.search(t)
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

    q = _sans_house(question)
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
    question = _sans_house(question)
    m = _YEAR_RE.search(question)
    if not m or not isinstance(v, dict) or _COUNT_DAYS_RE.search(question) or _DATE_RE.search(question) or _SPAN_RE.search(question) \
            or not re.search(r"how hot|hottest|highest|record", question, re.I):
        return None
    peak = (v.get("max_by_year") or {}).get(int(m.group(1)), (v.get("max_by_year") or {}).get(m.group(1)))
    return f"The highest reading at {v['station']} in {m.group(1)} was {peak[0]}°F on {peak[1]}." if peak else None


def record_sentence(question: str, facts: list[str], values: dict | None) -> str | None:
    """For "the hottest day on record": the station's all-time record, as the lead."""
    doc = next((d for d in STATION if d in facts), None)
    v = (values or {}).get(doc) if doc else None
    if not isinstance(v, dict) or not v.get("record_f") or not re.search(r"\brecord\b|\ball[- ]time\b|\bever\b", question or "", re.I) \
            or re.search(r"\b(?:low|lowest|cold|coldest|coolest|tide|rain\w*|snow\w*)\b", question or "", re.I):
        return None  # the record held here is the highest temperature
    return (f"The record at {v['station']} is {v['record_f']}°F, set on {v['record_date']} (records from "
            f"{v['record_since']}).")


_TREND_RE = re.compile(r"\bover the years\b|\b(?:gone|going|went) up\b|\btrend|\bincreas|\bmore\b[^.?!]*\b(?:than|now)\b"
                       r"|\bused to\b|\bthe records\b|\b(?:gotten|getting|got) (?:worse|hotter|warmer)\b|\bsince (?:19|20)\d\d\b", re.I)


def trend_sentence(question: str, facts: list[str], values: dict | None) -> str | None:
    """For "have 90 degree days gone up over the years": the station's own
    yearly counts as decade averages, as the lead. The sentence about this
    year and last says nothing about a trend."""
    doc = facts[0] if facts and facts[0] in STATION else None  # only when the station record is what was asked about
    v = (values or {}).get(doc) if doc else None
    if not isinstance(v, dict) or not _TREND_RE.search(question or ""):
        return None
    by_year = {int(y): n for y, n in (v.get("by_year") or {}).items() if int(y) != v.get("year")}  # whole years only
    spans = [(a, b) for a, b in ((1991, 2000), (2001, 2010), (2011, 2020), (2021, max(by_year, default=0)))
             if all(y in by_year for y in range(a, b + 1)) and b >= a]
    if len(spans) < 3:
        return None
    parts = [f"{sum(by_year[y] for y in range(a, b + 1)) / (b - a + 1):.1f} in {a} to {b}" for a, b in spans]
    return (f"At {v['station']} the yearly count of days at or above 90°F averaged {', '.join(parts[:-1])} and "
            f"{parts[-1]} [{doc}].")


def count_sentence(question: str, facts: list[str], values: dict | None) -> str | None:
    """For "how many days reached 90 in 2023": that year's count from the
    station's own yearly record, as the count lead. None when the question
    names no year the record holds (the station sentence then answers)."""
    doc = next((d for d in STATION if d in facts), None)
    v = (values or {}).get(doc) if doc else None
    question = _sans_house(question)
    m = _YEAR_RE.search(question)
    if not m and isinstance(v, dict) and v.get("year"):  # "this year", "last year": the station record's own years
        rel = re.search(r"\b(this|last) (?:year|summer)\b|\bso far\b", question, re.I)
        m = rel and re.match(r"(\d+)", str(v["year"] - (1 if (rel.group(1) or "").lower() == "last" else 0)))
    if not m or not isinstance(v, dict) or not _COUNT_DAYS_RE.search(question) or _SPAN_RE.search(question):
        return None
    # The record counts days at 90°F or above: a question about 95 or 100 is not answered by that count.
    if any(t != "90" for t in _DEGREES_RE.findall(_YEAR_RE.sub(" ", question))):
        return None
    n = (v.get("by_year") or {}).get(int(m.group(1)), (v.get("by_year") or {}).get(m.group(1)))
    if n is None:
        return None
    partial = f" through {v['through']}" if int(m.group(1)) == v.get("year") else ""
    return f"{n} day{'s' if n != 1 else ''} at or above 90°F at {v['station']} in {m.group(1)}{partial}."


_ALERTS_AT = next(i for i, (_, ids) in enumerate(TOPICS) if ids == ALERTS)
_PARTS = r"(?:parts?|areas?|neighbou?rhoods?|blocks?|districts?|streets?|places?)"
_RANK_RE = re.compile(rf"\b(?:which|what)\s+(?:community\s+)?{_PARTS}\b|\brank\b|\btop (?:five|ten|\d+)\b|\b(?:hottest|coolest|worst|most vulnerable)\s+{_PARTS}\b"
                      r"|\bwhere\b[^?.]*\b(?:hottest|coolest|worst|most)\b", re.I)


_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")[a-z]*\b", re.I)


def _beyond_forecast(q: str, today=None) -> bool:
    """The question names a time the 7-day forecast cannot reach: next summer
    or next year, or a month that is neither this one nor the next."""
    from datetime import date

    if _NEAR_RE.search(q):
        return False
    if re.search(r"\bnext (?:summer|year)\b|\b(?:labor|memorial|independence) day\b|\b(?:fourth|4th) of july\b|\bjuly fourth\b", q, re.I):
        return True
    now = (today or date.today()).month
    named = {_MONTHS.index(m.group(1).lower()[:3]) + 1 for m in _MONTH_RE.finditer(q) if m.group(1).lower() != "may" or re.search(r"\bin may\b|\bmay \d", q, re.I)}
    return bool(named) and not named & {now, now % 12 + 1}


def places_named(question: str) -> list[str]:
    """The neighbourhoods a question names, when it names more than one
    tabulation area and is neither a comparison nor about a street address:
    the answer covers one, and says so."""
    from riprap.core.burr.intake import _heat_compare  # noqa: PLC0415
    from riprap.core.burr.place import (  # noqa: PLC0415
        extract_address,
    )

    q = question or ""
    if extract_address(q) or _heat_compare(q):
        return []
    names = neighbourhoods_in(q)
    return names if len(names) > 1 else []


def neighbourhoods_in(question: str) -> list[str]:
    """The distinct tabulation areas a question names, by the name it uses, in order."""
    from app.areas import nta  # noqa: PLC0415
    from riprap.core.burr.place import _LANDMARK, _known_neighbourhoods  # noqa: PLC0415

    low, found = (question or "").lower(), {}
    # A hyphenated name is one place ("Bedford-Stuyvesant" was once reported as Bedford and Stuyvesant).
    whole = {re.sub(r"\s*\(.*?\)", "", n).strip().lower() for n in nta.load()["ntaname"].dropna() if "-" in n}
    whole |= {w.replace("-", " ") for w in whole}
    for n in sorted({*whole, *_known_neighbourhoods()}, key=len, reverse=True):
        m = re.search(rf"\b{re.escape(n)}\b(?!\s+(?:{_SUFFIX}|{_LANDMARK})\b)", low)
        if m and not any(m.start() >= v[0] and m.end() <= v[1] for v in found.values()) and (hits := nta.resolve(n)):
            found[n] = (m.start(), m.end(), hits[0]["nta_code"])
    spans = {}
    for n, (_, _, code) in sorted(found.items(), key=lambda kv: kv[1][0]):
        spans.setdefault(code, n.title())
    return list(spans.values())


def answer(question: str, texts: dict[str, str], values: dict | None = None) -> tuple[str, list[str]] | None:
    """(lead, facts) for a heat question, or None when no heat source
    answered. Leads: "facts", "count", "heat_forecast", "no_prediction_heat",
    "no_score", "no_ranking", "surface_yes", "surface_no" (synthesis.LEAD_PHRASES)."""
    from riprap.core.burr import answer_checks as ac

    q = _sans_house(question)

    def have(*groups) -> list[str]:
        return [i for g in groups for i in g if texts.get(i)]

    subjects = named(q, texts)
    # The model's estimate follows the city's map, as in a flood answer.
    subjects = sorted(subjects, key=lambda d: d in EXPERIMENTAL)
    tf = time_frame(q)
    if _SCORE_RE.search(q):
        if docs := have(HVI):
            return "no_score", docs
        if not _RANK_RE.search(q):
            return None  # a score asked where the index did not answer: nothing is quoted in its place
    # ("My kids will inherit our house. How many more heat waves in the coming decades?" asks for the projection.)
    if (_INDOORS_RE.search(q) or _DATE_RE.search(q)) and (_WILL_RE.search(q) or _NEAR_RE.search(q)) and not (
            _FAR_RE.search(q) and not _DATE_RE.search(q)):
        if _beyond_forecast(q) and (docs := have(SURFACE, STATION)):
            return "no_prediction_far", docs  # this week's forecast says nothing about next July
        docs = have(FORECAST, ALERTS, SURFACE)
        return ("no_prediction_heat", docs) if docs else None
    if _DEATHS_RE.search(q):
        return "no_deaths", have(VISITS)
    # Things no source here holds, said plainly, with the nearest record after: hospital admissions, visits in a
    # year outside the file's period, and whether a difference is significant (the file prints no intervals).
    period = next((re.findall(r"\d{4}", str(v.get("period") or "")) for d in VISITS
                   if isinstance(v := (values or {}).get(d), dict)), [])
    from riprap.core.burr.rule_answer import _clauses  # noqa: PLC0415

    # (In one clause: "my clients are seniors. How vulnerable is the district?" asks about the district.)
    if any(_GROUP_RE.search(c) and re.search(r"risk|vulnerab|affect|danger|visits?|hospital|\bsick\b", c, re.I)
           and not re.search(r"\b(?:my|our) (?:kids?|children|clients)\b", c, re.I) for c in _clauses(q)) and (
            docs := have(HVI, VISITS)):
        return "cannot_answer", docs  # the index and the visits are for all residents: nothing here is by age or group
    if _NOT_IN_TABLE_RE.search(q) and (docs := have(NPCC4, STATION)):
        return "cannot_answer", docs[:2]
    if re.search(r"\bat night\b|\bnight[- ]?time\b|\bovernight\b|\bindoors?\b|\binside\b", q, re.I):
        # Landsat passes in the late morning and the stations report daily highs: nothing here is a night or an
        # indoor reading.
        return "cannot_answer", have(STATION, SURFACE)[:2]
    if re.search(r"hospitali[sz]|\badmissions?\b|\bsignifican|\bconfidence\b|margin of error|\bstatistical", q, re.I) or (
            any(d in VISITS for d in subjects) and (_TREND_RE.search(q) or any(
                len(period) == 2 and not int(period[0]) <= int(y) <= int(period[1]) for y in _YEAR_RE.findall(q)))):
        # (The visits file is one five-year total: no year in it, and no trend.)
        return "cannot_answer", (have(VISITS) or subjects or have(HVI, STATION))[:4]
    if re.search(r"cooling cent", q, re.I) and all(d in COOLING for d in subjects) and (docs := have(COOLING)):
        return "cooling_centers", docs  # asked alone; beside other things it is one of the facts
    if TOPICS[_ALERTS_AT][0].search(q) and (not have(ALERTS) or _YEAR_RE.search(q) or re.search(r"\bhow many\b|\bwere\b|\blast (?:summer|year)\b", q, re.I)):
        # The alert source did not answer, or the question is about past alerts, which no source here holds:
        # "no active advisory" must not stand as the answer to either.
        return "cannot_answer", have(ALERTS, OBS, FORECAST)
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
        # The record counts days at 90°F: a question about 95 or 100 is told it is not answered, then given that.
        other = any(t != "90" for t in _DEGREES_RE.findall(_YEAR_RE.sub(" ", q)))
        return (("cannot_answer" if other else "count"), docs) if docs else None
    if _COMPARE_CITY_RE.search(q) and not any(d in COVER or d in HVI for d in subjects):
        docs = have(SURFACE)
        v = (values or {}).get(docs[0]) if docs else None
        hotter, cooler = bool(_HOTTER_RE.search(q)), bool(_COOLER_RE.search(q))
        if docs and isinstance(v, dict) and ac.is_yes_no_question(q) and _VS_CITY_RE.search(q) and hotter != cooler:
            if v.get("warmer_in_every_image"):
                return ("surface_yes" if hotter else "surface_no"), docs
            if v.get("cooler_in_every_image"):
                return ("surface_no" if hotter else "surface_yes"), docs
        return ("facts", [*docs, *(d for d in subjects if d not in docs)][:4]) if docs else None
    # "Which parts of the Bronx ...", "the hottest block in ...": the record for the place, said to be no ranking.
    facts = "no_ranking" if _RANK_RE.search(q) else "facts"
    if subjects:
        return ("count" if ac.is_count_question(q) and not any(d in COOLING or d in COVER for d in subjects) else facts), subjects[:4]
    docs = have(SURFACE, HVI, ("city_landcover", "city_landcover_nta"), STATION)
    return (facts, docs[:4]) if docs else None
