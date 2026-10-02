"""Intake — the first step of every briefing run.

  plan          -> the LLM planner (plan_intent) or the regex planner
                   (plan_heuristic). Writes `plan`, `intent` and the first
                   target string.
  geocode       -> point intents: resolve the target to lat/lon.
  resolve_area  -> neighbourhood intents: resolve the target to an NTA
                   polygon.

Branching:
  - If `plan.intent == "not_implemented"`, downstream Stones are skipped
    (the top-level Application's transitions wire that branch).
  - If `geocode` fails (no match), Stones still get to run with
    lat=lon=None; each pebble action degrades to its `no coords` trace
    record. The reconciler can still produce a "we couldn't locate this
    address" briefing.

Intake is a couple of small actions, not a sub-Application — the two
steps don't have internal state cycling, so the extra wrapping wouldn't
buy us anything.
"""
from __future__ import annotations

import re
import time
from typing import Any

from burr.core import State, action

from riprap.core.burr import heat_answer
from riprap.core.burr.pebble import trace_rec_for
from riprap.core.burr.place import (
    _NAMED_PLACE_RE,
    ELSEWHERE_RE,
    extract_address,
    geocode_matches,
    landmark_phrase,
    resolve_query,
)
from riprap.core.burr.rule_answer import (  # one definition of "now"
    _clauses,
    asks_now,
    recognised,
)

# Trailing risk phrases ("... at risk of flooding?", "... flood risk").
_TRAILING_RE = re.compile(
    r"[\s,]*(?:at\s+risk(?:\s+(?:of|for))?(?:\s+(?:flooding|flood|flooded))?"
    r"|flood(?:ing|ed)?(?:\s+(?:risk|exposure|hazard))?"
    r"|(?:extreme\s+)?heat(?:\s+(?:risk|exposure|hazard|briefing))?"
    r"|hazard\s+exposure)\s*\??\s*$",
    re.IGNORECASE,
)
# Leading clause that ends in a preposition and contains a risk/ask trigger,
# e.g. "flood risk at ", "what's the flood risk for ", "briefing on ".
_LEADIN_PREP_RE = re.compile(
    r"^.*?\b(?:flood(?:ing)?|heat|risk|hazard|briefing|report|exposure"
    r"|assess(?:ment)?)\b[^,\d]*?\b(?:at|for|near|of|in|on|around)\s+",
    re.IGNORECASE,
)
# Leading question / imperative filler words ("is ", "what's ", "show me ").
_LEADIN_WORDS_RE = re.compile(
    r"^(?:please\s+|can\s+you\s+|could\s+you\s+|"
    r"(?:what'?s?|what\s+is|how|is|are|show(?:\s+me)?|tell\s+me(?:\s+about)?"
    r"|give\s+me|get\s+me|find|look\s*up|check|assess)\b\s*)+",
    re.IGNORECASE,
)


def _address_from_query(query: str) -> str:
    """Pull the geocodable address out of a natural-language query.

    The LLM planner does this implicitly; the heuristic planner must do it
    explicitly or Nominatim chokes on "flood risk at 250 Broadway". Strips a
    leading lead-in clause and trailing risk phrases, conservatively — when
    nothing matches (a bare address or neighborhood), the input is returned
    unchanged.
    """
    orig = (query or "").strip()
    s = _TRAILING_RE.sub("", orig).strip()
    m = _LEADIN_PREP_RE.match(s)
    if m and s[m.end():].strip(" ,"):
        s = s[m.end():].strip(" ,")
    else:
        stripped = _LEADIN_WORDS_RE.sub("", s).strip(" ,")
        if stripped:
            s = stripped
    return s.rstrip(" ?") or orig


_COMPARE_RE = re.compile(r"^\s*compare\s+(.+?)\s+(?:to|with|and|vs\.?|versus)\s+(.+?)\s*\??$"
                         r"|^(.+?)\s+(?:vs\.?|versus)\s+(.+?)\s*\??$", re.IGNORECASE)
# Construction, not "NYCHA developments" or "buildings in the floodplain":
# those once got building permits for an answer.
_DEVELOPMENT_RE = re.compile(r"\b(construction|permits?|being built|new (buildings?|developments?)|projects? underway)\b",
                             re.IGNORECASE)
# An address that ends in another state's code ("..., San Francisco, CA"): the
# NYC address span would drop the city ("1 Dr", "1 Civic Plaza"), so the whole
# address is geocoded and routed to its deployment, or to none.
_OTHER_STATE_RE = re.compile(
    r",\s*(?!NY\b)(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMV]|O[HKR]|PA|RI|S[CD]"
    r"|T[NX]|UT|V[AT]|W[AIVY])\.?(?:\s+\d{5})?\s*\??\s*$")
_OUT_OF_SCOPE_RE = re.compile(r"\b(should (i|we) (buy|rent|sell|move|live|stay|evacuate|leave|take|sign|lease|avoid|pass)"
                              r"|(is|would) it (be )?safe\b|safe to (buy|rent|live|stay|move|park)|worth (buying|renting)"
                              r"|risk (is )?too (high|great|much)|too (risky|dangerous) to"
                              r"|good idea to (rent|buy|live|move|sign)"
                              r"|insurance (cost|premium|price|rate)(?! map)|cost me|sue (the|my|our|a|an|him|her|them)|lawsuit|lawyer|mortgage)\b", re.IGNORECASE)
NO_PLACE_NOW = ("Riprap reads the records for one place at a time, and this question names none. For what is "
                "flooding across the city right now, use the FloodNet sensor dashboard (dataviz.floodnet.nyc); "
                "official warnings come from the National Weather Service (weather.gov/okx) and Notify NYC. "
                "Add an address or a neighbourhood to get the readings near it.")
NO_PLACE_HEAT = ("Riprap reads the records for one place at a time, and this question names none it could find. "
                 "Add a street address, a neighbourhood, a community district such as QN12, or a borough. Official "
                 "heat warnings for the whole city come from the National Weather Service (weather.gov/okx) and "
                 "Notify NYC.")
_WIDE_AREA_RE = re.compile(r"\b(?:(the bronx|bronx)|(brooklyn)|(manhattan)|(queens)|(staten island)"
                           r"|(nyc|new york city|the city|citywide|city-wide|the five boroughs))\b", re.IGNORECASE)
_WIDE_CODES = ("BX", "BK", "MN", "QN", "SI", "NYC")


def _wide_area(q: str) -> str | None:
    """The borough a heat question names, or NYC for the whole city, when it
    names exactly one: a heat question about the Bronx is answered for the
    Bronx (the forecast, the alerts, the surface mean, the station), where
    a flood question needs a place."""
    named = {code for m in _WIDE_AREA_RE.finditer(q or "") for code, g in zip(_WIDE_CODES, m.groups(), strict=True) if g}
    boroughs = named - {"NYC"}
    return next(iter(boroughs)) if len(boroughs) == 1 else "NYC" if named == {"NYC"} else None


# "Is Mott Haven hotter than Riverdale?", "compare heat vulnerability BK16 vs BK06", "Corona vs Forest Hills, ...".
_HEAT_COMPARE_RE = re.compile(
    r"^\W*(?:is|are|was|were)\s+(?:it\s+)?(.+?)\s+(?:any\s+|much\s+)?(?:hott?er|warmer|cooler|more [\w ]+?|less [\w ]+?)\s+than\s+(.+?)\s*[?.,]"
    r"|^\W*compare\s+(?:the\s+)?(?:[a-z ]+?\s+)?(.+?)\s+(?:to|with|and|vs\.?|versus)\s+(.+?)\s*(?:[?.,]|$)"
    r"|^\W*(.+?)\s+(?:vs\.?|versus)\s+(.+?)\s*(?:[?.,]|$)", re.IGNORECASE)


def _heat_compare(q: str) -> list[dict] | None:
    """Two places a heat question sets side by side, each as a target, or
    None when it names fewer than two (or the second is the city itself)."""
    from app.areas import nta  # noqa: PLC0415

    m = _HEAT_COMPARE_RE.match(q + ("" if q.rstrip().endswith(("?", ".", ",")) else "?"))
    if not m:
        return None
    targets = []
    for words in (g for g in m.groups() if g):
        if re.search(r"\b(rest of|the city|average|nyc|new york city|citywide)\b", words, re.IGNORECASE):
            return None
        place = resolve_query(words)
        if place["kind"] == "district":
            targets.append({"type": "district", "text": place["text"]})
        elif place["kind"] == "address":
            targets.append({"type": "address", "text": _with_borough(place["text"], words)})
        elif place["kind"] == "neighborhood" and nta.resolve(place["text"]):
            targets.append({"type": "nta", "text": place["text"]})
        elif place["kind"] == "neighborhood":
            targets.append({"type": "address", "text": f"{place['text']}, New York, NY"})
        else:
            return None
    return targets if len(targets) == 2 and targets[0]["text"].lower() != targets[1]["text"].lower() else None


# A forecast for a named future day or date ("Will X flood next Tuesday?").
# Needs a future word, so "Did it flood on Monday?" stays a history question.
_FUTURE_DAY_RE = re.compile(
    r"\b(will|going to|gonna|expected to|likely to|forecast)\b.*\b(tomorrow|next (monday|tuesday|wednesday"
    r"|thursday|friday|saturday|sunday|week|weekend|month|year)|this (coming )?(monday|tuesday|wednesday"
    r"|thursday|friday|saturday|sunday|weekend)|on (monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|on (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}|\d{1,2}/\d{1,2}(/\d{2,4})?)\b",
    re.IGNORECASE)
# A question about forecasts, projections or what is coming. A named future
# day is refused first (_FUTURE_DAY_RE); this is the rest (refactor 8).
_FORECAST_Q_RE = re.compile(
    r"\b(forecasts?|forecasting|projections?|projected|outlook|predictions?|what is coming|what's coming"
    r"|in the (coming|next) (years|decades)|in the future|by 20\d\d)\b", re.IGNORECASE)


# A sentence that asks something, as opposed to a place typed alone.
_QUESTION_RE = re.compile(r"\?\s*$|^\W*(is|are|was|were|has|have|had|do|does|did|can|could|will|would|should|what|which"
                          r"|where|when|why|who|how)\b", re.IGNORECASE)


def forecast_question(query: str) -> bool:
    """A question about forecasts or projections, not about now or the past.
    It plans as a point (or area) question with focus time_frame future, so
    the Lodestone's forecast pebbles run; never as live_now."""
    return bool(_FORECAST_Q_RE.search(query or "")) and not _FUTURE_DAY_RE.search(query or "")


_OTHER_HAZARD_RE = {"air": re.compile(r"\b(air quality|aqi|air pollution|smog|pm ?2\.5|ozone(?! park))\b", re.I)}
# Advice about heat: what to do, whether it is safe, what is wrong with someone.
_HEAT_ADVICE_RE = re.compile(
    r"\b(?:bad|good|smart|wise|dumb|terrible) idea\b|\bthinking (?:of|about) (?:renting|buying|moving)\b"
    r"|\bshould (i|we|my \w+)\b|\bis it (too hot|ok|okay) to\b|\bcan (i|we|my \w+) (go|run|walk|exercise|work|play|leave)\b"
    r"|\bsymptoms?\b|\bwhat (should|do) (i|we) do\b|\bhow (do|can|should) (i|we) (stay|keep|treat|protect|cool)\b"
    # Found by a reviewer: advice asked without "should I".
    r"|\btoo hot (?:for|to)\b|\bprecautions?\b|\brecommend|\bdo (?:i|we) need\b|\bis it safe\b|\bsafe (?:to|for)\b"
    r"|\bwhat should (?:\w+ ){1,4}(?:do|take)\b", re.I)


_BOROUGH_WORDS = {"manhattan": "Manhattan", "brooklyn": "Brooklyn", "queens": "Queens", "bronx": "Bronx",
                  "staten island": "Staten Island"}


def _with_borough(span: str, query: str) -> str:
    """The address span with its borough, when the span lacks one and the
    query says or implies it: the geocoder cannot place "90-01 183rd St,
    Hollis" and puts a bare "200 Water Street" in Brooklyn. In order: a
    neighbourhood named with the address, "in <borough>" elsewhere in the
    query, a Queens-style hyphenated house number. A span that already
    carries a borough, a ZIP or "New York" is left as written."""
    from app.areas import nta  # noqa: PLC0415

    low = span.lower()
    if any(b in low for b in _BOROUGH_WORDS) or re.search(r"\b\d{5}\b|\b(new york|ny|nyc)\b", low):
        return span
    for area in [p.strip() for p in span.split(",")[1:] if p.strip()]:
        hits = nta.resolve(area)
        # The resolver matches substrings ("NY" finds Sunnyside): the part must be a whole word of the name.
        if hits and re.search(rf"\b{re.escape(area)}\b", hits[0]["nta_name"], re.IGNORECASE):
            return f"{span}, {hits[0]['borough']}"
    named = [full for word, full in _BOROUGH_WORDS.items()
             if re.search(rf"\bin (?:the )?{word}\b", query, re.IGNORECASE)]
    if len(named) == 1:
        return f"{span}, {named[0]}"
    if re.match(r"\s*\d+-\d+\s", span):
        return f"{span}, Queens"
    # A neighbourhood named elsewhere in the question ("... for Central Harlem near Harlem Hospital (506 Lenox
    # Avenue)"): its borough, when every area of that name is in one borough.
    from riprap.core.burr.place import _known_neighbourhoods  # noqa: PLC0415

    rest = query.replace(span.split(",")[0], " ").lower()
    near = max((n for n in _known_neighbourhoods() if re.search(rf"\b{re.escape(n)}\b", rest)), key=len, default=None)
    boroughs = {h["borough"] for h in nta.resolve(near)} if near else set()
    return f"{span}, {next(iter(boroughs))}" if len(boroughs) == 1 else span


def _names_a_place(query: str) -> bool:
    """A street address, a district, or a neighbourhood the city knows
    (a capitalised "Tuesday" is not one)."""
    from app.areas import nta  # noqa: PLC0415

    place = resolve_query(query)
    return place["kind"] in ("address", "district") or (place["kind"] == "neighborhood" and bool(nta.resolve(place["text"])))


def heuristic_plan(query: str) -> dict:
    """LLM-free intent routing, so no-LLM mode needs no model at all.

      "compare A to B" / "A vs B"           -> compare, two address targets
      "right now", "tonight", ...            -> live_now
      "construction", "permits", ...         -> development_check (an NTA)
      no house number and names an NTA       -> neighborhood
      anything else                          -> single_address
    """
    q = (query or "").strip()
    if heat_answer.INDOOR_HEATING_RE.search(q) and not re.search(r"\bflood", q, re.IGNORECASE):
        return {"intent": "not_implemented", "rationale": heat_answer.INDOOR_HEATING, "targets": []}
    if heat_answer.SPORT_RE.search(q):
        return {"intent": "not_implemented", "rationale": heat_answer.NOT_WEATHER, "targets": []}
    hazard = heat_answer.hazard_of(q)
    plan = _plan_for(q, hazard)
    if hazard == "heat" and plan["intent"] != "not_implemented":
        # The focus the heat sources are chosen by; the time frame comes from the heat rules.
        plan["focus"] = {"hazard": "heat", "time_frame": heat_answer.time_frame(q), "assets": []}
    return plan


def _plan_for(q: str, hazard: str) -> dict:
    """The plan for a query whose hazard is known (see heuristic_plan)."""
    from app.areas import nta  # noqa: PLC0415
    from app.planner import _not_implemented_message  # noqa: PLC0415

    heat = hazard == "heat"
    # A named future day is a prediction, declined as one ("Will it flood on
    # October 15" was once told Riprap cannot reconstruct a past date).
    msg = None if _FUTURE_DAY_RE.search(q) or heat else _not_implemented_message(q)
    if msg:
        return {"intent": "not_implemented", "rationale": msg, "targets": []}
    for other, pattern in _OTHER_HAZARD_RE.items():
        # ("It was smoggy last summer. Was it inside the Sandy zone?": another sentence asks about flooding.)
        if pattern.search(q) and not heat and not re.search(r"\bflood", q, re.IGNORECASE) and not any(
                recognised(c) for c in _clauses(q) if not pattern.search(c)):
            return {"intent": "out_of_scope", "rationale": f"Heuristic match: {other} question.",
                    "focus": {"hazard": other, "time_frame": "any", "assets": []},
                    "targets": [{"type": "address", "text": _address_from_query(q)}]}
    # A prediction for a named day with no place has nothing to answer with;
    # with a place, the rules decline the prediction and quote what is
    # forecast and mapped there (rule_answer: no_prediction).
    if _OUT_OF_SCOPE_RE.search(q) or (heat and _HEAT_ADVICE_RE.search(q)) or (
            not heat and _FUTURE_DAY_RE.search(q) and not _names_a_place(q)):
        return {"intent": "out_of_scope", "rationale": "Heuristic match: out of scope.",
                "focus": {"hazard": hazard, "time_frame": "any", "assets": []},
                "targets": [{"type": "address", "text": _address_from_query(q)}]}
    if heat and (pair := _heat_compare(q)):
        return {"intent": "compare", "rationale": "Heuristic match: compare.", "targets": pair}
    m = None if heat else _COMPARE_RE.match(q)
    # A comparison of two addresses. "Compare the current and 2080 flood maps
    # at 89-11 Merrick Boulevard" names one place and was once briefed as a
    # building called The Current in New Jersey.
    if m and all(extract_address(g) or nta.resolve(g.strip(" ?.")) for g in m.groups() if g):
        a, b = (g for g in m.groups() if g)
        return {"intent": "compare", "rationale": "Heuristic match: compare.",
                "targets": [{"type": "address", "text": _address_from_query(a)},
                            {"type": "address", "text": _address_from_query(b)}]}
    # Find the place from the words that name it (riprap/core/burr/place.py):
    # a community district, then a street address, then a short place
    # phrase. Never the whole question: that is how "... Queens ..." once
    # resolved to Astoria.
    place = resolve_query(q)
    if place["kind"] == "invalid":
        return {"intent": "not_implemented", "rationale": place["message"], "targets": [], "place": place}
    area_intent = "development_check" if _DEVELOPMENT_RE.search(q) else "neighborhood"
    if place["kind"] == "district":
        return {"intent": area_intent, "rationale": f"Heuristic match: community district {place['text']}.",
                "targets": [{"type": "district", "text": place["text"]}], "place": place}
    # A heat question never narrows to the live sources: the baked records answer in a tenth of a second, and
    # "is the pool open today" needs the list of pools, which is not a live source. The rules pick the facts.
    live = not heat and asks_now(q) and not forecast_question(q) and not _FUTURE_DAY_RE.search(q)
    if heat and place["kind"] is None:
        # No address, district, neighbourhood or named building. A borough or the
        # city is a place for a heat question; a question with none is told so
        # (the whole question once went to the geocoder and came back as a
        # Weather Service office in Albany).
        if scope := _wide_area(q):
            return {"intent": "neighborhood", "rationale": f"Heuristic match: {scope}.",
                    "targets": [{"type": "nta", "text": scope}], "place": place}
        # Nothing left once the heat words are gone ("heat", "extreme heat"): the word alone was once
        # geocoded to a heat-treating works in Brooklyn and briefed.
        bare = re.sub(r"\b(?:extreme|excessive|briefing|risk|exposure|hazard|profile|report|summer|the|in|at|for|of|on|an?)\b",
                      " ", heat_answer.HEAT_RE.sub(" ", _address_from_query(q)), flags=re.IGNORECASE).strip(" ,.?!")
        if not bare or (_QUESTION_RE.search(q) and not landmark_phrase(q)):
            return {"intent": "not_implemented", "rationale": NO_PLACE_HEAT, "targets": [], "place": place}
    # Only when the rest of the name is a direction: "Staten Island Mall" and "Bronx Zoo" are landmarks for the
    # geocoder (the mall once got the borough's reading, 13°F cooler than its own).
    if heat and place["kind"] == "neighborhood" and not nta.resolve(place["text"]) and _WIDE_AREA_RE.search(place["text"]) \
            and not re.sub(r"\b(?:the|north|south|east|west|shore|side|central|upper|lower|mid|downtown|uptown|end|of)\b|\W", "",
                           _WIDE_AREA_RE.sub("", place["text"]), flags=re.I) \
            and (scope := _wide_area(q)):
        # "Staten Island North Shore" is no tabulation area's name: the borough it names is the place.
        return {"intent": "neighborhood", "rationale": f"Heuristic match: {scope}.",
                "targets": [{"type": "nta", "text": scope}], "place": place}
    # Another city or state named in the question ("Pike Place Market in Seattle").
    elsewhere = ELSEWHERE_RE.search(q) if place["text"] and not ELSEWHERE_RE.search(place["text"]) else None
    if place["kind"] == "address":
        target = _address_from_query(q) if _OTHER_STATE_RE.search(q) else _with_borough(place["text"], q)
        intent = "live_now" if live else "single_address"
    elif live and place["kind"] == "neighborhood" and (hits := nta.resolve(place["text"])):
        # "Broad Channel high tide tonight": the live sources read at a point,
        # so the neighbourhood by name, for the geocoder (it was City Hall).
        intent, target = "live_now", f"{place['text']}, {hits[0]['borough']}, NY"
    elif live and place["kind"] is None and not ELSEWHERE_RE.search(q) and (mark := landmark_phrase(q)):
        intent, target = "live_now", f"{mark}, New York, NY"  # the geocoder decides
    elif live and place["kind"] is None:
        # "What is flooding right now" names no place, and Riprap reads one
        # place at a time: say where the citywide picture is (it was once
        # answered for City Hall, with "no sensors within 600 m").
        return {"intent": "not_implemented", "rationale": NO_PLACE_NOW, "targets": [], "place": place}
    elif live:
        # A place by name: the geocoder decides, in the city the question names.
        intent, target = "live_now", f"{place['text']}, {elsewhere.group(0).title() if elsewhere else 'New York, NY'}"
    elif place["kind"] == "neighborhood" and (hits := nta.resolve(place["text"])):
        # "Murray Hill in Queens": the borough picks among areas of one name.
        boro = re.search(re.escape(place["text"]) + r"\s*,?\s*(?:in\s+)?(?:the\s+)?(Manhattan|Brooklyn|Queens|Bronx|Staten Island)\b",
                         q, re.IGNORECASE)
        named_in = boro and boro.group(1).title() in {h["borough"] for h in hits}
        intent, target = area_intent, f"{place['text']}, {boro.group(1).title()}" if named_in else place["text"]
    else:
        # A landmark or anything else: the whole place text, so "Ferry
        # Building, San Francisco" keeps its city; the geocoder decides, and
        # fails honestly.
        named = place["kind"] == "neighborhood" and re.search(
            re.escape(place["text"]) + r"\s*,?\s*(?:in\s+)?(?:the\s+)?(Manhattan|Brooklyn|Queens|Bronx|Staten Island)\b", q)
        # "Hamilton Beach, Queens. Two things: ...": the place and its borough, not the whole question.
        if named:
            target = f"{place['text']}, {named.group(1)}, NY"
        elif place["kind"] == "neighborhood" and elsewhere and not _OTHER_STATE_RE.search(q):
            target = f"{place['text']}, {elsewhere.group(0).title()}"
        elif place["kind"] is None and not ELSEWHERE_RE.search(q) and (mark := landmark_phrase(q)):
            target = f"{mark}, New York, NY"  # "is jamaica hospital flooding right now": the landmark, for the geocoder
        elif place["kind"] == "neighborhood" and not _OTHER_STATE_RE.search(q) and (
                _QUESTION_RE.search(q) or (heat and _NAMED_PLACE_RE.search(place["text"]))):
            # A place name inside a question ("Did Hamilton Beach flood during Sandy and ...", "Does
            # Rockaway Boulevard flood?"): the name for the geocoder, never the rest of the sentence.
            target = f"{place['text']}, New York, NY"
        else:
            target = _address_from_query(q)
        intent = "single_address"
    kind = "nta" if intent in ("neighborhood", "development_check") else "address"
    out = {"intent": intent, "rationale": f"Heuristic match: {intent}.",
           "targets": [{"type": kind, "text": target}], "place": place}
    if not heat and (forecast_question(q) or _FUTURE_DAY_RE.search(q)):
        out["focus"] = {"hazard": "flood", "time_frame": "future", "assets": []}
    return out


@action(reads=["query"], writes=["plan", "intent", "first_target", "trace"])
def plan_heuristic(state: State) -> State:
    """Burr action for `heuristic_plan` (no-LLM mode)."""
    trace = list(state.get("trace", []))
    rec = trace_rec_for("plan_heuristic")
    plan = heuristic_plan(state.get("query") or "")
    target = plan["targets"][0]["text"]
    rec["ok"] = True
    rec["result"] = {"intent": plan["intent"], "tier": "heuristic", "target": target}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
    trace.append(rec)
    return state.update(plan=plan, intent=plan["intent"], first_target=target, trace=trace)


@action(reads=["query"], writes=["plan", "intent", "first_target", "trace"])
def plan_intent(state: State) -> State:
    """Run the planner. Writes `plan` (dataclass-as-dict), the resolved
    `intent` string, and the first target text (for geocoding)."""
    from app.planner import plan as run_planner  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("plan_intent")
    try:
        p = run_planner(state["query"])
        plan_dict = {"intent": p.intent, "targets": p.targets, "rationale": p.rationale}
        first = ""
        if p.targets:
            t0 = p.targets[0]
            # Each target is a dict; the "text" field holds the geocodable
            # address string. Falls back to the rationale if no targets.
            first = t0.get("text") or t0.get("address") or ""
        rec["ok"] = True
        rec["result"] = {"intent": p.intent, "n_targets": len(p.targets)}
        trace.append(rec)
        return state.update(plan=plan_dict, intent=p.intent,
                            first_target=first, trace=trace)
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(plan=None, intent="not_implemented",
                            first_target="", trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["lat", "lon"], writes=["deployment", "trace"])
def select_deployment(state: State) -> State:
    """Pick the deployment whose coverage bbox contains the geocoded point.

    The chosen deployment name (e.g. `nyc`, `chicago`) is written to
    state and read by the Stones fan-out. When no deployment covers the
    point, `deployment` is set to the sentinel `__none__` and only the
    federal pebbles run.

    This is what stops a Chicago query from firing NYC's `ida_hwm` or
    `sandy` pebble: the server's boot-time `RIPRAP_DEPLOYMENT` env var
    does not decide which pebbles run for a query.
    """
    from riprap.core.pebbles.deployments import pick_deployment  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("select_deployment")
    lat = state.get("lat")
    lon = state.get("lon")
    dep = pick_deployment(lat, lon)
    if dep is None:
        rec["ok"] = True  # not an error — just out-of-coverage
        rec["result"] = {"deployment": None, "city": None,
                         "lat": lat, "lon": lon,
                         "reason": "no deployment covers this point"}
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
        trace.append(rec)
        # Sentinel `__none__` (not None) so Stones can tell "out of
        # coverage: run the federal pebbles only" from "no deployment
        # resolved yet: fall back to the env var".
        return state.update(deployment="__none__", trace=trace)
    rec["ok"] = True
    rec["result"] = {"deployment": dep.name, "city": dep.city,
                     "state": dep.state}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
    trace.append(rec)
    return state.update(deployment=dep.name, trace=trace)


@action(reads=["first_target", "query"], writes=["geocode", "lat", "lon", "trace"])
def geocode_target(state: State) -> State:
    """Resolve the first target (or the raw query if empty) to lat/lon
    via `app.geocode.geocode_one` — NYC Geosearch first, OSM Nominatim
    fallback for any US address. This is what makes non-NYC deployments
    (Chicago, Seattle, Albany) work without code changes."""
    from app.geocode import geocode_one  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("geocode")
    raw_query = state.get("query") or ""
    target = (state.get("first_target") or raw_query or "").strip()
    if not target:
        rec["ok"] = False
        rec["err"] = "no target text"
        trace.append(rec)
        return state.update(geocode=None, lat=None, lon=None, trace=trace)
    try:
        # scope_hint carries the full raw query so a locality dropped
        # during target extraction (planner pulled "10 Downing Street"
        # out of "...at 10 Downing Street in London?") still reaches the
        # non-US scope check in geocode_one.
        h = geocode_one(target, scope_hint=raw_query)
        if h is None:
            rec["ok"] = False
            rec["err"] = "no geocode match (NYC Geosearch + Nominatim both empty)"
            trace.append(rec)
            return state.update(geocode=None, lat=None, lon=None, trace=trace)
        gdict: dict[str, Any] = {
            "address": h.address,
            "borough": h.borough,
            "lat": h.lat,
            "lon": h.lon,
            "bbl": h.bbl,
            "bin": h.bin,
            # "exact" when the geocoder returned the house number and street
            # asked for; "closest" for a landmark or a nearby or similar match.
            "match": "exact" if geocode_matches(target, h.address) else "closest",
        }
        rec["ok"] = True
        # The UI reads lat/lon out of this trace `result` to drive its
        # `geocodeSucceeded` flag (without them the /q/[queryId] page
        # falls through to the catch-all "Resolving address…" branch
        # forever, even after the briefing finishes).
        rec["result"] = {
            "address": h.address, "borough": h.borough,
            "lat": h.lat, "lon": h.lon,
        }
        trace.append(rec)
        return state.update(geocode=gdict, lat=h.lat, lon=h.lon, trace=trace)
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["err"] = str(e)
        trace.append(rec)
        return state.update(geocode=None, lat=None, lon=None, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["first_target", "query"],
        writes=["geocode", "lat", "lon", "nta", "polygon_wkt", "trace"])
def resolve_area(state: State) -> State:
    """Neighbourhood intents: resolve the target to a 2020 NTA polygon, or
    to a community district (a CDTA code such as QN12, the union of its
    NTAs).
    Writes the polygon (WKT, WGS84) for polygon-scope pebbles and its
    centroid as lat/lon for deployment routing and the map."""
    from app.areas import nta  # noqa: PLC0415

    trace = list(state.get("trace", []))
    rec = trace_rec_for("nta_resolve")
    target = (state.get("first_target") or "").strip()
    try:
        district = nta.by_district(target) if re.fullmatch(r"\s*(MN|BX|BK|QN|SI)\s*\d{2}\s*", target,
                                                               re.IGNORECASE) else None
        if re.fullmatch(r"\s*(MN|BX|BK|QN|SI|NYC)\s*", target, re.IGNORECASE):  # a borough or the city (heat)
            district = nta.by_borough(target.strip())
        # No whole-question fallback: scanning the question for any place
        # name matched a borough first ("Queens") and returned Astoria.
        name, _, boro = target.partition(", ")
        matches = ([district] if district else []) or (nta.resolve(name) if name else [])
        matches = [m for m in matches if m["borough"] == boro] or matches  # "Murray Hill, Queens"
        if not matches:
            rec["ok"], rec["err"] = False, f"no neighborhood matches {target!r}"
            trace.append(rec)
            return state.update(geocode=None, lat=None, lon=None, nta=None, polygon_wkt=None,
                                trace=trace)
        t = matches[0]
        c = t["geometry"].centroid
        info = {"nta_code": t["nta_code"], "nta_name": t["nta_name"], "borough": t["borough"],
                "bbox": list(t["geometry"].bounds), "n_matches": len(matches)}
        rec["ok"], rec["result"] = True, info
        trace.append(rec)
        exact = bool(district) or nta._normalize(name) == nta._normalize(t["nta_name"])
        geocode = {"address": f"{t['nta_name']}, {t['borough']}", "borough": t["borough"],
                   "lat": c.y, "lon": c.x, "bbl": None, "bin": None,
                   "match": "exact" if exact else "closest"}
        return state.update(geocode=geocode, lat=c.y, lon=c.x, nta=info,
                            polygon_wkt=t["geometry"].wkt, trace=trace)
    finally:
        rec["elapsed_s"] = round(time.time() - rec["started_at"], 2)


@action(reads=["plan", "intent", "deployment", "lat", "lon", "trace"],
        writes=["selected_pebbles", "consulted", "not_checked", "trace"])
def select_sources(state: State) -> State:
    """Decide which pebbles run (stones.select_pebbles) and record the
    sources consulted and the ones not checked. Unchosen pebbles appear in
    the trace as skipped, not failed."""
    from riprap.core.burr.stones import hazard_of, pebbles_for, select_pebbles  # noqa: PLC0415
    from riprap.core.pebbles.bridge import get_registry  # noqa: PLC0415

    trace = list(state.get("trace", []))
    registry = get_registry(state.get("deployment") or None)
    plan = {**(state.get("plan") or {}), "intent": state.get("intent")}
    selected = select_pebbles(plan, registry)
    available = pebbles_for(state.get("deployment"), state.get("lat"), state.get("lon"),
                            state.get("intent"), hazard_of(plan))

    def entry(pid):
        m = registry.get(pid).manifest
        return {"id": pid, "title": m.title, "stone": m.stone}

    consulted = [entry(p) for p in available if p in selected]
    not_checked = [entry(p) for p in available if p not in selected]
    for e in not_checked:
        rec = trace_rec_for(e["id"])
        rec.update(ok=True, result={"skipped": "not selected for this question"})
        trace.append(rec)
    return state.update(selected_pebbles=selected, consulted=consulted,
                        not_checked=not_checked, trace=trace)
