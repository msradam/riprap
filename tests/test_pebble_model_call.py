"""Tests for the model_call adapter — the generic inference-backend
pebble ("bring your own model" seam). Network is monkey-patched via
riprap.core.pebbles._http.post_url_json; these tests don't hit a real
backend.
"""
from __future__ import annotations

import httpx
import yaml
from pydantic import TypeAdapter

from riprap.core.pebbles import SpatialQuery
from riprap.core.pebbles.adapters import ModelCallPebble
from riprap.core.pebbles.schema import PebbleManifest

_ADAPTER = TypeAdapter(PebbleManifest)

_BASE_MANIFEST = """
id: my_model
type: model
title: model_call test
stone: capstone
adapter: model_call
config:
  path: /v1/some-model
  body:
    text: {{source: lat}}
    label_set: {{const: [a, b]}}
{extra}
provenance:
  source_name: test
{fallback}
"""


def _build(manifest_yaml: str, root) -> ModelCallPebble:
    raw = yaml.safe_load(manifest_yaml)
    m = _ADAPTER.validate_python(raw)
    return ModelCallPebble(m, root)


def test_happy_path_posts_resolved_body_and_returns_response(tmp_path, monkeypatch):
    from riprap.core.pebbles.adapters import model_call as mc

    captured = {}

    def fake_post(url, body, **kw):
        captured["url"] = url
        captured["body"] = body
        return {"ok": True, "elapsed_s": 0.1, "device": "cpu", "entities": ["x"]}

    monkeypatch.setattr(mc, "post_url_json", fake_post)
    monkeypatch.setenv("RIPRAP_ML_BASE_URL", "http://backend.example.com")

    p = _build(_BASE_MANIFEST.format(extra="", fallback=""), tmp_path)
    r = p.fetch(SpatialQuery(lat=40.7282, lon=-73.7949))

    assert r.error is None, r.error
    assert r.offline is False
    assert captured["url"] == "http://backend.example.com/v1/some-model"
    assert captured["body"] == {"text": 40.7282, "label_set": ["a", "b"]}
    assert r.value == {"ok": True, "elapsed_s": 0.1, "device": "cpu", "entities": ["x"]}


def test_config_base_url_overrides_env(tmp_path, monkeypatch):
    from riprap.core.pebbles.adapters import model_call as mc

    captured = {}
    monkeypatch.setattr(mc, "post_url_json", lambda url, body, **kw: captured.setdefault("url", url) or {"ok": True})
    monkeypatch.setenv("RIPRAP_ML_BASE_URL", "http://env-backend.example.com")

    p = _build(
        _BASE_MANIFEST.format(extra="  base_url: http://manifest-backend.example.com\n", fallback=""),
        tmp_path,
    )
    p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert captured["url"] == "http://manifest-backend.example.com/v1/some-model"


def test_response_path_extracts_field(tmp_path, monkeypatch):
    from riprap.core.pebbles.adapters import model_call as mc

    monkeypatch.setattr(
        mc, "post_url_json",
        lambda url, body, **kw: {"ok": True, "vectors": [[0.1, 0.2]]},
    )
    monkeypatch.setenv("RIPRAP_ML_BASE_URL", "http://backend.example.com")

    p = _build(
        _BASE_MANIFEST.format(extra="  response_path: vectors\n", fallback=""),
        tmp_path,
    )
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.value == [[0.1, 0.2]]


def test_ok_false_is_treated_as_offline(tmp_path, monkeypatch):
    from riprap.core.pebbles.adapters import model_call as mc

    monkeypatch.setattr(
        mc, "post_url_json",
        lambda url, body, **kw: {"ok": False, "err": "model exploded"},
    )
    monkeypatch.setenv("RIPRAP_ML_BASE_URL", "http://backend.example.com")

    p = _build(_BASE_MANIFEST.format(extra="", fallback="fallback:\n  on_offline: skip\n"), tmp_path)
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.offline is True
    assert r.value is None
    assert "model exploded" in r.error


def test_http_error_is_offline_not_a_crash(tmp_path, monkeypatch):
    from riprap.core.pebbles.adapters import model_call as mc

    def boom(url, body, **kw):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(mc, "post_url_json", boom)
    monkeypatch.setenv("RIPRAP_ML_BASE_URL", "http://backend.example.com")

    p = _build(_BASE_MANIFEST.format(extra="", fallback="fallback:\n  on_offline: skip\n"), tmp_path)
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.offline is True
    assert r.value is None
    assert "HTTP error" in r.error


def test_missing_base_url_is_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("RIPRAP_ML_BASE_URL", raising=False)
    p = _build(_BASE_MANIFEST.format(extra="", fallback=""), tmp_path)
    r = p.fetch(SpatialQuery(lat=40.0, lon=-73.0))
    assert r.offline is True
    assert "RIPRAP_ML_BASE_URL" in r.error
