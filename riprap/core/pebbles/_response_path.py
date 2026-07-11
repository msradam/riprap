"""Shared dotted-path response extraction for adapters that unwrap a JSON
response down to the field a pebble actually wants.

  response_path: data.score       walk_response_path(data, "data.score")
  response_path: items[0].name    supports [N] list indexing per segment

Missing segments return None rather than raising, so manifest authors can
use response_path defensively against an API's optional fields.
"""
from __future__ import annotations

import re
from typing import Any

_PATH_INDEX_RE = re.compile(r"^(.*?)\[(\d+)\]$")


def walk_response_path(data: Any, path: str) -> Any:
    if not path:
        return data
    cur = data
    for raw_seg in path.split("."):
        seg = raw_seg.strip()
        index: int | None = None
        m = _PATH_INDEX_RE.match(seg)
        if m:
            seg = m.group(1)
            index = int(m.group(2))
        if seg:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(seg)
            if cur is None:
                return None
        if index is not None:
            if not isinstance(cur, list) or index >= len(cur):
                return None
            cur = cur[index]
    return cur
