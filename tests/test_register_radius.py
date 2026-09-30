"""A register counts every asset within its radius, east and west as well
as north and south. The degree box that trims the candidates before the
haversine used one width for both axes, and a degree of longitude at NYC
is 84 km, not 111 km: entrances 750 to 800 m east or west were dropped."""
import json
import math

from app.registers import mta_entrances

# 200 Water Street, Manhattan: a dense station area with entrances near the edge.
LAT, LON = 40.707431, -74.00476


def _haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def test_entrance_count_matches_a_plain_haversine_over_the_file():
    feats = json.load(open(mta_entrances.MTA_ENTRANCES))["features"]
    want = sum(1 for f in feats if f["properties"].get("entrance_latitude")
               and _haversine_m(LAT, LON, float(f["properties"]["entrance_latitude"]),
                                float(f["properties"]["entrance_longitude"])) <= 800)
    assert mta_entrances.summary_for_point(LAT, LON)["n_entrances"] == want
