"""model_call — a pebble that fetches its value from an inference backend
over HTTP POST.

This is the "bring your own model" seam. It knows nothing about any
specific model — it builds a JSON body from the manifest + query, POSTs
it to a path on the configured inference backend, and returns the JSON
response. Any backend that speaks this contract works: the reference
implementation is riprap-inference (LitServe-based), but a from-scratch
Flask app returning the same envelope shape works identically.

Response envelope every model is expected to return (matches
riprap-inference's LitAPI classes and the Triton backends they replaced):

  {"ok": true,  "elapsed_s": ..., "device": ..., ...model-specific fields}
  {"ok": false, "err": "..."}

`ok: false` is treated as a pebble-level error (respects
`fallback.on_offline`), so a model_call pebble degrades the same way a
down HTTP API or a raster miss does — no special-casing needed downstream.

Manifest config shape:

  adapter: model_call
  config:
    base_url: ${RIPRAP_ML_BASE_URL}   # optional; defaults to that env var
    path: /v1/granite-embed
    body:
      texts: {source: query}          # same {source:}/{const:} spec as python_call
    headers:
      Authorization: "Bearer ${RIPRAP_ML_API_KEY}"   # optional; ${ENV_VAR} interpolation
    response_path: vectors            # optional dotted path (rest_json-style);
                                       # default is the whole response dict
    timeout_s: 60

Body values are resolved one level deep via the same `{source:}`/`{const:}`
vocabulary as python_call — plain literals (str/int/float/bool/list/None)
pass through unchanged. A literal dict value needs `{const: {...}}}` (a
bare nested dict is read as an unresolved source spec and will error).
"""
from __future__ import annotations

import os

import httpx

from riprap.core.pebbles._http import post_url_json
from riprap.core.pebbles._response_path import walk_response_path as _walk_response_path
from riprap.core.pebbles._source_spec import resolve_source_spec as _resolve
from riprap.core.pebbles.base import BasePebble, PebbleResult, SpatialQuery


class ModelCallPebble(BasePebble):
    def _fetch_raw(self, query: SpatialQuery) -> PebbleResult:
        cfg = self.manifest.config
        path = cfg.get("path")
        if not path:
            return PebbleResult(
                pebble_id=self.id, value=None,
                error="model_call: manifest.config.path is required",
            )
        base_url = (cfg.get("base_url") or os.environ.get("RIPRAP_ML_BASE_URL", "")).rstrip("/")
        if not base_url:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error="model_call: no base_url in config and RIPRAP_ML_BASE_URL is unset",
            )

        try:
            body = {k: _resolve(v, query) for k, v in (cfg.get("body") or {}).items()}
        except Exception as e:  # noqa: BLE001
            return PebbleResult(
                pebble_id=self.id, value=None,
                error=f"model_call: body resolution failed: {e}",
            )

        url = f"{base_url}{path}"
        timeout_s = float(cfg.get("timeout_s", 60.0))
        try:
            data = post_url_json(
                url, body, headers=cfg.get("headers"), timeout_s=timeout_s,
            )
        except httpx.HTTPError as e:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"model_call: HTTP error calling {url}: {e}",
            )

        if isinstance(data, dict) and data.get("ok") is False:
            return PebbleResult(
                pebble_id=self.id, value=None, offline=True,
                error=f"model_call: {path} returned ok=false: {data.get('err', 'unknown error')}",
            )

        value = _walk_response_path(data, cfg.get("response_path", "") or "")
        return PebbleResult(pebble_id=self.id, value=value)
