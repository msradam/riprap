"""Answer a question from its own words, without a language model.

`answer(question, texts, values)` picks the lead and the facts from the
evidence the sources returned, by patterns over the question (as
answer_checks does) and the sources' own values. The facts are the
sources' sentences word for word, so nothing here writes prose.

The order of the rules:

  1. "right now": the live readings, no yes or no (no alert is not an
     observation that nothing is flooding);
  2. a named asset class (subway, schools, public housing, hospitals): its
     register;
  3. has it flooded (in general, since or during a named storm): the
     past-event rule of answer_checks sets yes, no or cannot say;
  4. how many: the counted source;
  5. forecasts, projections and scenarios: those sources, no yes or no (a
     forecast or a scenario is not an observation);
  6. any other source the question names (FEMA zone, terrain, permits);
  7. any other question about flooding: the observed record.

A question that names two things ("was it in the Sandy area, and how many
311 complaints") gets both: the first rule that fires sets the lead and
every other named source is added to the facts.

Returns None when no rule names what the question is about. The caller
then asks the model, if one is configured, or shows the evidence.
"""

from __future__ import annotations

import re

from riprap.core.burr import answer_checks as ac

ASSET_DOCS = ("mta_entrance_exposure", "doe_school_exposure", "nycha_development_exposure", "doh_hospital_exposure")
# What reports the present, and what a forecast question is answered with, in order.
LIVE_FACTS = ("nws_alerts", "floodnet", "noaa_tides", "nws_water_forecast", "usgs_gauges", "nws_obs")
FORECAST_FACTS = ("nws_water_forecast", "npcc4_slr",
                  "dep_moderate_2050", "dep_extreme_2080", "dep_moderate_2050_nta", "dep_extreme_2080_nta")
OBSERVED = ("floodnet", "nyc311", "nyc311_nta", "ida_hwm", "sandy_inundation", "sandy_nta")
DEP = ("dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080",
       "dep_moderate_current_nta", "dep_moderate_2050_nta", "dep_extreme_2080_nta")
# Sources a question can name beyond answer_checks.RELEVANT, most specific first.
TOPICS = (
    (re.compile(r"\bfema\b|flood ?zones?\b|flood ?plain|\bfirm\b|flood insurance rate", re.I),
     ("fema_nfhl", "fema_pfirm", "dcp_floodplain_nta")),
    (re.compile(r"\bsandy\b", re.I), ("sandy_inundation", "sandy_nta")),
    (re.compile(r"stormwater|storm water|\bdep\b|scenarios?\b|(extreme|moderate) (rain|flood)|rain(fall)? (flood )?maps?"
                r"|flood maps?", re.I), DEP),
    (re.compile(r"elevation|low spot|low.lying|terrain|topograph|how high (is|above)|above sea level", re.I),
     ("microtopo", "microtopo_nta")),
    (re.compile(r"\bpermits?\b|construction|being built", re.I), ("dob_permits_nta",)),
    (re.compile(r"\bstream|river level|\bgauges?\b", re.I), ("usgs_gauges",)),
)
# Words for the present. Weather words alone ("it's pouring") are not
# enough: people say them before asking about the past.
# "Is there flooding risk" and "is it flooding often" are not about now.
_FLOODING_NOW_RE = re.compile(r"\bis (it|anything|the street|the block|there|this) (now )?flooding\b"
                              r"(?!\s+(risk|history|often|usually|regularly|a lot|problems?|issues?|records?|complaints?"
                              r"|common|frequent))", re.I)
_NOW_RE = re.compile(r"\b(right now|rite now|rn|currently|tonight|at the moment|current conditions|live conditions"
                     r"|happening now|going on now|as we speak)\b|" + _FLOODING_NOW_RE.pattern, re.I)
_FUTURE_RE = re.compile(r"\b(forecasts?|forecasting|projections?|projected|outlook|predictions?|what is coming|what's coming"
                        r"|in the (coming|next) (years|decades)|in the future|by (the )?20\d\ds?|20[5-9]0s?|2100)\b", re.I)
_FLOOD_RE = re.compile(r"\bflood", re.I)
_DURING_RE = re.compile(r"\b(during|in|after|by)\s+(?:tropical storm\s+|[a-z]+\s+)?(ida|sandy)\b", re.I)


_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|,\s+(?:and|but)\s+"
                              r"|\s+and\s+(?=(?:has|have|had|did|does|do|was|were|is|are|how|which|what)\b)", re.I)


# The period of an abbreviation ends no clause: "100 Main St. since Sandy" was
# once split there and answered "No." with the period lost.
_ABBREV_RE = re.compile(r"\b(St|Ave|Av|Blvd|Rd|Pl|Dr|Ln|Pkwy|Ter|Ct|Hwy|Expy|Mt|Ft|No|Apt)\.", re.I)
_INITIALS_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}")  # "P.S. 90", "U.S."


def _clauses(question: str) -> list[str]:
    """The question's clauses: people open with a preamble ("I'm writing a
    piece about ... Did the block flood during Ida?") and join two
    questions with "and"."""
    q = _INITIALS_RE.sub(lambda m: m.group(0).replace(".", ""), _ABBREV_RE.sub(r"\1", question or ""))
    parts = (re.sub(r"^\W*(and|but|so|also)\s+", "", c, flags=re.I).strip() for c in _CLAUSE_SPLIT_RE.split(q))
    return [c for c in parts if c]


def _happened_clause(question: str) -> str | None:
    """The clause that asks whether it flooded ("Has the block flooded
    since Ida"), wherever it sits."""
    # ("FloodNet" is a name, not a flood: "is there a FloodNet sensor near here" asks about the sensor.)
    return next((c for c in _clauses(question) if ac._HAPPENED_RE.search(re.sub(r"floodnet", "", c, flags=re.I))), None)


def asks_now(question: str) -> bool:
    """A question about the present. "Is it currently in a FEMA flood zone"
    is not one: a word for now beside a mapped or recorded subject asks
    about that subject, unless it also asks whether it is flooding."""
    q = question or ""
    if not _NOW_RE.search(q):
        return False
    mapped = (any(pattern.search(q) for pattern, ids in TOPICS if "usgs_gauges" not in ids)
              or any(i in ASSET_DOCS for i in _named_ids(q)))  # "which schools ... for a meeting tonight"
    return not mapped or bool(_FLOODING_NOW_RE.search(q))


def time_frame(question: str) -> str:
    q = question or ""
    if asks_now(q) and not _FUTURE_RE.search(q):
        return "now"
    if _FUTURE_RE.search(q) or ac.dep_scenario_asked(q):
        return "future"
    return "past" if _happened_clause(q) or ac._SINCE_RE.search(q) or _DURING_RE.search(q) else "any"


def _named_ids(question: str) -> list[str]:
    """Every doc id the question's words name, most specific first."""
    out: list[str] = []
    for pattern, ids in (*ac.RELEVANT, *TOPICS):
        if pattern.search(question or ""):
            out += [i for i in ids if i not in out]
    return out


def named(question: str, texts: dict[str, str]) -> list[str]:
    """The named sources that returned a sentence. "id#word" needs the word
    in the text (a rain question wants a precipitation reading)."""
    out = []
    for raw in _named_ids(question):
        i, _, word = raw.partition("#")
        if texts.get(i) and word in texts[i].lower() and i not in out:
            out.append(i)
    asked = ac.dep_scenario_asked(question)
    if asked:  # one DEP scenario named: the others were not asked about
        out = [i for i in out if not i.startswith("dep_") or i.startswith(asked)]
    if "nws_obs" in out and not (asks_now(question) or _RAIN_NOW_RE.search(question or "")):
        # "does it flood when it rains this hard": rain is the setting, not the subject
        out.remove("nws_obs")
    if ac._SINCE_RE.search(question or ""):
        # "since Ida" names a period, not the Ida record as the subject; the
        # past-event rule decides whether the storm's own record belongs.
        out = [i for i in out if i != ac._storm_record(question)]
    year = re.search(r"\b(2050|2080)\b", question or "")
    if year:  # the scenario for the year asked about comes first
        out.sort(key=lambda i: year.group(1) not in i)
    return out


_CRITERIA = (*DEP, "sandy_inundation", "sandy_nta")
_WEATHER_RE = re.compile(r"\brain|pouring|downpour|\bstorm|weather", re.I)
_MAP_SHOWS_RE = re.compile(r"\b(shows?|shown|inside|within|mapped|modell?ed|appears?|covers?|puts?)\b", re.I)
_ANY_RE = ac.ANY_RE
_COUNT_KEYS = {"ida_hwm": "n_within_radius", "nyc311": "n", "nyc311_nta": "n", "floodnet": "n_sensors"}
# "Are there any ..." gets a yes or no from a source's count only when it
# asks about the thing counted: marks, complaints, sensors. "Did any water
# reach it" and "any street flooding" ask whether it flooded, which a count
# of marks 640 m away or of complaints does not settle.
_COUNTED = {"ida_hwm": re.compile(r"\bmarks?\b|high.water", re.I),
            "nyc311": re.compile(r"complain|\breports?\b|\brequests?\b|\bcalls?\b|\b311\b", re.I),
            "floodnet": re.compile(r"\bsensors?\b|floodnet", re.I)}
_COUNTED["nyc311_nta"] = _COUNTED["nyc311"]
_HISTORY_RE = re.compile(r"\bflood(ing)? (history|record)|history of flood|past flood|flooded before", re.I)
_RAIN_NOW_RE = re.compile(r"\b(is it|still) raining|how much (rain|precip)|rainfall (so far|today)|precipitation", re.I)
_FAR_RE = re.compile(r"\b20[3-9]\ds?\b|\b2100\b|decades?|century|sea.level", re.I)


def asks_something(text: str) -> bool:
    """True when words beside a place name a source or a time frame
    ("200 Water Street Manhattan FEMA flood zone"): a question typed as a
    search phrase. The word "flood" alone does not count."""
    return bool(asks_now(text) or _FUTURE_RE.search(text or "") or _named_ids(text or "")
                or _HISTORY_RE.search(text or ""))


def recognised(question: str) -> bool:
    """True when a rule knows what kind of question this is, from its words alone."""
    q = question or ""
    return bool(asks_now(q) or _FUTURE_RE.search(q) or _named_ids(q) or _FLOOD_RE.search(q))


_SAFE_RE = re.compile(r"\b(safe|dry|high(er)? ground|spared|protected|outside|not (in|inside|exposed|at risk))\b", re.I)
_SCENARIO_RE = re.compile(r"stormwater|\bdep\b|scenarios?\b|\b2080\b|extreme rain", re.I)
_EXPOSED_RE = re.compile(r"exposed|exposure|at risk|vulnerab|flood[- ]?(zone|prone|plain|area|risk)", re.I)
_TOTALS = {"mta_entrance_exposure": "n_entrances", "doh_hospital_exposure": "n_hospitals"}  # full layers


def _asset_lead(question: str, docs: list[str], values: dict | None) -> str:
    """Yes, no or in part from the register's own counts, and only for
    what a register records: assets inside the 2012 Sandy extent, assets
    inside the DEP extreme scenario. The question's words say which count.
    It records no flooding since a date, and "is the school safe" asks the
    opposite, so those keep the neutral lead, as does "which schools"."""
    q = question or ""
    if not ac.is_yes_no_question(q) or _SAFE_RE.search(q) or ac._SINCE_RE.search(q) or re.search(r"\bida\b", q, re.I):
        return "facts"
    sandy, scenario = re.search(r"\bsandy\b", q, re.I), _SCENARIO_RE.search(q)
    if TOPICS[0][0].search(q) and not (sandy or scenario):
        return "facts"  # "in the FEMA flood zone": the registers do not read FEMA zones, so neither yes nor no
    keys = (["n_inside_sandy_2012"] if sandy and not scenario else ["n_in_dep_extreme_2080"] if scenario and not sandy
            else ["n_inside_sandy_2012", "n_in_dep_extreme_2080"] if sandy or scenario or _EXPOSED_RE.search(q) else [])
    vals = [(values or {}).get(d) for d in docs]
    if not keys or not all(isinstance(v, dict) and all(isinstance(v.get(k), int) for k in keys) for v in vals):
        return "facts"
    hit = max(sum(v[k] for v in vals) for k in keys)
    if not hit:
        # An asset just outside the mapped Sandy edge is not a plain no.
        return "facts" if "n_inside_sandy_2012" in keys and any(v.get("n_near_sandy_edge") for v in vals) else "no"
    # A full layer (every entrance, every hospital) with some inside and some
    # outside is "in part", unless the question asks whether any is.
    total = sum(v.get("n_checked") or v.get(_TOTALS[d]) or 0 for d, v in zip(docs, vals, strict=True) if d in _TOTALS)
    return "partly" if total > hit and not _ANY_RE.search(q) else "yes"


def _count_of(doc: str, question: str, value) -> int | None:
    """The count "are there any ..." asks about: the named 311 kind and not
    every complaint, sensor events and not sensors when the question asks
    about flooding."""
    if not isinstance(value, dict):
        return None
    if doc in ("nyc311", "nyc311_nta"):
        kind = ac.kind_asked(doc, question, value)
        return value["by_kind"].get(kind, 0) if kind else value.get("n")
    if doc == "floodnet" and re.search(r"\b(flood(ed|ing|s)?|events?|logged|recorded|water|depth)\b", question, re.I):
        return value.get("n_flood_events_3y") if value.get("n_sensors") else None  # no sensor: cannot say
    return value.get(_COUNT_KEYS.get(doc, ""))


def _share_lead(fraction: float, question: str) -> str:
    """Yes, no or in part for "was QN12 inside the Sandy zone" from the
    share of the area inside: a district with 0.8% inside is not a plain
    yes, unless the question asks whether any part was."""
    if not fraction:
        return "no"
    return "yes" if fraction >= 0.95 or _ANY_RE.search(question) else "partly"


def soften(lead: str, facts: list[str], values: dict | None) -> str:
    """Within 50 m of the mapped Sandy edge, on either side, the outline
    does not settle yes or no for one building: the sentence says how near
    the edge is, and the lead stays neutral."""
    v = (values or {}).get("sandy_inundation")
    near = isinstance(v, dict) and v.get("edge_m") is not None
    return "facts" if near and lead in ("yes", "no") and facts[:1] == ["sandy_inundation"] else lead


def answer(question: str, texts: dict[str, str], values: dict | None = None) -> tuple[str, list[str]] | None:
    """(lead, facts) or None. `lead` is one of synthesis.LEADS or "facts"
    (the neutral lead); `facts` are doc ids in the order they are quoted.

    A question in two parts ("was it in the Sandy area, and how many 311
    complaints") is answered part by part, in the order asked: the facts
    of each part, and the first part's yes or no when it has one."""
    if not question:
        return None
    parts = [(c, _answer_one(c, texts, values, generic=False)) for c in _clauses(question)]
    parts = [(c, a) for c, a in parts if a and a[1]]
    if len(_clauses(question)) > 1 and parts and time_frame(question) != "now":
        # One answering part after a preamble keeps its own lead ("I'm writing
        # about Harlem. Does the map show water at ...?").
        facts, about_assets = [], False
        for _, (_, fs) in parts:
            # After a part about an asset, "does it also show up in the 2050
            # map" is about the asset: its register sentence already says, and
            # the layer's sentence is about the address.
            facts += [f for f in fs if f not in facts and not (about_assets and f in _CRITERIA)]
            about_assets = about_assets or any(f in ASSET_DOCS for f in fs)
        facts = facts[:6]
        first = parts[0][1][0]
        return (first if first in ("yes", "no", "partly") or len(parts) == 1 else "facts"), facts
    return _answer_one(question, texts, values)


def _answer_one(question: str, texts: dict[str, str], values: dict | None = None, *,
                generic: bool = True) -> tuple[str, list[str]] | None:
    """One question, or one part of a two-part question (`generic` False:
    a part that names nothing gets no answer, so a preamble adds no facts)."""
    tf = time_frame(question)
    subjects = named(question, texts)
    assets = [d for d in subjects if d in ASSET_DOCS]

    def with_named(lead: str, facts: list[str]) -> tuple[str, list[str]]:
        return lead, [*facts, *(d for d in subjects if d not in facts)][:6]

    if tf == "now":
        # What the question names comes first; the stream gauge and the
        # airport observation only when named, or when it is raining.
        raining = isinstance((values or {}).get("nws_obs"), dict) and (values or {})["nws_obs"].get("raining")
        live = [i for i in subjects if i in LIVE_FACTS]
        wet = raining or _WEATHER_RE.search(question)  # "it's pouring": quote the observation either way
        live += [i for i in LIVE_FACTS if texts.get(i) and i not in live
                 and (i not in ("usgs_gauges", "nws_obs") or (i == "nws_obs" and wet))]
        if _happened_clause(question):  # "... and has it flooded before": the record as well
            live += [i for i in OBSERVED if texts.get(i) and i not in live]
        return ("facts", live[:6]) if live else None
    if assets:
        # The register sentence already says which assets are in the Sandy
        # extent and the DEP scenario, so those layers are the criteria of an
        # asset question, not further subjects.
        lead = _asset_lead(question, assets, values)
        if lead != "facts" and tf == "future" and not _MAP_SHOWS_RE.search(question):
            lead = "facts"  # "will the schools flood by 2080": a scenario is not an observation
        return lead, assets
    happened = _happened_clause(question) if tf == "past" else None
    past = ac.past_event_lead(happened, {"time_frame": "past"}, list(texts), texts, values) if happened else None
    if past:
        lead, facts = past
        if lead != "cannot_answer":
            return with_named(lead, facts)
        if not facts and not subjects:
            # "Has MN12 had any flooding since Ida": an area has no storm record
            # of its own, so the observed record it does have, with no yes or no.
            seen = [i for i in OBSERVED if texts.get(i)]
            return ("facts", seen) if seen else (lead, facts)
        if facts or not subjects:
            return lead, facts
        # The storm's point record does not exist for an area ("did Sandy flood
        # any of BX01"): the area's own sources answer. The Sandy share of an
        # area says yes or no by itself.
        share = (values or {}).get("sandy_nta") if "sandy_nta" in subjects else None
        if isinstance(share, dict) and share.get("fraction") is not None and ac.is_yes_no_question(happened):
            return _share_lead(share["fraction"], happened), ["sandy_nta"]
        return "facts", subjects[:6]
    share = (values or {}).get("sandy_nta")
    if subjects[:1] == ["sandy_nta"] and isinstance(share, dict) and share.get("fraction") is not None \
            and ac.is_yes_no_question(question):
        return with_named(_share_lead(share["fraction"], question), ["sandy_nta"])  # "was any part of QN12 inside"
    rel = ac.relevant_doc(question, texts)
    if ac.is_count_question(question) and rel:
        return with_named("count", [rel])
    if tf == "future":
        asked = ac.dep_scenario_asked(question)
        shown = (values or {}).get(asked) if asked else None
        if isinstance(shown, dict) and shown.get("depth_class") is not None and texts.get(asked) \
                and ac.is_yes_no_question(question) and _MAP_SHOWS_RE.search(question):
            # "Does the 2080 map show water here": what the map shows is a fact
            # about the map. "Will it flood" stays without a yes or no.
            return ("yes" if shown["depth_class"] else "no"), [asked]
        far = _FAR_RE.search(question)  # a question about the 2050s is not about this week's tide
        docs = ([d for d in texts if asked and d.startswith(asked)]
                or [d for d in subjects if d in DEP]
                or [i for i in FORECAST_FACTS if texts.get(i) and not (far and i == "nws_water_forecast")][:4])
        return with_named("facts", docs) if docs else None
    n = _count_of(subjects[0], question, (values or {}).get(subjects[0])) if subjects else None
    if (isinstance(n, int) and ac.is_yes_no_question(question) and _ANY_RE.search(question)
            and _COUNTED[subjects[0]].search(question)):
        # "Were any high-water marks surveyed near here": the source's own count says yes or no.
        return with_named("yes" if n else "no", [subjects[0]])
    if subjects:
        return "facts", subjects[:6]
    if any(i.partition("#")[0] != "nws_obs" for i in _named_ids(question)):
        # The question names a source and that source returned nothing (it
        # failed, or it does not exist for this kind of place): say so, do
        # not answer with something else.
        return "cannot_answer", []
    if generic and _FLOOD_RE.search(question):
        seen = [i for i in OBSERVED if texts.get(i)]
        return ("facts", seen) if seen else None
    return None
