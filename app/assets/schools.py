"""NYC DOE 2019 - 2020 School Point Locations (Socrata a3nt-yts4).

The file is the 2019 to 2020 school year's and has not been reissued under
this id. It holds 1,992 public schools: 1,729 managed by the Department of
Education and 263 charter schools (`managed_by` 1 and 2), so its rows are
"public schools", not "DOE schools"."""
from __future__ import annotations

import geopandas as gpd

from app.spatial import DATA, load_layer

BORO = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}
MANAGED_BY = {"1": "DOE", "2": "Charter"}


def load() -> gpd.GeoDataFrame:
    g = load_layer(DATA / "schools.geojson")
    g = g.rename(columns={
        "loc_code": "loc_code",
        "loc_name": "name",
        "address": "address",
        "bbl": "bbl",
        "bin": "bin",
        "boronum": "boro_num",
        "geodistric": "geo_district",
        "adimindist": "admin_district",
    })
    g["borough"] = g["boro_num"].astype(str).map(BORO)
    g["managed_by"] = g["managed_by"].astype(str).map(MANAGED_BY)
    g["bbl"] = g["bbl"].astype(str).str.replace(r"\.0$", "", regex=True)
    keep = ["loc_code", "name", "address", "borough", "bbl", "bin", "managed_by",
            "geo_district", "admin_district", "geometry"]
    return g[keep].copy()
