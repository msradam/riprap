"""How the land-cover model's tree canopy compares with the city's 2017 map.

    uv run python scripts/check_landcover_canopy.py

For each yearly map in data/eo/ it takes the mean canopy share over every
30 m cell that both the map and NYC Land Cover 2017 (data/landcover_nyc_2017.tif)
have a value for, and subtracts the 2017 map's. The result is merged into
data/experimental/landcover.json, where `app.experimental.hedge` reads
`canopy_vs_city_map_2017_words` for the land-cover sentence. Run it after
scripts/run_landcover_batch.py rewrites that file; until then the sentence
says its saved evaluation is out of date.

Citywide canopy does not move by points between summers, so a difference
here is the model and its images, not the trees. The repository's test
against the 2021 map (data/experimental/landcover_nyc_eval.json) agrees for
the one year it covers: 5.7 points low on the June 2021 image.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "experimental" / "landcover.json"


def words(diff: dict[int, float]) -> str:
    """The differences as a clause: the years that read low, then the rest."""
    def span(years):
        vals = sorted(abs(diff[y]) for y in years)
        return f"{vals[0]}" if vals[0] == vals[-1] else f"{vals[0]} to {vals[-1]}"

    def named(years):
        return f"{len(years)} of its {len(diff)} yearly maps ({', '.join(map(str, years))})"

    low, high = [y for y in diff if diff[y] < 0], [y for y in diff if diff[y] >= 0]
    first, rest = (low, high) if low else (high, [])
    out = f"{span(first)} points {'less' if low else 'more'} tree canopy than the city's 2017 map in {named(first)}"
    return out + (f" and {span(rest)} points more in {named(rest)}" if rest else "")


def main(out_path: Path = OUT) -> int:
    import rasterio

    from app.eo import landcover as lc

    with rasterio.open(lc.CITY_MAP) as src:
        city, grid = src.read(lc.TREES + 1), (src.shape, src.transform)
    diff = {}
    for year in lc.years():
        with rasterio.open(lc.EO_DIR / f"landcover_{year}.tif") as src:
            assert (src.shape, src.transform) == grid, f"the {year} map is on another grid"
            ours = src.read(lc.TREES + 1)
        both = (ours != 255) & (city != 255)
        diff[year] = round(float(ours[both].mean()) - float(city[both].mean()), 1)
    out = {"canopy_minus_city_map_2017_points": {str(y): d for y, d in diff.items()},
           "canopy_vs_city_map_2017_words": words(diff)}
    out_path.write_text(json.dumps({**json.loads(out_path.read_text()), **out}, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    assert words({2018: -4.2, 2021: -4.2, 2024: 3.2}) == (
        "4.2 points less tree canopy than the city's 2017 map in 2 of its 3 yearly maps (2018, 2021) "
        "and 3.2 points more in 1 of its 3 yearly maps (2024)")
    raise SystemExit(main())
