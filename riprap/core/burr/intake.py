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

from riprap.core.burr.pebble import trace_rec_for
from riprap.core.burr.place import (
    ELSEWHERE_RE,
    extract_address,
    geocode_matches,
    landmark_phrase,
    resolve_query,
)
from riprap.core.burr.rule_answer import _clauses, asks_now, recognised  # one definition of "now"

# Trailing risk phrases ("... at risk of flooding?", "... flood risk").
_TRAILING_RE = re.compile(
    r"[\s,]*(?:at\s+risk(?:\s+(?:of|for))?(?:\s+(?:flooding|flood|flooded))?"
    r"|flood(?:ing|ed)?(?:\s+(?:risk|exposure|hazard))?"
    r"|hazard\s+exposure)\s*\??\s*$",
    re.IGNORECASE,
)
# Leading clause that ends in a preposition and contains a risk/ask trigger,
# e.g. "flood risk at ", "what's the flood risk for ", "briefing on ".
_LEADIN_PREP_RE = re.compile(
    r"^.*?\b(?:flood(?:ing)?|risk|hazard|briefing|report|exposure"
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


_OTHER_HAZARD_RE = {"heat": re.compile(r"\b(heat island|heat ?waves?|heat vulnerab|extreme heat|hot(ter|test)?\b[^.?!]{0,30}\bsummer"
                                       r"|(surface|air) temperatures?|cooling cent(er|re)s?)", re.I),
                    "air": re.compile(r"\b(air quality|aqi|air pollution|smog|pm ?2\.5|ozone(?! park))\b", re.I)}


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
    return f"{span}, Queens" if re.match(r"\s*\d+-\d+\s", span) else span


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
    from app.areas import nta  # noqa: PLC0415
    from app.planner import _not_implemented_message  # noqa: PLC0415

    q = (query or "").strip()
    # A named future day is a prediction, declined as one ("Will it flood on
    # October 15" was once told Riprap cannot reconstruct a past date).
    msg = None if _FUTURE_DAY_RE.search(q) else _not_implemented_message(q)
    if msg:
        return {"intent": "not_implemented", "rationale": msg, "targets": []}
    for hazard, pattern in _OTHER_HAZARD_RE.items():
        # ("It gets hot here in the summer and the basement floods" is still a flood question, and so
        # is "It was hot last summer. Was it inside the Sandy zone?": another sentence asks about flooding.)
        if pattern.search(q) and not re.search(r"\bflood", q, re.IGNORECASE) and not any(
                recognised(c) for c in _clauses(q) if not pattern.search(c)):
            return {"intent": "out_of_scope", "rationale": f"Heuristic match: {hazard} question.",
                    "focus": {"hazard": hazard, "time_frame": "any", "assets": []},
                    "targets": [{"type": "address", "text": _address_from_query(q)}]}
    # A prediction for a named day with no place has nothing to answer with;
    # with a place, the rules decline the prediction and quote what is
    # forecast and mapped there (rule_answer: no_prediction).
    if _OUT_OF_SCOPE_RE.search(q) or (_FUTURE_DAY_RE.search(q) and not _names_a_place(q)):
        return {"intent": "out_of_scope", "rationale": "Heuristic match: out of scope.",
                "focus": {"hazard": "flood", "time_frame": "any", "assets": []},
                "targets": [{"type": "address", "text": _address_from_query(q)}]}
    m = _COMPARE_RE.match(q)
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
    live = asks_now(q) and not forecast_question(q) and not _FUTURE_DAY_RE.search(q)
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
        elif place["kind"] == "neighborhood" and _QUESTION_RE.search(q) and not _OTHER_STATE_RE.search(q):
            # A place name inside a question ("Did Hamilton Beach flood during Sandy and ...", "Does
            # Rockaway Boulevard flood?"): the name for the geocoder, never the rest of the sentence.
            target = f"{place['text']}, New York, NY"
        else:
            target = _address_from_query(q)
        intent = "single_address"
    kind = "nta" if intent in ("neighborhood", "development_check") else "address"
    out = {"intent": intent, "rationale": f"Heuristic match: {intent}.",
           "targets": [{"type": kind, "text": target}], "place": place}
    if forecast_question(q) or _FUTURE_DAY_RE.search(q):
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
        exact = bool(district) or nta._normalize(target) == nta._normalize(t["nta_name"])
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
    from riprap.core.burr.stones import pebbles_for, select_pebbles  # noqa: PLC0415
    from riprap.core.pebbles.bridge import get_registry  # noqa: PLC0415

    trace = list(state.get("trace", []))
    registry = get_registry(state.get("deployment") or None)
    plan = {**(state.get("plan") or {}), "intent": state.get("intent")}
    selected = select_pebbles(plan, registry)
    available = pebbles_for(state.get("deployment"), state.get("lat"), state.get("lon"),
                            state.get("intent"))

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
