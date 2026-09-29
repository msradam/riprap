"""The district share sentence for a DEP scenario: rainfall flooding by
depth class, and the future high tide area (class 3) apart from it."""

from app.areas import nta_evidence
from app.flood_layers import dep_stormwater


def _share(monkeypatch, scenario, fractions):
    monkeypatch.setattr(dep_stormwater, "coverage_for_polygon", lambda polygon, scen: {
        "scenario": scen, "label": dep_stormwater.label(scen), "fraction_any": round(sum(fractions.values()), 4),
        "fraction_class": dict(fractions), "polygon_area_m2": 1.0})
    return nta_evidence.dep(None, scenario)


def test_2050_share_names_the_future_high_tide_area(monkeypatch):
    v = _share(monkeypatch, "dep_moderate_2050", {1: 0.015, 2: 0.0, 3: 0.2})
    assert v["narrative"] == (
        "DEP Moderate Stormwater (2.13 in/hr, 2050 SLR): 1.5% of this area is modeled to flood from rainfall, "
        "1.5% as nuisance flooding (4 in to under 1 ft) and 0.0% as deep and contiguous flooding (1 ft or more); "
        "20.0% is in the future high tide area (coastal tidal inundation projected for 2050).")
    assert v["headline_value"] == "1.5% modeled to flood from rainfall, 20.0% future high tide"


def test_2080_share_uses_its_year(monkeypatch):
    v = _share(monkeypatch, "dep_extreme_2080", {1: 0.1, 2: 0.05, 3: 0.01})
    assert "15.0% of this area is modeled to flood from rainfall" in v["narrative"]
    assert v["narrative"].endswith("1.0% is in the future high tide area (coastal tidal inundation projected for 2080).")


def test_current_share_has_no_tide_clause(monkeypatch):
    v = _share(monkeypatch, "dep_moderate_current", {1: 0.02, 2: 0.01, 3: 0.0})
    assert v["narrative"] == (
        "DEP Moderate Stormwater (2.13 in/hr, current SLR): 3.0% of this area is modeled to flood from rainfall, "
        "2.0% as nuisance flooding (4 in to under 1 ft) and 1.0% as deep and contiguous flooding (1 ft or more).")
    assert "4 ft" not in v["narrative"]
