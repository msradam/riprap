"""A deployment's coverage is its polygon, not only its bbox: Hoboken and
Nassau County sit inside NYC's bbox and got the city's Sandy layer applied
("outside the 2012 Sandy inundation footprint", for a town that flooded)."""
from riprap.core.pebbles.deployments import pick_deployment


def test_new_jersey_and_nassau_points_are_out_of_nyc_coverage():
    assert pick_deployment(40.7433, -74.0324) is None  # Hoboken
    assert pick_deployment(40.7120, -73.7110) is None  # Elmont, Nassau County


def test_the_five_boroughs_stay_covered():
    for lat, lon in [(40.6797, -74.0123), (40.7114, -73.7867), (40.6437, -74.0765), (40.5853, -73.8203),
                     (40.8296, -73.9262)]:
        assert pick_deployment(lat, lon).name == "nyc"
