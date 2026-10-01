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
    assert s["narrative"].startswith("0 flood-exposed NYC DOE schools within 1500 m of this address "
                                     "(the register lists only schools found inside the 2012 Sandy")
    assert "not every school" in s["narrative"]
    assert _register_counts(s["narrative"] + ".") == (0, 0, 0)
    n = exposure.summary_for_point(*ROCKAWAY, "nycha")
    assert "flood-exposed NYCHA development" in n["narrative"] and "not every development" in n["narrative"]


def test_exposed_register_counts_every_row_in_range_and_lists_the_nearest():
    from app.registers import exposure

    s = exposure.summary_for_point(*ROCKAWAY, "doe_schools", radius_m=3000, max_n=2)
    assert s["n_schools"] > 2 and len(s["schools"]) == 2
    assert s["narrative"].startswith(f"{s['n_schools']} flood-exposed NYC DOE schools")


def test_full_layer_count_is_every_entrance_in_range():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "mta_entrances")
    assert s["n_entrances"] > s["n_checked"] == len(s["entrances"]) == 8
    assert f"; of the nearest {s['n_checked']}:" in s["narrative"]


def test_exposed_assets_are_named_nearest_first():
    """A question that asks which schools gets the schools, not only a count."""
    from app.registers import exposure

    s = exposure.summary_for_point(40.677, -74.0105, "doe_schools")  # Red Hook
    assert s["narrative"].endswith("Inside the 2012 Sandy extent: P.S. 015 Patrick F. Daly (116 m), "
                                   "South Brooklyn Community High School (328 m)")
    assert _register_counts(s["narrative"] + ".") == (2, 2, 0)  # the counts still parse


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
    assert n["narrative"].startswith("2 flood-exposed NYCHA developments in this area (the register lists only")
    assert n["narrative"].endswith("Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST")
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
