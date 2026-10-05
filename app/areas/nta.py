"""NYC Neighborhood Tabulation Area (NTA 2020) resolver.

NTAs are NYC Department of City Planning's official neighborhood unit:
~262 polygons covering all 5 boroughs, including some park / airport
slivers. They are the canonical "neighborhood" unit for NYC civic data.

This module provides:
  - load() → GeoDataFrame with all NTAs (cached)
  - resolve(name) → list of matching NTAs by fuzzy name match, or by borough
  - by_code(code) → exact lookup
  - polygon_for(code) → shapely Polygon in EPSG:4326
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Polygon

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "nyc_ntas_2020.geojson"

# Common alias map: user-typed strings → canonical NTA names. We don't need to
# be exhaustive here; the fuzzy matcher catches most cases. This handles the
# few hard ones where the official NTA name differs from local usage.
ALIASES = {
    "jfk":              "John F. Kennedy International Airport",
    "laguardia":        "LaGuardia Airport",
    "bed stuy":         "Bedford-Stuyvesant (West)",
    "bed-stuy":         "Bedford-Stuyvesant (West)",
    "bedstuy":          "Bedford-Stuyvesant (West)",
    "the rockaways":    "Rockaway Beach-Arverne-Edgemere",
    "rockaway":         "Rockaway Beach-Arverne-Edgemere",
    "brighton":         "Brighton Beach",
    "lower east side":  "Lower East Side",
    "les":              "Lower East Side",
    "soho":             "SoHo-Little Italy-Hudson Square",
    "tribeca":          "Tribeca-Civic Center",
    "fidi":             "Financial District-Battery Park City",
    "lower manhattan":  "Financial District-Battery Park City",
    "the battery":      "Financial District-Battery Park City",
    "battery park":     "Financial District-Battery Park City",
    "downtown brooklyn":"Downtown Brooklyn-DUMBO-Boerum Hill",
    "dumbo":            "Downtown Brooklyn-DUMBO-Boerum Hill",
    "park slope":       "Park Slope",
    "carroll gardens":  "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "red hook":         "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "gowanus":          "Carroll Gardens-Cobble Hill-Gowanus-Red Hook",
    "hollis":           "Queens Village-Hollis-Bellerose",
    "long island city": "Hunters Point-Sunnyside-West Maspeth",
    "lic":              "Hunters Point-Sunnyside-West Maspeth",
    "astoria":          "Astoria (Central)",
    "flushing":         "Flushing-Willets Point",
    "harlem":           "Central Harlem (North)",
    "east harlem":      "East Harlem (North)",
    "el barrio":        "East Harlem (North)",
    "washington heights":"Washington Heights (North)",
    "midtown":          "Midtown South-Flatiron-Union Square",
    "upper east side":  "Upper East Side-Carnegie Hill",
    "ues":              "Upper East Side-Carnegie Hill",
    "upper west side":  "Upper West Side-Lincoln Square",
    "uws":              "Upper West Side-Lincoln Square",
    "coney island":     "Coney Island-Sea Gate",
}

BOROUGH_NORMALIZE = {
    "manhattan": "Manhattan", "mn": "Manhattan",
    "brooklyn":  "Brooklyn",  "bk": "Brooklyn",  "kings": "Brooklyn",
    "queens":    "Queens",    "qn": "Queens",
    "bronx":     "Bronx",     "the bronx": "Bronx", "bx": "Bronx",
    "staten island": "Staten Island", "si": "Staten Island", "richmond": "Staten Island",
}


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z]+", "", (s or "").lower())


def _words(s: str) -> str:
    return re.sub(r"[^a-z]+", " ", re.sub(r"['’]", "", (s or "").lower())).strip()


def _holds(names, query: str):
    """Which names hold the query as whole words: "Green" is in "Green-Wood
    Cemetery" and not in "Greenpoint" (a match on letters alone once briefed
    "1 Bowling Green" as Greenpoint). Spacing inside the query is free, so
    "La Guardia" still finds "LaGuardia Airport"."""
    words = _words(query).split()
    if not words:
        return names.map(lambda _s: False)
    pattern = re.compile(r"\b" + r"\s*".join(map(re.escape, words)) + r"\b")
    return names.fillna("").map(lambda s: bool(pattern.search(_words(s))))


@lru_cache(maxsize=1)
def load() -> gpd.GeoDataFrame:
    """Load the NTA 2020 GeoJSON; coerce CRS to EPSG:4326. Cached."""
    g = gpd.read_file(DATA_PATH)
    if g.crs is None or g.crs.to_string() != "EPSG:4326":
        g = g.to_crs("EPSG:4326")
    return g


def by_code(code: str) -> dict | None:
    g = load()
    hit = g[g["nta2020"] == code]
    if hit.empty:
        return None
    return _row_to_dict(hit.iloc[0])


def by_district(code: str) -> dict | None:
    """A community district (CDTA 2020 code such as 'QN12') as one area:
    the union of its NTAs, shaped like an NTA match."""
    code = re.sub(r"\s+", "", code or "").upper()
    g = load()
    hit = g[g["cdta2020"] == code]
    if hit.empty:
        return None
    return {"nta_code": code, "nta_name": hit.iloc[0]["cdtaname"], "borough": hit.iloc[0]["boroname"],
            "cdta": hit.iloc[0]["cdtaname"], "geometry": hit.geometry.union_all()}


BOROUGH_CODES = {"MN": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}


@lru_cache(maxsize=8)
def by_borough(code: str) -> dict | None:
    """A borough ('BX') or the whole city ('NYC') as one area: the union of
    its tabulation areas, shaped like an NTA match. A heat question about a
    borough is answered from the sources that hold at that scale."""
    g = load()
    code = (code or "").upper()
    if code == "NYC":
        return {"nta_code": "NYC", "nta_name": "New York City", "borough": "New York City", "cdta": None,
                "geometry": g.geometry.union_all()}
    name = BOROUGH_CODES.get(code)
    if not name:
        return None
    return {"nta_code": code, "nta_name": "the Bronx" if code == "BX" else name, "borough": name, "cdta": None,
            "geometry": g[g["boroname"] == name].geometry.union_all()}


def _row_to_dict(row) -> dict:
    return {
        "nta_code":  row["nta2020"],
        "nta_name":  row["ntaname"],
        "borough":   row["boroname"],
        "cdta":      row.get("cdtaname"),
        "geometry":  row["geometry"],
    }


def borough_match(query: str) -> str | None:
    """If query matches a borough name (or common abbreviation), return the
    canonical name. Otherwise return None."""
    q = query.strip().lower()
    return BOROUGH_NORMALIZE.get(q)


def resolve(query: str) -> list[dict[str, Any]]:
    """Resolve a free-text query to NTA(s).

    Strategy (in priority order):
      1. Borough match → all NTAs in borough.
      2. Alias map → exact NTA name match.
      3. Case-insensitive EXACT name match (so 'Kew Gardens' wins over
         'Kew Gardens Hills' when both exist).
      4. The query as whole words of the NTA name. When multiple match,
         prefer the one whose normalized name length is closest to the
         query — avoids 'Kew Gardens' resolving to 'Kew Gardens Hills'.
      5. CDTA-name fallback, whole words again.
    """
    g = load()
    q = (query or "").strip()
    if not q:
        return []
    boro = borough_match(q)
    if boro:
        hits = g[g["boroname"] == boro]
        return [_row_to_dict(r) for _, r in hits.iterrows()]

    alias = ALIASES.get(q.lower())
    if alias:
        hits = g[g["ntaname"] == alias]
        if not hits.empty:
            return [_row_to_dict(r) for _, r in hits.iterrows()]

    # Exact (case-insensitive) — preferred over substring
    name_lower = g["ntaname"].fillna("").str.lower()
    exact = g[name_lower == q.lower()]
    if not exact.empty:
        return [_row_to_dict(r) for _, r in exact.iterrows()]

    qn = _normalize(q)
    if not qn:
        return []
    contains = g[_holds(g["ntaname"], q)].copy()
    if not contains.empty:
        contains["_diff"] = contains["ntaname"].fillna("").map(
            lambda s: abs(len(_normalize(s)) - len(qn))
        )
        contains = contains.sort_values("_diff")
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    contains = g[_holds(g["cdtaname"], q)]
    if not contains.empty:
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    return []


def resolution_note(typed: str, area: dict, borough: str | None = None) -> str | None:
    """What a reader must be told when the name they typed is not the name
    of the area briefed: which tabulation area it is, that it is wider than
    the name ("Roosevelt Island" is briefed with the Upper East Side), and
    which other areas carry the name ("East Harlem" is two areas, "Murray
    Hill" is in two boroughs). None when the typed name is the area's own.
    `borough` is the borough the query named, which already chose among them."""
    name = area["nta_name"]
    if _normalize(typed) == _normalize(name):
        return None
    g = load()
    # An alias that is not in the area's own name ("El Barrio" for East Harlem): the others of the area's name.
    held = typed if typed.lower() in name.lower() else re.sub(r"\s*\(.*?\)", "", name).strip()
    others = g[_holds(g["ntaname"], held) & (g["nta2020"] != area["nta_code"])]
    if borough:
        others = others[others["boroname"] == borough]
    listed = [f"{r.ntaname} ({r.boroname})" for r in others.itertuples()]
    parts = [re.sub(r"\s*\(.*?\)", "", p).strip() for p in name.split("-")]
    rest = [p for p in parts if _words(p) != _words(typed)]
    described = f"{name} ({area['borough']})"
    out = [f"The name {typed} matches {len(listed) + 1} of City Planning's 2020 Neighborhood Tabulation Areas. This "
           f"briefing describes {described} only." if listed else
           f"This briefing describes City Planning's 2020 Neighborhood Tabulation Area {described}, the area Riprap "
           f"matched to the name {typed}."]
    if rest and len(rest) < len(parts):
        also = " and ".join([", ".join(rest[:-1]), rest[-1]] if len(rest) > 1 else rest)
        out.append(f"That area also takes in {also}: Riprap holds no boundary for {typed} alone.")
    if listed:
        more = f" and {len(listed) - 5} more" if len(listed) > 5 else ""
        out.append(f"The {'others are' if len(listed) > 1 else 'other is'} {'; '.join(listed[:5])}{more}.")
    return " ".join(out)


# City Planning's tabulation area types other than residential (ntatype "0"): areas with few or no homes.
_AREA_TYPES = {"5": "a jail island", "6": "a special area with few or no homes", "7": "a cemetery", "8": "an airport",
               "9": "a park"}


def type_note(code: str) -> str | None:
    """What a reader must be told when the area briefed is a park, a
    cemetery, an airport or another area with few or no homes: that it is
    one, and which residential areas adjoin it. ("Does Kissena Park flood?"
    was answered with the park's 2 complaints and no word that the blocks
    beside it, in other tabulation areas, had filed 81.) None for a
    residential area or a code that is not a tabulation area's."""
    g = load()
    hit = g[g["nta2020"] == code]
    if hit.empty or hit.iloc[0]["ntatype"] not in _AREA_TYPES:
        return None
    row = hit.iloc[0]
    # ponytail: "adjoins" is within about 30 m of the boundary, in degrees; reproject if that ever needs to be exact.
    near = g[(g["ntatype"] == "0") & g.intersects(row.geometry.buffer(0.0003))]
    beside = "; ".join(sorted(near["ntaname"])) or "none Riprap could name"
    return (f"City Planning classes {row['ntaname']} as {_AREA_TYPES[row['ntatype']]}, a tabulation area of its own "
            "with few or no homes inside it, so records that residents file (311 complaints especially) are "
            f"counted in the residential areas beside it and not here. Those are: {beside}. Ask about one of them, "
            "or about a street address, for the blocks around it.")


DISTRICT_NOTE = ("The shape used for {code} is City Planning's Community District Tabulation Area, an approximation of the "
                 "official community district. Counts of facilities inside it can differ from counts for the official "
                 "district boundary.")


def centre(geometry):
    """The point an area is read at when a source takes one point: its
    centroid, or, when the centroid falls outside the area, a point the
    area does contain. The centre of Breezy Point-Belle Harbor-Rockaway
    Park-Broad Channel is in Jamaica Bay, outside every deployment, and so
    are the centres of four other areas made of islands or a curved shore."""
    c = geometry.centroid
    return c if geometry.contains(c) else geometry.representative_point()


def polygon_for(code: str) -> Polygon | None:
    hit = by_code(code)
    return hit["geometry"] if hit else None
