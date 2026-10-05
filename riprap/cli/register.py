"""riprap-register: every asset of a class with its flood flags, as CSV.

    uv run riprap-register --asset-class schools [--out FILE] [--all]

Joins NYC public schools, NYCHA developments or subway entrances to the
2012 Sandy inundation zone and the three DEP stormwater scenarios and
writes one row per asset with a 0 or 1 per layer. The citywide list an
analyst would otherwise build in GIS. By default only assets inside at
least one layer are written; --all writes every asset. No score and no
ranking: the columns are the layers themselves.
"""
from __future__ import annotations

import argparse
import importlib
import sys
import warnings
from pathlib import Path

LAYERS = ("sandy", "dep_moderate_current", "dep_moderate_2050", "dep_extreme_2080")
CLASSES = ("schools", "nycha", "mta_entrances")


def flags(asset_class: str):
    """The asset class as a DataFrame with one 0/1 column per layer."""
    from app.flood_layers import dep_stormwater, sandy_inundation

    g = importlib.import_module(f"app.assets.{asset_class}").load()
    if g.crs is None or g.crs.to_string() != "EPSG:2263":
        g = g.to_crs("EPSG:2263")
    if "sandy" not in g.columns:  # NYCHA sets it from the share of each outline inside
        g["sandy"] = sandy_inundation.join(g).astype(int)
    for scen in LAYERS[1:]:
        g[scen] = (dep_stormwater.join(g, scen)["depth_class"] > 0).astype(int)
    ll = g.geometry.to_crs("EPSG:4326")
    g["lat"], g["lon"] = ll.y.round(6), ll.x.round(6)
    return g.drop(columns="geometry")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--asset-class", default="schools", choices=CLASSES)
    ap.add_argument("--out", default=None, help="CSV path (default outputs/<class>_flood_flags.csv)")
    ap.add_argument("--all", action="store_true", help="write every asset, not only the exposed ones")
    args = ap.parse_args()
    warnings.filterwarnings("ignore")  # the GDB reader warns about ring order on every load
    df = flags(args.asset_class)
    n = len(df)
    if not args.all:
        df = df[df[list(LAYERS)].sum(axis=1) > 0]
    df = df.sort_values(["borough", "name"])
    out = Path(args.out) if args.out else Path("outputs") / f"{args.asset_class}_flood_flags.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {len(df)} of {n} {args.asset_class} -> {out}", file=sys.stderr)
    for layer in LAYERS:
        print(f"  inside {layer}: {int(df[layer].sum())}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
