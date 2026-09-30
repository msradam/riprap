"""A register counts every asset within its radius, east and west as well
as north and south. The degree box that trims the candidates before the
haversine used one width for both axes, and a degree of longitude at NYC
is 84 km, not 111 km: entrances 750 to 800 m east or west were dropped."""
import json

from app.registers import exposure
from app.registers._loader import haversine_m

# 200 Water Street, Manhattan: a dense station area with entrances near the edge.
LAT, LON = 40.707431, -74.00476



def test_entrance_count_matches_a_plain_haversine_over_the_file():
    feats = json.load(open(exposure.CLASSES["mta_entrances"].geojson))["features"]
    want = sum(1 for f in feats if f["properties"].get("entrance_latitude")
               and haversine_m(LAT, LON, float(f["properties"]["entrance_latitude"]),
                                float(f["properties"]["entrance_longitude"])) <= 800)
    assert exposure.summary_for_point(LAT, LON, "mta_entrances")["n_entrances"] == want
