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
_CODE_KIND_NUM_RE = re.compile(rf"\b(MN|BX|BK|QN|SI)\s+{_KIND}\s*{_NUM}", re.IGNORECASE)  # "SI CD 2"
# The city's own three-digit code: borough digit, then the district ("community district 301" is BK01).
_BOROCD_RE = re.compile(rf"\b{_KIND}\s*(?:no\.?\s*|#\s*)?([1-5])(0[1-9]|1[0-8])\b", re.IGNORECASE)
_BOROCD_PREFIX = {"1": "MN", "2": "BX", "3": "BK", "4": "QN", "5": "SI"}
_BORO_NUM_RE = re.compile(rf"^\s*{_BORO_WORDS}\s+(\d{{1,2}})\s*[?.!]?\s*$", re.IGNORECASE)

_SUFFIX = (r"(?:street|st|avenue|ave|av|boulevard|blvd|road|rd|place|pl|drive|dr|lane|ln|parkway|pkwy|terrace|ter"
           r"|court|ct|way|plaza|plz|square|sq|highway|hwy|expressway|expy|turnpike|tpke|loop|walk|row|crescent"
           r"|circle|path|slip|alley|broadway|bowery|concourse|oval)")
# Street words need a letter and are never a preposition, so "311 near 200
# Water Street" finds "200 Water Street", not "311 near 200 Water Street".
_STREET_WORD = r"(?!(?:near|at|in|on|around|of|for|by|from|to|and|or)\b)[A-Za-z0-9'.]*[A-Za-z][A-Za-z0-9'.]*"
# A quadrant after the street ("Pennsylvania Ave NW") stays with it.
# A street name is a word and a suffix ("Water Street"), so "450 St. Nicholas
# Avenue" is not cut at "450 St" and "311 street flooding" is no address;
# Broadway, the Bowery and Brooklyn's lettered avenues ("Avenue U") stand alone.
_ADDRESS_RE = re.compile(rf"\b(\d{{1,6}}(?:-\d{{1,4}})?[A-Za-z]?)\s+((?:{_STREET_WORD}\s+){{1,5}}?{_SUFFIX}|broadway|bowery|avenue\s+[a-z]\b)"
                         r"\b\.?(?:\s+(?:NW|NE|SW|SE)\b)?", re.IGNORECASE)
# After the street: ", Queens", " in the Bronx", ", Red Hook, Brooklyn", ", NY", " 11423".
_TAIL_AREA_RE = re.compile(r"^\s*(?:,\s*|\s+in\s+(?:the\s+)?)([A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,2})")
# A borough right after the street, with or without a comma, in any case or
# common abbreviation: "200 Water Street Manhattan", "1310 Surf Ave, Bklyn".
# Without it the geocoder picks a borough itself (Water Street in Dumbo).
_TAIL_BORO_RE = re.compile(r"^\s*,?\s*(?:(?:in|on)\s+)?(?:the\s+)?(manhattan|brooklyn|bklyn|bkln|queens|qns|bronx|bx"
                           r"|staten island)\b\.?"
                           # "Manhattan Beach" and "Brooklyn Heights" are neighbourhoods, not the borough
                           r"(?!\s+(?:Beach|Heights|Village|Valley|Bridge|Terrace|Park|Hills?|Navy|Gardens)\b)", re.IGNORECASE)
_BORO_FULL = {"manhattan": "Manhattan", "brooklyn": "Brooklyn", "bklyn": "Brooklyn", "bkln": "Brooklyn",
              "queens": "Queens", "qns": "Queens", "bronx": "Bronx", "bx": "Bronx", "staten island": "Staten Island"}
_TAIL_STATE_RE = re.compile(r"^\s*,?\s*(?:NY|New York)\b(?!\s+(?:City|County))")
_TAIL_ZIP_RE = re.compile(r"^\s*,?\s*(\d{5})\b")
_CAPS_RUN_RE = re.compile(r"\b[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*")
# Two streets joined by "and", "&" or "at", with no house number: neither
# geocoder Riprap uses places an intersection (NYC GeoSearch parses the
# cross street and returns nothing; Nominatim returns nothing), so it is
# refused with the reason rather than sent to a street's nearest point.
_NAMED_STREET = rf"((?:{_STREET_WORD}\s+){{1,3}}?{_SUFFIX}|broadway|bowery|avenue\s+[a-z]\b)"
_INTERSECTION_RE = re.compile(rf"\b{_NAMED_STREET}\s+(?:and|&|at)\s+{_NAMED_STREET}\b", re.IGNORECASE)
# "my place at Ocean Parkway", "my street and the next street": a street
# word after one of these is a common noun, not a street's name.
_NOT_A_STREET_NAME = {"my", "our", "your", "their", "his", "her", "the", "this", "that", "a", "an", "next", "same",
                      "which", "what", "any", "every", "each", "one", "whole"}


def _intersection(text: str) -> bool:
    """True when the text joins two named streets ("Atlantic Avenue and
    Court Street"), each with a name before its suffix."""
    return any(not any(len(g.split()) > 1 and g.split()[-2].lower() in _NOT_A_STREET_NAME for g in m.groups())
               for m in _INTERSECTION_RE.finditer(text or ""))
_ZIP_ONLY_RE = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*[?.!]?\s*$")
# Capitalised words that start a question or name an agency or storm, not a place.
_NOT_PLACE = {"is", "are", "was", "were", "what", "how", "has", "have", "does", "did", "do", "tell", "show",
              "can", "could", "will", "would", "which", "where", "when", "why", "who", "the", "a", "an", "i",
              "nyc", "new", "york", "city", "fema", "dep", "nws", "noaa", "usgs", "mta", "nycha", "doe", "sandy",
              "ida", "hurricane", "floodnet", "npcc4", "ny", "in", "we're", "i'm", "it's", "its",
              "national", "weather", "service", "health", "department", "council", "npcc", "heat", "landsat",
              "riprap"}


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
    m = _CODE_KIND_NUM_RE.search(t)
    if m:
        return _district(m.group(1), int(m.group(2)))
    m = _BORO_KIND_NUM_RE.search(t)
    if m:
        return _district(_BOROUGH[m.group(1).lower()], int(m.group(2)))
    m = _BOROCD_RE.search(t)
    if m:
        return _district(_BOROCD_PREFIX[m.group(1)], int(m.group(2)))
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


# A house number and a street whose type nobody listed ("1 Bowling Green", "15 Central Park West", "10 Hudson
# Yards"). These once fell through to the neighbourhood lookup and were briefed as Greenpoint and as all of
# Central Park. A capitalised run after the number, or in any case the text from its start to a comma or its end.
_HOUSE = r"(?<![\w-])(\d{1,6}(?:-\d{1,4})?[A-Za-z]?)\s+"
_UNLISTED_RES = (
    re.compile(_HOUSE + r"([A-Z][A-Za-z'.]*(?:\s+[A-Z][A-Za-z0-9'.]*){0,4})"),
    re.compile(r"^\W*" + _HOUSE + rf"({_STREET_WORD}(?:\s+{_STREET_WORD}){{0,4}})(?=\s*(?:,|[?.!]*\s*$))", re.IGNORECASE))
# The word before a house number, when there is one: a question word or a preposition, never a label ("PS 15",
# "Pier 6", "top 10").
_BEFORE_HOUSE = {"at", "near", "around", "for", "about", "to", "and", "on", "by", "of", "from", "with", "outside"}
# ponytail: a fixed list of things that are counted ("100 year floodplain", "20 homes"); a count it misses is
# sent to the geocoder as an address and comes back unmatched, not as another place.
_COUNTED = {"year", "years", "yr", "feet", "foot", "ft", "inch", "inches", "percent", "degree", "degrees", "complaints",
            "calls", "hours", "day", "days", "minutes", "miles", "blocks", "homes", "houses", "buildings", "people",
            "boroughs", "times",
            "sandy", "ida", "hurricane", "flood", "floods", "flooding", "flooded", "heat", "stormwater"}
_YEAR_RE = re.compile(r"(?:19|20)\d\d|2100")


def _not_a_house_number(number: str, after: str) -> bool:
    """311 is the complaint line, five digits are a ZIP code ("11212 hot"),
    and a year before a neighbourhood's name is a year ("2080 Coney Island",
    "since 2012 Red Hook", "the 2050s Red Hook")."""
    return number == "311" or bool(re.fullmatch(r"\d{5}", number)) or bool(
        _YEAR_RE.fullmatch(number.lower().rstrip("s")) and any(
            re.search(rf"\b{re.escape(n)}\b", after.lower()) for n in _known_neighbourhoods()))


def _unlisted_address(text: str) -> tuple[str, int] | None:
    """(span, where it ends) for a house number and a name with no listed
    street type, or None."""
    for pattern in _UNLISTED_RES:
        for m in pattern.finditer(text):
            before = re.findall(r"[A-Za-z']+", text[:m.start()])
            first = m.group(2).split()[0].lower().strip(".'")
            if before and before[-1].lower() not in _NOT_PLACE | _BEFORE_HOUSE:
                continue
            if first in _COUNTED or re.fullmatch(_SUFFIX, first) or _not_a_house_number(m.group(1), m.group(2)):
                continue  # "311 street flooding" is no address
            return text[m.start(1):m.end()], m.end()
    return None


def extract_address(text: str) -> str | None:
    """The street-address span in free text, with its borough,
    neighbourhood, state and ZIP when they follow it; None when there is no
    house number plus street."""
    text = _ORDINAL_STREET_RE.sub(lambda m: m.group(1) + _ordinal_suffix(int(m.group(1))), text or "")
    m = _ADDRESS_RE.search(text)
    found = (m.group(0), m.end()) if m else _unlisted_address(text)
    if not found:
        return None
    span, rest = found[0].rstrip("."), (text or "")[found[1]:]
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


# "131 beach 96 st", "560 5 avenue": a numbered street typed without its
# ordinal, which neither the address pattern nor the geocoders match. Only
# after a house number or a street prefix, so "at 1 St Marks Place" and
# "311 street flooding" are left alone.
_ORDINAL_STREET_RE = re.compile(
    r"(?:(?<=\d\s)|(?<=beach\s)|(?<=east\s)|(?<=west\s)|(?<=north\s)|(?<=south\s)|(?<=\b[ewns]\s))"
    r"(\d{1,3})(?=\s+(?:st|street|ave|avenue|av|rd|road|pl|place|dr|drive)\b)", re.IGNORECASE)


def _ordinal_suffix(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def place_phrase(text: str) -> str | None:
    """A short place name for a neighbourhood lookup ("Red Hook",
    "Jamaica"), never a whole question: a run of capitalised words that is
    not a question word, an agency, a storm or a borough alone. A run that
    names a known neighbourhood wins ("We're drafting ... In Hollis, how
    many" is about Hollis); otherwise the first run."""
    from app.areas import nta  # noqa: PLC0415

    found: list[str] = []
    for m in _CAPS_RUN_RE.finditer(text or ""):
        run = m.group(0)
        words = run.split()
        # A known neighbourhood is kept whole, before any word is stripped
        # from it: "East New York" was once cut to "East" (the East Village)
        # and "Has New Brighton" to "Brighton" (Brighton Beach).
        whole = next((w for i in range(len(words)) if (w := " ".join(words[i:]).strip(" ,.?")).lower()
                      in _known_neighbourhoods()), None)
        if whole:
            found.append(whole)
            continue
        while words and words[0].lower().strip(".,") in _NOT_PLACE:
            words = words[1:]
        while words and words[-1].lower().strip(".,") in _NOT_PLACE:
            words = words[:-1]
        phrase = " ".join(words).strip(" ,.")
        # One capitalised word that opens a sentence is the sentence's first
        # word, not a place ("Thinking of renting ..." was once geocoded to a
        # trail upstate), and a compass word alone is half a name ("East" of
        # "East 109th" once resolved to the East Village).
        opens = not (text or "")[:m.start()].strip() or (text or "")[:m.start()].rstrip()[-1:] in ".!?:"
        if len(words) == 1 and (opens or phrase.lower() in _HALF_NAMES) and phrase.lower() not in _known_neighbourhoods():
            continue
        if phrase and len(words) <= 4 and phrase.lower() not in _BOROUGH:
            found.append(phrase)
    # A named building or park ("Wagner Houses", "Crotona Park") is the place,
    # before any neighbourhood word elsewhere in the question.
    # An acronym is not a place to guess at: "ER" (in "ER visits") once matched GramERcy by substring.
    found = [f for f in found if len(f) > 3 or f.lower() in nta.ALIASES]
    named = next((f for f in found if _NAMED_PLACE_RE.search(f) and f.lower() not in _known_neighbourhoods()), None)
    if named:
        return named
    for phrase in found:
        hits = nta.resolve(phrase)
        # The resolver matches substrings: the phrase must be whole words of the name, or an alias.
        if phrase.lower() in nta.ALIASES or (hits and re.search(rf"\b{re.escape(phrase)}\b", hits[0]["nta_name"],
                                                                 re.IGNORECASE)):
            return phrase
    # A misspelled name ("Bedford Stuyvesnt", once sent to Bedford Park in the Bronx by its first word):
    # the neighbourhood it is closest to, when it is close.
    for phrase in found:
        if len(phrase.split()) > 1 and (near := _close_name(phrase)):
            return near
    # Typed in lower case ("whats going on in hunts point"): a known
    # neighbourhood name as whole words, the longest one. Not when the name
    # is part of a street or a landmark ("Flushing Avenue", "Jamaica
    # Hospital"), and not when the text names another city or state
    # ("woodlawn chicago").
    # ponytail: a name that is also a word ("flushing") matches; a part-of-speech
    # check is the upgrade if that ever misroutes a real question.
    low = (text or "").lower()
    if ELSEWHERE_RE.search(low):
        return found[0] if found else None
    known = [n for n in _known_neighbourhoods()
             if (m := re.search(rf"\b{re.escape(n)}\b(?!\s+(?:{_SUFFIX}|{_LANDMARK})\b)", low))
             # "what about 15 central park west": a name right after a house number is a street's
             and not ((h := re.search(r"(?<![\w-])(\d{1,6}(?:-\d{1,4})?[a-z]?)\s+$", low[:m.start()]))
                      and not _not_a_house_number(h.group(1), n))]
    if known:
        return max(known, key=len).title()
    words = re.findall(r"[a-z']+", low)
    for n in (3, 2, 1):  # "heat brownsvile", "coney iland"
        for i in range(len(words) - n + 1):
            if near := _close_name(" ".join(words[i:i + n])):
                return near
    return found[0] if found else None


def _close_name(phrase: str) -> str | None:
    """The neighbourhood a misspelled phrase is closest to, or None. Whole
    names only, seven letters or more, so a common word is not corrected
    into a place."""
    import difflib  # noqa: PLC0415

    from app.areas import nta  # noqa: PLC0415

    p = phrase.lower().strip()
    # Not a borough ("staten island" is not Hart Island) and not a hazard phrase ("heat island" is not either).
    if len(p) < 7 or any(b in p for b in _BOROUGH) or re.search(r"\b(?:heat|hot|flood\w*|island)\b", p) and "iland" not in p:
        return None
    names = {re.sub(r"\s*\(.*?\)", "", n).strip().lower().replace("-", " "): n for n in nta.load()["ntaname"].dropna()}
    names.update({k: k for k in _known_neighbourhoods() if len(k) >= 7})
    hit = difflib.get_close_matches(p, list(names), n=1, cutoff=0.88)
    if not hit or hit[0] == p or hit[0][0] != p[0] or len(hit[0].split()) != len(p.split()):
        return None  # a typo keeps its first letter and its number of words ("is coney island" is no typo)
    full = names[hit[0]]
    return re.sub(r"\s*\(.*?\)", "", full).strip().title() if full != hit[0] else hit[0].title()


# A building, a market or a corner named after a preposition ("the block around La Marqueta, East Harlem").
_AT_NAME_RE = re.compile(r"\b(?:around|near|at|outside|beside|behind|by|in front of|next to|across from)\s+(?:the\s+)?"
                         r"((?-i:[A-Z])[\w.'-]*(?:\s+(?-i:[A-Z])[\w.'-]*){0,3})", re.IGNORECASE)
_NOT_A_SPOT = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
               "hurricane", "superstorm", "tropical", "community", "board", "district"}


def unplaced_name(text: str, area: str) -> str | None:
    """The named spot a question asks about ("La Marqueta") when the
    answer is for the area beside it ("East Harlem") because the spot was
    never looked up: a capitalised name after "around", "near" or "at" that
    is no neighbourhood, borough, district, storm or agency. The answer then
    says the spot could not be located and gives no yes or no about it."""
    from app.areas import nta  # noqa: PLC0415

    for m in _AT_NAME_RE.finditer(text or ""):
        name = m.group(1).strip(" ,.")
        low = name.lower()
        if (low in _known_neighbourhoods() or low in _BOROUGH or low in area.lower() or area.lower() in low
                or any(re.sub(r"'s$", "", w).strip(".,") in _NOT_PLACE | _NOT_A_SPOT for w in low.split()) or parse_district(name)[0]
                or nta.resolve(name)):
            continue
        return name
    return None


def landmark_phrase(text: str) -> str | None:
    """A landmark or a street named after a neighbourhood, typed in lower
    case ("red hook ferry terminal"): the whole name, for the geocoder."""
    named = [m.group(0) for n in _known_neighbourhoods()
             if (m := re.search(rf"\b{re.escape(n)}(?:\s+(?:{_SUFFIX}|{_LANDMARK}))+\b", (text or "").lower()))]
    return max(named, key=len).title() if named else None


_HALF_NAMES = {"east", "west", "north", "south", "upper", "lower", "new", "old", "fort", "mount", "saint", "st"}
# A capitalised run that ends in one of these names a building, a campus or a park.
_NAMED_PLACE_RE = re.compile(r"\s(?:Houses|Towers|Homes|Park|Playground|Hospital|Library|Pool|Terminal|Airport|Stadium"
                             r"|College|University|Center|Centre|Plaza|Museum|Zoo|Garden|Gardens|Field)$")
# After a neighbourhood's name these make it a building or a station, not the area.
_LANDMARK = (r"(?:hospital|houses|station|terminal|cent(?:er|re)|college|university|library|school|mall|airport"
             r"|stadium|bridge|tunnel|cemetery|medical|market|pier|ferry|yards?|depot)")
# Another city Riprap covers, or another state by name: the place is not an
# NYC neighbourhood that happens to share a word with it.
ELSEWHERE_RE = re.compile(
    r"\b(chicago|seattle|albany|alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida"
    r"|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan"
    r"|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|north carolina"
    r"|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah"
    r"|vermont|virginia|washington state|west virginia|wisconsin|wyoming)\b"
    r"(?!\s+" + _SUFFIX + r"\b)", re.IGNORECASE)  # "Pennsylvania Avenue" is a street in East New York


_NEIGHBOURHOODS: list[str] = []


def _known_neighbourhoods() -> list[str]:
    """Lower-cased neighbourhood names: each part of a tabulation area's name
    ("Carroll Gardens-Cobble Hill-Gowanus-Red Hook" is four) and the aliases."""
    if not _NEIGHBOURHOODS:
        from app.areas import nta  # noqa: PLC0415

        # Green-Wood is one word: split, it made "Green" a neighbourhood, and "Bowling Green" was Greenpoint.
        parts = {re.sub(r"\s*\(.*?\)", "", p).strip().lower()
                 for name in nta.load()["ntaname"].dropna() for p in name.replace("Green-Wood", "Green Wood").split("-")}
        _NEIGHBOURHOODS.extend(sorted(p for p in parts | set(nta.ALIASES) if len(p) >= 5 and p not in _BOROUGH))
    return _NEIGHBOURHOODS


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
    if _intersection(text):
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
    if g and re.fullmatch(r"\d+(?:-\d+)?", g[0]):
        # The result leads with its own house number: that is the one to match. ("400 1/2, Bay Street" was
        # once an exact match for "1 Bay Street", by the 1 in "1/2".)
        return g[0].replace("-", "") == number.replace("-", "") and bool(street & set(g))
    has_number = number in g or number.replace("-", "") in {t.replace("-", "") for t in g}
    return has_number and bool(street & set(g))
