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
    # ("1 sensor ... is flagged ..., so its depths are not used for the peak")
    # without turning 28 events into an absence.
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


# A DEP stormwater scenario named in a question, by its year, and the words
# that mark a stormwater question (not a sea-level one).
_DEP_YEAR = ((re.compile(r"\b2080\b|\bextre+m", re.I), "dep_extreme_2080"), (re.compile(r"\b2050\b"), "dep_moderate_2050"),
             (re.compile(r"\bcurrent\b", re.I), "dep_moderate_current"))
_STORMWATER_RE = re.compile(r"stormwater|\bdep\b|\bscenario\b", re.I)
_NOT_STORMWATER_RE = re.compile(r"sea.level|surge|\btide", re.I)


def dep_scenario_asked(question: str) -> str | None:
    """The DEP stormwater scenario pebble id ("dep_moderate_2050") a question
    names ("What does the 2050 stormwater scenario show?"), or None when it
    names none, or more than one, or asks about sea level."""
    q = question or ""
    if not _STORMWATER_RE.search(q) or _NOT_STORMWATER_RE.search(q):
        return None
    named = [pid for pat, pid in _DEP_YEAR if pat.search(q)]
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


# How near an Ida high-water mark must be to say "yes, this block flooded".
# ponytail: one fixed distance (a long Queens block); use the block's own geometry if the yes ever needs to be finer.
IDA_BLOCK_M = 250
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
    if rel not in ("nyc311", "nyc311_nta") or not isinstance(v, dict) or "by_year" not in v:
        return kind_lead(q, docs, values), False
    today = today or datetime.date.today()
    m = _YEAR_RE.search(q)
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
        return (f"{n} flood-related 311 complaint{'s' if n != 1 else ''} filed since the start of {since.year}, "
                "by the year each was filed."), False
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
    return (f"{n} flood-related 311 complaint{'s' if n != 1 else ''} filed in {year}"
            f"{' so far' if year == today.year else ''}, by the year each was filed."), False


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
            f"descriptor{'s' if ' and ' in names else ''} {names}.")


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
    if lead in ("cannot_answer", "experimental", "no_prediction"):
        return []  # no yes, no or count to check: silence, or a neutral lead set by code
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
    r"|\b(last|this) (spring|summer|fall|autumn|winter)\b",
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


def _event(doc_id: str, v: dict, start: int | None, this_year: int, start_date=None, today=None) -> bool | None:
    """True: the source reports a flood event in the asked period. False: it
    answered and reports none in the period. None: it cannot say (no value,
    unavailable, or its window does not cover the period)."""
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
        window_start = this_year - _FLOODNET_WINDOW_YEARS
        if v["n_flood_events_3y"] > 0:
            # Events only at sensors FloodNet flags for maintenance do not
            # settle it: the sentence quotes them with the flag, and no yes.
            if not v.get("n_flood_events_good_3y", v["n_flood_events_3y"]):
                return None
            return True if start is None or window_start >= start else None
        return False if start is None or window_start <= start else None
    if doc_id == "ida_hwm" and "n_within_radius" in v:
        # USGS surveyed marks at selected sites only: none nearby does not
        # show the area stayed dry. A mark says the block flooded only when it
        # is on or beside the block; one 700 m away says the neighbourhood did.
        near = v.get("nearest_dist_m")
        return True if v["n_within_radius"] > 0 and (near is None or near <= IDA_BLOCK_M) else None
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
    verdict = {i: _event(i, v, start, year, start_date, today) for i in relevant
               if isinstance(v := (values or {}).get(i), dict) and docs.get(i)}
    return relevant, verdict


def past_event_source(question: str, focus: dict | None, lead: str, docs: dict[str, str],
                      values: dict | None, this_year: int | None = None) -> str | None:
    """The source a rule-set "yes" or "no" rests on: the first relevant
    source reporting an event for "yes", the first relevant source for "no"."""
    if lead not in ("yes", "no") or not is_past_event_question(question, focus):
        return None
    relevant, verdict = _past_event_verdict(question, docs, values, this_year)
    if lead == "yes":
        return next((i for i in relevant if verdict.get(i) is True), None)
    return next((i for i in relevant if i in verdict), None)


def _storm_record(question: str) -> str | None:
    """The named storm's own record: ida_hwm for Ida, sandy_inundation for Sandy."""
    q = (question or "").lower()
    return next((d for w, d in (("ida", "ida_hwm"), ("sandy", "sandy_inundation")) if re.search(rf"\b{w}\b", q)),
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
    if (_SHORT_PERIOD_RE.search(question or "") and _period_start(question) is None) or _BEFORE_RE.search(question or ""):
        # "Did it flood this weekend?", "on Monday?": the sources count over
        # years, and a total over three years says neither yes nor no about a
        # few days. "Before Sandy?": no source here reaches back before it.
        # The record is quoted (its newest event is dated), with no lead.
        return "facts", [i for i in relevant if i in verdict and not unavailable(i, docs, values)]
    positive = [i for i, e in verdict.items() if e is True]
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
