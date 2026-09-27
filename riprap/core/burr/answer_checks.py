"""Deterministic checks on answer claims against their cited evidence.

The claim verifier checks citations and numbers. These checks cover five
ways an answer can still misstate its evidence (refactor 3):

  absence       "no", "none", "not", "zero", "without" about a source whose
                cited document reports a result
  universal     "all", "every", "both", or "the <assets> are", where the
                cited register counts fewer inside than in total
  inference     "which means", "indicating", "therefore" ... joining two
                sources, or a warning or forecast stated as an observation
  dropped_count the answer omits the count or value of the source the
                question is about, when that source produced one
  datum         an elevation stated without its datum, or without the
                height above ground when the source gives one

Every check is a pattern over words; none reads meaning. They are used by
scripts/answer_audit.py and, in guarded answer mode, by the verifier.
"""

from __future__ import annotations

import re

CLASSES = ("absence", "universal", "inference", "dropped_count", "datum")

_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
               "eighty": 80, "ninety": 90})
_WORD_RE = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)

ABSENCE_RE = re.compile(r"\b(no|none|not|zero|without|never)\b|n't\b", re.IGNORECASE)
# A document that itself reports an absence or a zero.
_DOC_ABSENCE_RE = re.compile(r"\b(no|none|not|zero|without|outside|never)\b|(?<![\d.,])0(?![\d.,])",
                             re.IGNORECASE)
_UNIVERSAL_RE = re.compile(r"\b(all|every|both|each of)\b", re.IGNORECASE)
_THE_ASSETS_RE = re.compile(
    r"^\W*the\s+(?:[\w'-]+\s+){0,3}?(developments|entrances|schools|hospitals|sensors|gauges)\b"
    r"[^.]*?\b(are|were)\b", re.IGNORECASE)
# "{n} <assets> within {r} m of this address: {a} inside the 2012 Sandy ... and {b} inside the DEP ..."
_REGISTER_RE = re.compile(r"(\d[\d,]*)\s[^:]*?within\s[\d,.]+\s?m\b[^:]*:\s*(\d+) inside the 2012 Sandy"
                          r"[^.]*?(\d+) inside the DEP", re.IGNORECASE)
_INFER_RE = re.compile(r"\b(which means|meaning that|indicating|indicates|suggests|suggesting|therefore"
                       r"|thus|as a result)\b|,\s*so\b", re.IGNORECASE)
_WARNING_DOC_RE = re.compile(r"\b(warning|watch|advisory|statement|forecast|projects?|expects?)\b",
                             re.IGNORECASE)
_OBSERVED_RE = re.compile(
    r"\b(flooding|inundation) (is|are) (currently |now |actively )?(occurring|happening|underway|taking place)\b"
    r"|\bcurrently (flooding|flooded|underwater|experiencing flooding)\b"
    r"|\b(is|are) (currently |now )(flooding|flooded|underwater)\b", re.IGNORECASE)
_ELEVATION_RE = re.compile(r"\belevation\b", re.IGNORECASE)
_DATUM_RE = re.compile(r"\b(navd ?88|ngvd ?29|mllw|mean lower low water|mean sea level|datum|above ground"
                       r"|above grade|height above)\b", re.IGNORECASE)
_DISTANCE_OR_YEAR_RE = re.compile(r"^\s?(m|km|meters?|metres?|mi|miles?)\b", re.IGNORECASE)

# Question words -> the doc_ids of the source that answers them, most
# specific first. Used only by the dropped_count check.
RELEVANT = (
    (re.compile(r"subway|entrance", re.I), ("mta_entrance_exposure",)),
    (re.compile(r"school", re.I), ("doe_school_exposure",)),
    (re.compile(r"hospital", re.I), ("doh_hospital_exposure",)),
    (re.compile(r"nycha|public housing", re.I), ("nycha_development_exposure",)),
    (re.compile(r"\b311\b|complaint", re.I), ("nyc311", "nyc311_nta")),
    (re.compile(r"sensor|floodnet", re.I), ("floodnet",)),
    (re.compile(r"high.water|\bida\b", re.I), ("ida_hwm",)),
    (re.compile(r"\brain|precip", re.I), ("nws_obs#precip",)),
    (re.compile(r"\btide|water level|harbor", re.I), ("noaa_tides",)),
    (re.compile(r"sea.level", re.I), ("npcc4_slr",)),
    (re.compile(r"\balert|warning", re.I), ("nws_alerts",)),
)


def words_to_digits(text: str) -> str:
    """'Four schools' -> '4 schools', so number words are checked like digits."""
    return _WORD_RE.sub(lambda m: str(_WORDS[m.group(1).lower()]), text)


def reports_result(doc: str) -> bool:
    """True when a document reports something present, not an absence."""
    return bool(doc) and not _DOC_ABSENCE_RE.search(doc)


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


def check_claim(text: str, doc_ids: list[str], docs: dict[str, str]) -> list[tuple[str, str]]:
    """Per-claim checks (absence, universal, inference, datum). Returns
    (class, reason) pairs; empty when the claim passes."""
    hits: list[tuple[str, str]] = []
    cited = {i: docs.get(i, "") for i in doc_ids}
    if ABSENCE_RE.search(text):
        positive = [i for i, d in cited.items() if reports_result(d)]
        if positive:
            hits.append(("absence", f"states an absence, but {', '.join(positive)} reports a result"))
    universal = _UNIVERSAL_RE.search(text) or _THE_ASSETS_RE.search(text)
    if universal:
        for i, d in cited.items():
            counts = _register_counts(d)
            if not counts:
                continue
            total, sandy, dep = counts
            scoped = [c for c, pat in ((sandy, r"sandy"), (dep, r"\bdep\b|stormwater|2080"))
                      if re.search(pat, text, re.I)] or [sandy, dep]
            if any(c < total for c in scoped):
                hits.append(("universal", f"implies all, but {i} counts {min(scoped)} of {total}"))
    if _INFER_RE.search(text) and len(set(doc_ids)) >= 2:
        hits.append(("inference", "draws a conclusion joining two sources"))
    elif _OBSERVED_RE.search(text) and any(_WARNING_DOC_RE.search(d) for d in (text, *cited.values())):
        hits.append(("inference", "states a warning or forecast as an observation"))
    if _ELEVATION_RE.search(text) and re.search(r"\d", text):
        if not _DATUM_RE.search(text):
            hits.append(("datum", "states an elevation without its datum"))
        elif any("above ground" in d.lower() for d in cited.values()) and "above ground" not in text.lower():
            hits.append(("datum", "omits the height above ground the source gives"))
    return hits


def check_answer(answer_texts: list[str], question: str, docs: dict[str, str]) -> list[tuple[str, str]]:
    """Answer-level check (dropped_count). An empty answer (the cannot-answer
    line) is not flagged: saying the evidence does not answer is honest."""
    if not answer_texts:
        return []
    rel = relevant_doc(question, docs)
    if rel is None:
        return []
    counts = count_numbers(docs[rel], _NEAR.get(rel, ""))
    if not counts:
        return []
    from riprap.core.burr.synthesis import _parse

    # Exact equality: the verifier's unit-conversion tolerance would let
    # "0.76 ft" (2.49 m) stand in for a count of 2.
    said = {p[0] for n in count_numbers(words_to_digits(" ".join(answer_texts))) if (p := _parse(n))}
    lead = _parse(counts[0])
    if lead and lead[0] == 0 and ABSENCE_RE.search(" ".join(answer_texts)):
        return []  # "no hospitals" states a count of 0
    if lead and lead[0] not in said:
        return [("dropped_count", f"omits the figure from {rel} ({counts[0]})")]
    return []


def check_lead(lead: str, facts: list[str], question: str, docs: dict[str, str]) -> list[tuple[str, str]]:
    """Extractive mode: check the model's lead against the facts it chose.
    The facts are template sentences shown verbatim, so only the lead and
    the choice of facts can be wrong."""
    if lead == "cannot_answer":
        return []
    if not facts:
        return [("empty", f"lead {lead!r} with no facts")]
    texts = [docs.get(i, "") for i in facts]
    hits: list[tuple[str, str]] = []
    positive = [i for i, t in zip(facts, texts, strict=True) if reports_result(t)]
    if lead == "no" and positive:
        hits.append(("absence", f"lead 'no', but {', '.join(positive)} reports a result"))
    if lead == "yes":
        if not positive:
            hits.append(("absence", "lead 'yes', but every fact reports an absence"))
        partial = [i for i, t in zip(facts, texts, strict=True) if (c := _register_counts(t)) and min(c[1:]) < c[0]]
        if partial:
            hits.append(("universal", f"lead 'yes', but {', '.join(partial)} counts only some; use 'partly'"))
    if lead == "count" and not any(count_numbers(t) for t in texts):
        hits.append(("dropped_count", "lead 'count' needs a fact with a count"))
    rel = relevant_doc(question, docs)
    if rel and rel not in facts and count_numbers(docs[rel], _NEAR.get(rel, "")):
        hits.append(("dropped_count", f"omits {rel}, the source the question is about"))
    return hits
