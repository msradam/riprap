"""Pydantic models for pebble YAML manifests.

A pebble manifest declares one data source. The `type:` field discriminates
how the source is fetched:

  - `live`   — HTTP/socket call against a remote endpoint
  - `baked`  — file-backed geospatial query (GeoJSON / GeoTIFF / Parquet)
  - `model`  — model endpoint call (vLLM / Triton / Ollama), with explicit
               offline-fallback semantics so the briefing degrades cleanly
               when inference is unavailable.

The schema is intentionally permissive on `config:` — each adapter validates
its own config sub-shape. The top-level fields here are the contract every
pebble obeys regardless of type.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# A vintage is an ISO date (or year / year-month) or "at_fetch": resolved
# when the pebble runs, from Socrata metadata or the read time itself.
# See riprap/core/pebbles/vintage.py.
# YAML parses a bare 2024-07-03 as a date, so accept that too.
Vintage = Annotated[
    str,
    BeforeValidator(lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v)),
    Field(pattern=r"^(at_fetch|\d{4}(-\d{2}(-\d{2})?)?)$"),
]


class Provenance(BaseModel):
    """Where this data came from. Surfaces in the briefing as citation.

    `date_modified` is the source's own vintage (schema.org dateModified):
    the date of the version we hold, or null when that is unknown.
    `retrieved_at` is when our copy was made (prov:generatedAtTime).
    Shipped manifests declare both keys; tests enforce it.
    """
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_url: str | None = None
    license: str | None = None
    date_modified: Vintage | None = None
    retrieved_at: Vintage | None = None
    citation: str | None = None
    doc_id: str | None = None  # short slug used by RAG / citation chips
    # A value field holding this reading's own vintage, which then replaces
    # date_modified in the citation (FEMA NFHL: the FIRM panel's effective date).
    date_modified_field: str | None = None


class Narration(BaseModel):
    """Deterministic phrasing for inference-offline mode + LLM grounding hint."""
    model_config = ConfigDict(extra="forbid")

    short: str | None = None
    template: str | None = None  # str.format-style with {field} placeholders


class Fallback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on_offline: Literal["skip", "stub", "error"] = "skip"
    message: str | None = None


class Spatial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["point", "polygon", "raster"] = "point"
    crs: str = "EPSG:4326"


# Coarse named regions for pebble coverage. `us_conus` matches anywhere
# in the lower-48 (Hawaii + Alaska excluded by default); `global` always
# matches. Concrete bboxes are also supported via Coverage.bbox.
PebbleRegion = Literal["us_conus", "global"]


class Coverage(BaseModel):
    """Where this pebble's data is meaningful — the spatial gate the
    routing layer uses to decide whether to fire it for a given query.

    A pebble is fired for (lat, lon) when either:
      - `region` covers the point (us_conus → CONUS bbox; global → always)
      - `bbox` contains the point

    When neither is set, the pebble inherits its deployment's coverage
    (from stones.yaml). This is the back-compat path — every existing
    manifest is left unchanged and still fires inside its deployment.
    """
    model_config = ConfigDict(extra="forbid")

    region: PebbleRegion | None = None
    bbox: list[float] | None = None  # [min_lon, min_lat, max_lon, max_lat]


class Display(BaseModel):
    """UI render hints. The pebble → evidence card mapping lives here.

    `order` is the sort key within a stone's row of cards (smaller first).
    `kind` tells the frontend which card body component to render:
      - text     plain narration-template prose (default)
      - stat     a single number/boolean with units (e.g. Sandy inside/outside)
      - list     a list of features (e.g. Ida HWM sites, FloodNet sensors)
      - chart    a time-series chart
      - map_only no card body; the data renders only on the map layer
    `variant` is a finer-grained component hint within `kind` — the
    SvelteKit cardAdapter uses it to pick the actual evidence-card
    component (headline / tabular / spark / register / etc.). When
    unspecified, the adapter falls back to a `kind`-derived default.
    `map_layer` indicates the value carries geometries the map should draw.
    `icon` is an optional short string the card heading can show (emoji ok).
    """
    model_config = ConfigDict(extra="forbid")

    order: int | None = None
    kind: Literal["text", "stat", "list", "chart", "map_only"] = "text"
    variant: str | None = None
    map_layer: bool = False
    icon: str | None = None


# Epistemic tier — the kind of evidence this pebble produces.
# Drives the small EMP / MOD / PRX / SYN chip on each evidence card.
#
#   empirical  — directly measured or observed (sensors, gauges, HWMs)
#   modeled    — scenario-based prediction (DEM, flood-extent simulation)
#   proxy      — indirect indicator (microtopo, complaint counts)
#   synthetic  — generated / hallucinated by a model (TerraMind LULC)
Tier = Literal["empirical", "modeled", "proxy", "synthetic"]


class _PebbleBase(BaseModel):
    """Fields shared across all pebble types."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    title: str
    # One plain line saying what question this source answers; the
    # planner reads it to choose which pebbles a question needs.
    answers: str | None = None
    stone: str  # which Stone this pebble rolls up to
    # Model layers say whether their evaluation supports showing them as
    # evidence (production) or only as a labelled experiment.
    maturity: Literal["production", "experimental"] = "production"
    tier: Tier | None = None  # epistemic tier (empirical/modeled/proxy/synthetic)
                              # Required for production deployments; defaults
                              # to None so existing manifests load without
                              # edits — the UI renders "—" until declared.
    adapter: str  # short name resolved in adapters.ADAPTERS
    shaper: str | None = None  # optional short name resolved in shapers.SHAPERS;
                               # runs after adapter.fetch() to reshape value dict
                               # for downstream consumers (back-compat hook).
    trace_summary: dict[str, str] | None = None
    # Maps trace_key -> value_key. The FSM trace `rec["result"]` is built by
    # looking up each value_key in the shaped pebble value. Lets callers
    # rename / cherry-pick a small set of fields for the SSE trace without
    # writing per-pebble glue. Example:
    #   trace_summary:
    #     n_within_800m: n_within_radius
    #     max_height_above_gnd_ft: max_height_above_gnd_ft
    spatial: Spatial = Field(default_factory=Spatial)
    coverage: Coverage | None = None  # where this pebble fires; defaults
                                      # to its deployment's bbox when None
    config: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    narration: Narration = Field(default_factory=Narration)
    fallback: Fallback = Field(default_factory=Fallback)
    display: Display = Field(default_factory=Display)


class LivePebble(_PebbleBase):
    type: Literal["live"]


class BakedPebble(_PebbleBase):
    type: Literal["baked"]


class ModelPebble(_PebbleBase):
    type: Literal["model"]


PebbleManifest = Annotated[
    LivePebble | BakedPebble | ModelPebble,
    Field(discriminator="type"),
]
"""A validated pebble manifest. Discriminated on `type`."""
