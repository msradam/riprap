"""The district share sentence for a city stormwater flood map: rainfall
flooding by the city's own category names, the future high tide category
(class 3) apart from it, and what the map is and is not."""

from app.areas import nta_evidence
from app.flood_layers import dep_stormwater

LIMITS = ('not a forecast: its rainfall flooding categories cover public areas and rain only, it "does not provide the '
          'exact depth of flooding at any location", and it is not a flood plain determination.')


def _share(monkeypatch, scenario, fractions):
    monkeypatch.setattr(dep_stormwater, "coverage_for_polygon", lambda polygon, scen: {
        "scenario": scen, "label": dep_stormwater.label(scen), "fraction_any": round(sum(fractions.values()), 4),
        "fraction_class": dict(fractions), "polygon_area_m2": 1.0})
    return nta_evidence.dep(None, scenario)


def test_2050_share_names_the_future_high_tide_category(monkeypatch):
    v = _share(monkeypatch, "dep_moderate_2050", {1: 0.015, 2: 0.0, 3: 0.2})
    assert v["narrative"] == (
        'On the city\'s stormwater flood map "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise", 1.5% of this '
        'area is in a rainfall flooding category: 1.5% in "Nuisance Flooding (greater or equal to 4 in. and less than '
        '1 ft.)" and 0.0% in "Deep and Contiguous Flooding (1 ft. and greater)"; 20.0% is in its "Future High Tides '
        '2050" category, which is coastal tidal inundation projected for 2050. This map is a modelled scenario (a '
        f"design storm paired with 2050 sea level rise), {LIMITS}")
    assert v["headline_value"] == "1.5% modeled to flood from rainfall, 20.0% future high tide"


def test_2080_share_uses_its_year(monkeypatch):
    v = _share(monkeypatch, "dep_extreme_2080", {1: 0.1, 2: 0.05, 3: 0.01})
    assert "15.0% of this area is in a rainfall flooding category" in v["narrative"]
    assert ('1.0% is in its "Future High Tides 2080" category, which is coastal tidal inundation projected for 2080.'
            in v["narrative"])


def test_current_share_has_no_tide_clause_and_names_a_horizon(monkeypatch):
    v = _share(monkeypatch, "dep_moderate_current", {1: 0.02, 2: 0.01, 3: 0.0})
    assert v["narrative"] == (
        'On the city\'s stormwater flood map "Moderate Flood (2.13 inches/hr) with Current Sea Levels" (the near '
        'term), 3.0% of this area is in a rainfall flooding category: 2.0% in "Nuisance Flooding (greater or equal '
        'to 4 in. and less than 1 ft.)" and 1.0% in "Deep and Contiguous Flooding (1 ft. and greater)". This map is '
        f"a modelled scenario (a design storm paired with current sea levels, the near term), {LIMITS}")
    assert "tid" not in v["narrative"].lower()


def test_a_share_above_zero_still_reads_as_a_result():
    """The scenario caveat is the second sentence: a "not" in the first
    made every share read as an absence to the answer rules."""
    from riprap.core.burr import answer_checks as ac

    assert ac.reports_result(dep_stormwater.share_sentence({1: 0.02, 2: 0.01}, "dep_limited_current"))
