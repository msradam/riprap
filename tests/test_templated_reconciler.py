"""Per-sentence citation repair in the no-LLM reconciler.

`every_numeric_claim_cited` (SPJ 7.1) audits per sentence, so a
multi-sentence pebble narrative with one trailing citation fails the
predicate on its earlier sentences. `_cite_numeric_sentences` is the
repair; these tests are the regression seal on the NYC 12/13 bug.
"""

from __future__ import annotations

from riprap.core.burr.evidence import cite as _cite_numeric_sentences
from riprap.core.compliance.predicates import every_numeric_claim_cited


def test_each_numeric_sentence_gets_marker():
    body = (
        "34 NYC 311 flood-related complaints filed within 200 m of this "
        "location in the last 5 years. Most common descriptor: Sewer Backup."
    )
    out = _cite_numeric_sentences(body, "nyc311")
    assert "200 m of this location in the last 5 years [nyc311]." in out
    # No unit-number in the descriptor sentence — left uncluttered.
    assert out.endswith("Most common descriptor: Sewer Backup.")


def test_abbreviation_fragments_without_numbers_untouched():
    body = (
        "No marks were surveyed within 800 m of this address. Nearest mark: "
        "Intersection of Carroll St. and Nevins St., Brooklyn (1459 m away)."
    )
    out = _cite_numeric_sentences(body, "ida_hwm")
    # The 'Carroll St.' fragment the naive splitter produces has no
    # unit-number, so no marker lands mid-name.
    assert "Carroll St. and" in out
    assert "(1459 m away) [ida_hwm]." in out


def test_already_cited_sentences_untouched():
    body = "Stage 2.31 ft at the gauge [usgs_gauges]."
    assert _cite_numeric_sentences(body, "usgs_gauges") == body


def test_repaired_paragraph_passes_the_predicate():
    body = (
        "Elevation 16.79 m; HAND 16.66 m above nearest drainage; TWI 9.46. "
        "Local basin relief: 10.61 m."
    )
    out = _cite_numeric_sentences(body, "microtopo")
    assert every_numeric_claim_cited(out).passed


# The sentences the reconciler words itself: the stormwater maps, the leads
# and the list of sources that failed.

def _state(**over):
    from types import SimpleNamespace

    from app.context.nyc311 import Complaint, _summarize
    from riprap.core.pebbles.shapers.dep_scenario import shape

    def dep(sid, cls, edge=None):
        return shape({"depth_class": cls, "edge_m": edge},
                     SimpleNamespace(id=sid, title="t", provenance=SimpleNamespace(citation="c")))

    return {
        "intent": "single_address", "deployment": "nyc", "plan": {"question": ""},
        "sandy": {"inside": False, "inside_phrasing": "sits outside", "inside_or_outside": "outside", "edge_note": ""},
        "dep_limited_current": dep("dep_limited_current", 0),
        "dep_moderate_current": dep("dep_moderate_current", 0, 6),
        "dep_moderate_2050": dep("dep_moderate_2050", 0, 6),
        "dep_extreme_2080": dep("dep_extreme_2080", 0, 4),
        "nyc311": _summarize([Complaint("1", "Sewer Backup (Use Comments) (SA)", "2025-01-01", None, None)] * 3,
                             years=5, radius_m=200),
        **over,
    }


def test_stormwater_sentence_names_each_map_as_a_scenario_at_the_mapped_point():
    from riprap.core.burr.templated_reconciler import compose_briefing
    from riprap.core.compliance import check_briefing

    paragraph, _ = compose_briefing(_state())
    assert ("The city's stormwater flood maps are modelled scenarios (each a design storm paired with a sea level), "
            "not forecasts; at the point mapped for this address they show: "
            '"Limited Flood (1.77 inches/hr) with Current Sea Levels" (the near term), no flooding category '
            "[dep_limited_current]; "
            '"Moderate Flood (2.13 inches/hr) with Current Sea Levels" (the near term), no flooding category '
            "[dep_moderate_current]; ") in paragraph
    # A mapped edge that several maps share is said once, after the list, and carried into the In brief.
    assert paragraph.count("within about") == 1 and "at a mapped edge [dep_limited_current]" in paragraph
    assert ('"Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", no flooding category [dep_extreme_2080]; on 3 of '
            "these maps the point is at the edge of mapped flooding (within about 6 m). Their rainfall flooding categories cover public areas "
            'and rain only, and the city says the map "does not provide the exact depth of flooding at any location"; '
            "it is not a flood plain determination.") in paragraph
    assert "DEP stormwater scenarios at this address" not in paragraph and "in/hr" not in paragraph
    assert [r.name for r in check_briefing(paragraph).failed] == []


def test_an_address_outside_every_mapped_extent_is_not_called_safe():
    """NYC Emergency Management: most buildings damaged in Ida were outside
    every mapped scenario. The caveat is in the In brief paragraph and in
    the stormwater sentence, each time an outside reading is."""
    from app.flood_layers.dep_stormwater import OUTSIDE_CAVEAT
    from riprap.core.burr.templated_reconciler import compose_briefing
    from riprap.core.compliance import check_briefing

    paragraph, _ = compose_briefing(_state())
    lead = paragraph.split("**In brief.**\n", 1)[1].split("\n\n", 1)[0]
    cited = "[dep_limited_current][dep_moderate_current][dep_moderate_2050][dep_extreme_2080]."
    assert ("outside every flooding category on the city's stormwater flood maps (modelled scenarios, not forecasts) "
            "for current, 2050 and 2080 sea-level rise") in lead
    assert f"{OUTSIDE_CAVEAT[:-1]} {cited}" in lead
    assert paragraph.count(OUTSIDE_CAVEAT[:-1]) == 2  # the lead, and the stormwater sentence in the body
    assert [r.name for r in check_briefing(paragraph).failed] == []
    # Inside a mapped extent, the lead makes no outside reading to qualify.
    wet = _state()
    wet["dep_extreme_2080"] = {**wet["dep_extreme_2080"], "category_code": 2}
    lead = compose_briefing(wet)[0].split("**In brief.**\n", 1)[1].split("\n\n", 1)[0]
    assert "does not mean safe" not in lead and "inside a rainfall flooding category on the city's" in lead


def test_the_address_lead_says_the_311_count_is_a_count_of_reports():
    from riprap.core.burr.templated_reconciler import compose_briefing

    state = _state()
    lead = compose_briefing(state)[0].split("**In brief.**\n", 1)[1].split("\n\n", 1)[0]
    # The source sentence's own words: "flood and sewer complaints", and the window's first day.
    assert (f"3 flood and sewer 311 complaints were filed within 200 m in the last 5 years, since "
            f"{state['nyc311']['since']} (a count of reports; a low count can mean under-reporting, not the absence "
            "of flooding) [nyc311].") in lead


def test_a_district_lead_carries_the_311_breakdown():
    """QN12's lead read "4499 flood-related 311 complaints" alone, though
    61% were sewer backups and 12% street flooding."""
    from app.context.nyc311 import Complaint, _summarize
    from riprap.core.burr.templated_reconciler import compose_briefing

    def c(desc, n):
        return [Complaint(f"{desc}{i}", desc, f"2025-01-01T00:{i:02d}:00", None, None) for i in range(n)]

    v = _summarize(c("Sewer Backup (Use Comments) (SA)", 6) + c("Catch Basin Clogged", 3) + c("Street Flooding (SJ)", 1),
                   years=3, radius_m=None, where="in Community District QN12 (by the record's community board field)")
    paragraph, _ = compose_briefing({"intent": "neighborhood", "deployment": "nyc", "plan": {"question": ""},
                                     "nyc311_nta": v})
    lead = paragraph.split("**In brief.**\n", 1)[1].split("\n\n", 1)[0]
    assert lead == ("10 flood and sewer 311 complaints were filed in Community District QN12 (by the record's community "
                    f"board field) in the last 3 years, since {v['since']}, by 311 descriptor group: 6 sewer backup, 3 catch basin, 1 street "
                    "flooding (a count of reports; a low count can mean under-reporting, not the absence of flooding) "
                    "[nyc311_nta].")


def test_a_source_that_failed_is_listed_as_not_checked():
    """FEMA's preliminary map service once failed for a Rockaway Park
    address: the sentence was dropped and the briefing said zone X with no
    word that the map which reads AE there had not answered."""
    from riprap.core.burr.templated_reconciler import compose_briefing
    from riprap.core.compliance import check_briefing

    consulted = [{"id": "fema_pfirm", "title": "FEMA preliminary flood map (PFIRM), flood zone at this point"},
                 {"id": "sandy", "title": "NYC Sandy Inundation Zone (2012 empirical extent)"},
                 {"id": "dcp_floodplain_nta", "title": "People and buildings in the floodplain"}]
    trace = [{"step": "fema_pfirm", "ok": False, "started_at": 1791212460.0,
              "err": "python_call: preliminary_for_point raised: timed out"},
             {"step": "sandy", "ok": True}, {"step": "dcp_floodplain_nta", "ok": True, "result": {"skipped": "x"}}]
    paragraph, _ = compose_briefing(_state(consulted=consulted, trace=trace))
    assert ("**Not checked.** These sources were consulted at 2026-10-05 15:01 UTC and did not answer, so nothing "
            "above is a reading of them and their silence is not an absence: FEMA preliminary flood map (PFIRM), "
            "flood zone at this point.\n\n**Out of scope.**") in paragraph
    assert [r.name for r in check_briefing(paragraph).failed] == []
    assert "**Not checked.**" not in compose_briefing(_state(consulted=consulted, trace=trace[1:]))[0]
    # The JSON result lists the same sources under `failed`, and a comparison lists both places'.
    from riprap.core.burr import app

    out = app._final({**_state(consulted=consulted, trace=trace), "paragraph": paragraph})
    assert out["failed"] == [{"id": "fema_pfirm", "title": consulted[0]["title"], "started_at": 1791212460.0,
                              "reason": "python_call: preliminary_for_point raised: timed out"}]
    assert app._final({**_state(consulted=consulted, trace=trace[1:]), "paragraph": paragraph})["failed"] == []
    plan = {"intent": "compare", "targets": [{"type": "address", "text": "A"}, {"type": "address", "text": "B"}]}
    both = app.run_compare("A vs B", plan, lambda q, p: {"paragraph": q, "lat": 40.7, "deployment": "nyc",
                                                         "failed": out["failed"] if q == "B" else []})
    assert both["failed"] == [{**out["failed"][0], "place": "PLACE B"}]


def test_a_sentence_shared_by_several_facts_is_printed_once_with_every_mark():
    """Four stormwater maps printed the city's disclaimer four times and
    "does not mean safe" once per map. Any sentence several quoted facts
    share is printed once, after the last of them, with all their marks."""
    from riprap.core.burr.evidence import cite_each

    out = cite_each([("Map A shows 3 ft. It is a scenario. Outside is not safe.", "a", False),
                     ("Map B shows 1 ft. It is a scenario.", "b", False),
                     ("Outside is not safe. It is a scenario.", "c", False),
                     ("12 complaints. A count is a count of reports.", "d", False)])
    assert out == ["Map A shows 3 ft [a].", "Map B shows 1 ft [b].",
                   "It is a scenario [a][b][c]. Outside is not safe [a][c].",
                   "12 complaints [d]. A count is a count of reports."]


def test_a_district_briefing_prints_the_stormwater_disclaimer_once():
    from app.flood_layers.dep_stormwater import share_sentence

    state = {"intent": "neighborhood", "deployment": "nyc", "plan": {},
             **{f"{s}_nta": {"fraction_class": {1: 0.02, 2: 0.01}, "narrative": share_sentence({1: 0.02, 2: 0.01}, s)}
                for s in ("dep_limited_current", "dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080")}}
    from riprap.core.burr.templated_reconciler import compose_briefing

    paragraph, _ = compose_briefing(state)
    assert paragraph.count("does not provide the exact depth of flooding at any location") == 1
    assert ("flood plain determination [dep_extreme_2080_nta][dep_moderate_2050_nta][dep_moderate_current_nta]"
            "[dep_limited_current_nta].") in paragraph


def test_the_briefing_text_itself_says_which_place_it_describes(monkeypatch):
    """The note that says which tabulation area or borough was chosen
    travelled beside the text (geocode.note, MCP place_note, the page's
    place line). Someone who copied the paragraph had only "this area"."""
    from types import SimpleNamespace

    from riprap.core.burr import synthesis as syn
    from riprap.core.burr.synthesis import Doc
    from riprap.core.burr.templated_reconciler import compose_briefing

    note = ("This briefing describes City Planning's 2020 Neighborhood Tabulation Area Upper East Side-Lenox "
            "Hill-Roosevelt Island (Manhattan), the area Riprap matched to the name Roosevelt Island.")
    geocode = {"address": "Upper East Side-Lenox Hill-Roosevelt Island, Manhattan", "note": note}
    paragraph, _ = compose_briefing(_state(geocode=geocode, query="Roosevelt Island"))
    top = paragraph.split("\n\n")
    assert top[1] == f"Place described: Upper East Side-Lenox Hill-Roosevelt Island, Manhattan. {note}"
    assert paragraph.count(note) == 1 and top[2].startswith("**In brief.**")
    # A place with no note is still named, and a rule answer and a heat answer open the same way.
    plain = compose_briefing(_state(geocode={"address": "80 PIONEER STREET, Brooklyn, NY, USA", "note": None}))[0]
    assert plain.split("\n\n")[1] == "Place described: 80 PIONEER STREET, Brooklyn, NY, USA."
    assert "Place described" not in compose_briefing(_state())[0]  # no place resolved: no line
    docs = [Doc("sandy_inundation", "Hazard Reader", "This address sits outside the 2012 Sandy footprint.", False),
            Doc("heat_surface", "Hazard Reader", "The surface here ran 2.0°F warmer than the city's land average.", False)]
    items = [SimpleNamespace(doc_id=d.doc_id, pebble_id=d.doc_id) for d in docs]
    monkeypatch.setattr(syn, "_documents", lambda s: (docs, items, None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    for question, hazard in (("Was this inside the area Hurricane Sandy flooded?", "flood"),
                             ("Is this block hotter than the rest of the city?", "heat")):
        out = syn.synthesize({"intent": "single_address", "geocode": geocode, "sandy_inundation": {"inside": False},
                              "heat_surface": {"mean_diff_f": 2.0, "n_images": 9},
                              "plan": {"question": question, "focus": {"hazard": hazard}}}, use_llm=False)
        assert out["paragraph"].split("\n\n")[1].startswith("Place described: Upper East Side"), question
        assert out["paragraph"].count(note) == 1 and "**Answer.**" in out["paragraph"]


def test_a_bare_query_naming_three_places_says_which_one_was_briefed():
    """"Red Hook vs Hollis vs Coney Island" briefed Red Hook without a word
    about the other two."""
    from riprap.core.burr.templated_reconciler import compose_briefing

    state = _state(intent="neighborhood", query="Red Hook vs Hollis vs Coney Island", plan={},
                   geocode={"address": "Carroll Gardens-Cobble Hill-Gowanus-Red Hook, Brooklyn", "note": None},
                   sandy_nta={"fraction": 0.3, "narrative": "30.0% of this area lies inside the 2012 Sandy extent."})
    paragraph, _ = compose_briefing(state)
    assert ("**Out of scope.** This query names more than one place (Red Hook, Hollis and Coney Island). Riprap reads "
            "one place at a time, and this briefing is for Carroll Gardens-Cobble Hill-Gowanus-Red Hook, Brooklyn; ask "
            'about each on its own, or set two side by side with "A vs B".') in paragraph
    assert "names more than one place" not in compose_briefing({**state, "query": "Red Hook"})[0]
