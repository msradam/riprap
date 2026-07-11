"""Heuristic-planner address extraction (no-LLM / templated tier).

The LLM planner extracts the address implicitly; the heuristic planner must
do it explicitly or the geocoder chokes on natural-language queries like
"flood risk at 250 Broadway".
"""

import pytest

from riprap.core.burr.intake import _address_from_query


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("flood risk at 250 Broadway, Manhattan", "250 Broadway, Manhattan"),
        ("what's the flood risk for 1 Wall St", "1 Wall St"),
        ("tell me about flooding near 100 Gold St, Brooklyn", "100 Gold St, Brooklyn"),
        ("is 442 East Houston St at risk of flooding?", "442 East Houston St"),
        ("show me 30 Rockefeller Plaza", "30 Rockefeller Plaza"),
        # Bare address / neighborhood — must pass through untouched.
        ("250 Broadway, Manhattan", "250 Broadway, Manhattan"),
        ("Red Hook, Brooklyn", "Red Hook, Brooklyn"),
    ],
)
def test_address_from_query(query: str, expected: str) -> None:
    assert _address_from_query(query) == expected


def test_empty_query_returns_empty() -> None:
    assert _address_from_query("") == ""
    assert _address_from_query("   ") == ""
