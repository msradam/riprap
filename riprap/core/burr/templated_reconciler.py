"""Templated reconciler: the no-LLM Capstone.

In no-LLM mode the Burr app ends with `reconcile_templated` instead of
the LLM synthesis. The result is a deterministic briefing built from
each pebble's `narration.template` filled from its value dict (see
`evidence.py`).

Why this exists:
  * NGO / Pi-class deployments without a GPU or even a CPU LLM
  * Civic-tech audit: every claim is traceable to a manifest entry by
    construction, with no hallucination surface
  * Latency: sub-second briefing prose. The whole `/api/agent` round
    trip lands in under 30 s end-to-end, dominated by live HTTP probes
  * A baseline that the LLM tier can be compared against

The output shape (paragraph, audit, grounding, citations) matches the
LLM tier, so the frontend renders both the same way.
"""

from __future__ import annotations

import time

from burr.core import State, action

from riprap.core.burr import evidence
from riprap.core.pebbles.shapers.dep_scenario import code as dep_code
from riprap.core.pebbles.shapers.dep_scenario import result as dep_result
from riprap.core.pebbles.shapers.dep_scenario import shared_edge as dep_shared_edge

OUTSIDE_COVERAGE = ("This place is outside the cities Riprap covers. Only federal sources were read (FEMA flood "
                    "zones, the Weather Service, USGS gauges); no local record of past flooding, complaints or "
                    "sensors is included.")


def place_line(state) -> str | None:
    """Which place the briefing describes, in the text itself, with the
    note that says which tabulation area, borough or approximate district
    shape was used (`geocode.note`). The page and the JSON carry both
    beside the text; someone who copies the text alone has only "this
    area" and "this address"."""
    g = state.get("geocode") or {}
    if not g.get("address"):
        return None
    return f"Place described: {g['address']}." + (f" {g['note']}" if g.get("note") else "")


MORE_PLACES = ("This {asked} names more than one place ({names}). Riprap reads one place at a time, and this {given} is "
               "for {answered}; ask about each on its own, or set two side by side with \"{how}\".")
NOT_PLACED = ("This {asked} also names {names}, which Riprap could not match to a place in New York City, so this "
              "{given} is for {answered} alone.")


def with_place_notes(footer: str, text: str, answered: str, heat: bool, bare: bool = False) -> str:
    """The Out of scope footer with what a question or a bare query that
    names several places is told: which place was answered, and which
    were not read or not matched. ("Red Hook vs Hollis vs Coney Island"
    once briefed Red Hook without a word about the other two.)"""
    from riprap.core.burr import heat_answer

    def listed(items: list[str]) -> str:
        return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"

    words = {"asked": "query" if bare else "question", "given": "briefing" if bare else "answer",
             "answered": answered or "the place named at the top"}
    if others := heat_answer.places_named(text):
        note = MORE_PLACES.format(names=listed(others), how="heat A vs B" if heat else "A vs B", **words)
        footer = footer.replace("**Out of scope.** ", f"**Out of scope.** {note} ", 1)
    if unknown := heat_answer.not_placed(text):
        # "Is East Harlem hotter than Phoenix?" once dropped Phoenix without a word.
        note = NOT_PLACED.format(names=listed(unknown), **words)
        footer = footer.replace("**Out of scope.** ", f"**Out of scope.** {note} ", 1)
    return footer


def _scope_header(state=None) -> str:
    """The scope declaration every briefing opens with, for a place
    outside every deployment what was not read, and then the place the
    briefing describes (place_line)."""
    # The second and third sentences travel with every briefing, in the JSON and MCP output as on the page:
    # a briefing about a block is not a judgement on the people who live there.
    head = ("This is an automated hazard-exposure briefing produced by Riprap from "
            "live and precomputed data sources. It is informational only and not a "
            "substitute for a professional risk assessment. These are public records about a place, not an "
            "assessment of any property or of the people who live there. Riprap computes no score or rating, "
            "and records can be missing where people report less.")
    if state is None:
        return head
    head = f"{head} {OUTSIDE_COVERAGE}" if state.get("deployment") == "__none__" else head
    return f"{head}\n\n{place}" if (place := place_line(state)) else head


SCOPE_REFUSAL = (
    "Riprap does not answer this question. It reports public flood evidence for a "
    "place: flood maps, past flood records, live sensors and forecasts, each cited to "
    "its source. It does not give advice on buying, renting or insuring property, "
    "legal advice, or a prediction for a specific day. For those, consult a licensed "
    "professional; for a regulatory flood determination, use FEMA's Flood Map "
    "Service Center (msc.fema.gov); for a home in New York City, FloodHelpNY "
    "(floodhelpny.org) explains flood insurance and resiliency options."
)
HEAT_REFUSAL = (
    "Riprap does not answer this question. It reports public heat evidence for a place: "
    "the measured surface temperature, the Health Department's vulnerability index and "
    "heat illness counts, station records and the Weather Service's forecast, each cited "
    "to its source. It does not give health or safety advice, or say what to do in the "
    "heat. For that, see the NYC Health Department's extreme heat guidance (nyc.gov/health), "
    "the National Weather Service (weather.gov/safety/heat) or call 311; in an emergency "
    "call 911."
)
COVERAGE_REFUSAL = (
    "Riprap's New York City deployment covers flood and heat evidence. It has no {what} "
    "sources for this place, so it cannot answer this question. Ask about flooding or "
    "heat at this address to see what it does cover."
)
_HAZARD_WORDS = {"air": "air-quality"}


def refusal(state) -> str:
    """Fixed text for queries Riprap does not answer; never model prose."""
    plan = state.get("plan") or {}
    if state.get("intent") == "not_implemented":
        return plan.get("rationale") or "Riprap cannot answer this query."
    hazard = (plan.get("focus") or {}).get("hazard", "flood")
    if hazard == "heat":
        return HEAT_REFUSAL
    if hazard != "flood":
        return COVERAGE_REFUSAL.format(what=_HAZARD_WORDS.get(hazard, "other"))
    return SCOPE_REFUSAL


# (It once read "does not assess title, structural condition, or compliance with specific zoning rules": the
# words of a property report, in a tool that says it is not for real estate.)
NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing is not a flood zone determination, an engineering assessment or advice. "
    "Where a probe was offline at run time, the relevant section omits that signal."
)
# The portal's layers, as BetaNYC's announcement of it (beta.nyc, 2025-05-28) lists them, include "the new
# Outdoor Heat Exposure Index" and "Air Temperature". The line names the portal and BetaNYC, no individual.
HEAT_NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing does not measure the temperature inside a building, give health advice, or "
    "predict the heat on a given day at a given address. Air temperature and an outdoor heat exposure index are "
    "mapped on the NYC Urban Heat Portal (https://urbanheat.nyc), by BetaNYC. Where a source "
    "was offline at run time, the relevant section omits that signal."
)


# The four point stormwater maps, smallest storm first, and the sea level
# each is paired with. "2050 sea-level rise" (not "2050 sea level") is the
# phrase the disclosure check reads as a time horizon.
_DEP_HORIZON = {"dep_limited_current": "current", "dep_moderate_current": "current", "dep_moderate_2050": "2050",
                "dep_extreme_2080": "2080"}
_DEP_POINT = tuple(_DEP_HORIZON)
NOT_CHECKED = ("**Not checked.** These sources were consulted{when} and did not answer, so nothing above is a reading "
               "of them and their silence is not an absence:")


def _dep_sentence(state, items) -> str | None:
    """The stormwater map sentences as one statement: that the maps are
    modelled scenarios and not forecasts, what each shows at the mapped
    point by the city's own names (each part cited), what the maps do not
    give, and, when any reads outside, that outside does not mean safe.
    None unless two or more maps ran."""
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT, PLAN_CHANCE, named

    parts, outside = [], []
    shown = {pid: state.get(pid) for pid in _DEP_POINT
             if any(e.pebble_id == pid for e in items) and dep_code(state.get(pid)) is not None}
    # A mapped edge that two or more maps share is said once, after the list.
    edge = dep_shared_edge(shown)
    for pid, v in shown.items():
        e = next(e for e in items if e.pebble_id == pid)
        parts.append(f"{named(pid)}, {dep_result(v, pid, edge=not edge)} [{e.doc_id}]")
        if not dep_code(v):
            outside.append(e.doc_id)
    if len(parts) < 2:
        return None
    out = ("The city's stormwater flood maps are modelled scenarios (each a design storm paired with a sea level), "
           f"not forecasts; at the point mapped for this address they show: {'; '.join(parts)}{edge}. Their rainfall "
           "flooding categories cover public areas and rain only, and the city says the map \"does not provide the "
           "exact depth of flooding at any location\"; it is not a flood plain determination. "
           f"{PLAN_CHANCE}")
    return f"{out} {OUTSIDE_CAVEAT[:-1]} {''.join(f'[{i}]' for i in outside)}." if outside else out


def failed_sources(state) -> list[dict]:
    """The sources a run consulted that did not answer (a timeout, an HTTP
    error, an unreadable reply), each with its id, title, reason and the
    time it was tried. The briefing's "Not checked." section, the JSON
    result's `failed` and the MCP tools' `failed` all read this."""
    from riprap.core.pebbles.bridge import plain_reason

    # The reason in a reader's words: the raw error ("python_call: summary_for_point raised: HTTP 429 ...")
    # stays in the trace and the log.
    down = {t.get("step"): t for t in state.get("trace") or [] if t.get("ok") is False}
    return [{"id": e["id"], "title": e.get("title"),
             "reason": plain_reason(str(down[e["id"]].get("err") or "")) or "the source did not answer",
             "started_at": down[e["id"]].get("started_at")}
            for e in state.get("consulted") or [] if e["id"] in down]


def _not_checked(state) -> str | None:
    """The failed sources by name. A failed FEMA preliminary map once left
    a briefing saying zone X with no word that the map which reads AE
    there had not answered."""
    from datetime import UTC, datetime

    failed = failed_sources(state)
    if not failed:
        return None
    tried = [f["started_at"] for f in failed if f["started_at"]]
    when = f" at {datetime.fromtimestamp(min(tried), UTC):%Y-%m-%d %H:%M} UTC" if tried else ""
    return f"{NOT_CHECKED.format(when=when)} {'; '.join(f['title'] for f in failed)}."


def _lead(state, items) -> str | None:
    """A bare-address briefing's opening: the Sandy footprint, the FEMA
    zone, the DEP scenarios and the 311 count, each from its verified
    template sentence's value and cited, then checked by the claim
    verifier like any claim. Parts that fail the check are left out."""
    from app.flood_layers.dep_stormwater import TIDE_CLASS
    from riprap.core.burr.synthesis import Doc, verify

    by_pebble = {e.pebble_id: e for e in items}
    claims = []

    def add(pid: str, text: str, ids: list[str] | None = None):
        claims.append({"section": "lead", "text": text, "doc_ids": ids or [by_pebble[pid].doc_id]})

    if "sandy" in by_pebble and isinstance(state.get("sandy"), dict):
        edge = state["sandy"].get("edge_m")
        add("sandy", f"{'inside' if state['sandy'].get('inside') else 'outside'} the 2012 Sandy inundation footprint"
            + (f" (about {max(edge, 1)} m from its mapped edge)" if edge is not None else ""))
    fema = state.get("fema_nfhl")
    if "fema_nfhl" in by_pebble and isinstance(fema, dict) and fema.get("fld_zone"):
        from app.context.fema_nfhl import zone_reading

        reading = None if fema.get("sfha") else zone_reading(fema.get("zone_subty"))
        # The map's year goes with the zone (FEMA 1.5): outside New York the
        # sentence has no other year and the vintage check failed.
        year = fema.get("effective_year")
        add("fema_nfhl", f"in FEMA flood zone {fema['fld_zone']}" + (f" ({reading})" if reading else "")
            + (f" on the {year} effective map" if year else ""))
    dep = {p: state[p] for p in _DEP_POINT if p in by_pebble and isinstance(state.get(p), dict)}
    if dep:
        ids = [by_pebble[p].doc_id for p in dep]
        wet = [p for p, v in dep.items() if dep_code(v)]
        # Class 3 is the scenario's future high tide area (tidal inundation),
        # not its rainfall flooding, so it gets its own clause.
        rain = [p for p in wet if dep_code(dep[p]) != TIDE_CLASS]
        tide = [p for p in wet if dep_code(dep[p]) == TIDE_CLASS]

        def horizons(ps) -> str:
            """'current, 2050 and 2080 sea-level rise': the disclosure check needs a horizon."""
            h = list(dict.fromkeys(_DEP_HORIZON[p] for p in ps))  # two maps share the current sea level
            if h == ["current"]:
                return "current sea level (the near term)"
            return (h[0] if len(h) == 1 else f"{', '.join(h[:-1])} and {h[-1]}") + " sea-level rise"

        # What the city's map shows at the mapped point, never a finding for the lot.
        maps = "the city's stormwater flood maps (modelled scenarios, not forecasts)"
        if not wet:
            add("", f"outside every flooding category on {maps} for {horizons(dep)}"
                    + (", at a mapped edge" if any(v.get("edge_m") for v in dep.values()) else ""), ids)
        if rain:
            add("", f"inside a rainfall flooding category on {maps} for {horizons(rain)}",
                [by_pebble[p].doc_id for p in rain])
        if tide:
            add("", "inside the future high tide category (coastal tidal inundation, not rainfall flooding) of "
                    f"{maps} for {horizons(tide)}", [by_pebble[p].doc_id for p in tide])
        if not wet and not (state.get("sandy") or {}).get("inside") and not (fema or {}).get("sfha"):
            # Outside every mapped extent: the reading that most needs "outside is not safe".
            from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT

            claims.append({"section": "lead", "text": OUTSIDE_CAVEAT[:-1], "doc_ids": ids, "own_sentence": True})
    n311 = state.get("nyc311")
    if "nyc311" in by_pebble and isinstance(n311, dict) and "n" in n311:
        n = f"{'At least ' if n311.get('capped') else ''}{n311['n']}"
        # A count of reports, said so where the count is: a low one is not an absence of flooding.
        add("nyc311", f"{n} complaint{'s' if n311['n'] != 1 else ''} to 311 about flooding and sewer backups "
                      f"{'were' if n311['n'] != 1 else 'was'} filed within "
                      f"{n311['radius_m']:.0f} m in the last {n311['years']} years{_since(n311)} (a count of reports; "
                      "a low count can mean under-reporting, not the absence of flooding)")
    docs = [Doc(e.doc_id, "lead", e.text, False) for e in items]
    own = {c["text"] for c in claims if c.get("own_sentence")}
    kept, _ = verify(claims, docs)
    cited = [(c["doc_ids"], c["text"], f"{c['text']} {''.join(f'[{i}]' for i in c['doc_ids'])}") for c in kept]
    where = [t for ids, text, t in cited if "nyc311" not in ids and text not in own]
    after = [t for ids, text, t in cited if "nyc311" in ids or text in own]
    out = []
    if where:
        where = where if len(where) < 2 else [*where[:-1], f"and {where[-1]}"]
        out.append(f"This address is {(', ' if len(where) > 2 else ' ').join(where)}.")
    out += [f"{t}." for t in after]
    return " ".join(out) or None


def _since(n311: dict) -> str:
    """', since 2021-10-06': the window's first day, as the 311 source sentence states it."""
    return f", since {n311['since']}" if n311.get("since") else ""


def _area_lead(state, items) -> str | None:
    """A community district or neighbourhood briefing's opening, cited and
    checked like the address lead: what was reported first (the 311 count,
    with what the complaints were about), then what is mapped (the stormwater
    map shares, the Sandy share). The Sandy share led once, and for an
    inland district it is the smallest number."""
    from app.flood_layers.dep_stormwater import named
    from riprap.core.burr.synthesis import Doc, verify

    by_pebble = {e.pebble_id: e for e in items}
    claims = []
    n311 = state.get("nyc311_nta")
    if "nyc311_nta" in by_pebble and isinstance(n311, dict) and "n" in n311:
        # The total alone read as a count of floods: in QN12, 61% of it is sewer backups and 12% street
        # flooding. So the kinds come with it (311's descriptors, each kind's old and new name together).
        kinds = ", ".join(f"{k} {kind}" for kind, k in (n311.get("by_kind") or {}).items())
        claims.append({"section": "lead", "doc_ids": [by_pebble["nyc311_nta"].doc_id],
                       "text": f"{'At least ' if n311.get('capped') else ''}{n311['n']} "
                               f"complaint{'s' if n311['n'] != 1 else ''} to 311 about flooding and sewer backups "
                               f"{'were' if n311['n'] != 1 else 'was'} filed "
                               f"{n311.get('where') or 'inside this area'} in the last {n311['years']} years"
                               f"{_since(n311)}"
                               + (f", by 311 descriptor group: {kinds}" if kinds else "")
                               + " (a count of reports; a low count can mean under-reporting, not the absence of "
                                 "flooding)"})
    shares = []
    for pid in ("dep_extreme_2080_nta", "dep_moderate_2050_nta"):
        v = state.get(pid)
        if pid in by_pebble and isinstance(v, dict) and v.get("fraction_class") is not None:
            # Classes 1 and 2 are rainfall flooding, the share the cited
            # sentence states; class 3 is the map's future high tide category.
            rain = sum(f for k, f in v["fraction_class"].items() if str(k) in ("1", "2"))
            tide = round(float(v["fraction_class"].get("3", v["fraction_class"].get(3, 0)) or 0) * 100, 1)
            shares.append((pid, f"{round(rain * 100, 1)}% of this area is in a rainfall flooding category of the "
                                f"city's modelled stormwater scenario {named(pid.removesuffix('_nta'))}"
                           + (f" and {tide}% is in its future high tide category" if tide else "")))
    if shares:
        claims.append({"section": "lead", "doc_ids": [by_pebble[p].doc_id for p, _ in shares],
                       "text": ", ".join(t for _, t in shares)})
    sandy = state.get("sandy_nta")
    if "sandy_nta" in by_pebble and isinstance(sandy, dict) and sandy.get("fraction") is not None:
        claims.append({"section": "lead", "doc_ids": [by_pebble["sandy_nta"].doc_id],
                       "text": f"{sandy['fraction'] * 100:.1f}% of this area lies inside the 2012 Sandy inundation extent"})
    docs = [Doc(e.doc_id, "lead", e.text, False) for e in items]
    kept, _ = verify(claims, docs)
    return " ".join(f"{c['text']} {''.join(f'[{i}]' for i in c['doc_ids'])}." for c in kept) or None


def _heat_lead(state, items, area: bool) -> str | None:
    """A heat briefing's opening for an address or an area: the measured
    surface temperature, the tree canopy on the city's map and the Health
    Department's index, each from its source's value, cited, and checked by
    the claim verifier like any claim."""
    from riprap.core.burr.synthesis import Doc, verify

    sfx = "_nta" if area else ""
    by_pebble = {e.pebble_id: e for e in items}
    claims = []

    def add(pid: str, text: str):
        claims.append({"section": "lead", "text": text, "doc_ids": [by_pebble[pid].doc_id]})

    v = state.get(f"heat_surface{sfx}")
    if f"heat_surface{sfx}" in by_pebble and isinstance(v, dict) and v.get("mean_diff_f") is not None:
        d = v["mean_diff_f"]
        whole = (state.get("nta") or {}).get("nta_code") in ("BX", "BK", "MN", "QN", "SI", "NYC")
        name = (state.get("nta") or {}).get("nta_name")
        # A borough or the city is said to be one: a school that resolved to its borough once read "this area".
        where = (f"{'the Bronx' if name == 'Bronx' else name} as a whole" if whole else "this area") if area \
            else f"the ground within {v['radius_m']:.0f} m of this address"
        how = "within half a degree of" if abs(d) < 0.5 else f"{abs(d):.1f}°F {'warmer' if d > 0 else 'cooler'} than"
        add(f"heat_surface{sfx}", f"The surface of {where} ran {how} the city's land average over {v['n_images']} clear "
                                  "summer Landsat images (surface temperature, not air temperature)")
    v = state.get(f"city_landcover{sfx}")
    if f"city_landcover{sfx}" in by_pebble and isinstance(v, dict) and v.get("tree_canopy_pct") is not None:
        where = "this area" if area else f"the ground within {v['radius_m']:.0f} m"
        add(f"city_landcover{sfx}", f"{v['tree_canopy_pct']}% of {where} is under tree canopy and {v['built_pct']}% is "
                                    "paved or built over on the city's 2017 land cover map")
    v = state.get(f"hvi{sfx}")
    if f"hvi{sfx}" in by_pebble and isinstance(v, dict) and v.get("hvi") is not None:
        whose = "This area" if area else f"Its neighbourhood, {v['area']},"
        add(f"hvi{sfx}", f"{whose} scores {v['hvi']} out of 5 on the Health Department's Heat Vulnerability Index, a "
                         "rank among neighbourhoods and not a measurement")
    docs = [Doc(e.doc_id, "lead", e.text, False) for e in items]
    kept, _ = verify(claims, docs)
    return " ".join(f"{c['text']} {''.join(f'[{i}]' for i in c['doc_ids'])}." for c in kept) or None


def no_place(state) -> str:
    """The briefing when the query named no place the geocoder could find."""
    from riprap.core.burr.rule_answer import ENGLISH_ONLY, not_english

    asked = (state.get("first_target") or state.get("query") or "").strip()
    out = (f"{_scope_header()}\n\nRiprap could not match \"{asked}\" to a place. Give a street address with "
           "its city or borough, such as 90-01 183rd Street, Queens, or an NYC community district such as QN12.")
    # A question in another language with no address in it lands here: it is told why in its own language too.
    return f"{out} {ENGLISH_ONLY}" if not_english(state.get("query") or "") else out


def nothing_built(state) -> str:
    """The briefing when no source produced evidence: which sources failed
    to respond and which answered with nothing, not a bare "no data"."""
    if state.get("lat") is None:
        return no_place(state)
    from riprap.core.burr.stones import hazard_of

    if hazard_of(state.get("plan")) == "heat" and state.get("deployment") != "nyc":
        where = (state.get("geocode") or {}).get("address") or "this place"
        return (f"{_scope_header()}\n\nRiprap's heat briefing covers New York City only, and the place it found for "
                f"this query is outside it: {where}. So this briefing has no heat evidence to show. If you meant a place "
                "in the city, add its borough.")
    ok = {t.get("step"): t.get("ok") for t in state.get("trace") or []}
    consulted = state.get("consulted") or []
    failed = [e["title"] for e in consulted if ok.get(e["id"]) is False]
    empty = [e["title"] for e in consulted if ok.get(e["id"]) is not False]
    out = [f"{_scope_header()}\n\nRiprap could not build this briefing: no source it consulted returned evidence "
           "for this place."]
    if failed:
        out.append(f"Failed to respond: {'; '.join(failed)}.")
    if empty:
        out.append(f"Answered with nothing for this place: {'; '.join(empty)}.")
    return " ".join(out)


# A plain place briefing quotes a live reading only when it is notable; a
# "right now" question quotes them all (rule_answer). The readings stay in
# the evidence table either way.
# ponytail: a fixed 1 ft above the predicted tide; use the gauge's own action
# stage if the tide source ever carries one.
_QUIET_UNLESS = {
    "nws_obs": lambda v: v.get("raining"),
    "usgs_gauges": lambda v: v.get("n_gauges_in_area"),
    "noaa_tides": lambda v: (v.get("residual_ft") or 0) >= 1.0,
    "nws_water_forecast": lambda v: v.get("flood_category"),
    # The experimental models: quoted in a plain briefing only when they show
    # something, never as a wall of caveats. A question that asks gets them.
    "ttm_battery_surge": lambda v: v.get("notable"),
    "landcover": lambda v: False,
    "landcover_nta": lambda v: False,
    # The city's land cover map: a question about paving or canopy gets it;
    # a flood briefing does not open with it.
    "city_landcover": lambda v: False,
    "city_landcover_nta": lambda v: False,
}
# A plain heat briefing quotes the city's land cover map (canopy is a ground
# condition of heat), and the live readings only on a hot day: an air
# temperature of 85 F or a forecast high of 90 F.
# ponytail: fixed thresholds; use the Weather Service's own HeatRisk category if the briefing ever reads it.
_QUIET_UNLESS_HEAT = {
    "landcover": lambda v: False,
    "landcover_nta": lambda v: False,
    **{k: (lambda v: (v.get("temp_f") or 0) >= 85) for k in ("heat_obs", "heat_obs_nta")},
    **{k: (lambda v: (v.get("max_high_f") or 0) >= 90 or (v.get("max_apparent_f") or 0) >= 95)
       for k in ("nws_heat_forecast", "nws_heat_forecast_nta")},
}


def _quiet(state, e) -> bool:
    from riprap.core.burr.stones import hazard_of

    rules = _QUIET_UNLESS_HEAT if hazard_of(state.get("plan")) == "heat" else _QUIET_UNLESS
    notable = rules.get(e.pebble_id)
    value = state.get(e.pebble_id)
    return bool(notable) and isinstance(value, dict) and not notable(value)


def compose_briefing(state) -> tuple[str, dict[str, dict]]:
    """One section per Stone (stones.yaml order), one cited sentence per
    pebble with a value, the DEP scenarios merged into one sentence.
    A bare-address briefing opens with a short cited lead. Returns
    (paragraph, citations by doc_id). A not_implemented query gets the
    planner's explanation instead."""
    if state.get("intent") in ("not_implemented", "out_of_scope"):
        return refusal(state), {}
    stones, registry = evidence.load(state.get("deployment"))
    items = evidence.collect(state, stones, registry)
    sections = [_scope_header(state)]
    question = (state.get("plan") or {}).get("question")
    intent = state.get("intent")
    from riprap.core.burr.stones import hazard_of

    if hazard_of(state.get("plan")) == "heat":
        lead = (_heat_lead(state, items, area=intent == "neighborhood")
                if intent in ("single_address", "neighborhood") and not question else None)
    else:
        lead = (_lead(state, items) if intent == "single_address" and not question
                else _area_lead(state, items) if intent == "neighborhood" and not question else None)
    if lead:
        sections.append(f"**In brief.**\n{lead}")
    dep, dep_done = _dep_sentence(state, items), False
    for stone in stones.all():
        if stone.id == "capstone":
            continue  # Capstone is the synthesis output, not a data stone
        out: list = []  # a finished sentence, or a (text, doc_id, every) fact still to cite
        for e in items:
            # An experimental source stays quiet under an unanswered question too.
            if e.stone_id != stone.id or ((not question or e.maturity == "experimental") and _quiet(state, e)):
                continue
            if dep and e.pebble_id in _DEP_POINT:
                if not dep_done:  # the merged sentence goes where the first scenario was
                    out.append(dep)
                    dep_done = True
                continue
            out.append((e.text, e.doc_id, e.maturity == "experimental"))
        # Cited together, so a closing sentence several sources share is printed once.
        cited = iter(evidence.cite_each([f for f in out if not isinstance(f, str)]))
        body = " ".join(filter(None, (f if isinstance(f, str) else next(cited) for f in out)))
        if body:
            sections.append(f"**{evidence.stone_heading(stone)}**\n{body}")
    if len(sections) == 1:
        return nothing_built(state), {}
    if failed := _not_checked(state):
        sections.append(failed)
    heat = hazard_of(state.get("plan")) == "heat"
    # A bare query (or a question nothing answered) that names several places says which one this is.
    sections.append(with_place_notes(HEAT_NON_SCOPE_FOOTER if heat else NON_SCOPE_FOOTER,
                                     question or state.get("query") or "",
                                     (state.get("geocode") or {}).get("address") or "", heat, bare=not question))
    return "\n\n".join(sections), evidence.citations(items)


@action(
    reads=["geocode", "intent", "deployment", "plan", "consulted", *evidence.all_pebble_ids()],
    writes=["paragraph", "audit", "grounding", "citations", "trace"],
)
def reconcile_templated(state: State) -> State:
    """Burr action: the no-LLM briefing. No model call; every sentence is
    a manifest template filled from a pebble value, and a question's answer
    is chosen by rules."""
    trace = list(state.get("trace", []))
    rec = {"step": "reconcile_templated", "started_at": time.time(), "ok": True,
           "result": None, "err": None, "elapsed_s": 0.0}
    grounding = {"tier": "no_llm", "claims": [], "dropped_claims": []}
    try:
        if (state.get("plan") or {}).get("question") and state.get("intent") not in ("not_implemented", "out_of_scope"):
            # A question: the rules pick the lead and the facts (rule_answer),
            # or the evidence briefing stands and says it was not answered.
            from riprap.core.burr.synthesis import synthesize

            out = synthesize(state, use_llm=False)
            paragraph, cites, grounding = out["paragraph"], out["citations"], out["grounding"]
            if (failed := _not_checked(state)) and failed not in paragraph:
                paragraph = f"{paragraph}\n\n{failed}"
        else:
            paragraph, cites = compose_briefing(state)
        rec["result"] = {"n_chars": len(paragraph), "n_citations": len(cites), "tier": "no_llm"}
    except Exception as e:  # noqa: BLE001 - surfaced via trace
        rec["ok"], rec["err"] = False, str(e)
        paragraph, cites = "", {}
    rec["elapsed_s"] = round(time.time() - rec["started_at"], 4)
    trace.append(rec)
    return state.update(
        paragraph=paragraph,
        audit={"raw": paragraph, "dropped": grounding.get("dropped_claims") or [], "tier": "no_llm"},
        grounding=grounding,
        citations=cites,
        trace=trace,
    )
