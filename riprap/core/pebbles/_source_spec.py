"""Shared `{source: ...}` / `{const: ...}` resolver for adapters that build
arguments (Python call kwargs, HTTP request bodies) from a SpatialQuery.

  {source: lat}        query.lat
  {source: lon}        query.lon
  {source: radius_m}   query.radius_m
  {source: pt_2263}    shapely.Point in EPSG:2263
  {source: pt_4326}    shapely.Point in EPSG:4326
  {source: query}      the full SpatialQuery object
  {const: 800}         literal value
  "plain string"        passed through unchanged (not a dict)
"""
from __future__ import annotations

from typing import Any

from riprap.core.pebbles.base import SpatialQuery


def _build_pt_2263(lat: float, lon: float):
    """WGS84 lat/lon -> shapely Point in EPSG:2263. Lazy import so the
    heavy geopandas/pyproj stack only loads when a pebble needs it."""
    import geopandas as gpd  # noqa: PLC0415
    from shapely.geometry import Point  # noqa: PLC0415
    return (gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
            .to_crs("EPSG:2263").iloc[0].geometry)


def _build_pt_4326(lat: float, lon: float):
    from shapely.geometry import Point  # noqa: PLC0415
    return Point(lon, lat)


def resolve_source_spec(spec: Any, query: SpatialQuery) -> Any:
    if not isinstance(spec, dict):
        return spec  # raw value, e.g. plain string
    if "const" in spec:
        return spec["const"]
    src = spec.get("source")
    if src == "lat":
        return query.lat
    if src == "lon":
        return query.lon
    if src == "radius_m":
        return query.radius_m
    if src == "pt_2263":
        return _build_pt_2263(query.lat, query.lon)
    if src == "pt_4326":
        return _build_pt_4326(query.lat, query.lon)
    if src == "query":
        return query
    raise ValueError(f"unknown source {src!r}")
