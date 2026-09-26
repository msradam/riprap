"""Embed the policy corpus once and write data/rag_index.npz.

Run after adding or changing a PDF in corpus/. Needs the `ml` extra:

    uv sync --extra ml
    uv run python scripts/build_rag_index.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import rag  # noqa: E402

t0 = time.time()
n = rag.build_index()
print(f"wrote {n} chunks to {rag.INDEX_PATH} in {time.time() - t0:.1f}s "
      f"({rag.INDEX_PATH.stat().st_size / 1e6:.1f} MB)")
