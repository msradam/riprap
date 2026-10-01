"""Pre-compute a flood-exposure register into data/registers/<asset_class>.json.

Run: python scripts/build_register.py {nycha,schools} [--regenerate]
"""
from __future__ import annotations

import importlib
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.register_builder import build_register  # noqa: E402

META_KEYS = {
    "nycha": ("name", "address", "borough", "tds_num"),
    "schools": ("name", "address", "borough", "bbl", "bin"),
}

if __name__ == "__main__":
    asset_class = sys.argv[1] if len(sys.argv) > 1 else ""
    if asset_class not in META_KEYS:
        sys.exit(f"usage: build_register.py {{{','.join(META_KEYS)}}}")
    loader = importlib.import_module(f"app.assets.{asset_class}").load
    build_register(asset_class, loader, meta_keys=META_KEYS[asset_class], regenerate="--regenerate" in sys.argv)
