"""Place findings of the 5 October 2026 sanity check (rows 1, 2, 10, 20, 22
and 31): an area routed by a point in the water, an address with an unlisted
street type briefed as a neighbourhood, a bare address sent upstate, and
areas answered under a name the reader did not type. Offline."""

import pytest
from burr.core import State

from app import geocode as g
from app.areas import nta
from riprap.core.burr.intake import heuristic_plan, resolve_area
from riprap.core.burr.place import place_phrase, resolve_query
from riprap.core.pebbles.deployments import pick_deployment


def _area(target: str, query: str | None = None):
    return resolve_area(State({"first_target": target, "query": query or target, "trace": []}))


def test_every_tabulation_area_and_district_routes_to_new_york():
    # The centre of 5 of the 262 areas is in the water, outside the coverage polygon: "Rockaway Park", "Broad
    # Channel", "Belle Harbor" and "City Island" got "Riprap could not build this briefing".
    areas = nta.load()
    assert len(areas) == 262
    for code, name in [*zip(areas["nta2020"], areas["ntaname"], strict=True), *((c, c) for c in sorted(set(areas["cdta2020"])))]:
        out = _area(name)
        assert out["nta"]["nta_code"] == code, name
        dep = pick_deployment(out["lat"], out["lon"])
        assert dep is not None and dep.name == "nyc", name


def test_area_sources_read_at_one_point_use_a_point_inside_the_area(monkeypatch):
    """The area alerts and the heat sources that take one point read it at
    the centroid, which for the same 5 areas is in the water."""
    from app.areas import nta_evidence
    from app.context import nws_alerts
    from app.heat import weather

    area = nta.resolve("Rockaway Park")[0]["geometry"]
    assert not area.contains(area.centroid) and area.contains(nta.centre(area))
    square = nta.resolve("Hollis")[0]["geometry"]
    assert nta.centre(square).equals(square.centroid)  # the centroid, wherever it is inside
    seen = []
    monkeypatch.setattr(nws_alerts, "summary_for_point", lambda lat, lon, **k: seen.append((lon, lat)) or {})
    nta_evidence.alerts(area)
    weather.alerts_area(area)
    weather._at_centre(lambda lat, lon: seen.append((lon, lat)) or {})(area)
    from shapely.geometry import Point

    assert len(seen) == 3 and all(area.contains(Point(p)) for p in seen)


@pytest.mark.parametrize("query,span", [
    ("1 Bowling Green", "1 Bowling Green"),  # was Greenpoint, by the letters of "Green"
    ("87 Dover Green, Staten Island", "87 Dover Green, Staten Island"),
    ("15 Central Park West", "15 Central Park West"),  # was all of Central Park
    ("1 bowling green", "1 bowling green"),
    ("10 Hudson Yards", "10 Hudson Yards"),
    ("Is 15 Central Park West in a flood zone?", "15 Central Park West"),
    ("How hot is 1 Bowling Green?", "1 Bowling Green"),
])
def test_a_house_number_and_a_name_is_an_address_whatever_the_street_type(query, span):
    assert resolve_query(query) == {"kind": "address", "text": span, "certain": True, "message": None}
    assert heuristic_plan(query)["intent"] == "single_address"


@pytest.mark.parametrize("query,place", [
    ("311 complaints in Red Hook", "Red Hook"), ("311 complaints red hook", "Red Hook"),
    ("100 year floodplain gowanus", "Gowanus"), ("2080 Coney Island", "Coney Island"),
    ("Since 2012 Red Hook has flooded twice", "Red Hook"), ("PS 15 Red Hook", "Red Hook"),
])
def test_a_count_a_year_or_a_label_is_not_a_house_number(query, place):
    assert resolve_query(query)["kind"] == "neighborhood" and resolve_query(query)["text"] == place


def test_a_name_is_matched_as_whole_words_never_by_its_letters():
    assert "Greenpoint" not in [h["nta_name"] for h in nta.resolve("Green")]
    assert nta.resolve("Bowling Green") == []
    assert [h["nta_name"] for h in nta.resolve("La Guardia")] == ["LaGuardia Airport"]
    assert nta.resolve("Hells Kitchen")[0]["nta_name"] == "Hell's Kitchen"
    assert nta.resolve("Kew Gardens")[0]["nta_name"] == "Kew Gardens"
    # In lower case too, a name after a house number is a street's, and "Green" is no neighbourhood.
    assert place_phrase("what about 15 central park west") is None
    assert place_phrase("Is Bowling Green flooded?") == "Bowling Green"


def _hit(number, street, borough):
    return g.GeocodeHit(address=f"{number} {street}, {borough}", borough=borough, lat=40.7, lon=-73.99, bbl=None,
                        bin=None, raw={"housenumber": number, "street": street})


def _no_nominatim(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the national lookup must not be asked")
    monkeypatch.setattr(g, "geocode_nominatim", boom)


def test_an_address_with_no_borough_is_looked_for_in_the_city_first(monkeypatch):
    # "45 Main Street" went to St. Lawrence County, 472 km north.
    _no_nominatim(monkeypatch)
    monkeypatch.setattr(g, "geocode", lambda text, limit=1: [_hit("45", "MAIN STREET", "Brooklyn"),
                                                             _hit("42-45", "MAIN STREET", "Queens")])
    hit = g.geocode_one("45 Main Street")
    assert hit.borough == "Brooklyn" and hit.note is None


def test_an_address_in_two_boroughs_says_which_was_chosen(monkeypatch):
    _no_nominatim(monkeypatch)
    hits = [_hit("100", "BROADWAY", "Manhattan"), _hit("100", "BROADWAY", "Brooklyn")]
    monkeypatch.setattr(g, "geocode", lambda text, limit=1: hits)
    bare = g.geocode_one("100 Broadway")
    assert bare.borough == "Manhattan"
    assert "more than one borough (Manhattan, Brooklyn)" in bare.note and "the one in Manhattan" in bare.note
    # With the borough, the hit in that borough, though it is not the first ("100 Broadway, Brooklyn" was refused).
    named = g.geocode_one("100 Broadway, Brooklyn")
    assert named.borough == "Brooklyn"


def test_an_address_in_another_city_is_not_looked_for_in_new_york(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Geosearch must not be called")
    monkeypatch.setattr(g, "geocode", boom)
    assert g._geosearch_in_city("45 Main Street, Albany NY") is None
    assert g._geosearch_in_city("45 Main Street", scope_hint="flood risk at 45 Main Street in Chicago") is None
    assert g._geosearch_in_city("Red Hook") is None


def test_a_name_answered_for_a_wider_area_says_so():
    # "Roosevelt Island" is briefed with the Upper East Side, and the prose says only "this area".
    geocode = _area("Roosevelt Island")["geocode"]
    assert geocode["address"] == "Upper East Side-Lenox Hill-Roosevelt Island, Manhattan"
    assert "Upper East Side-Lenox Hill-Roosevelt Island (Manhattan)" in geocode["note"]
    assert "also takes in Upper East Side and Lenox Hill" in geocode["note"]
    assert "no boundary for Roosevelt Island alone" in geocode["note"]


def test_a_name_that_is_several_areas_names_the_one_briefed_and_the_others():
    note = _area("East Harlem", "Is East Harlem hot?")["geocode"]["note"]
    assert "matches 2 of City Planning's 2020 Neighborhood Tabulation Areas" in note
    assert "describes East Harlem (North) (Manhattan) only" in note and "The other is East Harlem (South) (Manhattan)." in note
    assert "Murray Hill-Broadway Flushing (Queens)" in _area("Murray Hill")["geocode"]["note"]
    # The half or the borough the reader named has chosen already.
    assert _area("East Harlem", "East Harlem (South)")["geocode"]["note"] is None
    assert "Kips Bay" not in _area("Murray Hill, Queens")["geocode"]["note"].split("That area")[0]
    assert _area("Hunts Point")["geocode"]["note"] is None  # the area's own name needs no note


def test_a_district_says_its_shape_is_the_tabulation_approximation():
    # Manhattan district 6 holds 62 subway entrances in this shape and 27 in the official boundary.
    note = _area("MN06")["geocode"]["note"]
    assert "MN06 is City Planning's Community District Tabulation Area, an approximation of the official" in note
    assert "Counts of facilities inside it can differ" in note
    assert _area("BX")["geocode"]["note"] is None  # a borough is not an approximation
