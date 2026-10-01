"""Tests for BYOD load paths: .riprap/ + RIPRAP_EXTRA_MANIFESTS.

Covers the registry-merge logic in riprap/core/pebbles/registry.py and
the manifest-dir path-resolution change in BasePebble. We don't hit the
network; the underlying pebble (csv_points) reads a local CSV fixture.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from riprap.core.pebbles import SpatialQuery
from riprap.core.pebbles.registry import load_registry

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "byod"
NYC = REPO / "deployments" / "nyc"


@pytest.fixture
def clean_env(monkeypatch):
    """Force a clean RIPRAP_EXTRA_MANIFESTS for each test."""
    monkeypatch.delenv("RIPRAP_EXTRA_MANIFESTS", raising=False)
    yield monkeypatch


def test_base_registry_excludes_byod_pebble(clean_env):
    """With no BYOD env or .riprap dir, the example pebble must not appear."""
    reg = load_registry(NYC)
    assert "fdny_firehouses" not in reg
    assert "nws_obs" in reg  # sanity: base deployment still loads


def test_extra_manifests_env_merges_pebble(clean_env):
    clean_env.setenv("RIPRAP_EXTRA_MANIFESTS", str(EXAMPLE))
    reg = load_registry(NYC)
    assert "fdny_firehouses" in reg
    # Real fetch against the CSV: 189 Atlantic Ave should have ≥1 firehouse
    # in the 1.5 km radius the manifest declares.
    pebble = reg.get("fdny_firehouses")
    result = pebble.fetch(SpatialQuery(lat=40.6906, lon=-73.9882))
    assert result.value is not None
    assert result.value["n_within_radius"] >= 1
    assert result.value["radius_m"] == 1500


def test_extra_manifests_single_file_entry(clean_env):
    """RIPRAP_EXTRA_MANIFESTS accepts a single .yaml file path too."""
    yaml_path = EXAMPLE / "fdny_firehouses.yaml"
    clean_env.setenv("RIPRAP_EXTRA_MANIFESTS", str(yaml_path))
    reg = load_registry(NYC)
    assert "fdny_firehouses" in reg


def test_dotriprap_auto_discovery(tmp_path, clean_env, monkeypatch):
    """A .riprap dir in the CWD should be auto-merged."""
    workdir = tmp_path / "user_project"
    riprap_dir = workdir / ".riprap"
    riprap_dir.mkdir(parents=True)
    shutil.copy(EXAMPLE / "fdny_firehouses.yaml", riprap_dir / "fdny_firehouses.yaml")
    shutil.copy(EXAMPLE / "fdny_firehouses.csv", riprap_dir / "fdny_firehouses.csv")
    monkeypatch.chdir(workdir)

    reg = load_registry(NYC)
    assert "fdny_firehouses" in reg
    pebble = reg.get("fdny_firehouses")
    result = pebble.fetch(SpatialQuery(lat=40.6906, lon=-73.9882))
    assert result.value is not None
    assert result.value["n_within_radius"] >= 1


def test_byod_manifest_resolves_paths_against_manifest_dir(tmp_path, clean_env):
    """A BYOD pebble's `path:` should resolve next to its yaml, not against
    the active deployment_root. This is the key portability guarantee."""
    shutil.copy(EXAMPLE / "fdny_firehouses.yaml", tmp_path / "fdny_firehouses.yaml")
    shutil.copy(EXAMPLE / "fdny_firehouses.csv", tmp_path / "fdny_firehouses.csv")
    clean_env.setenv("RIPRAP_EXTRA_MANIFESTS", str(tmp_path))

    reg = load_registry(NYC)
    pebble = reg.get("fdny_firehouses")
    # Sanity: pebble has manifest_dir set, deployment_root still points at NYC
    assert pebble.manifest_dir == tmp_path.resolve()
    assert pebble.deployment_root == NYC.resolve()
    result = pebble.fetch(SpatialQuery(lat=40.6906, lon=-73.9882))
    assert result.value is not None
    assert result.value["n_within_radius"] >= 1


def test_byod_pebble_portable_across_deployments(clean_env):
    """Same BYOD manifest must load + fetch correctly against multiple base
    deployments. A spatial mismatch (NYC CSV vs Chicago address) returns 0
    within radius rather than erroring."""
    clean_env.setenv("RIPRAP_EXTRA_MANIFESTS", str(EXAMPLE))

    chicago_root = REPO / "deployments" / "chicago"
    reg = load_registry(chicago_root)
    assert "fdny_firehouses" in reg
    assert "chicago_311" in reg  # base Chicago pebble still present

    pebble = reg.get("fdny_firehouses")
    chicago_loop = SpatialQuery(lat=41.8781, lon=-87.6298)
    result = pebble.fetch(chicago_loop)
    assert result.value is not None
    assert result.value["n_within_radius"] == 0
    # The nearest FDNY firehouse from the Chicago Loop is over 1,000 km away.
    assert result.value["nearest"]["distance_m"] > 1_000_000


def test_byod_id_collision_overrides_base(tmp_path, clean_env, capsys):
    """A BYOD pebble with the same id as a base pebble should override and
    emit a warning. Use nws_obs as the collision target."""
    override_yaml = tmp_path / "nws_obs.yaml"
    override_yaml.write_text(
        """\
id: nws_obs
type: live
title: My private NWS obs (BYOD override)
stone: touchstone
adapter: rest_json
spatial: {scope: point}
config:
  url: https://example.invalid/obs
  shape: {path: data}
provenance:
  source_name: BYOD override fixture
  doc_id: nws_obs
"""
    )
    clean_env.setenv("RIPRAP_EXTRA_MANIFESTS", str(override_yaml))

    reg = load_registry(NYC)
    assert reg.get("nws_obs").manifest.title.startswith("My private NWS obs")
    captured = capsys.readouterr()
    assert "BYOD override" in captured.err
    assert "nws_obs" in captured.err
