"""An address in another state keeps its city and state, so it routes to
that deployment or to none (routing.spec probes, design pass 2 closing round)."""

from riprap.core.burr.intake import heuristic_plan


def _target(q: str) -> str:
    return heuristic_plan(q)["targets"][0]["text"]


def test_out_of_state_addresses_keep_the_whole_address():
    assert _target("1 Dr Carlton B Goodlett Place, San Francisco, CA") == "1 Dr Carlton B Goodlett Place, San Francisco, CA"
    assert _target("1 Civic Plaza NW, Albuquerque, NM") == "1 Civic Plaza NW, Albuquerque, NM"


def test_new_york_addresses_keep_the_nyc_span():
    assert _target("90-01 183rd Street, Queens, NY 11423") == "90-01 183rd Street, Queens, NY 11423"
    assert _target("Is 80 Pioneer Street, Brooklyn at risk?") == "80 Pioneer Street, Brooklyn"
