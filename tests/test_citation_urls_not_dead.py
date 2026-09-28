"""Citation URLs and vintages come from manifest provenance only.

Five dataset ids were confirmed dead by live requests (the DEP Stormwater
dataset was consolidated into one collection page, NTA-map and NYCHA were
renamed, the city hospitals and HVI ids now 404). No network calls here,
just a guard against the dead ids reappearing and against manifests
shipping without a vintage."""
from __future__ import annotations

from pathlib import Path

import yaml

# The USGS STN Data Portal page answered 404 in refactor 5; the live check
# is scripts/check_links.py, which needs the network.
_DEAD_DATASET_IDS = ("d73m-mf6p", "d3qk-pfyz", "i9rv-hdr5", "u3ic-3hcp", "4xj4-2vap", "STNDataPortal")
_MANIFESTS = sorted((Path(__file__).resolve().parent.parent / "deployments").glob("*/manifests/*.yaml"))


def test_no_manifest_cites_a_dead_dataset_id():
    for manifest in _MANIFESTS:
        text = manifest.read_text()
        for dead in _DEAD_DATASET_IDS:
            assert dead not in text, f"{manifest} still points at retired dataset {dead}"


def test_dep_tiers_point_at_the_current_collection():
    for manifest in _MANIFESTS:
        if manifest.name.startswith("dep_"):
            assert "9i7c-xyvv" in manifest.read_text()


def test_every_manifest_declares_its_vintage():
    for manifest in _MANIFESTS:
        prov = yaml.safe_load(manifest.read_text())["provenance"]
        assert "date_modified" in prov and "retrieved_at" in prov, manifest
        assert prov["retrieved_at"], f"{manifest}: retrieved_at must not be null"


def test_every_manifest_says_what_it_answers():
    for manifest in _MANIFESTS:
        assert yaml.safe_load(manifest.read_text()).get("answers"), f"{manifest}: add an answers: line"
