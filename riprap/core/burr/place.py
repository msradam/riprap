"""Find the place in a query without an LLM (refactor 5).

The order matters, and each step works on the words that name a place,
never on the whole question:

  1. a community district reference ("QN12", "QN 12", "Queens CB 12",
     "Community District 12 Queens", "Brooklyn 15"), checked against the
     59 real districts; an invalid one is refused with the nearest valid
     form;
  2. a street address span (house number, street, optional borough,
     neighbourhood or ZIP), which alone goes to the geocoder;
  3. only then a short place phrase ("Red Hook", "Jamaica") for a
     neighbourhood lookup, marked as uncertain.

A borough name on its own is not a place: "Queens" used to resolve to the
first Queens neighbourhood (Astoria) for any question that mentioned it.
"""

from __future__ import annotations

import re

# The 59 community districts: 12 in Manhattan and the Bronx, 18 in
# Brooklyn, 14 in Queens, 3 on Staten Island.
DISTRICTS = {"MN": 12, "BX": 12, "BK": 18, "QN": 14, "SI": 3}
BOROUGH_NAMES = {"MN": "Manhattan", "BX": "the Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}
_BOROUGH = {"manhattan": "MN", "new york county": "MN", "the bronx": "BX", "bronx": "BX", "brooklyn": "BK",
            "kings county": "BK", "queens": "QN", "staten island": "SI", "richmond county": "SI"}
_BORO_WORDS = r"(manhattan|new york county|the bronx|bronx|brooklyn|kings county|queens|staten island|richmond county)"
_KIND = r"(?:community\s+(?:board|district)|board|district|cb|cd)"
_NUM = r"(?:no\.?\s*|number\s+|#\s*)?(\d{1,3})(?![\d-])(?!\s*(?:st|nd|rd|th)\b)"

_CODE_RE = re.compile(r"\b(MN|BX|BK|QN|SI)\s*-?\s*(\d{1,3})\b(?![\d-])", re.IGNORECASE)
_BORO_KIND_NUM_RE = re.compile(rf"\b{_BORO_WORDS}\s*,?\s*{_KIND}\s*{_NUM}", re.IGNORECASE)
_KIND_NUM_BORO_RE = re.compile(rf"\b{_KIND}\s*{_NUM}(?:\s*(?:,|in|of)?\s*{_BORO_WORDS})?", re.IGNORECASE)
_BORO_NUM_RE = re.compile(rf"^\s*{_BORO_WORDS}\s+(\d{{1,2}})\s*[?.!]?\s*$", re.IGNORECASE)

_SUFFIX = (r"(?:street|st|avenue|ave|av|boulevard|blvd|road|rd|place|pl|drive|dr|lane|ln|parkway|pkwy|terrace|ter"
           r"|court|ct|way|plaza|plz|square|sq|highway|hwy|expressway|expy|turnpike|tpke|loop|walk|row|crescent"
           r"|circle|path|slip|alley|broadway|bowery|concourse)")
# Street words need a letter and are never a preposition, so "311 near 200
# Water Street" finds "200 Water Street", not "311 near 200 Water Street".
_STREET_WORD = r"(?!(?:near|at|in|on|around|of|for|by|from|to|and|or)\b)[A-Za-z0-9'.]*[A-Za-z][A-Za-z0-9'.]*"
# A quadrant after the street ("Pennsylvania Ave NW") stays with it.
_ADDRESS_RE = re.compile(rf"\b(\d{{1,6}}(?:-\d{{1,4}})?[A-Za-z]?)\s+((?:{_STREET_WORD}\s+){{0,5}}?{_SUFFIX})\b\.?"
                         r"(?:\s+(?:NW|NE|SW|SE)\b)?", re.IGNORECASE)
# After the street: ", Queens", " in the Bronx", ", Red Hook, Brooklyn", ", NY", " 11423".
_TAIL_AREA_RE = re.compile(r"^\s*(?:,\s*|\s+in\s+(?:the\s+)?)([A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,2})")
# A borough right after the street, with or without a comma, in any case or
# common abbreviation: "200 Water Street Manhattan", "1310 Surf Ave, Bklyn".
# Without it the geocoder picks a borough itself (Water Street in Dumbo).
_TAIL_BORO_RE = re.compile(r"^\s*,?\s*(?:in\s+)?(?:the\s+)?(manhattan|brooklyn|bklyn|bkln|queens|qns|bronx|bx"
                           r"|staten island)\b\.?", re.IGNORECASE)
_BORO_FULL = {"manhattan": "Manhattan", "brooklyn": "Brooklyn", "bklyn": "Brooklyn", "bkln": "Brooklyn",
              "queens": "Queens", "qns": "Queens", "bronx": "Bronx", "bx": "Bronx", "staten island": "Staten Island"}
# A street that is its own name; any other suffix needs a street word before it.
_STANDALONE_STREETS = {"broadway", "bowery"}
_TAIL_STATE_RE = re.compile(r"^\s*,?\s*(?:NY|New York)\b(?!\s+(?:City|County))")
_TAIL_ZIP_RE = re.compile(r"^\s*,?\s*(\d{5})\b")
_CAPS_RUN_RE = re.compile(r"\b[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*")
# Two streets joined by "and", "&" or "at", with no house number: neither
# geocoder Riprap uses places an intersection (NYC GeoSearch parses the
# cross street and returns nothing; Nominatim returns nothing), so it is
# refused with the reason rather than sent to a street's nearest point.
_INTERSECTION_RE = re.compile(rf"\b((?:{_STREET_WORD}\s+){{0,3}}?{_SUFFIX})\s+(?:and|&|at)\s+"
                              rf"((?:{_STREET_WORD}\s+){{0,3}}?{_SUFFIX})\b", re.IGNORECASE)
_ZIP_ONLY_RE = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*[?.!]?\s*$")
# Capitalised words that start a question or name an agency or storm, not a place.
_NOT_PLACE = {"is", "are", "was", "were", "what", "how", "has", "have", "does", "did", "do", "tell", "show",
              "can", "could", "will", "would", "which", "where", "when", "why", "who", "the", "a", "an", "i",
              "nyc", "new", "york", "city", "fema", "dep", "nws", "noaa", "usgs", "mta", "nycha", "doe", "sandy",
              "ida", "hurricane", "floodnet", "npcc4", "ny"}


def _district(prefix: str, n: int) -> tuple[str | None, str | None]:
    prefix = prefix.upper()
    count = DISTRICTS[prefix]
    if 1 <= n <= count:
        return f"{prefix}{n:02d}", None
    nearest = f"{prefix}{min(max(n, 1), count):02d}"
    return None, (f"{BOROUGH_NAMES[prefix]} has community districts {prefix}01 to {prefix}{count:02d}, so "
                  f"{prefix}{n:02d} is not one of them. Did you mean {nearest}?")


def parse_district(text: str) -> tuple[str | None, str | None]:
    """(district code, refusal). Both None when the text names no district."""
    t = text or ""
    m = _CODE_RE.search(t)
    if m:
        return _district(m.group(1), int(m.group(2)))
    m = _BORO_KIND_NUM_RE.search(t)
    if m:
        return _district(_BOROUGH[m.group(1).lower()], int(m.group(2)))
    m = _KIND_NUM_BORO_RE.search(t)
    if m:
        if m.group(2):
            return _district(_BOROUGH[m.group(2).lower()], int(m.group(1)))
        return None, (f"Community district {int(m.group(1))} exists in more than one borough. Name the borough, "
                      f"for example QN {int(m.group(1))} or BK {int(m.group(1))}.")
    m = _BORO_NUM_RE.match(t)
    if m:
        return _district(_BOROUGH[m.group(1).lower()], int(m.group(2)))
    return None, None


def extract_address(text: str) -> str | None:
    """The street-address span in free text, with its borough,
    neighbourhood, state and ZIP when they follow it; None when there is no
    house number plus street."""
    # "311 street flooding complaints near 80 Pioneer St": a number and a
    # bare street word are not an address; the next match is.
    m = next((m for m in _ADDRESS_RE.finditer(text or "")
              if len(m.group(2).split()) > 1 or m.group(2).lower().rstrip(".") in _STANDALONE_STREETS), None)
    if not m:
        return None
    span, rest = m.group(0).rstrip("."), (text or "")[m.end():]
    for _ in range(3):  # up to two area names and a borough: ", Red Hook, Brooklyn"
        if b := _TAIL_BORO_RE.match(rest):
            span += f", {_BORO_FULL[b.group(1).lower()]}"
            rest = rest[b.end():]
            break
        a = _TAIL_AREA_RE.match(rest)
        if not a:
            break
        span += f", {a.group(1)}"
        rest = rest[a.end():]
    if s := _TAIL_STATE_RE.match(rest):
        span += ", NY"
        rest = rest[s.end():]
    if z := _TAIL_ZIP_RE.match(rest):
        span += f" {z.group(1)}"
    return span


def place_phrase(text: str) -> str | None:
    """A short place name for a neighbourhood lookup ("Red Hook",
    "Jamaica"), never a whole question: the first run of capitalised words
    that is not a question word, an agency, a storm or a borough alone."""
    for run in _CAPS_RUN_RE.findall(text or ""):
        words = run.split()
        while words and words[0].lower().strip(".,") in _NOT_PLACE:
            words = words[1:]
        while words and words[-1].lower().strip(".,") in _NOT_PLACE:
            words = words[:-1]
        phrase = " ".join(words).strip(" ,")
        if phrase and len(words) <= 4 and phrase.lower() not in _BOROUGH:
            return phrase
    return None


def resolve_query(text: str) -> dict:
    """What kind of place the query names, and the words for it:
    {"kind": "district" | "address" | "neighborhood" | "invalid" | None,
     "text": ..., "certain": bool, "message": refusal text or None}."""
    code, refusal = parse_district(text)
    if refusal:
        return {"kind": "invalid", "text": None, "certain": True, "message": refusal}
    if code:
        return {"kind": "district", "text": code, "certain": True, "message": None}
    span = extract_address(text)
    if span:
        return {"kind": "address", "text": span, "certain": True, "message": None}
    if z := _ZIP_ONLY_RE.match(text or ""):
        return {"kind": "invalid", "text": None, "certain": True, "message": (
            f"A ZIP code such as {z.group(1)} covers many blocks, and Riprap briefs one place at a time. "
            "Give a street address in it, a neighbourhood name, or a community district such as QN12.")}
    if _INTERSECTION_RE.search(text or ""):
        return {"kind": "invalid", "text": None, "certain": True, "message": (
            "Riprap cannot place a street intersection: its geocoders resolve house numbers, not "
            "corners. Give a street address on that block, with the house number.")}
    phrase = place_phrase(text)
    if phrase:
        return {"kind": "neighborhood", "text": phrase, "certain": False, "message": None}
    return {"kind": None, "text": None, "certain": False, "message": None}


_ORD = re.compile(r"(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
_ABBR = {"st": "street", "ave": "avenue", "av": "avenue", "blvd": "boulevard", "rd": "road", "pl": "place",
         "dr": "drive", "ln": "lane", "pkwy": "parkway", "ter": "terrace", "ct": "court", "e": "east", "w": "west",
         "n": "north", "s": "south"}


def _tokens(s: str) -> list[str]:
    s = _ORD.sub(r"\1", (s or "").lower())
    return [_ABBR.get(w) or w for w in re.findall(r"[a-z0-9]+(?:-[0-9]+)?", s)]


_GENERIC = {"street", "avenue", "road", "place", "boulevard", "drive", "lane", "new", "york", "ny", "usa",
            "manhattan", "bronx", "brooklyn", "queens", "staten", "island", "the"}


def geocode_matches(asked: str, got: str) -> bool:
    """True when the geocoder returned the house number and street that
    were asked for, however it formats them ("90-01 183 STREET" from NYC
    Geosearch, "560, Grand Street, ..." from Nominatim)."""
    a = _tokens(asked)
    if not a or not re.fullmatch(r"\d+(?:-\d+)?", a[0]):
        return False  # a landmark or phrase, not a street address
    number = a[0]
    named = [w for w in a[1:] if w not in _GENERIC and not re.fullmatch(r"\d{5}", w)]
    # A direction alone ("east") does not identify the street.
    street = {w for w in named if w not in {"east", "west", "north", "south"}} or set(named) or set(a[1:2])
    g = _tokens(got)
    has_number = number in g or number.replace("-", "") in {t.replace("-", "") for t in g}
    return has_number and bool(street & set(g))
