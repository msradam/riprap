"""Adapters — concrete fetchers keyed by short name in pebble manifests.

Each adapter is a Pebble subclass that knows how to fetch one *class* of
source (HTTP live, baked GeoJSON, model endpoint, ...). The manifest's
`adapter:` field is a short name resolved here in ADAPTERS.
"""
from __future__ import annotations

from riprap.core.pebbles.adapters.baked_vector import BakedVectorPebble
from riprap.core.pebbles.adapters.csv_points import CSVPointsPebble
from riprap.core.pebbles.adapters.model_call import ModelCallPebble
from riprap.core.pebbles.adapters.python_call import PythonCallPebble
from riprap.core.pebbles.adapters.rest_json import RestJSONPebble
from riprap.core.pebbles.adapters.socrata_records import SocrataRecordsPebble

ADAPTERS: dict[str, type] = {
    "baked_vector": BakedVectorPebble,
    "csv_points": CSVPointsPebble,
    "model_call": ModelCallPebble,
    "python_call": PythonCallPebble,
    "rest_json": RestJSONPebble,
    "socrata_records": SocrataRecordsPebble,
}

__all__ = [
    "ADAPTERS",
    "BakedVectorPebble",
    "CSVPointsPebble",
    "LocalCorpusWithNERPebble",
    "ModelCallPebble",
    "PythonCallPebble",
    "RestJSONPebble",
    "SocrataRecordsPebble",
]
