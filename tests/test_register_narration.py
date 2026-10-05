"""Register sentences say what was counted. The schools and NYCHA
registers hold only exposed assets, so their count must not read as every
asset in range; the MTA and hospital layers hold every asset, so their
count is every asset in range even when only the nearest are checked."""

from riprap.core.burr.answer_checks import _register_counts

BROOKLYN_HEIGHTS = (40.6905, -73.9935)  # 189 Atlantic Avenue
ROCKAWAY = (40.5947, -73.7668)


def test_helper_plural_scope_and_nearest():
    from app.registers._loader import narrative

    one = narrative("hospital", "hospitals", 1, 3000, 0, 0)
    assert one.startswith("1 hospital within 3000 m of this address: 0 inside")
    capped = narrative("MTA subway entrance", "MTA subway entrances", 43, 800, 1, 2, n_checked=8)
    assert capped.startswith("43 MTA subway entrances within 800 m of this address; of the nearest 8: 1 inside")
    assert "nearest" not in narrative("hospital", "hospitals", 3, 3000, 0, 0, n_checked=3)
    assert _register_counts(capped + ".") == (43, 1, 2)  # the answer checks still parse it


def test_exposed_only_register_names_its_scope():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "doe_schools")
    assert s["n_schools"] == 0
    assert s["narrative"].startswith("0 public schools inside a mapped flood extent within 1500 m of this address "
                                     "(from the NYC Department of Education's school locations for the 2019 to 2020")
    assert "not every school" in s["narrative"]
    assert _register_counts(s["narrative"] + ".") == (0, 0, 0)
    n = exposure.summary_for_point(*ROCKAWAY, "nycha")
    assert "NYCHA developments inside a mapped flood extent within" in n["narrative"] and "not every development" in n["narrative"]


def test_exposed_register_counts_every_row_in_range_and_lists_the_nearest():
    from app.registers import exposure

    s = exposure.summary_for_point(*ROCKAWAY, "doe_schools", radius_m=3000, max_n=2)
    assert s["n_schools"] > 2 and len(s["schools"]) == 2
    assert s["narrative"].startswith(f"{s['n_schools']} public schools inside a mapped flood extent within")


def test_full_layer_count_is_every_entrance_in_range():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "mta_entrances")
    assert s["n_entrances"] > s["n_checked"] == len(s["entrances"]) == 8
    assert f"; of the nearest {s['n_checked']}:" in s["narrative"]


def test_exposed_assets_are_named_nearest_first():
    """A question that asks which schools gets the schools, not only a count."""
    from app.registers import exposure

    s = exposure.summary_for_point(40.677, -74.0105, "doe_schools")  # Red Hook
    assert ("Inside the 2012 Sandy extent: P.S. 015 Patrick F. Daly (116 m), "
            "South Brooklyn Community High School (328 m). ") in s["narrative"]
    # A school within 50 m of the outline is named after them, and not counted as exposed.
    assert ("Outside the 2012 Sandy extent but within 50 m of its mapped edge (the outline is not "
            "exact to a building): Red Hook Neighborhood School (462 m), PAVE Academy Charter "
            "School (570 m). The city's stormwater flood maps are modelled scenarios") in s["narrative"]
    assert _register_counts(s["narrative"]) == (2, 2, 0)  # the counts still parse


def test_a_station_with_several_entrances_is_named_once():
    from app.registers import exposure

    s = exposure.summary_for_point(40.711001, -73.777712, "mta_entrances")  # Hollis
    assert s["n_in_dep_extreme_2080"] > 1 and s["narrative"].count("Jamaica-179 St (F)") == 1


def test_no_exposed_asset_names_nothing():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "doe_schools")
    assert "Inside the" not in s["narrative"]


def test_district_register_names_the_exposed_assets():
    """Brooklyn Community District 6: the two Red Hook developments were
    inside the Sandy extent (an independent overlay of phvi-damg on the
    Sandy polygons gives 60% and 85% of their sites; Gowanus 0.7%)."""
    from app.areas import nta
    from app.registers import exposure

    bk06 = nta.by_district("BK06")["geometry"]
    n = exposure.summary_for_polygon(bk06, "nycha")
    assert n["n_inside_sandy_2012"] == 2
    assert n["narrative"].startswith("2 NYCHA developments inside a mapped flood extent in this area (the register lists only")
    assert ("Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST. Under 10% of the outline inside "
            "the 2012 Sandy extent (not counted): GOWANUS") in n["narrative"]
    assert _register_counts(n["narrative"] + ".") == (2, 2, 0)
    m = exposure.summary_for_polygon(bk06, "mta_entrances")  # every entrance in the outline, each checked
    assert m["n_entrances"] > 20 and "(the register lists only" not in m["narrative"]


def test_district_floodplain_counts_come_from_the_planning_profile(monkeypatch):
    """A district briefing quotes NYC Planning's own counts of buildings,
    units and residents in the 1% floodplain, with their basis; a
    neighbourhood has no such profile and the source says nothing."""
    from types import SimpleNamespace

    from app.areas import nta_evidence
    from riprap.core import http

    seen = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rows": [{"fp_100_bldg": 327, "fp_100_resunits": 1972, "fp_100_pop": 580.0, "fp_100_area": 0.28}]}

    monkeypatch.setattr(http, "get", lambda url, **k: seen.update(k["params"]) or R())
    v = nta_evidence.floodplain(None, SimpleNamespace(extras={"area_code": "BX01"}))
    assert "borocd = 201" in seen["q"]
    assert (v["n_buildings"], v["n_residential_units"], v["n_residents_2010"]) == (327, 1972, 580)
    assert v["narrative"].startswith("NYC Planning's Community District Profile counts 327 buildings, 1,972 "
                                     "residential units and 580 residents in the 1% annual chance floodplain")
    assert "2010 census" in v["narrative"] and "2015 preliminary" in v["narrative"]
    assert nta_evidence.floodplain(None, SimpleNamespace(extras={"area_code": "BK0603"})) is None  # a neighbourhood


def test_the_tidal_category_is_not_counted_as_stormwater_flooding():
    """Class 3 of the Extreme map is "Future High Tides 2080", coastal tidal
    inundation. Four schools near Coney Island in that category were listed
    "Inside the modeled DEP extreme scenario". The sentence names the map as
    the city does, splits its count, and lists the two kinds apart; the
    map's limits travel with the list."""
    from app.registers import exposure

    s = exposure.summary_for_point(40.5757, -73.986, "doe_schools")
    assert (s["n_in_dep_extreme_2080"], s["n_in_dep_extreme_2080_rainfall"], s["n_in_dep_extreme_2080_tidal"]) == (4, 0, 4)
    assert ('and 4 inside the DEP stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", a modelled '
            "scenario (0 in a rainfall flooding category and 4 in its future high tides category, which is coastal tidal "
            "inundation projected for 2080 and not rainfall flooding)") in s["narrative"]
    assert ('In the future high tides category of the modelled "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise" map '
            "(coastal tidal inundation projected for 2080, not rainfall flooding): ") in s["narrative"]
    assert "In a rainfall flooding category of the modelled" not in s["narrative"]
    assert "extreme stormwater scenario" not in s["narrative"]
    assert s["narrative"].endswith('"does not provide the exact depth of flooding at any location", and it is not a '
                                   "flood plain determination.")
    assert _register_counts(s["narrative"])[2] == 4  # the lead rules still read every category


def test_a_station_gets_one_exposure_count_for_an_address_and_for_an_area():
    """Jamaica-179 St had 8 of 8 entrances inside for an address (each
    buffered by 8 m) and 5 of 9 for a district (the bare point). Every asset
    is now read at its own point by both paths, the sentence says so, no
    buffer is reported, and a row carries the kind of category, never a
    depth class for a structure."""
    from shapely.geometry import box

    from app.registers import exposure

    at = exposure.summary_for_point(40.711001, -73.777712, "mta_entrances")
    area = exposure.summary_for_polygon(box(-73.80, 40.70, -73.76, 40.72), "mta_entrances")
    by_point = {(e["entrance_lat"], e["entrance_lon"]): e["dep_extreme_2080_category"] for e in area["entrances"]}
    assert at["entrances"] and all(by_point[e["entrance_lat"], e["entrance_lon"]] == e["dep_extreme_2080_category"]
                                   for e in at["entrances"])
    for v in (at, area, exposure.summary_for_point(40.711001, -73.777712, "doh_hospitals")):
        assert "footprint_buffer_m" not in v
    assert "(each entrance read at its own point on the maps, with no buffer)" in at["narrative"]
    assert "(each entrance read at its own point on the maps, with no buffer)" in area["narrative"]
    row = at["entrances"][0]
    assert row["dep_extreme_2080_category"] in ("rainfall flooding", "future high tides", "outside")
    assert not [k for k in row if k.endswith(("_class", "_label"))]


def test_a_printed_zero_that_does_not_fit_is_said_to_be_printed(monkeypatch):
    """BX02's profile prints 0 residential units beside 848 residents. "The
    profile gives no residential unit count" was not what a reader saw in
    the table: the sentence says the profile prints a zero that does not fit."""
    from types import SimpleNamespace

    from app.areas import nta_evidence
    from riprap.core import http

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rows": [{"fp_100_bldg": 189, "fp_100_resunits": 0, "fp_100_pop": 848.0, "fp_100_area": 1.14}]}

    monkeypatch.setattr(http, "get", lambda url, **k: R())
    v = nta_evidence.floodplain(None, SimpleNamespace(extras={"area_code": "BX02"}))
    assert v["n_residential_units"] is None and "gives no" not in v["narrative"]
    assert v["narrative"].endswith("The profile prints 0 residential units for this district, a zero that does not fit its "
                                   "own count of 189 buildings and 848 residents, so it is not repeated here as a count.")


def test_an_initial_inside_a_name_in_capitals_does_not_end_the_sentence():
    """"JUDITH S [doe_school_exposure]. KAYE SCHOOL": the citation mark landed inside a school's name."""
    from riprap.core.burr.evidence import cite
    from riprap.core.compliance.predicates import _sentences

    text = "Inside the 2012 Sandy extent: JUDITH S. KAYE SCHOOL (120 m), P.S. 015 (300 m)."
    assert cite(text, "doe_school_exposure") == text[:-1] + " [doe_school_exposure]."
    assert _sentences("in FEMA flood zone X. FEMA uses the 2007 maps.") == ["in FEMA flood zone X.", "FEMA uses the 2007 maps."]
