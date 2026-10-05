"""Deterministic rules on an extractive answer's lead against its cited
evidence: a "no" needs facts that report an absence, a "partly" one
positive and one negative or partial fact, a count question the count
lead, a yes or no about past flooding follows the record, and a "no" or
a 0 never rests on a source that could not answer (`unavailable`).

Every rule is a pattern over words; none reads meaning. The five per-claim
checks of the retired guarded mode (absence, universal, inference, dropped
count, datum) are kept at the git tag archive/guarded-answer-mode.
"""

from __future__ import annotations

import re

_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
               "eighty": 80, "ninety": 90})
_WORD_RE = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)

# A document that itself reports an absence or a zero. FEMA's zone X is
# "an area of minimal flood hazard": outside the mapped floodplain, so an
# absence, not a result a "no" would contradict.
_DOC_ABSENCE_RE = re.compile(r"\b(no|none|not|zero|without|outside|never)\b|(?<![\d.,])0(?![\d.,])"
                             r"|minimal flood hazard", re.IGNORECASE)
# A document or value that says its source could not answer.
_UNAVAILABLE_RE = re.compile(r"\bunavailable\b|\bnot available\b|could not be (read|reached)|failed to respond"
                             r"|\bunreachable\b", re.IGNORECASE)
# "{n} <assets> within {r} m of this address: {a} inside the 2012 Sandy ... and {b} inside the DEP ...",
# or "{n} <assets> in this area: ..." for a neighbourhood or district.
_REGISTER_RE = re.compile(r"(\d[\d,]*)\s[^:]*?(?:within\s[\d,.]+\s?m\b|in this area)[^:]*:\s*(\d+) inside the 2012 Sandy"
                          r"[^.]*?(\d+) inside the DEP", re.IGNORECASE)
_DISTANCE_OR_YEAR_RE = re.compile(r"^\s?(m|km|meters?|metres?|mi|miles?)\b", re.IGNORECASE)

# Question words -> the doc_ids of the source that answers them, most
# specific first: the source a question is about.
RELEVANT = (
    (re.compile(r"subway|entrance", re.I), ("mta_entrance_exposure",)),
    (re.compile(r"school", re.I), ("doe_school_exposure",)),
    (re.compile(r"hospital", re.I), ("doh_hospital_exposure",)),
    (re.compile(r"nycha|public housing", re.I), ("nycha_development_exposure",)),
    (re.compile(r"\b311\b|complaint|street flooding|sewer back|catch basin|manhole", re.I), ("nyc311", "nyc311_nta")),
    (re.compile(r"sensor|floodnet", re.I), ("floodnet",)),
    (re.compile(r"high.water|\bida\b", re.I), ("ida_hwm",)),
    (re.compile(r"\brain|precip", re.I), ("nws_obs#precip",)),
    (re.compile(r"\btide|water level|harbor", re.I), ("noaa_tides",)),
    (re.compile(r"sea.level", re.I), ("npcc4_slr",)),
    (re.compile(r"\balert|warning", re.I), ("nws_alerts",)),
)


# Leads only code sets, never a model: honest silence, a neutral lead, or (for heat) a yes or no "at the
# surface" read from the measurement's own value, which the word patterns below do not understand.
CODE_LEADS = ("cannot_answer", "experimental", "no_prediction", "no_satellite", "heat_forecast", "no_prediction_heat", "no_prediction_far", "no_score", "no_ranking", "no_deaths", "cooling_centers",
              "surface_yes", "surface_no", "no_advice", "needs_address", "no_change_record",
              # Review round 1: flooding recorded near an address and not at it, a named past day, what Riprap
              # does not hold, a question not read as English, a register under "will it flood", a cause asked
              # of records that give none, and the two heat leads for "safe" and for air temperature.
              "near", "day", "not_held", "not_english", "no_prediction_register", "no_cause", "no_advice_heat",
              "no_air_temp",
              # Review round 2: a named year, season or month (read from the records dated in it), a depth
              # asked of maps that give none, a flood zone asked of an area, and a named place that was not found.
              "period", "no_depth", "area_zone", "no_area_zone", "not_located", "no_rating_heat")
# Leads that say the question was not answered (`grounding.answered` is False under them).
UNANSWERED_LEADS = ("cannot_answer", "not_held", "not_english", "no_depth", "no_area_zone")
_AREA_SHARE_RE = re.compile(r"([\d.]+)% of this area lies inside")
# "Is there any ...", "are there ...": a yes needs only one.
ANY_RE = re.compile(r"\b(any|is there an?|are there|was there an?|were there)\b", re.I)


def words_to_digits(text: str) -> str:
    """'Four schools' -> '4 schools', so number words are checked like digits."""
    return _WORD_RE.sub(lambda m: str(_WORDS[m.group(1).lower()]), text)


def reports_result(doc: str) -> bool:
    """True when a document reports something present, not an absence. An
    asset register reports a result when any of its inside counts is above
    zero ("3 hospitals: 0 inside Sandy and 1 inside the DEP scenario")."""
    counts = _register_counts(doc)
    if counts:
        return max(counts[1:]) > 0
    share = _AREA_SHARE_RE.search(doc or "")
    if share:
        return float(share.group(1)) > 0  # "0.0% of this area lies inside" is an absence
    # The finding is the first sentence; a later sentence may qualify it
    # ("FloodNet's record showed no flood event under way at them when this
    # was read") without turning 8 events into an absence.
    first = re.split(r"(?<=\.)\s+(?=[A-Z0-9])", doc.strip(), maxsplit=1)[0] if doc else ""
    return bool(first) and not _DOC_ABSENCE_RE.search(first)


def _partial(doc: str) -> bool:
    """An asset register with some, but not all, of its assets inside, or
    an area with part of it inside a mapped extent."""
    counts = _register_counts(doc)
    share = _AREA_SHARE_RE.search(doc or "")
    return (bool(counts) and any(0 < k < counts[0] for k in counts[1:])) or (bool(share) and 0 < float(share.group(1)) < 95)


def is_count_question(question: str) -> bool:
    return bool(_COUNT_QUESTION_RE.search(question or ""))


_COUNT_QUESTION_RE = re.compile(r"\bhow (many|much)\b|\bshare\b|\bpercent|\bproportion\b|\bfraction\b"
                                r"|\bnumber of\b|\bcount\b", re.IGNORECASE)


def _register_counts(doc: str) -> tuple[int, int, int] | None:
    m = _REGISTER_RE.search(doc or "")
    return tuple(int(g.replace(",", "")) for g in m.groups()) if m else None  # type: ignore[return-value]


# For these sources only the number next to the word answers the question
# (a rain question wants the precipitation, not the temperature).
_NEAR = {"nws_obs": "precip"}


def count_numbers(doc: str, near: str = "") -> list[str]:
    """Numbers in a document that are counts or values, not distances or
    years; with `near`, only numbers followed closely by that word."""
    from riprap.core.burr.synthesis import numbers_in

    out = []
    for m in re.finditer(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?", doc or ""):
        n = m.group(0)
        if n not in numbers_in(n):
            continue  # 311, 911
        if _DISTANCE_OR_YEAR_RE.match(doc[m.end():]):
            continue
        if re.fullmatch(r"(19|20)\d\d", n) or len(n.replace(",", "")) > 7:
            continue  # a year, or an identifier such as a FIRM panel
        if near and near not in doc[m.end():m.end() + 12].lower():
            continue
        out.append(n)
    return out


# A DEP stormwater scenario named in a question, by its year or its storm,
# and the words that mark a stormwater question (not a sea-level one). Two
# maps use current sea levels: "limited" names the smaller storm, and
# "current" alone still means the Moderate Flood map, as before the Limited
# map was read.
_DEP_YEAR = ((re.compile(r"\b2080\b|\bextre+m|\b100[- ]year (?:storm|rain)", re.I), "dep_extreme_2080"), (re.compile(r"\b2050\b"), "dep_moderate_2050"),
             (re.compile(r"\blimited\b|\b1\.77\b", re.I), "dep_limited_current"),
             (re.compile(r"\bcurrent\b", re.I), "dep_moderate_current"))
_STORMWATER_RE = re.compile(r"stormwater|\bdep\b|\bscenario\b|\b100[- ]year (?:storm|rain)", re.I)
_NOT_STORMWATER_RE = re.compile(r"sea.level|surge|\btide", re.I)


def dep_scenario_asked(question: str) -> str | None:
    """The DEP stormwater scenario pebble id ("dep_moderate_2050") a question
    names ("What does the 2050 stormwater scenario show?"), or None when it
    names none, or more than one, or asks about sea level."""
    q = question or ""
    if not _STORMWATER_RE.search(q) or _NOT_STORMWATER_RE.search(q):
        return None
    named = [pid for pat, pid in _DEP_YEAR if pat.search(q)]
    if "dep_limited_current" in named and not re.search(r"\bmoderate\b", q, re.I):
        named = [n for n in named if n != "dep_moderate_current"]  # "the limited scenario under current conditions"
    return named[0] if len(named) == 1 else None


def relevant_doc(question: str, docs: dict[str, str]) -> str | None:
    """The doc_id of the source the question is about, if it produced one."""
    for pattern, ids in RELEVANT:
        if pattern.search(question or ""):
            for i in ids:
                # "id#word": that source only when its text has the word
                # (an observation answers a rain question only with a
                # precipitation reading, not a temperature).
                i, _, word = i.partition("#")
                if docs.get(i) and word in docs[i].lower():
                    return i
            return None
    return None


# How near a record must be for a plain "Yes." about an address: on its block. One distance for FloodNet
# sensors and Ida high-water marks alike; a record farther off gives the "near" lead, which states the distance.
# ponytail: one fixed distance; use the block's own geometry if the yes ever needs to be finer.
BLOCK_M = 100
NEAR = "near"  # a verdict of _event: an event was recorded, farther than BLOCK_M from the address
# The structured field that holds each source's headline figure.
COUNT_FIELD = {
    "ida_hwm": "n_within_radius", "mta_entrance_exposure": "n_entrances", "doe_school_exposure": "n_schools",
    "doh_hospital_exposure": "n_hospitals", "nycha_development_exposure": "n_developments",
    "nyc311": "n", "nyc311_nta": "n", "floodnet": "n_flood_events_3y", "nws_alerts": "n_active",
    "noaa_tides": "observed_ft_mllw",
}


def kind_asked(rel: str, question: str, value: dict | None) -> str | None:
    """The 311 complaint kind the question names, when `rel` is a 311
    source whose value splits its count by kind."""
    from app.context.nyc311 import kind_named

    if rel in ("nyc311", "nyc311_nta") and isinstance(value, dict) and "by_kind" in value:
        return kind_named(question)
    return None


_ASKS_REPORTS_RE = re.compile(r"\b311\b|complain|report", re.I)
_YEAR_RE = re.compile(r"\b(?:in|during|for|of)\s+(20[12]\d)\b", re.I)
_OTHER_PERIOD_RE = re.compile(r"\b(last|this|past) (month|week|weekend|night|morning|few|couple|\d+)|yesterday|today|this (spring|summer|fall|"
                              r"autumn|winter)|last (spring|summer|fall|autumn|winter)\b", re.I)


def count_lead(question: str, docs: dict[str, str], values: dict | None, today=None) -> tuple[str | None, bool]:
    """(lead sentence, undetermined) for a count question about 311.

    The source states one window ("in the last 3 years"). A question about
    one year ("last year", "in 2024") gets that year's count from the
    value's by_year when the window covers the whole year, or the year so
    far for the current one. A period the value cannot give (a month, a
    year the window only partly covers, one kind in one year) is
    undetermined: the caller drops the count lead, so the window's total
    is not shown as the answer to another question."""
    import datetime

    q = question or ""
    rel = relevant_doc(q, docs)
    v = (values or {}).get(rel) if rel else None
    today = today or datetime.date.today()
    m = _YEAR_RE.search(q)
    if rel == "floodnet" and m and isinstance(v, dict) and "by_year" in v:
        # "How many flood events did the sensors record in 2024?": that year's count, when the sensors'
        # period covers the whole year (or it is this year so far); otherwise no count as the answer.
        year, start = int(m.group(1)), str(v.get("period_start") or "9999")[:10]
        if year > today.year or (year < today.year and start > f"{year}-01-01"):
            return None, True
        so_far = " so far" if year == today.year else ""
        rows, complete = floodnet_rows(v)
        if complete:
            # Days before events: two sensors a block apart log one storm as two events ("4 flood events"
            # in 2026 at Hollis was two storms at two sensors).
            dated = [_local(e) for r in rows for e in r.get("events") or [] if str(_local(e))[:4] == str(year)]
            n, d = len(dated), len(set(dated))
            return (f"Flooding was recorded on {d} {'day' if d == 1 else 'separate days'} in {year}{so_far} ({n} sensor "
                    f"event{'' if n == 1 else 's'}), by the {_basis(rows)} day each event started [floodnet]."), False
        n = int(v["by_year"].get(str(year), 0))
        return (f"{n} flood event{'s' if n != 1 else ''} recorded in {year}{so_far}, "
                "by the UTC year each event started [floodnet]."), False
    if rel not in ("nyc311", "nyc311_nta") or not isinstance(v, dict) or "by_year" not in v:
        return kind_lead(q, docs, values), False
    year = (today.year - 1 if re.search(r"\blast year\b", q, re.I) else today.year if re.search(r"\bthis year\b", q, re.I)
            else int(m.group(1)) if m else None)
    since = _period_start_date(q)
    if year is None and since:
        # "since 2023": the years from then on, when the window reaches back to
        # that January. "Since Ida" starts mid-year and the value splits by
        # year only, so the window's total is not offered as the answer.
        try:
            window_start = today.replace(year=today.year - int(v.get("years") or 0))
        except ValueError:  # February 29
            window_start = today.replace(year=today.year - int(v.get("years") or 0), day=28)
        if (since.month, since.day) != (1, 1) or window_start > since or kind_asked(rel, q, v):
            return None, True
        n = sum(int(k) for y, k in (v.get("by_year") or {}).items() if int(y) >= since.year)
        return (f"{n} complaint{'s' if n != 1 else ''} to 311 about flooding and sewer backups filed since the start of "
                f"{since.year}, by the year each was filed [{rel}]."), False
    if year is None:
        return (None, True) if _OTHER_PERIOD_RE.search(q) else (kind_lead(q, docs, values), False)
    try:
        start = today.replace(year=today.year - int(v.get("years") or 0))
    except ValueError:  # February 29
        start = today.replace(year=today.year - int(v.get("years") or 0), day=28)
    covered = year == today.year or (year < today.year and start <= datetime.date(year, 1, 1))
    if not covered or kind_asked(rel, q, v):
        return None, True
    n = int((v.get("by_year") or {}).get(str(year), 0))
    return (f"{n} complaint{'s' if n != 1 else ''} to 311 about flooding and sewer backups filed in {year}"
            f"{' so far' if year == today.year else ''}, by the year each was filed [{rel}]."), False


def kind_lead(question: str, docs: dict[str, str], values: dict | None) -> str | None:
    """For a question about one kind of 311 complaint, the lead that states
    that kind's count and the descriptors counted, built from the pebble's
    structured value (the cited sentence after it gives the full split)."""
    from app.context.nyc311 import KIND

    rel = relevant_doc(question, docs)
    value = (values or {}).get(rel) if rel else None
    kind = kind_asked(rel or "", question, value)
    if not kind:
        return None
    k = value["by_kind"].get(kind, 0)  # type: ignore[index]
    names = " and ".join(f'"{d}"' for d, kd in KIND.items() if kd == kind)
    years = value.get("years")  # type: ignore[union-attr]
    window = f" in the last {years} year{'s' if years != 1 else ''}" if isinstance(years, int) else ""
    return (f"{k} {kind} complaint{'s' if k != 1 else ''}{window}, counting the 311 "
            f"descriptor{'s' if ' and ' in names else ''} {names} [{rel}].")


def relevant_figure(rel: str, docs: dict[str, str], values: dict | None = None,
                    question: str = "") -> float | None:
    """The headline figure of the source a question is about: from the
    pebble's structured value when there is one (a sentence can hold a
    street number, "67th St."), else the first count in its sentence."""
    v = (values or {}).get(rel)
    if isinstance(v, dict):
        if rel == "nws_obs":  # a rain question wants the precipitation reading
            for k in ("precip_last_hour_mm", "precip_last_6h_mm"):
                if v.get(k):
                    return float(v[k])
            return 0.0 if 0 in (v.get("precip_last_hour_mm"), v.get("precip_last_6h_mm")) else None
        kind = kind_asked(rel, question, v)
        if kind:  # "how many street flooding complaints": that kind's count, not the total
            return float(v["by_kind"].get(kind, 0))
        if COUNT_FIELD.get(rel) in v:
            x = v[COUNT_FIELD[rel]]
            return float(x) if isinstance(x, (int, float)) else None
    from riprap.core.burr.synthesis import _parse

    counts = count_numbers(docs.get(rel, ""), _NEAR.get(rel, ""))
    parsed = _parse(counts[0]) if counts else None
    return parsed[0] if parsed else None


def unavailable(doc_id: str, docs: dict[str, str], values: dict | None = None) -> bool:
    """True when the source behind a document could not answer: its value
    is marked unavailable or carries an error, or its text says so. Such a
    source supports neither a "no" nor a count of 0."""
    v = (values or {}).get(doc_id)
    if isinstance(v, dict) and (v.get("available") is False or v.get("error")):
        return True
    return bool(_UNAVAILABLE_RE.search(docs.get(doc_id, "")))


def rel_zero_down(question: str, docs: dict[str, str], values: dict | None) -> bool:
    """The source the question is about gives 0, but it was unavailable."""
    rel = relevant_doc(question, docs)
    return bool(rel) and unavailable(rel, docs, values) and relevant_figure(rel, docs, values, question) == 0


def check_lead(lead: str, facts: list[str], question: str, docs: dict[str, str],
               values: dict | None = None) -> list[tuple[str, str]]:
    """Extractive mode: check the model's lead against the facts it chose.
    The facts are template sentences shown verbatim, so only the lead and
    the choice of facts can be wrong."""
    if lead in CODE_LEADS:
        return []  # no yes, no or count to check: silence, or a lead set by a rule from a source's own value
    if not facts:
        return [("empty", f"lead {lead!r} with no facts")]
    texts = dict(zip(facts, (docs.get(i, "") for i in facts), strict=True))
    hits: list[tuple[str, str]] = []
    positive = [i for i, t in texts.items() if reports_result(t)]
    negative = [i for i, t in texts.items() if not reports_result(t)]
    partial = [i for i, t in texts.items() if _partial(t)]
    if is_count_question(question) and lead not in ("count", "facts"):
        hits.append(("dropped_count", f"lead {lead!r}: a count or share question needs the count lead"))
    down = [i for i in facts if unavailable(i, docs, values)]
    if lead == "no" and down:
        hits.append(("unavailable", f"lead 'no', but {', '.join(down)} was unavailable, not a zero"))
    if lead in ("count", "facts") and rel_zero_down(question, docs, values):
        hits.append(("unavailable", "a count of 0 from a source that was unavailable"))
    if lead == "no" and positive:
        hits.append(("absence", f"lead 'no', but {', '.join(positive)} reports a result"))
    if lead == "yes":
        if not positive:
            hits.append(("absence", "lead 'yes', but every fact reports an absence"))
        if partial and not ANY_RE.search(question or ""):
            hits.append(("universal", f"lead 'yes', but {', '.join(partial)} counts only some; use 'partly'"))
    if lead == "partly" and not (positive and (negative or partial)):
        hits.append(("universal", "lead 'partly' needs one fact reporting a result and one reporting "
                                  "none or only some"))
    if lead == "count" and not any(count_numbers(t) for t in texts.values()):
        hits.append(("dropped_count", "lead 'count' needs a fact with a count"))
    rel = relevant_doc(question, docs)
    # "since Ida" names the period, not the subject: no Ida mark within
    # 800 m does not contradict flooding since Ida that the sensors and
    # 311 recorded (USGS surveyed marks at selected sites only).
    since_storm = rel == _storm_record(question) and _period_start(question) is not None
    if rel in texts and lead in ("yes", "partly") and not reports_result(texts[rel]) and not since_storm:
        hits.append(("absence", f"lead {lead!r}, but {rel}, the source the question is about, reports none"))
    if rel and rel not in facts and relevant_figure(rel, docs, values, question) is not None:
        hits.append(("dropped_count", f"omits {rel}, the source the question is about"))
    return hits


# Refactor 6: the lead of a yes or no question about past flooding is set
# by rule, not chosen by the model. The model still picks and orders the
# facts. A rule is simpler than a prompt and can be checked.
# ("Is there flood risk here?" asks about risk: a "No." from sensors with no events once answered it.)
_HAPPENED_RE = re.compile(r"^\W*(has|have|had|did|was|were|is there|are there)\b.*"
                          r"\bflood(?![- ]?(risk|zone|plain|map|insurance|hazard|prone))", re.IGNORECASE)
# One word may stand before the storm's name ("hurricane", "superstorm", or a misspelling of either).
# "Has it flooded after Ida?" asks about the time since, like "since Ida" (it was once answered
# "Yes." from Ida's own marks). "Marks surveyed after Ida" and "imagery after Ida" are about the storm.
_SINCE_RE = re.compile(r"\b(?:since|flood(?:ed)?(?: here| there)?\s+after)\s+(?:[a-z]+\s+)?(ida|sandy|(?:19|20)\d\d)\b",
                       re.IGNORECASE)
# "Before Sandy, had it flooded?": no source here says what happened before a storm or a year.
# ("Has it flooded before during Sandy" is not "before Sandy": only a storm's title may stand between.)
_BEFORE_RE = re.compile(r"\bbefore\s+(?:hurricane\s+|tropical storm\s+|superstorm\s+)?(ida|sandy|(?:19|20)\d\d)\b",
                        re.IGNORECASE)
# A few days, a named day or a month: the sources count over years, so their
# totals say neither yes nor no about it. ("The last few years" is not short.)
_SHORT_PERIOD_RE = re.compile(
    r"\b(this|last|past|over the) (week|weekend|month|night|morning|afternoon|evening)\b"
    r"|\b(yesterday|today|tonight|recently|lately)\b"
    r"|\b(on|last|this) (mon|tues|wednes|thurs|fri|satur|sun)day\b"
    r"|\b(\d+|a|a few|a couple of|two|three|four|five|six) (days?|weeks?|months?) ago\b"
    r"|\b(last|past) (few|couple of|\d+|two|three|four|five|six) (days|weeks|months)\b"
    r"|\b(in|last|this) (january|february|march|april|may|june|july|august|september|october|november|december)\b"
    r"|\b(last|this) (spring|summer|fall|autumn|winter)\b"
    # A period no rule here turns into dates: it must not be answered as if the question named none.
    r"|\b(years?|decades?) (ago|back)\b|\b(earlier|early|late|later) (this|last) year\b|\bthe other (day|week)\b",
    re.IGNORECASE)
_STORM_YEAR = {"ida": 2021, "sandy": 2012}
# The day each named storm struck NYC, so "since Ida" starts on its date,
# not on January 1 of its year.
_STORM_DATE = {"ida": (2021, 9, 1), "sandy": (2012, 10, 29)}
_FLOODNET_WINDOW_YEARS = 3


_YES_NO_RE = re.compile(r"^\W*(is|are|was|were|has|have|had|do|does|did|can|could|will|would|should)\b", re.IGNORECASE)


def is_yes_no_question(question: str) -> bool:
    """A question that can take a yes or no: it opens with a verb ("Has the
    block flooded"), not with what, which, where or how."""
    return bool(_YES_NO_RE.match(question or ""))


def is_past_event_question(question: str, focus: dict | None) -> bool:
    return ((focus or {}).get("time_frame") == "past" and bool(_HAPPENED_RE.search(question or ""))
            and not is_count_question(question))


def _period_start_date(question: str):
    """The first day of the asked period: a named storm's date, or January 1
    of a named year. None when the question names no period."""
    import datetime

    m = _SINCE_RE.search(question or "")
    if not m:
        return None
    w = m.group(1).lower()
    return datetime.date(*_STORM_DATE[w]) if w in _STORM_DATE else datetime.date(int(w), 1, 1)


def _period_start(question: str) -> int | None:
    m = _SINCE_RE.search(question or "")
    if not m:
        return None
    w = m.group(1).lower()
    return _STORM_YEAR.get(w) or int(w)


def _iso_date(text):
    import datetime

    try:
        return datetime.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def no_period(lead: str, source: str | None, question: str, values: dict | None) -> str:
    """What follows a "No." that rests on FloodNet when the question names
    no period: the day the sensors' record starts, so the no is not read as
    "never". Empty for any other lead, source or question."""
    v = (values or {}).get(source or "")
    if lead != "no" or source != "floodnet" or not isinstance(v, dict) or _period_start(question) is not None:
        return ""
    start = _iso_date(v.get("period_start"))
    return (f"The sensors' record quoted here starts on {start.isoformat()}, so this is a no for the time since then "
            "only.") if start else ""


def floodnet_rows(v: dict, point=None) -> tuple[list[dict], bool]:
    """(rows, complete): one row per sensor with verified events, as
    {"distance_m", "status", "events": [{"date", "max_depth_mm"}]}, nearest
    first; `distance_m` is None for an area. Read from the value's private
    `_rows` when it has one (every event, so `complete`). A value without it
    gives what its public fields hold: each sensor's `lat`, `lon`, `status`
    and `n_events`, with the events named in `highest_event`, `peak_event`
    and `flagged_peak_event` (not every event, so not `complete`). `point`
    is the queried (lat, lon), from which that fallback measures distance."""
    if isinstance(v.get("_rows"), list):
        return v["_rows"], True
    from app.geocode import _haversine_km

    known = [e for e in (v.get(k) for k in ("highest_event", "peak_event", "flagged_peak_event")) if isinstance(e, dict)]
    rows = []
    for s in v.get("sensors") or []:
        if not s.get("n_events"):
            continue
        d = (round(_haversine_km(point[0], point[1], s["lat"], s["lon"]) * 1000, 1)
             if point and s.get("lat") is not None and s.get("lon") is not None else None)
        events = {(str(e.get("start_time"))[:10], e.get("max_depth_mm")) for e in known
                  if e.get("deployment_id") == s.get("deployment_id")}
        rows.append({"distance_m": d, "status": s.get("status"),
                     "events": [{"date": day, "max_depth_mm": mm} for day, mm in sorted(events, key=str)]})
    return sorted(rows, key=lambda r: (r["distance_m"] is None, r["distance_m"] or 0)), False


def _local(e: dict) -> str:
    """The day an event is matched on: its New York date when the row
    carries one (app/context/floodnet.py), else its UTC date."""
    return e.get("local_date") or e.get("date") or ""


def _basis(rows: list[dict]) -> str:
    """"New York" or "UTC": which calendar the rows' days are in."""
    return "New York" if any("local_date" in e for r in rows for e in r.get("events") or []) else "UTC"


def nearest_m(doc_id: str, v: dict, point=None, since=None, until=None) -> float | None:
    """Metres from the queried address to the nearest record of flooding the
    source holds: a FloodNet sensor with a verified event (dated from
    `since` to `until` when given), or an Ida high-water mark. None for an
    area, or when the value gives no distance."""
    if doc_id == "ida_hwm":
        return v.get("nearest_dist_m")
    lo, hi = (since.isoformat() if since else ""), (until.isoformat() if until else "9999")
    return next((r["distance_m"] for r in floodnet_rows(v, point)[0] if r.get("distance_m") is not None
                 and (not (since or until) or any(lo <= _local(e) <= hi for e in r.get("events") or []))), None)


_NEAREST = {"floodnet": "FloodNet sensor with a verified flood event", "ida_hwm": "USGS high-water mark from Hurricane Ida"}


def nearest_record(sources: list[str], values: dict | None, since=None) -> tuple[str, float] | None:
    """(source, metres) for the nearest observed record among `sources`: a
    sensor with a verified event since `since`, or an Ida mark."""
    found = [(d, s) for s in sources if isinstance(v := (values or {}).get(s), dict) and s in _NEAREST
             and (d := nearest_m(s, v, (values or {}).get("_point"), since)) is not None]
    return (min(found)[1], min(found)[0]) if found else None


def near_lead(sources: list[str] | str, values: dict | None, since=None) -> str:
    """The lead for flooding recorded near an address and not on its block,
    with the distance to the nearest record of any kind in it (a sensor
    211 m off once led while an Ida mark stood 130 m away), cited."""
    hit = nearest_record([sources] if isinstance(sources, str) else sources, values, since)
    how_far = f": the nearest {_NEAREST[hit[0]]} is {hit[1]:.0f} m away [{hit[0]}]" if hit else ""
    return (f"Flooding was recorded near this address, not at it{how_far}. Riprap gives a plain yes about an address "
            f"only when such a record is within {BLOCK_M} m of it.")


def yes_lead(source: str | None, values: dict | None, since=None) -> str:
    """What follows a "Yes." about an address: the record it rests on and
    how far that is. Empty for an area or a source with no distance."""
    hit = nearest_record([source], values, since) if source else None
    return f"The record this rests on is a {_NEAREST[hit[0]]} {hit[1]:.0f} m from this address [{hit[0]}]." if hit else ""


_MONTH_NAMES = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_DAY_RE = re.compile(r"\b(" + "|".join(_MONTH_NAMES) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d\d)\b"
                     r"|\b((?:19|20)\d\d)-(\d\d)-(\d\d)\b|\b(\d{1,2})/(\d{1,2})/((?:19|20)\d\d)\b", re.IGNORECASE)
# The days each named storm's flooding fell on in the city: a question about one of them is about the storm.
_STORM_DAYS = {"ida": ((2021, 9, 1), (2021, 9, 2)), "sandy": ((2012, 10, 29), (2012, 10, 30))}


def named_day(question: str):
    """The calendar day a question names in full ("May 20, 2026",
    "2026-05-20", "5/20/2026"), or None."""
    import datetime

    m = _DAY_RE.search(question or "")
    if not m:
        return None
    mon, d, y, y2, m2, d2, m3, d3, y3 = m.groups()
    try:
        if mon:
            return datetime.date(int(y), _MONTH_NAMES.index(mon.lower()) + 1, int(d))
        return datetime.date(int(y2), int(m2), int(d2)) if y2 else datetime.date(int(y3), int(m3), int(d3))
    except ValueError:
        return None


def storm_of_day(question: str) -> str | None:
    """"ida" or "sandy" when the question names a day of that storm."""
    day = named_day(question)
    return next((w for w, days in _STORM_DAYS.items() if day and (day.year, day.month, day.day) in days), None)


def day_lead(question: str, docs: dict[str, str], values: dict | None) -> tuple[str, str, list[str]] | None:
    """(lead, sentence, facts) for "did it flood on <a named past day>",
    read from FloodNet's verified events dated that day (UTC). The lead is
    "day" with a sentence that says what the record holds for the day, or
    "cannot_answer" when the value does not date its events. None when the
    question names no day, or no sensor record came back."""
    day = named_day(question)
    v = (values or {}).get("floodnet")
    if not day or not isinstance(v, dict) or not docs.get("floodnet") or "n_flood_events_3y" not in v:
        return None
    if not v.get("n_sensors"):
        return "cannot_answer", "", ["floodnet"]
    rows, complete = floodnet_rows(v, (values or {}).get("_point"))
    start = _iso_date(v.get("period_start"))
    if start and day < start:
        return "day", (f"The FloodNet record quoted here starts on {start.isoformat()}, after {day.isoformat()}, so the "
                       "sensors say nothing about that day [floodnet]."), ["floodnet"]
    # A resident asks in local dates: an event that began at 9:59 pm on 11 June in New York is dated 12 June
    # in UTC, and the question about 11 June was once told no event was dated that day.
    hits = [(r, e) for r in rows for e in r.get("events") or [] if _local(e) == day.isoformat()]
    tz = f"({_basis(rows)} time)" if _basis(rows) == "New York" else "(UTC)"
    if not hits:
        if not complete:
            return "cannot_answer", "", ["floodnet"]
        n = v["n_sensors"]
        return "day", (f"FloodNet's verified record has no flood event dated {day.isoformat()} {tz} at the {n} "
                       f"sensor{'' if n == 1 else 's'} read for this place [floodnet]. That is not a record that the "
                       "street stayed dry: a sensor reads one spot, and events still to be verified are not counted."), ["floodnet"]
    n, deepest = len(hits), max((e.get("max_depth_mm") or 0) for _, e in hits)
    count = f"{n} flood event{'' if n == 1 else 's'}"
    near = min((r["distance_m"] for r, _ in hits if r.get("distance_m") is not None), default=None)
    if near is None:
        return "day", (f"FloodNet's verified record has {count} dated {day.isoformat()} {tz} at the sensors read for "
                       f"this place, the deepest {deepest:.0f} mm [floodnet]."), ["floodnet"]
    if near <= BLOCK_M:
        return "day", (f"FloodNet's verified record has {count} dated {day.isoformat()} {tz} at sensors within 600 m, "
                       f"the nearest of them {near:.0f} m from this address, the deepest {deepest:.0f} mm [floodnet]."), ["floodnet"]
    return "day", (f"Flooding was recorded near this address on {day.isoformat()} {tz}, not at it: FloodNet's verified "
                   f"record has {count} that day, at sensors the nearest of which is {near:.0f} m away, the deepest "
                   f"{deepest:.0f} mm [floodnet]."), ["floodnet"]


_SEASONS = {"spring": (3, 5), "summer": (6, 8), "fall": (9, 11), "autumn": (9, 11)}
_PERIOD_YEAR_RE = re.compile(r"(?<![-/\d])\b(20[012]\d)\b(?![-/]\d)")
_SEASON_YEAR_RE = re.compile(r"\b(spring|summer|fall|autumn) (?:of )?(20[012]\d)\b", re.I)
_MONTH_YEAR_RE = re.compile(r"\b(" + "|".join(_MONTH_NAMES) + r")[a-z]*\.? (?:of )?(20[012]\d)\b", re.I)
_LAST_N_RE = re.compile(r"\b(?:in|over|during|within) the (?:last|past) (?:(\d+|two|three|four|five|six|twelve|eighteen) )?"
                        r"(days?|weeks?|months?|years?)\b", re.I)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def asked_period(question: str, today=None):
    """(first day, last day, words for it) of the past period a question
    names: a year ("in 2024", "last year"), a season or a month of a year
    ("the summer of 2025", "June 2025"), a span of years, or "in the last
    N months". None when it names none, names a full day (named_day), or
    asks about the time since or before something (_SINCE_RE, _BEFORE_RE).
    A house number is not a year, and a clause without a past period it can
    date is left to _SHORT_PERIOD_RE."""
    import calendar
    import datetime

    q = question or ""
    today = today or datetime.date.today()
    if named_day(q) or _SINCE_RE.search(q) or _BEFORE_RE.search(q):
        return None
    if m := _SEASON_YEAR_RE.search(q):
        (a, b), y = _SEASONS[m.group(1).lower()], int(m.group(2))
        return (datetime.date(y, a, 1), datetime.date(y, b, calendar.monthrange(y, b)[1]),
                f"the {m.group(1).lower()} of {y} ({calendar.month_name[a]} to {calendar.month_name[b]})")
    if m := _MONTH_YEAR_RE.search(q):
        mon, y = _MONTH_NAMES.index(m.group(1).lower()[:3]) + 1, int(m.group(2))
        return datetime.date(y, mon, 1), datetime.date(y, mon, calendar.monthrange(y, mon)[1]), f"{calendar.month_name[mon]} {y}"
    if m := _LAST_N_RE.search(q):
        n = int(_WORDS.get((m.group(1) or "one").lower(), 1) if not (m.group(1) or "").isdigit() else m.group(1))
        unit = m.group(2).lower().rstrip("s")
        first = today - datetime.timedelta(days=n * _UNIT_DAYS[unit])
        return first, today, f"the last {f'{n} {unit}s' if n != 1 else unit} (since {first.isoformat()})"
    if re.search(r"\b(last|this) year\b", q, re.I):
        y = today.year - (1 if re.search(r"\blast year\b", q, re.I) else 0)
        return datetime.date(y, 1, 1), datetime.date(y, 12, 31), str(y)
    # A year that is not a house number ("2024 Grand Concourse") or part of an address ("20-24 ...").
    from riprap.core.burr.place import extract_address

    span = extract_address(q) or ""
    years = sorted({int(y) for y in _PERIOD_YEAR_RE.findall(q.replace(span, " ") if span else q)})
    if not years:
        return None
    label = str(years[0]) if len(years) == 1 else f"{years[0]} to {years[-1]}"
    return datetime.date(years[0], 1, 1), datetime.date(years[-1], 12, 31), label


def period_lead(question: str, docs: dict[str, str], values: dict | None, today=None) -> tuple[str, str, list[str]] | None:
    """(lead, sentence, facts) for "did it flood in <a year, a season, a
    month>", read only from the records dated in that period: FloodNet's
    verified events by their day, 311 by its calendar years, and Ida's
    marks when the period holds 1 September 2021. A yes or no about 2024
    once rested on events of 2025 and 2026. The lead is "period" with a
    sentence that carries its own yes or no (a no is worded for the
    sensors' record, never for the place), or "cannot_answer" with a
    sentence that says what period each record covers when none of them
    reaches the one asked. None when the question names no period."""
    import datetime

    today = today or datetime.date.today()
    period = asked_period(question, today)
    if not period:
        return None
    first, last, label = period
    if first > today:
        return "cannot_answer", f"The period asked about, {label}, has not begun, so no record here holds anything for it.", []
    last, q = min(last, today), (question or "").lower()
    complaints = "nyc311" if "nyc311" in docs else "nyc311_nta"
    names_sensors, names_311 = re.search(r"\bsensors?\b|floodnet", q), re.search(r"\b311\b|complaint", q)
    verdict, said, facts = None, [], []
    v = (values or {}).get("floodnet")
    if not (names_311 and not names_sensors) and isinstance(v, dict) and docs.get("floodnet") and v.get("n_sensors"):
        rows, complete = floodnet_rows(v, (values or {}).get("_point"))
        start, n = _iso_date(v.get("period_start")), v["n_sensors"]
        if not complete and (not start or first <= start):
            return None  # the whole record lies inside the period asked: the general rule reads its total
        facts.append("floodnet")
        if not start or last < start or not complete:
            said.append(f"The FloodNet record quoted here starts on {start.isoformat() if start else 'a date it does not give'}"
                        f"{', after ' + label if start and last < start else ''}, so it holds nothing for that period and "
                        "gives no yes or no about it [floodnet].")
        else:
            hits = [(r, e) for r in rows for e in r.get("events") or [] if first.isoformat() <= _local(e) <= last.isoformat()]
            days, tz = len({_local(e) for _, e in hits}), f" (by {_basis(rows)} date)"
            count = f"{len(hits)} flood event{'' if len(hits) == 1 else 's'} on {days} day{'' if days == 1 else 's'}"
            near = min((r["distance_m"] for r, _ in hits if r.get("distance_m") is not None), default=None)
            if hits and near is None:
                verdict = "yes"
                said.append(f"Yes, in {label}, at the sensors read for this area: FloodNet's verified record has {count} "
                            f"in that period{tz} [floodnet].")
            elif hits and near <= BLOCK_M:
                verdict = "yes"
                said.append(f"Yes, in {label}: FloodNet's verified record has {count} in that period{tz} at sensors "
                            f"within 600 m, the nearest of them {near:.0f} m from this address [floodnet].")
            elif hits:
                verdict = "near"
                said.append(f"Flooding was recorded near this address in {label}, not at it: FloodNet's verified record "
                            f"has {count} in that period{tz}, at sensors the nearest of which is {near:.0f} m away "
                            f"[floodnet]. Riprap gives a plain yes about an address only when such a record is within "
                            f"{BLOCK_M} m of it.")
            elif start <= first:
                verdict = "no"
                said.append(f"No, not in the sensors' record for {label}: FloodNet's verified record has no flood event "
                            f"in that period{tz} at the {n} sensor{'' if n == 1 else 's'} read for this place [floodnet]. "
                            "That is a no for those sensors only, not for the place: a sensor reads one spot, and events "
                            "still to be verified are not counted.")
            else:
                said.append(f"The FloodNet record quoted here starts on {start.isoformat()}, inside {label}, and has no "
                            "flood event from then to the end of that period; it does not cover the whole period, so "
                            "it gives no yes or no about it [floodnet].")
    elif isinstance(v, dict) and docs.get("floodnet") and not (names_311 and not names_sensors):
        facts.append("floodnet")  # its sentence says no sensor is in range
    marks = (values or {}).get("ida_hwm")
    if first <= datetime.date(*_STORM_DATE["ida"]) <= last and isinstance(marks, dict) and marks.get("n_within_radius") \
            and docs.get("ida_hwm") and not (names_sensors or names_311):
        d = marks.get("nearest_dist_m")
        facts.append("ida_hwm")
        if verdict != "yes":
            verdict = "yes" if d is None or d <= BLOCK_M else verdict or "near"
        said.append("USGS surveyed a high-water mark from Hurricane Ida (1 September 2021)"
                    + (f" {d:.0f} m from this address" if d is not None else " near this address") + " [ida_hwm].")
    c = (values or {}).get(complaints)
    if not (names_sensors and not names_311) and isinstance(c, dict) and docs.get(complaints) and "by_year" in c:
        facts.append(complaints)
        since = _iso_date(c.get("since"))
        whole = first.year == last.year and (first.month, first.day) == (1, 1) and (
            (last.month, last.day) == (12, 31) or last == today)
        # "In the last five years" is the 311 count's own window (a day's slack: the window is cut at midnight UTC).
        window = bool(since) and last == today and abs((first - since).days) <= 1
        if window and not said and verdict is None:
            return None  # nothing else was read for the period: the general rule answers from the window's total
        if window:
            k = int(c.get("n") or 0)
            said.append(f"{k} complaint{'' if k == 1 else 's'} to 311 about flooding and sewer backups {'was' if k == 1 else 'were'} "
                        f"filed in {label}, the whole window of the count quoted here; a count of reports, not of floods "
                        f"[{complaints}].")
        elif whole and since and since <= first:
            k = int((c.get("by_year") or {}).get(str(first.year), 0))
            if names_311 and verdict is None:
                verdict = "yes" if k else "no"
            said.append(f"{k} complaint{'' if k == 1 else 's'} to 311 about flooding and sewer backups {'was' if k == 1 else 'were'} "
                        f"filed in {first.year}{' so far' if last == today and first.year == today.year else ''}, by the "
                        f"year each was filed; a count of reports, not of floods [{complaints}].")
        else:
            said.append(f"The 311 count quoted here {'starts on ' + since.isoformat() if since else 'covers its own window'} "
                        f"and is split by calendar year only, so it gives no count for {label} [{complaints}].")
    if not said and not facts:
        return None
    if not said:
        said.append(f"No record here is dated within {label}.")
    return ("period" if verdict else "cannot_answer"), " ".join(said), facts


def _event(doc_id: str, v: dict, start: int | None, this_year: int, start_date=None, today=None,
           point=None) -> bool | str | None:
    """True: the source reports a flood event in the asked period, on the
    block when the place is an address. NEAR: it reports one farther than
    BLOCK_M from the address. False: it answered and reports none in the
    period. None: it cannot say (no value, unavailable, or its window does
    not cover the period)."""
    if v.get("available") is False or v.get("error"):
        return None
    if doc_id in ("nyc311", "nyc311_nta") and "n" in v:
        by_year = {int(y): n for y, n in (v.get("by_year") or {}).items()}
        if start is None:
            return v["n"] > 0
        if sum(n for y, n in by_year.items() if y > start):
            return True
        # Events in the start year itself may fall before the event named;
        # and a window that starts after the period cannot show "none".
        years = int(v.get("years") or 0)
        if start_date and today:
            # The window runs back `years` from today: it covers the period
            # only if it starts on or before the period's first day.
            try:
                window_start = today.replace(year=today.year - years)
            except ValueError:  # February 29
                window_start = today.replace(year=today.year - years, day=28)
            covers = window_start <= start_date
        else:
            covers = this_year - years <= start
        return None if by_year.get(start) or not covers else False
    if doc_id == "floodnet" and "n_flood_events_3y" in v:
        if v.get("n_sensors") == 0:
            return None  # no sensor in range: silence, not "no flooding"
        # The record starts on the value's period_start: the 3-year window's
        # first day, or the earliest install date when every sensor is younger
        # (a sensor installed last month with no events once answered "since
        # Ida?" with "No."). Compared as dates when the question names a day.
        recorded_from = _iso_date(v.get("period_start"))
        if recorded_from and start_date:
            covers, within = recorded_from <= start_date, recorded_from >= start_date
        else:
            window_start = recorded_from.year if recorded_from else this_year - _FLOODNET_WINDOW_YEARS
            covers, within = start is None or window_start <= start, start is None or window_start >= start
        if v["n_flood_events_3y"] > 0:
            # Every counted event is one a person at FloodNet verified, so it counts whatever the
            # sensor's status is today: the status is of the sensor now, not of the event then, and
            # the sentence still quotes it. (Events at sensors not listed "good" once gave no yes.)
            if not within:
                # "Since 2025", asked of a record that starts in 2023: the events dated from then on, when
                # every event is in hand; the period's total is not all in the period asked.
                rows, complete = floodnet_rows(v, point)
                if not (complete and start_date):
                    return None
                if not any(_local(e) >= start_date.isoformat() for r in rows for e in r.get("events") or []):
                    return False
            near = nearest_m(doc_id, v, point, None if within else start_date)
            return NEAR if near is not None and near > BLOCK_M else True
        return False if covers else None
    if doc_id == "ida_hwm" and "n_within_radius" in v:
        # USGS surveyed marks at selected sites only: none nearby does not
        # show the area stayed dry. A mark says the block flooded only when it
        # is on or beside the block; one 700 m away says the neighbourhood did.
        near = v.get("nearest_dist_m")
        return (True if near is None or near <= BLOCK_M else NEAR) if v["n_within_radius"] > 0 else None
    if doc_id == "sandy_inundation" and "inside" in v:
        return bool(v["inside"])
    return None


def _past_event_verdict(question: str, docs: dict[str, str], values: dict | None,
                        this_year: int | None = None) -> tuple[list[str], dict[str, bool | None]]:
    """The sources a past-event question rests on, in precedence order, and
    what each reports for the asked period (see _event)."""
    import datetime

    year = this_year or datetime.date.today().year
    q = (question or "").lower()
    start = _period_start(question)
    storm = _storm_record(question)
    complaints = "nyc311" if "nyc311" in docs else "nyc311_nta"
    if storm and start is None:
        relevant = [storm]  # "during Ida", "inside the area Sandy flooded": the storm's own record
    elif re.search(r"\bsensors?\b|floodnet", q):
        relevant = ["floodnet"]  # the question names the source
    elif re.search(r"\b311\b|complaint", q):
        relevant = [complaints]
    else:
        relevant = ["floodnet", complaints]  # measured before proxy: FloodNet leads when it answers
    start_date = _period_start_date(question)
    today = datetime.date.today()
    if this_year:
        today = today.replace(year=this_year, day=min(today.day, 28))
    verdict = {i: _event(i, v, start, year, start_date, today, (values or {}).get("_point")) for i in relevant
               if isinstance(v := (values or {}).get(i), dict) and docs.get(i)}
    return relevant, verdict


def past_event_source(question: str, focus: dict | None, lead: str, docs: dict[str, str],
                      values: dict | None, this_year: int | None = None) -> str | None:
    """The source a rule-set "yes" or "no" rests on: the first relevant
    source reporting an event for "yes", the first relevant source for "no"."""
    if lead not in ("yes", "no", "near") or not is_past_event_question(question, focus):
        return None
    relevant, verdict = _past_event_verdict(question, docs, values, this_year)
    if lead == "near":
        return next((i for i in relevant if verdict.get(i) == NEAR), None)
    if lead == "yes":
        return next((i for i in relevant if verdict.get(i) is True), None)
    return next((i for i in relevant if i in verdict), None)


def _storm_record(question: str) -> str | None:
    """The named storm's own record: ida_hwm for Ida, sandy_inundation for
    Sandy. A question that names a day of the storm ("on September 1, 2021")
    names the storm."""
    q = (question or "").lower()
    day = storm_of_day(q)
    return next((d for w, d in (("ida", "ida_hwm"), ("sandy", "sandy_inundation")) if w == day or re.search(rf"\b{w}\b", q)),
                None)


def _storm_reports(doc_id: str, values: dict | None) -> bool:
    """The storm's record reports something at this place: marks nearby, or
    the address inside the extent."""
    v = (values or {}).get(doc_id)
    if not isinstance(v, dict):
        return False
    return bool(v.get("n_within_radius")) if doc_id == "ida_hwm" else bool(v.get("inside"))


def past_event_lead(question: str, focus: dict | None, facts: list[str], docs: dict[str, str],
                    values: dict | None, this_year: int | None = None) -> tuple[str, list[str]] | None:
    """`_past_event_lead`, and for "since Ida" the Ida mark sentence with
    it whenever a mark is in range: the marks do not set the yes or no
    ("since" is read as the time after the storm), but an answer about the
    time since Ida once left out a mark 130 m from the address. Never under
    a "No."."""
    out = _past_event_lead(question, focus, facts, docs, values, this_year)
    marks = (values or {}).get("ida_hwm")
    if (out and out[0] != "no" and _storm_record(question) == "ida_hwm" and _period_start(question) is not None
            and isinstance(marks, dict) and marks.get("n_within_radius") and docs.get("ida_hwm") and "ida_hwm" not in out[1]):
        return out[0], [*out[1], "ida_hwm"]
    return out


def _past_event_lead(question: str, focus: dict | None, facts: list[str], docs: dict[str, str],
                     values: dict | None, this_year: int | None = None) -> tuple[str, list[str]] | None:
    """(lead, facts) for a yes or no question about past flooding, or None
    for any other question. `yes` when a relevant observed source reports an
    event in the asked period; `no` only when every relevant source answered
    and reported none; `cannot_answer` otherwise. A source the rule relies on is added to
    the facts when the model left it out, so the lead is always cited. Under
    `cannot_answer` the facts are the relevant sources that did return a
    sentence ("No FloodNet sensors deployed within 600 m"), so the reader
    sees why the sources are silent."""
    if not is_past_event_question(question, focus):
        return None
    relevant, verdict = _past_event_verdict(question, docs, values, this_year)
    if ((_SHORT_PERIOD_RE.search(question or "") or (not _storm_record(question) and period_lead(question, docs, values)))
            and _period_start(question) is None) \
            or _BEFORE_RE.search(question or ""):
        # "Did it flood this weekend?", "on Monday?": the sources count over
        # years, and a total over three years says neither yes nor no about a
        # few days. "Before Sandy?": no source here reaches back before it.
        # The record is quoted (its newest event is dated), with no lead.
        return "facts", [i for i in relevant if i in verdict and not unavailable(i, docs, values)]
    positive = [i for i, e in verdict.items() if e is True]
    nearby = [i for i, e in verdict.items() if e == NEAR]
    if nearby and all(i in ("nyc311", "nyc311_nta") for i in positive):
        # A sensor 400 m off, or a mark 174 m off, recorded flooding: that is "near this address", with the
        # distance in the lead, and not a "Yes." about the address (its block is within BLOCK_M).
        return "near", [*nearby, *(i for i in relevant if i not in nearby and i in verdict
                                   and not unavailable(i, docs, values))]
    if positive and all(i in ("nyc311", "nyc311_nta") for i in positive) and not _ASKS_REPORTS_RE.search(question or ""):
        # 311 requests are reports, most of them sewer backups and clogged
        # basins: alone they do not make "has it flooded" a Yes. The count is
        # quoted with no yes or no. "Have people reported flooding to 311"
        # asks about the reports and keeps its yes.
        return "facts", [*positive, *(i for i in relevant if i not in positive and i in verdict
                                      and not unavailable(i, docs, values))]
    if positive:
        # A "yes" quotes only the evidence for yes: the sources that report an
        # event, and the storm's own record when it reports something here.
        # FEMA zones, DEP scenarios or terrain under a "Yes." read as
        # counter-evidence; they stay in the evidence table. The source the
        # rule relied on (the key sentence, lead_fact) comes first.
        storm = _storm_record(question)
        keep = set(positive) | ({storm} if storm and _storm_reports(storm, values) else set())
        return "yes", [positive[0], *(f for f in facts if f in keep and f != positive[0])]
    if len(verdict) == len(relevant) and all(e is False for e in verdict.values()):
        # A "no" rests on the relevant sources alone: a positive fact about
        # something else (a 311 count for a sensor question) is not shown under it.
        return "no", [f for f in facts if f in relevant] + [i for i in relevant if i not in facts]
    return "cannot_answer", [i for i in relevant if i in verdict and not unavailable(i, docs, values)]
