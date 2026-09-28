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
    "the rockaways":    "Rockaway Beach-Arverne-Edgemere",
    "rockaway":         "Rockaway Beach-Arverne-Edgemere",
    "brighton":         "Brighton Beach",
    "lower east side":  "Lower East Side",
    "les":              "Lower East Side",
    "soho":             "SoHo-Little Italy-Hudson Square",
    "tribeca":          "Tribeca-Civic Center",
    "fidi":             "Financial District-Battery Park City",
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
      4. Substring match on normalized NTA name. When multiple match,
         prefer the one whose normalized name length is closest to the
         query — avoids 'Kew Gardens' resolving to 'Kew Gardens Hills'.
      5. CDTA-name substring fallback.
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
    name_norm = g["ntaname"].fillna("").map(_normalize)
    contains = g[name_norm.str.contains(qn, na=False)].copy()
    if not contains.empty:
        contains["_diff"] = contains["ntaname"].fillna("").map(
            lambda s: abs(len(_normalize(s)) - len(qn))
        )
        contains = contains.sort_values("_diff")
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    cdta_norm = g["cdtaname"].fillna("").map(_normalize)
    contains = g[cdta_norm.str.contains(qn, na=False)]
    if not contains.empty:
        return [_row_to_dict(r) for _, r in contains.iterrows()]

    return []


def polygon_for(code: str) -> Polygon | None:
    hit = by_code(code)
    return hit["geometry"] if hit else None


def blending_note(query_text: str, target: dict) -> str | None:
    """NTAs are hyphen-joined compounds of several named places (e.g. "Red
    Hook" queries resolve to "Carroll Gardens-Cobble Hill-Gowanus-Red
    Hook", NTA BK0601) — every figure returned is a polygon-wide average
    or count across the whole compound, not the sub-place alone, and a
    user who asked about only one of them has no way to know that from
    the numbers themselves. Real production case: a resilience-planning
    query for "Red Hook, Brooklyn" got Carroll Gardens/Cobble
    Hill/Gowanus data blended in with no disclosure. Returns a deterministic
    disclosure sentence when the query named one compound part but not the
    others, or None if the query already named the full compound (or we
    can't tell which part motivated it)."""
    name = target["nta_name"]
    parts = [p.strip() for p in name.split("-") if p.strip()]
    if len(parts) < 2:
        return None
    q_norm = _normalize(query_text)
    if _normalize(name) in q_norm:
        return None
    matched = [p for p in parts if _normalize(p) in q_norm]
    if not matched or len(matched) == len(parts):
        return None
    other = [p for p in parts if p not in matched]
    return (
        f"**Note on geographic scope.** {' and '.join(matched)} is not its "
        f"own reporting unit in this data — it is blended into the NYC DCP "
        f"Neighborhood Tabulation Area \"{name}\" (NTA {target['nta_code']}), "
        f"together with {', '.join(other)}. Every figure below is a "
        f"polygon-wide average or count across that full blended area, not "
        f"{' or '.join(matched)} alone."
    )


