"""Bare-address briefings (refactor 5, phase 5): a cited lead built from
the verified facts, one DEP sentence instead of three, and plain words for
percentile, HAND and TWI. Offline: the pebble values are given."""

from app.context.microtopo import _ordinal
from app.context.nyc311 import Complaint, _summarize
from riprap.core.burr.templated_reconciler import compose_briefing
from riprap.core.compliance import check_briefing
from riprap.core.compliance.predicates import every_numeric_claim_cited


def _manifest(sid):
    from types import SimpleNamespace

    return SimpleNamespace(id=sid, title="t", provenance=SimpleNamespace(citation="DEP"))


def _dep(sid, cls):
    """The pebble value as the shaper makes it, so the lead is checked against the real sentence."""
    from riprap.core.pebbles.shapers.dep_scenario import shape

    return shape({"depth_class": cls, "edge_m": None}, _manifest(sid))


STATE = {
    "intent": "single_address", "deployment": "nyc", "plan": {"question": ""},
    "sandy": {"inside": False, "inside_phrasing": "sits outside", "inside_or_outside": "outside", "edge_note": ""},
    "fema_nfhl": {"fld_zone": "X", "firm_panel": "3604970234F", "effective_year": 2007,
                  "narrative": "This address sits in FEMA flood zone X, per NFHL FIRM panel 3604970234F, effective 2007."},
    "dep_moderate_current": _dep("dep_moderate_current", 0),
    "dep_moderate_2050": _dep("dep_moderate_2050", 0),
    "dep_extreme_2080": _dep("dep_extreme_2080", 3),
    "nyc311": _summarize([Complaint("1", "Sewer Backup (Use Comments) (SA)", "2025-01-01", None, None)] * 82,
                         years=5, radius_m=200),
}


def test_bare_address_opens_with_a_cited_lead():
    paragraph, _ = compose_briefing(STATE)
    lead = paragraph.split("**In brief.**\n", 1)[1].split("\n\n", 1)[0]
    assert lead == ("This address is outside the 2012 Sandy inundation footprint [sandy_inundation], "
                    "in FEMA flood zone X on the 2007 effective map [fema_nfhl], and inside the future high tide category "
                    "(coastal tidal inundation, not rainfall flooding) of the city's stormwater flood maps (modelled "
                    "scenarios, not forecasts) for 2080 sea-level rise [dep_extreme_2080]. 82 flood and sewer 311 "
                    f"complaints were filed within 200 m in the last 5 years, since {STATE['nyc311']['since']} (a count "
                    "of reports; a low count can mean "
                    "under-reporting, not the absence of flooding) [nyc311].")
    assert every_numeric_claim_cited(paragraph)
    assert [r.name for r in check_briefing(paragraph).failed] == []
    # Outside New York the lead has no Sandy clause, so the zone's own map year
    # is the only vintage in the sentence (the Chicago briefing failed FEMA 1.5).
    elsewhere = {k: v for k, v in STATE.items() if k in ("intent", "plan", "fema_nfhl")} | {"deployment": "chicago"}
    assert "firm_citation_has_vintage" not in [r.name for r in check_briefing(compose_briefing(elsewhere)[0]).failed]


def test_all_outside_lead_names_the_horizons_and_passes_the_disclosure_checks():
    dry = {**STATE, "dep_extreme_2080": _dep("dep_extreme_2080", 0)}
    paragraph, _ = compose_briefing(dry)
    assert ("outside every flooding category on the city's stormwater flood maps (modelled scenarios, not forecasts) "
            "for current, 2050 and 2080 sea-level rise [dep_moderate_current][dep_moderate_2050][dep_extreme_2080]") in paragraph
    report = check_briefing(paragraph)
    assert [r.name for r in report.failed] == []


def test_question_briefings_have_no_lead():
    paragraph, _ = compose_briefing({**STATE, "plan": {"question": "Has this block flooded?"}})
    assert "**In brief.**" not in paragraph


def test_dep_scenarios_are_one_sentence_naming_each_result():
    paragraph, _ = compose_briefing(STATE)
    assert "are modelled scenarios (each a design storm paired with a sea level), not forecasts:" not in paragraph  # the template sentences are gone
    assert ("at the point mapped for this address they show: "
            '"Moderate Flood (2.13 inches/hr) with Current Sea Levels" (the near term), no flooding category '
            '[dep_moderate_current]; "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise", no flooding category '
            '[dep_moderate_2050]; "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", the category "Future High '
            'Tides 2080" (coastal tidal inundation, not rainfall flooding) [dep_extreme_2080].') in paragraph
    assert [r.name for r in check_briefing(paragraph).failed] == []


def test_dep_class_labels_follow_the_files_domain():
    from app.flood_layers.dep_stormwater import class_label, domain

    assert [class_label(c, "dep_moderate_2050") for c in (0, 1, 2, 3)] == [
        "outside", "nuisance flooding (4 in to under 1 ft)", "deep and contiguous flooding (1 ft or more)",
        "future high tides: coastal tidal inundation projected for 2050"]
    assert class_label(3, "dep_extreme_2080") == "future high tides: coastal tidal inundation projected for 2080"
    assert domain("dep_moderate_2050")[3] == "Future High Tides 2050"
    assert domain("dep_extreme_2080")[2] == "Deep and Contiguous Flooding (1 ft. and greater)"
    assert 3 not in domain("dep_moderate_current")


def test_dep_scenario_narration_per_class():
    from riprap.core.pebbles.shapers.dep_scenario import shape

    m50, m80 = _manifest("dep_moderate_2050"), _manifest("dep_extreme_2080")
    limits = (" The city's stormwater flood maps are modelled scenarios (each a design storm paired with a sea level), "
              "not forecasts: their rainfall flooding categories cover public areas and rain only, the city says the "
              'map "does not provide the exact depth of flooding at any location", and it is not a flood plain '
              "determination.")
    stem = 'The city\'s stormwater flood map "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise" shows the category '
    assert shape(1, m50)["narrative"] == (stem + '"Nuisance Flooding (greater or equal to 4 in. and less than 1 ft.)" at '
                                          "the point mapped for this address." + limits.format(year=2050))
    assert shape(2, m50)["narrative"] == (stem + '"Deep and Contiguous Flooding (1 ft. and greater)" at the point mapped '
                                          "for this address." + limits.format(year=2050))
    assert shape(3, m50)["narrative"] == (stem + '"Future High Tides 2050" (coastal tidal inundation, not rainfall '
                                          "flooding) at the point mapped for this address." + limits.format(year=2050))
    assert shape(3, m80)["narrative"] == ('The city\'s stormwater flood map "Extreme Flood (3.66 inches/hr) with 2080 Sea '
                                          'Level Rise" shows the category "Future High Tides 2080" (coastal tidal '
                                          "inundation, not rainfall flooding) at the point mapped for this address."
                                          + limits.format(year=2080))
    # The value names the map's category by code and by the city's name; no key calls it a depth.
    v = shape(3, m80)
    assert (v["category_code"], v["category"]) == (3, "Future High Tides 2080") and not [k for k in v if "depth" in k]
    for cls in (1, 2, 3):
        assert "4 ft" not in shape(cls, m50)["narrative"]


def test_rain_and_tide_hits_get_separate_lead_clauses():
    mixed = {**STATE, "dep_moderate_current": _dep("dep_moderate_current", 2)}
    paragraph, _ = compose_briefing(mixed)
    assert ("inside a rainfall flooding category on the city's stormwater flood maps (modelled scenarios, not forecasts) "
            "for current sea level (the near term) [dep_moderate_current]") in paragraph
    assert "(modelled scenarios, not forecasts) for 2080 sea-level rise [dep_extreme_2080]" in paragraph
    assert [r.name for r in check_briefing(paragraph).failed] == []


def test_percentiles_are_ordinals():
    assert [_ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21, 29, 112)] == \
        ["1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "29th", "112th"]


def test_current_only_flooding_still_names_a_horizon():
    wet_now = {**STATE, "dep_moderate_current": _dep("dep_moderate_current", 1),
               "dep_extreme_2080": _dep("dep_extreme_2080", 0)}
    paragraph, _ = compose_briefing(wet_now)
    assert "for current sea level (the near term) [dep_moderate_current]" in paragraph
    assert [r.name for r in check_briefing(paragraph).failed] == []


def test_llm_render_cites_every_numeric_sentence_of_a_quoted_fact():
    from riprap.core.burr.synthesis import Doc, _render

    fact = ("USGS surveyed 2 Hurricane Ida high-water mark(s) within 800 m of this address. "
            "Nearest mark: 182nd St. (174 m away)")
    kept = [{"section": "answer", "text": fact, "doc_ids": ["ida_hwm"], "numbers": []}]
    out = _render(kept, [Doc("ida_hwm", "Hazard Reader", fact, False)], ["Hazard Reader"], "q?", "Yes.")
    assert "within 800 m of this address [ida_hwm]." in out and "(174 m away) [ida_hwm]." in out
    assert every_numeric_claim_cited(out)


def test_scope_header_says_precomputed_not_baked():
    from riprap.core.burr.templated_reconciler import _scope_header

    h = _scope_header()
    assert "from live and precomputed data sources" in h and "baked" not in h
