"""No-LLM place resolution (refactor 5): districts, address spans, short
place phrases, and the geocode match check. Offline: no geocoding."""

import pytest

from riprap.core.burr.place import (
    extract_address,
    geocode_matches,
    parse_district,
    place_phrase,
    resolve_query,
)


@pytest.mark.parametrize("text,code", [
    ("QN12", "QN12"), ("QN 12", "QN12"), ("qn-12", "QN12"), ("Queens CB 12", "QN12"),
    ("Queens Community Board 12", "QN12"), ("Community District 12 Queens", "QN12"), ("Queens CD 12", "QN12"),
    ("Brooklyn 15", "BK15"), ("BK15", "BK15"), ("BX 1", "BX01"), ("Staten Island community district 2", "SI02"),
    ("What share of Manhattan CD 3 flooded in Sandy?", "MN03"), ("How many complaints has QN04 had?", "QN04"),
])
def test_district_phrasings(text, code):
    assert parse_district(text) == (code, None)


def test_invalid_and_ambiguous_districts_are_refused_with_a_suggestion():
    code, msg = parse_district("Queens CB 15")
    assert code is None and "QN01 to QN14" in msg and "QN14" in msg
    assert parse_district("SI 4")[1].endswith("Did you mean SI03?")
    assert "Name the borough" in parse_district("Community District 12")[1]


def test_addresses_are_not_districts():
    assert parse_district("2017 East 17th Street, Brooklyn, NY 11229") == (None, None)
    assert parse_district("Brooklyn 11229") == (None, None)


@pytest.mark.parametrize("text,span", [
    ("Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?", "90-01 183rd Street, Queens"),
    ("How many flooding complaints have been made to 311 near 200 Water Street, Manhattan?",
     "200 Water Street, Manhattan"),
    ("Tell me about 355 Food Center Drive in the Bronx", "355 Food Center Drive, Bronx"),
    ("Is 200 Water Street in Manhattan in a FEMA flood zone", "200 Water Street, Manhattan"),
    ("Did the area around 79-01 Broadway, Queens flood during Hurricane Ida?", "79-01 Broadway, Queens"),
    ("90-01 183rd Street, Queens, NY 11423", "90-01 183rd Street, Queens, NY 11423"),
])
def test_address_span_is_extracted(text, span):
    assert extract_address(text) == span


def test_place_phrase_is_short_and_never_a_borough_alone():
    assert place_phrase("Is Red Hook at risk of flooding?") == "Red Hook"
    assert place_phrase("Jamaica, Queens") == "Jamaica"
    assert place_phrase("What is flooding like in Queens?") is None
    assert resolve_query("Queens")["kind"] is None


def test_geocode_match_needs_the_same_number_and_street():
    assert geocode_matches("90-01 183rd Street, Queens", "90-01 183 STREET, Hollis, NY, USA")
    assert geocode_matches("560 Grand Street, Manhattan", "560, Grand Street, Lower East Side, Manhattan")
    assert not geocode_matches("80 Pioneer Street", "82, Pioneer Street, Red Hook")
    assert not geocode_matches("2017 East 17th Street, Brooklyn", "2017 East 19th Street, Brooklyn")
    assert not geocode_matches("Yankee Stadium", "Yankee Stadium, Bronx")


def test_address_keeps_its_quadrant_and_city():
    from riprap.core.burr.place import extract_address

    assert extract_address("1600 Pennsylvania Ave NW, Washington DC") == "1600 Pennsylvania Ave NW, Washington DC"


@pytest.mark.parametrize("text", [
    "Broadway and 116th Street", "Flatbush Avenue and Avenue U, Brooklyn", "Water Street & Pearl Street",
    "flooding at Atlantic Avenue at Flatbush Avenue",
])
def test_an_intersection_is_refused_with_the_reason(text):
    r = resolve_query(text)
    assert r["kind"] == "invalid" and "intersection" in r["message"] and "house number" in r["message"]


def test_a_house_number_beside_a_corner_word_is_still_an_address():
    assert resolve_query("Is 200 Water Street at risk from Pearl Street and the river?")["kind"] == "address"


@pytest.mark.parametrize("text", ["11693", " 10305 ", "11423?"])
def test_a_zip_code_alone_is_refused_with_the_reason(text):
    r = resolve_query(text)
    assert r["kind"] == "invalid" and "ZIP code" in r["message"] and "street address" in r["message"]


def test_a_zip_after_an_address_stays_an_address():
    assert resolve_query("90-01 183rd Street, Queens, NY 11423")["kind"] == "address"
