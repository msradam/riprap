"""URL fetch helpers for the declarative pebble adapters, on top of the
shared client in riprap/core/http.py (caching, retries, timeouts).

  fetch_url_text(url, *, cache_ttl_s, headers, timeout_s) -> str
  fetch_url_json(url, *, cache_ttl_s, headers, timeout_s) -> Any

A `cache_ttl_s` of 0 disables caching for that call.

Header values support `${ENV_VAR}` interpolation so manifests can declare
auth tokens without baking secrets into YAML (the substitution happens
at request time, never written back into the manifest).
"""
from __future__ import annotations

import os
import re
from typing import Any

from riprap.core import http

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        out[k] = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), str(v))
    return out


def fetch_url_text(url: str, *, cache_ttl_s: int = 300,
                   headers: dict[str, str] | None = None,
                   timeout_s: float = 10.0) -> str:
    r = http.get(url, headers=_interpolate_headers(headers), timeout=timeout_s, ttl_s=cache_ttl_s)
    r.raise_for_status()
    return r.text


def fetch_url_json(url: str, *, cache_ttl_s: int = 300,
                   headers: dict[str, str] | None = None,
                   timeout_s: float = 10.0, personal: bool = False) -> Any:
    """`personal=True` for records that may hold personal data (311 free
    text): the response bypasses the HTTP cache and every string is
    redacted of emails and phone numbers before it is returned."""
    r = http.get(url, headers=_interpolate_headers(headers), timeout=timeout_s, ttl_s=cache_ttl_s,
                 store=not personal)
    r.raise_for_status()
    if personal:
        from riprap.core.redact import redact

        return redact(r.json())
    return r.json()


