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

Two rules sit in front of these for questions about the future:

  * a question an experimental model can answer (a surge at the Battery,
    land cover) gets that model's hedged sentence, after the official
    source for the same thing when there is one. For a question about past
    flooding a model never sets a yes or no;
  * a question about what satellite imagery showed of a flood gets no model:
    the satellite water layer was retired after two tests showed no skill
    (docs/MODELS.md). The lead says so and the surveyed record follows;
  * "will it flood" at a place or on a day gets no yes or no and no
    refusal either: the lead says no source here predicts that, and the
    forecasts and scenarios that exist follow.

A question that names two things ("was it in the Sandy area, and how many
311 complaints") gets both: the first rule that fires sets the lead and
every other named source is added to the facts.

A question about outdoor heat is answered by the heat rules
(heat_answer.py), which `answer` hands it to; everything below is the
flood half.

Three rules sit in front of all of these:

  * a question not written in English is not read at all, and says so
    (`not_english`);
  * insurance, price, buying, renting, safety: Riprap gives none of that
    advice, says so, and quotes the record (`asks_advice`);
  * a question that asks for something Riprap does not hold (people,
    income, basements, law, benefits, advice to an agency, a score, a
    ranking, a trend, the rain on a past day, another 311 topic) is told
    which in its first sentence and marked unanswered (`NOT_HELD`).

Returns None when no rule names what the question is about: a word the
rules did not read ("endorse", "fault") leaves a question unanswered and
never under the neutral lead. The caller then asks the model, if one is
configured, or shows the evidence under a line that says it is not an
answer.
"""

from __future__ import annotations

import re

from riprap.core.burr import answer_checks as ac
from riprap.core.burr import heat_answer
from riprap.core.pebbles.shapers.dep_scenario import code as dep_code

ASSET_DOCS = ("mta_entrance_exposure", "doe_school_exposure", "nycha_development_exposure", "doh_hospital_exposure")
# What reports the present, and what a forecast question is answered with, in order.
LIVE_FACTS = ("nws_alerts", "floodnet", "noaa_tides", "nws_water_forecast", "usgs_gauges", "nws_obs")
FORECAST_FACTS = ("nws_water_forecast", "npcc4_slr",
                  "dep_moderate_2050", "dep_extreme_2080", "dep_moderate_2050_nta", "dep_extreme_2080_nta")
OBSERVED = ("floodnet", "nyc311", "nyc311_nta", "ida_hwm", "sandy_inundation", "sandy_nta")
# The city's four stormwater maps, smallest storm first, for an address and for an area.
DEP = ("dep_limited_current", "dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080",
       "dep_limited_current_nta", "dep_moderate_current_nta", "dep_moderate_2050_nta", "dep_extreme_2080_nta")
# Sources a question can name beyond answer_checks.RELEVANT, most specific first.
TOPICS = (
    (re.compile(r"\bfema\b|flood ?zones?\b|flood ?plain|\bfirm\b|flood insurance rate|\b[15]00[- ]year\b", re.I),
     ("fema_nfhl", "fema_pfirm", "dcp_floodplain_nta")),
    (re.compile(r"\bsandy\b", re.I), ("sandy_inundation", "sandy_nta")),
    (re.compile(r"stormwater|storm water|\bdep\b|scenarios?\b|(extreme|moderate) (rain|flood)|rain(fall)? (flood )?maps?"
                r"|flood maps?", re.I), DEP),
    (re.compile(r"elevation|low spot|low.lying|terrain|topograph|how high (is|above)(?! (the |tomorrow's |tonight's |today's )?((predicted|storm|high|next) )*(surge|tides?|water)\b)"
                r"|above sea level", re.I),
     ("microtopo", "microtopo_nta")),
    (re.compile(r"\bpermits?\b|construction|being built", re.I), ("dob_permits_nta",)),
    (re.compile(r"\bstream|river level|\bgauges?\b", re.I), ("usgs_gauges",)),
)
# Where water lingers after rain is a question for the city's stormwater
# model (the satellite model was tested for it and failed, docs/MODELS.md),
# but only when the question names no other source and is not about now:
# "standing water right now" wants the sensors, and "311 complaints about
# standing water" wants the complaints.
_PONDING_RE = re.compile(r"\blinger|standing water|\bponding|slow to drain|water (that )?(sits?|stays?|pools?|collects?)", re.I)
# What satellite imagery showed of a flood: no source here says (the layer was retired, docs/MODELS.md).
_SATELLITE_RE = re.compile(r"satellite|sentinel|from space|imagery", re.I)
# What the two experimental models can answer (app/experimental.py,
# docs/MODELS.md): question words, the model's documents, and the official
# sources quoted before them (for land cover, the city's own 2017 map).
EXPERIMENTAL = (
    # ("Green" alone is a street, a park and a cemetery: "100 Green Street", "Bowling Green".)
    (re.compile(r"\bpaved|\bpaving|pavement|impervious|\bgreen(ery|er| spaces?| cover| areas?)\b|\b(how|is|are) green\b(?!-| (st|street|ave|avenue|pl|place|rd|road|ln|lane|point)\b)"
                r"|much (of (it|this|the \w+) )?is green|\bland.?cover|built.?(over|up)|tree (cover|canopy)|vegetat|\brunoff",
                re.I), ("landcover", "landcover_nta"), ("city_landcover", "city_landcover_nta")),
    # ("The Sandy surge zone" is a map, and a surge that happened is the record's to answer.)
    (re.compile(r"(?<!sandy )(?<!sandy's )\bsurge\b(?! (zone|area|extent|line|map))|predicted tide"
                r"|(above|higher than|over) the (predicted |normal |astronomical )?tide"
                r"|high tide|king tide|\b(at|for) the battery\b(?! park)", re.I),
     ("ttm_battery_surge",), ("nws_water_forecast", "noaa_tides")),
)
# "Will it flood": a prediction for a place. No source or model here makes
# one, so the lead says so and the forecasts that exist follow.
# ("Will this be in a flood zone" and "will flood insurance ..." ask about a map and a price.)
_WILL_FLOOD_RE = re.compile(r"\b(will|going to|gonna|likely to|expected to|about to)\b[^.?!]*"
                            r"\bflood(?!net|[- ]?(zone|plain|insurance|map))"
                            r"|\bflood\w*\s+(?:(?:is|are)\s+(?:expected|likely|forecast|predicted)|expected|likely|predicted)\b",
                            re.I)  # ("the flood forecast" is a noun, and the forecast answers it)
# Insurance, price, property value, buying, renting, or whether a home is safe: Riprap reports records and
# does none of these. The FEMA zone is the record that bears on insurance, the effective map first. ("The flood
# insurance rate map" is a map, and "is the school safe" is answered from the school register, below.)
_ADVICE_RE = re.compile(
    r"\binsur(?:ance|ed?|ing|ers?)\b(?! rate maps?)|\bpremiums?\b|\bmortgages?\b"
    r"|\b(?:property|home|house|resale|market|real estate) (?:values?|prices?)\b|\bworth (?:buying|renting|it)\b"
    r"|\bhow much (?:is|are|does|do|would|will)\b[^.?!]*\b(?:worth|costs?)\b"
    r"|\bshould (?:i|we) (?:buy|rent|sell|move|live|stay|sign|lease)\b"
    r"|\b(?:good|bad|smart|wise) (?:idea|place|time) to (?:buy|rent|live|move|sign)\b"
    r"|\b(?:is|would) it (?:be )?safe\b|\bsafe to (?:buy|rent|live|stay|move)\b"
    r"|\bsafe (?:from|against|in|during) (?:a |the |any |heavy )?(?:flood\w*|storms?|rain\w*|hurricanes?)\b"
    r"|\b(?:dangerous|unsafe)\b"
    r"|\b(?:is|are|will|would)\b[^.?!]*\b(?:homes?|houses?|apartments?|basements?|buildings?|blocks?|street|st|avenue|ave)\b[^.?!]*\bsafe\b",
    re.I)
ADVICE_FACTS = ("fema_nfhl", "fema_pfirm", "dcp_floodplain_nta")
# "Is it safe", a basement: the decline, then what was observed, then the stormwater maps, then FEMA. Never the
# FEMA zone alone: "zone X (an area of minimal flood hazard)" once stood as the whole answer at an address with
# 10 sensor events and 81 complaints beside it.
_SAFETY_RE = re.compile(r"\b(?:un)?safe(?:ty)?\b|\bbasements?\b|\bcellars?\b|\bdanger", re.I)
SAFETY_FACTS = ("floodnet", "nyc311", "nyc311_nta", "ida_hwm", "sandy_inundation", "sandy_nta", *DEP, *ADVICE_FACTS)
# Records read around a street address only, by what the question calls them.
ADDRESS_ONLY = ("ida_hwm",)
# A change over time in land cover: the city's map is one year and the model is not compared across years.
_CHANGE_RE = re.compile(r"\bsince (?:19|20)\d\d\b|\bover (?:the )?(?:time|years|decades?|last|past)\b|\bchang(?:e|es|ed|ing)\b"
                        r"|\b(?:become|became|becoming|gotten|getting|grown|growing|got)\b[^.?!]*\b(?:more|less|fewer)\b"
                        r"|\b(?:more|less|fewer)\b[^.?!]*\bthan (?:it (?:was|used)|before|in (?:19|20)\d\d|\d+ years)\b"
                        r"|\b(?:increas|decreas|declin|shr[iu]nk|expand)\w*|\bused to\b|\btrend|\b(?:lost|losing|gained|gaining)\b",
                        re.I)
NO_PREDICTION_FACTS = ("nws_alerts", "nws_water_forecast", "fema_nfhl", "dcp_floodplain_nta",
                       "dep_moderate_current", "dep_moderate_current_nta", "sandy_inundation", "sandy_nta")


# What Riprap does not hold, by the words a question uses to ask for it: (topic, words, the sentence that opens
# the answer, flood questions only). A question that asks for one of these is unanswered: the sentence says so
# first, and the records for the place follow. Heat has its own leads for a score and a ranking (heat_answer.py),
# and a trend in hot days is in the station record, so those three rows are for flood questions.
HELP_POINTERS = ("The city's own services: 311 (https://portal.311.nyc.gov), Notify NYC "
                 "(https://a858-nycnotify.nyc.gov) and FloodHelpNY (https://www.floodhelpny.org).")
_COUNT_OF = (r"\b(?:how many|how much|number of|count of|share of|percent(?:age)? of|proportion of"
             r"|what (?:share|percent(?:age)?|proportion|fraction))\b")
_PEOPLE = (r"(?:people|persons?|residents?|households?|famil(?:y|ies)|adults?|seniors?|elderly|child(?:ren)?|kids?"
           r"|tenants?|renters?|owners?|homeowners?|immigrants?|speakers?|workers?|new yorkers)")
_OTHER_311 = (r"(?:noise|rodents?|rats?|mice|potholes?|parking|graffiti|garbage|trash|litter|dumping|homeless\w*"
              r"|street ?lights?|mold|bed ?bugs?|pests?|heat(?:ing)?|hot water|sidewalks?|taxis?|vendors?|construction)")
NOT_HELD = (
    ("people", re.compile(
        # (Not "how many complaints have people filed": the thing counted there is complaints.)
        rf"{_COUNT_OF}(?:(?!\b(?:complaints?|reports?|requests?|calls?|sensors?|events?|marks?|floods?)\b)[^.?!])*\b{_PEOPLE}\b|\bwho (?:lives?|lived|resides?|owns?|rents?|floods|gets? flooded|(?:is|are) (?:most|more|at|affected|vulnerable|exposed|hit))\b"
        r"|\bpopulation\b|\bdemographic|\bcensus\b|\bby (?:age|race|ethnicity)\b|\bhow old\b"
        r"|\bage (?:groups?|of (?:the )?(?:residents|people))\b|\blanguages?\b|\b(?:speak|speaks|spoken)\b"
        r"|\b(?:black|latino|latina|hispanic|asian|white) (?:residents|people|households|new yorkers|population)\b"
        r"|\bliv(?:e|es|ing) alone\b", re.I),
     "Riprap holds no records about the people or households at a place: not who lives there, how many, their "
     "age, race or language, or whether they rent or own. The one count of residents it quotes is City Planning's "
     "for a community district's floodplain.", False),
    ("income", re.compile(r"\bincomes?\b|\bpoverty\b|\brent[- ]burden|\bwealth\w*\b|\bearnings?\b|\bwages?\b", re.I),
     "Riprap reports no income or poverty figures for a place.", False),
    ("basements", re.compile(r"\bbasements?\b|\bcellars?\b|\bbelow[- ]grade\b", re.I),
     "Riprap holds no records of basements or of the inside of any building: no list of basement apartments, legal "
     "or not, and no record of water inside a home.", False),
    ("law", re.compile(r"\bevict\w*|\blandlords?\b|\bleases?\b|\b(?:il)?legal(?:ly)?\b|\blaws?\b|\blawful\w*|\b(?:tenants?'?|legal|my|our|their|renters?'?) rights\b"
                       r"|\bliab(?:le|ility)\b|\bviolations?\b|\bdisclos\w+|\brequired to\b|\bsue\b|\blawsuit", re.I),
     "Riprap holds no legal records and gives no legal advice: nothing here says what a landlord, a tenant or an "
     f"owner may or must do. {HELP_POINTERS}", False),
    ("benefits", re.compile(r"\beligib\w+|\bqualif(?:y|ies|ied)\b|\bbuy-?outs?\b|\bgrants?\b|\bbenefits?\b|\bassistance\b"
                            r"|\b(?:disaster|fema|federal|city) (?:aid|relief)\b|\breimburs\w+|\bcompensat\w+"
                            r"|\bvouchers?\b|\b(?:get|find|need|for|seek) help\b|\bhelp (?:after|with|paying)\b", re.I),
     "Riprap holds no records of aid, buyouts or benefits, and cannot say who is eligible for a programme or where "
     f"to get help. {HELP_POINTERS}", False),
    ("advice", re.compile(r"\bshould\b(?! (?:worry|be worried|care)\b)|\bprioriti[sz]\w+|\brecommend\w*|\bought to\b|\bfix first\b|\bworth it\b"
                          r"|\bbest (?:way|option|approach|place)\b|\bwhat (?:can|could|must) [^.?!]*\bdo\b", re.I),
     "Riprap gives no advice and sets no priorities: it does not say what an agency, a board or a resident should "
     "do, or do first.", False),
    ("score", re.compile(r"\b(?:scores?|ratings?|rated|grades?)\b|^\s*rate\b|\byou rate\b|\bon a scale\b|\bscale of \d", re.I),
     "Riprap computes no flood score or rating of its own, and quotes none.", True),
    ("ranking", re.compile(
        r"\b(?:which|what)\s+(?:community\s+)?(?:parts?|areas?|neighbou?rhoods?|blocks?|districts?|streets?|places?|boroughs?)\b"
        r"|\brank(?:ed|ing|s)?\b|\btop (?:five|ten|\d+)\b|\b(?:most|worst|least)[- ]flood\w*|\bfloods? (?:the )?(?:most|worst|least)\b"
        r"|\b(?:most|worst|least) (?:flooding|floods|flooded)\b|\bwhere\b[^?.]*\b(?:worst|most)\b"
        r"|\b(?:worst|best|safest|driest|wettest)\s+(?:blocks?|streets?|areas?|parts?|places?|neighbou?rhoods?)\b", re.I),
     "Riprap does not rank places against each other or single out one block, street or part of a place.", True),
    ("trend", re.compile(r"\bgetting (?:worse|better|more|less)\b|\bgot(?:ten)? (?:worse|better)\b|\bworsen\w*|\btrend\w*"
                         r"|\b(?:increas|decreas|declin)\w+|\bmore (?:often|frequent\w*|common)\b"
                         r"|\bover (?:the )?(?:time|years|decades?)\b"
                         r"|\bthan (?:it )?(?:used to|before|in the past|(?:\d+|a few|ten|five) years ago)\b", re.I),
     "Riprap holds no record that shows a trend in flooding at a place: FloodNet's sensors were installed at "
     "different times, many of them inside the period counted, so a rising count can be new sensors, and 311 "
     "counts by year are counts of reports filed.", True),
    ("rain_on_a_day", re.compile(
        r"\bhow much (?:rain|precipitation)\b[^.?!]*\b(?:fell|fall|did|was|were|came|got|during|on)\b"
        r"|\b(?:rainfall|rain|precipitation) (?:totals?|amounts?|intensit\w+|rates?|records?)\b"
        r"|\b(?:storm|rain\w*|downpour)\b[^.?!]*\b(?:match\w*|exceed\w*|equal\w*|compar\w+|as (?:big|bad|heavy|strong|intense) as"
        r"|bigger than|worse than|meet)\b[^.?!]*\b(?:scenarios?|design storm|maps?)\b", re.I),
     "Riprap holds no rainfall record for a past day or storm, so it cannot set a storm against the city's "
     "stormwater scenarios: the only rain figure it reads is the Weather Service's latest hourly observation.", True),
    ("other_311", re.compile(rf"\b{_OTHER_311}\b[^.?!]*\b(?:311|complaints?|service requests?)\b"
                             rf"|\b(?:311|complaints?|service requests?)\b[^.?!]*\b(?:about|for|of|on)\s+(?:\w+\s+)?{_OTHER_311}\b", re.I),
     "Riprap reads four kinds of 311 complaint, all about water: sewer backups, catch basins, street flooding and "
     "manhole overflows. It holds no other 311 topic.", False),
)
_RAIN_SO_FAR_RE = re.compile(r"\btoday\b|\bso far\b|\b(?:last|past) (?:hour|\d+ hours|few hours)\b|\bis falling\b", re.I)


def _asks(clause: str) -> bool:
    """A clause that asks something: it ends with a question mark or opens
    with a question word. ("My basement flooded last year." is a preamble.)"""
    c = (clause or "").strip()
    first = re.match(r"\W*([A-Za-z']+)", c)
    return c.endswith("?") or bool(first and first.group(1).lower() in _ASKS)


def not_held(question: str) -> tuple[str, str] | None:
    """(topic, sentence) for the first thing the question asks for that
    Riprap does not hold (NOT_HELD), or None. Only clauses that ask are
    read, so a preamble ("I rent a basement on Pioneer Street. Has the
    block flooded?") names nothing."""
    q = question or ""
    heat = heat_answer.hazard_of(q) == "heat"
    for c in _clauses(q):
        if not _asks(c):
            continue
        for topic, pattern, sentence, flood_only in NOT_HELD:
            if (flood_only and heat) or not pattern.search(c):
                continue
            if topic == "people" and TOPICS[0][0].search(c):
                continue  # "how many people live in the floodplain": City Planning's district profile counts them
            if topic == "advice" and asks_now(q):
                continue  # "is the street passable right now, or should I move my car": the live readings
            if topic == "trend" and EXPERIMENTAL[0][0].search(c):
                continue  # paving over time has its own lead (no_change_record)
            if topic == "rain_on_a_day" and (asks_now(q) or _RAIN_SO_FAR_RE.search(c)):
                continue  # "how much rain has fallen today": the latest observation
            if topic == "ranking" and any(i in ASSET_DOCS for i in _named_ids(c)):
                continue  # "which schools are in the flood zone": the register lists them
            return topic, sentence
    return None


# A question Riprap cannot read: it reads English only. Another script anywhere in the text, inverted Spanish
# punctuation, or two Spanish words that English place names do not use ("El Barrio" and "La Guardia" are places).
# ponytail: a word list for Spanish and script ranges for the rest; a language-identification model is the
# upgrade if questions in other Latin-script languages (Haitian Creole, Polish) keep passing as bare addresses.
_OTHER_SCRIPT_RE = re.compile(r"[Ѐ-ӿ֐-ۿऀ-෿฀-໿ᄀ-ᇿ぀-ヿ"
                              r"㐀-鿿가-힯]|[¿¡]")
# One word that only Spanish has, or two that a place name could hold one of. (No "se", "mi", "es", "ha" or
# "como": "123 SE Main St, Detroit, MI" is an address.)
_SPANISH_RE = re.compile(r"\b(?:inund(?:a|an|ó|ado|ada|ados|adas|ación|acion|aciones)|huracán|lluvia|sótano|cuánt\w+|dónde|qué|cómo|está|están|aquí|después)\b", re.I)
_SPANISH_WEAK_RE = re.compile(r"\b(?:desde|durante|calle|zona|agua|calor|seguro|segura|tiene|puede|donde|cuant\w+"
                              r"|huracan|riesgo|sotano|alguna)\b", re.I)
ENGLISH_ONLY = ("Riprap reads questions in English only, and this one was not read as English, so it is not answered. "
                "FloodHelpNY (https://www.floodhelpny.org) and 311 serve other languages. "
                "Español: Riprap solo lee preguntas en inglés. FloodHelpNY y el 311 atienden en otros idiomas. "
                "中文：Riprap 只能阅读英文问题。FloodHelpNY 和 311 提供其他语言的服务。 "
                "বাংলা: Riprap শুধু ইংরেজি প্রশ্ন পড়ে। FloodHelpNY এবং 311 অন্যান্য ভাষায় সেবা দেয়।")


def not_english(text: str) -> bool:
    """True when the text holds a question in a language Riprap does not
    read. A bare address stays a bare address whatever script surrounds it."""
    t = text or ""
    return bool(_OTHER_SCRIPT_RE.search(t) or _SPANISH_RE.search(t)
                or len({m.group(0).lower() for m in _SPANISH_WEAK_RE.finditer(t)}) >= 2)


# The words of a plain question about flooding at a place ("Does Hollis flood?", "How bad is the flooding on my
# block?", "tell me about flooding near 80 Pioneer Street"). The observed record answers such a question, and no
# other: a word outside this list is something no rule read ("endorse", "fault", "lawsuit"), and the question is
# then left unanswered instead of being given the record under the neutral lead.
# ponytail: a word list; a question classifier is the upgrade if plain questions keep falling outside it.
_PLAIN = frozenset("""
a about actually after again ago all also always am an and any anything are area around as at bad badly be been
before being big block blocks briefing building by can common concern concerns could damage data details did do does
during event events ever evidence experience experienced exposed exposure flood flooded flooding floods for frequent frequently
from get gets getting give going got had happen happened happens has have hazard hazards heavy here high history
hit home house how hurricane i ida if in info information is issue issues it its just kind know known last lately
like look lot lots low major many me minor much my near nearby neighborhood neighbourhood normally occur occurred
of often on or our overview past place please problem problems prone rain rains rainstorm rainstorms really recent
recently record recorded records regularly report risk risks risky sandy see seen serious severe show significant
since so some sometimes status still storm storms street streets summary superstorm tell that the there these they
thing things this time times to too tropical typically up us usually very vulnerable want was water we were wet
what when where whether with would year years you your
""".split())
_PLACE_WORD_RE = re.compile(r"\b(?:new york|nyc|ny|manhattan|brooklyn|queens|bronx|staten island|street|st|avenue|ave"
                            r"|boulevard|blvd|road|rd|place|pl|drive|dr|lane|ln|parkway|pkwy|court|ct|terrace)\b", re.I)


def plain_flood_question(question: str) -> bool:
    """True when the clause that asks is a plain question about flooding
    at the place, every word of it one the generic rule reads (_PLAIN), the
    place's own words aside. A search phrase with no asking clause ("hollis
    flooding history") is read whole."""
    from riprap.core.burr.place import resolve_query

    q = question or ""
    place = resolve_query(q).get("text") or ""
    clauses = [c for c in _clauses(q) if _asks(c)] or [q]
    for c in clauses:
        rest = re.sub(re.escape(place), " ", c, flags=re.I) if place else c
        rest = _PLACE_WORD_RE.sub(" ", rest)
        # A capitalised word after the first is a name (a place, a storm), not part of what is asked.
        words = re.findall(r"[A-Za-z']+", rest)
        asked = [w.lower().removesuffix("'s") for i, w in enumerate(words) if i == 0 or not w[0].isupper()]
        if all(w in _PLAIN for w in asked):
            return True
    return False


def asks_advice(question: str) -> bool:
    """A question about insurance, price, buying, renting or whether a home
    is safe. A statement before a question is a preamble ("I am buying a
    house on Pioneer Street. Has the block flooded?"), and a question about a
    school, a hospital, a subway entrance or public housing is the register's."""
    return any(_ADVICE_RE.search(c) and not (c.rstrip().endswith((".", "!")) and not ac.is_yes_no_question(c))
               and not any(i in ASSET_DOCS for i in _named_ids(c)) for c in _clauses(question or ""))


def experimental(question: str, texts: dict[str, str]) -> tuple[list[str], list[str]]:
    """(official documents, experimental documents) for the first
    experimental topic the question names. The official ones answer even
    when the model did not run (it is not installed, or its file is missing)."""
    for pattern, docs, official in EXPERIMENTAL:
        have, beside = [d for d in docs if texts.get(d)], [d for d in official if texts.get(d)]
        if (have or beside) and pattern.search(question or ""):
            if any(d not in official and d not in docs for d in named(question, texts)):
                # The question names another source as well ("high tide
                # flooding complaints"): that source answers, by its own rule.
                return [], []
            return beside, have
    return [], []


# Words for the present. Weather words alone ("it's pouring") are not
# enough: people say them before asking about the past.
# "Is there flooding risk" and "is it flooding often" are not about now.
# ("Is the street flooded" is the present too: "can I get to the subway stop, is the street flooded?")
_FLOODING_NOW_RE = re.compile(r"\bis (it|anything|the street|the block|the road|my street|my block|there|this) (now )?"
                              r"(flooding|flooded(?! (before|in|during|by|since|on)\b))\b"
                              r"(?!\s+(risk|history|often|usually|regularly|a lot|problems?|issues?|records?|complaints?"
                              r"|common|frequent))", re.I)
_NOW_RE = re.compile(r"\b(right now|rite now|rn|currently|tonight|at the moment|current conditions|live conditions"
                     r"|happening now|going on now|as we speak|passable|impassable"
                     r"|can (?:i|we) (?:get|drive|walk|bike|cross) (?:to|through|across|down|home|there|out))\b|"
                     + _FLOODING_NOW_RE.pattern, re.I)
_FUTURE_RE = re.compile(r"\b(forecasts?|forecasting|projections?|projected|outlook|predictions?|what is coming|what's coming"
                        r"|in the (coming|next) (years|decades)|in the future|by (the )?20\d\ds?|20[5-9]0s?|2100"
                        r"|(next|coming) (few |couple of |\w+ )?(hours|days)|tomorrow|next week|this (coming )?weekend)\b", re.I)
_FLOOD_RE = re.compile(r"\bflood", re.I)
_DURING_RE = re.compile(r"\b(during|in|after|by)\s+(?:tropical storm\s+|[a-z]+\s+)?(ida|sandy)\b", re.I)


_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|,\s+(?:and|but)\s+"
                              r"|\s+and\s+(?=(?:has|have|had|did|does|do|was|were|is|are|how|which|what)\b)", re.I)


# The period of an abbreviation ends no clause: "100 Main St. since Sandy" was
# once split there and answered "No." with the period lost.
# It does when a sentence plainly starts after it ("... 100 Main St. Has it
# flooded ...", "... Pine St. Since Ida, has it flooded?"). Typed in lower
# case ("i live at 100 main st. has it flooded"), a question word after it
# starts a sentence unless the sentence so far already opened as a question
# ("did 100 main st. have flooding" is one clause).
_ABBREV_RE = re.compile(r"\b((?i:St|Ave|Av|Blvd|Rd|Pl|Dr|Ln|Pkwy|Ter|Ct|Hwy|Expy|Mt|Ft|No|Apt|Jr|Sr|N|S|E|W))\."
                        r"(?=(?:\s+([A-Za-z']+))?)")
_ASKS = {"has", "have", "had", "did", "does", "do", "was", "were", "is", "are", "will", "would", "can", "could",
         "should", "what", "which", "where", "when", "why", "who", "how"}
_STARTS = _ASKS | {"i", "it", "we", "the", "this", "that", "my", "our", "there", "any", "since", "so", "during",
                   "after", "before", "and", "but", "also", "then", "now", "please", "tell", "show"}
_INITIALS_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}")  # "P.S. 90", "U.S."


def _abbreviation(m: re.Match) -> str:
    """The abbreviation with its period only where a sentence starts after it."""
    nxt = m.group(2) or ""
    if nxt[:1].isupper():
        ends = nxt.lower() in _STARTS
    else:
        so_far = re.split(r"[.!?]\s+", m.string[:m.start()])[-1]
        ends = nxt in _ASKS and not ac.is_yes_no_question(so_far)
    return m.group(0) if ends else m.group(1)


def _clauses(question: str) -> list[str]:
    """The question's clauses: people open with a preamble ("I'm writing a
    piece about ... Did the block flood during Ida?") and join two
    questions with "and"."""
    q = _INITIALS_RE.sub(lambda m: m.group(0).replace(".", ""), _ABBREV_RE.sub(_abbreviation, question or ""))
    parts = (re.sub(r"^\W*(and|but|so|also)\s+", "", c, flags=re.I).strip() for c in _CLAUSE_SPLIT_RE.split(q))
    # "Since Ida, has it flooded?" reads as "has it flooded since Ida?": the rules look at how a clause opens.
    # Without a comma only a storm or a year is moved ("since ida has it flooded"): "During which storms
    # was this flooded?" and "Since my office is at ..., has it flooded?" are left as written.
    parts = (re.sub(r"^((?:since|during|after|before)\b[^,?]*),\s*(.+?)([?.!]*)$", r"\2 \1\3", c, flags=re.I) for c in parts)
    parts = (re.sub(r"^((?:since|during|after|before)\s+(?:hurricane\s+|tropical storm\s+|superstorm\s+)?"
                    r"(?:ida|sandy|(?:19|20)\d\d))\s+(?=(?:has|have|had|did|was|were|is|are)\b)(.+?)([?.!]*)$",
                    r"\2 \1\3", c, flags=re.I) for c in parts)
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


# A house number that reads as a year ("2100 Bartow Avenue", "2050 Grand Concourse") is not one.
# Only capitalised words may stand between the number and the street word, and "in", "by" or "the"
# before it make it a year ("In 2050 will Ocean Parkway flood?", "by 2050 put Hamilton Avenue ...").
_HOUSE_YEAR_RE = re.compile(r"(?<!\bin )(?<!\bby )(?<!\bthe )\b(20[3-9]\d|2100)(?=\s+(?:(?-i:[A-Z])[\w'.]*\s+){0,3}?"
                            r"(?:street|st|avenue|ave|av|boulevard|blvd|road|rd|place|pl|drive|dr|lane|ln|parkway"
                            r"|pkwy|terrace|court|ct|way|plaza|highway|expressway|turnpike|broadway|concourse)\b)", re.I)


def _asks_future(q: str) -> bool:
    """A word for the future, except "this weekend" in a question that asks
    whether it flooded ("Did it flood this weekend?" is about the past)."""
    q = _HOUSE_YEAR_RE.sub("", q)
    words = [m.group(0).lower() for m in _FUTURE_RE.finditer(q)]
    return any(not w.endswith("weekend") for w in words) or bool(words and not _happened_clause(q))


def time_frame(question: str) -> str:
    q = question or ""
    if heat_answer.hazard_of(q) == "heat":
        return heat_answer.time_frame(q)
    if asks_now(q) and not _asks_future(q):
        return "now"
    if _asks_future(q) or ac.dep_scenario_asked(q):
        return "future"
    return "past" if _happened_clause(q) or ac._SINCE_RE.search(q) or _DURING_RE.search(q) else "any"


def _named_ids(question: str) -> list[str]:
    """Every doc id the question's words name, most specific first."""
    out: list[str] = []
    for pattern, ids in (*ac.RELEVANT, *TOPICS):
        if pattern.search(question or ""):
            out += [i for i in ids if i not in out]
    if (not [i for i in out if not i.startswith("nws_obs")] and _PONDING_RE.search(question or "")
            and not _NOW_RE.search(question or "")):  # ("after rain" names the rain reading, which is the setting)
        out += DEP
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
_NEAR_RE = re.compile(r"\b(hours?|days?|tonight|tomorrow|this week(end)?|next week(end)?)\b", re.I)
_FAR_RE = re.compile(r"\b20[3-9]\ds?\b|\b2100\b|decades?|century|sea.level", re.I)


# A cause asked about: "does rain flood ...", "is the flooding from the tide". FloodNet's events are not labelled
# by cause. ("Does it flood after heavy rain" names the setting, and the record answers it as before.)
_CAUSE_RE = re.compile(r"\b(?:rain\w*|downpours?|cloudbursts?|tid(?:e|es|al)|storm ?water|surges?)\b[^.?!]*\bflood"
                       r"|\bflood\w*\b[^.?!]*\b(?:from|by|because of|due to|caused by) "
                       r"(?:the |a |heavy |high |hard )*(?:rain\w*|tid(?:e|es|al)|surges?|downpours?)\b", re.I)
CAUSE_NOTE = ("FloodNet's API does not label a flood event by its cause, so the sensor record above does not say "
              "whether the water came from rain, a tide or a surge.")


def asks_cause(question: str) -> bool:
    return bool(_CAUSE_RE.search(question or ""))


FEMA_POINTER = ("This is a reading of FEMA's maps at one point, not a flood zone determination. For a regulatory "
                "flood determination, FEMA's Flood Map Service Center is at https://msc.fema.gov.")


def closing(question: str, lead: str, facts: list[str], values: dict | None, texts: dict[str, str]) -> str:
    """What follows the quoted facts of an answer: that the sensors give no
    cause when the question names one; under a FEMA zone that was asked
    about, that the reading is no determination and where one is made; and
    NYC Emergency Management's "outside does not mean safe" when the zone
    read is outside the Special Flood Hazard Area or the question asked
    whether a place is safe. Each is added only when the facts do not
    already say it."""
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT

    out = []
    if asks_cause(question) and "floodnet" in facts:
        out.append(CAUSE_NOTE)
    fema = (values or {}).get("fema_nfhl") if "fema_nfhl" in facts else None
    asked = lead == "no_advice" or bool(TOPICS[0][0].search(question or ""))
    if isinstance(fema, dict) and asked:
        out.append(FEMA_POINTER)
    safety = lead == "no_advice" and bool(_SAFETY_RE.search(question or ""))
    said = any(OUTSIDE_CAVEAT[:42] in texts.get(f, "") for f in facts)  # an outside stormwater reading carries it
    if (safety or (isinstance(fema, dict) and asked and not fema.get("sfha"))) and not said:
        out.append(OUTSIDE_CAVEAT)
    return " ".join(out)


def asks_something(text: str) -> bool:
    """True when words beside a place name a source or a time frame
    ("200 Water Street Manhattan FEMA flood zone"): a question typed as a
    search phrase. The word "flood" alone does not count."""
    if heat_answer.hazard_of(text) == "heat":
        return heat_answer.asks_something(text)
    return bool(asks_now(text) or _FUTURE_RE.search(text or "") or _named_ids(text or "") or _HISTORY_RE.search(text or "")
                or _SATELLITE_RE.search(text or "") or any(p.search(text or "") for p, _, _ in EXPERIMENTAL))


def names_flood(clause: str) -> bool:
    """A clause that is plainly about flooding: the word itself, or a flood
    source by name (the Sandy zone, 311, a FEMA map, the tide). The heat
    rules ask this of every clause without a heat word: "It was hot last
    summer. Was it inside the Sandy zone?" is a flood question. An alert or a
    warning alone is not enough: both hazards have them."""
    c = clause or ""
    # (A school, a hospital or public housing is an asset of either briefing, and a satellite measures both.)
    # ("Scenario" alone is a projection of either hazard; a stormwater or rain word makes it the city's flood maps.)
    dep_named = re.search(r"stormwater|storm water|\bdep\b|\brain|flood maps?", c, re.I)
    return bool(_FLOOD_RE.search(c) or EXPERIMENTAL[1][0].search(c)
                or [i for i in _named_ids(c) if i != "nws_alerts" and i not in ASSET_DOCS and (dep_named or i not in DEP)])


def recognised(question: str) -> bool:
    """True when a rule knows what kind of question this is, from its words alone."""
    q = question or ""
    return bool(asks_now(q) or _FUTURE_RE.search(q) or _named_ids(q) or _FLOOD_RE.search(q) or _SATELLITE_RE.search(q)
                or any(p.search(q) for p, _, _ in EXPERIMENTAL) or heat_answer.hazard_of(q) == "heat" or asks_advice(q))


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
    if not_english(question):
        return "not_english", []
    heat = heat_answer.hazard_of(question) == "heat"
    if not heat:
        question = _HOUSE_YEAR_RE.sub("", question)
    if not heat and asks_advice(question) and not asks_now(question):
        # Out of scope, said first. Safety and basements: the observed record, the stormwater maps, then FEMA.
        # Insurance and price: the FEMA zone, the effective map before the preliminary one. ("Is the street
        # passable right now, or should I move my car" is a question about now: the live readings answer.)
        return "no_advice", [d for d in (SAFETY_FACTS if _SAFETY_RE.search(question) else ADVICE_FACTS) if texts.get(d)]
    if not_held(question):
        return "not_held", []  # the sentence that says what is not held is synthesis's to print (not_held again)
    if heat:
        return heat_answer.answer(question, texts, values)
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
        same = len({a[0] for _, a in parts}) == 1  # "how much is paved and how much is green": one lead for both
        return (first if first in ("yes", "no", "partly") or same else "facts"), facts
    return _answer_one(question, texts, values)


def _answer_one(question: str, texts: dict[str, str], values: dict | None = None, *,
                generic: bool = True) -> tuple[str, list[str]] | None:
    """One question, or one part of a two-part question (`generic` False:
    a part that names nothing gets no answer, so a preamble adds no facts)."""
    tf = time_frame(question)
    subjects = named(question, texts)
    assets = [d for d in subjects if d in ASSET_DOCS]

    official, models = experimental(question, texts)

    def with_named(lead: str, facts: list[str]) -> tuple[str, list[str]]:
        # A model the question names follows the record; it never leads it,
        # and a question about what the model showed gets no yes or no from
        # the record above it ("did satellite imagery show flooding" is not
        # answered "Yes." by a surveyed mark).
        lead = "facts" if (models or _SATELLITE_RE.search(question)) and lead in ("yes", "no", "partly") else lead
        return lead, [*[*facts, *(d for d in subjects if d not in facts)][:6], *models]

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
        return ("facts", [*live[:6], *models]) if live else None
    if assets:
        # The register sentence already says which assets are in the Sandy
        # extent and the DEP scenario, so those layers are the criteria of an
        # asset question, not further subjects.
        lead = _asset_lead(question, assets, values)
        if lead != "facts" and tf == "future" and not _MAP_SHOWS_RE.search(question):
            lead = "facts"  # "will the schools flood by 2080": a scenario is not an observation
        if _WILL_FLOOD_RE.search(question) and not (_MAP_SHOWS_RE.search(question) or _FAR_RE.search(question)
                                                     or _SCENARIO_RE.search(question)):
            # "Which schools in BK18 will flood?": a prediction, declined for an area's assets as for an
            # address, before the register that says which sit inside a mapped extent.
            lead = "no_prediction_register"
        return lead, assets
    happened = _happened_clause(question) if tf == "past" else None
    if happened and not ac.storm_of_day(question) and (day := ac.day_lead(question, texts, values)):
        # "Did it flood on May 20, 2026?": the sensor events dated that day. (A day of Ida or Sandy is
        # the storm's own record's to answer, below.)
        return day[0], day[2]
    if _SATELLITE_RE.search(question) and not models and not official and tf != "future":
        # "What did satellite imagery show after Ida": no source here says. The
        # storm's own surveyed record first, then the rest of the observed record.
        storm = ac._storm_record(question)
        seen = [d for d in (storm, *OBSERVED) if d and texts.get(d)]
        return ("no_satellite", list(dict.fromkeys(seen))) if seen else None
    if happened:
        # Whether it flooded is the record's to answer, and no model says
        # anything about the past: "Has the pavement here ever flooded?" is
        # not a land-cover question.
        models = []
    # (A statement is not a question: "My landlord says it will never flood." is a preamble.)
    stated = question.rstrip().endswith((".", "!")) and not ac.is_yes_no_question(question)
    if _WILL_FLOOD_RE.search(question) and not stated and not (
            _MAP_SHOWS_RE.search(question) or _FAR_RE.search(question) or _SCENARIO_RE.search(question)):
        # (A question about a named scenario or a far horizon is answered by that projection, below.)
        ahead = [d for d in NO_PREDICTION_FACTS if texts.get(d)]
        return ("no_prediction", [*ahead, *(models or [d for d in ("ttm_battery_surge",) if texts.get(d)])]) if ahead else None
    if (models or official) and not happened:
        # The model's hedged sentence is the answer, after the official source
        # for the same thing when one answered.
        if EXPERIMENTAL[0][0].search(question) and _CHANGE_RE.search(question):
            # "Has it become more paved since 2018?": the map's figure and the model's are two methods, and
            # printed one after the other they read as a rise. The lead says so before either figure.
            return "no_change_record", [*official, *models]
        return ("facts" if official else "experimental"), [*official, *models]
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
        if models:
            # No record near enough to say, and the question asks what the model
            # showed: the record's sentence, then the model's, with no lead.
            return ("facts" if facts else "experimental"), [*facts, *models]
        if facts or not subjects:
            return lead, [*facts, *models]
        # The storm's point record does not exist for an area ("did Sandy flood
        # any of BX01"): the area's own sources answer. The Sandy share of an
        # area says yes or no by itself.
        share = (values or {}).get("sandy_nta") if "sandy_nta" in subjects else None
        if isinstance(share, dict) and share.get("fraction") is not None and ac.is_yes_no_question(happened):
            return _share_lead(share["fraction"], happened), ["sandy_nta"]
        return "facts", [*subjects[:6], *models]
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
        if isinstance(shown, dict) and dep_code(shown) is not None and texts.get(asked) \
                and ac.is_yes_no_question(question) and _MAP_SHOWS_RE.search(question):
            # "Does the 2080 map show water here": what the map shows is a fact
            # about the map. "Will it flood" stays without a yes or no.
            return ("yes" if dep_code(shown) else "no"), [asked]
        far = _FAR_RE.search(question)  # a question about the 2050s is not about this week's tide,
        near = _NEAR_RE.search(question)  # and one about the next few days is not about the 2050s
        docs = ([d for d in texts if asked and d.startswith(asked)]
                or [d for d in subjects if d in DEP]
                or [i for i in FORECAST_FACTS if texts.get(i) and not (far and i == "nws_water_forecast")
                    and not (near and not far and i != "nws_water_forecast")][:4])
        return with_named("facts", docs) if docs else None
    if asks_cause(question) and not [d for d in subjects if d not in DEP]:
        # "Does rain flood 20 West 12th Road?": the sensors' events carry no cause (synthesis says so after
        # them), and the city's stormwater maps say which category is mapped there, rainfall or tidal.
        seen = [i for i in (*OBSERVED, *DEP) if texts.get(i)]
        if seen:
            return "facts", seen
    n = _count_of(subjects[0], question, (values or {}).get(subjects[0])) if subjects else None
    if (isinstance(n, int) and ac.is_yes_no_question(question) and _ANY_RE.search(question)
            and _COUNTED[subjects[0]].search(question)):
        # "Were any high-water marks surveyed near here": the source's own count says yes or no.
        return with_named("yes" if n else "no", [subjects[0]])
    if subjects:
        return "facts", subjects[:6]
    period = ("sandy", "ida") if ac._SINCE_RE.search(question) else ()  # "since Sandy" names a period, not a subject
    if any(i.partition("#")[0] != "nws_obs" and not i.startswith(period) for i in _named_ids(question)):
        # The question names a source and that source returned nothing (it
        # failed, or it does not exist for this kind of place): say so, do
        # not answer with something else. A flood-zone question about a
        # neighbourhood, which has no FEMA reading of its own, still gets
        # the two maps the area does have, under the cannot-answer line.
        mapped = [d for d in ("sandy_nta", "dep_moderate_current_nta") if texts.get(d)] if TOPICS[0][0].search(question) else []
        if not mapped and any(d.endswith("_nta") for d in texts) and any(i in ADDRESS_ONLY for i in _named_ids(question)):
            # "How deep did the water get on 183rd Street in Hollis during Ida?": no house number, so the
            # question was read for the neighbourhood, and the marks are read around an address. Say that
            # and what to type (it once ended "Here is what they show." and showed nothing).
            return "needs_address", []
        return "cannot_answer", mapped
    if generic and _FLOOD_RE.search(question) and plain_flood_question(question):
        seen = [i for i in OBSERVED if texts.get(i)]
        return ("facts", seen) if seen else None
    return None
