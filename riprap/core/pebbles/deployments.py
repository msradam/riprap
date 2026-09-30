"""Deployment discovery + per-query routing.

Every deployment under `deployments/` carries a `stones.yaml` with an
optional top-level `coverage:` block declaring its bbox + city/state:

  coverage:
    bbox: [min_lon, min_lat, max_lon, max_lat]  # WGS84
    polygon: data/nyc_ntas_2020.geojson         # optional, repo-relative
    city: New York City
    state: NY

The bbox is the quick test; when `polygon` is given, the point must also
fall inside the union of that file's features (NYC's bbox alone took in
Hoboken and Nassau County, and the city's own layers then reported them
"outside the Sandy footprint").

When a query is geocoded, `pick_deployment(lat, lon)` picks the deployment
whose bbox contains the resolved point. That deployment's manifest set is
the one that fans out for the run — so a Boston query never fires NYC's
`ida_hwm` pebble, regardless of which deployment the server happened to
boot with as its default.

Falls back to `None` when no deployment covers the point; the caller is
responsible for short-circuiting the briefing to a "not covered yet"
response in that case.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Deployment:
    name: str                    # 'nyc', 'boston', ...
    root: Path                   # absolute path to deployments/<name>/
    bbox: tuple[float, float, float, float] | None  # (min_lon, min_lat, max_lon, max_lat)
    city: str | None
    state: str | None
    polygon: Path | None = None

    def contains(self, lat: float, lon: float) -> bool:
        if self.bbox is None:
            return False
        min_lon, min_lat, max_lon, max_lat = self.bbox
        if not ((min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)):
            return False
        return self.polygon is None or _coverage_shape(self.polygon).contains(_point(lon, lat))


def _point(lon: float, lat: float):
    from shapely.geometry import Point  # noqa: PLC0415

    return Point(lon, lat)


@lru_cache(maxsize=4)
def _coverage_shape(path: Path):
    """The union of a coverage file's features, prepared for point tests."""
    import geopandas as gpd  # noqa: PLC0415
    from shapely.prepared import prep  # noqa: PLC0415

    return prep(gpd.read_file(path).to_crs("EPSG:4326").geometry.union_all())


def _repo_root() -> Path:
    # riprap/core/pebbles/deployments.py → repo root is 4 levels up
    return Path(__file__).resolve().parent.parent.parent.parent


@lru_cache(maxsize=1)
def discover_deployments() -> tuple[Deployment, ...]:
    """Scan `deployments/` for stones.yaml and parse the coverage block.

    Cached: deployments are scanned once per process. Tests that need to
    refresh after writing new manifests can call `discover_deployments.cache_clear()`.
    """
    root = _repo_root() / "deployments"
    if not root.is_dir():
        return ()
    out: list[Deployment] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        stones_yaml = child / "stones.yaml"
        if not stones_yaml.is_file():
            continue
        try:
            data = yaml.safe_load(stones_yaml.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        cov = data.get("coverage") or {}
        bbox_raw = cov.get("bbox")
        bbox = None
        if (isinstance(bbox_raw, list) and len(bbox_raw) == 4
                and all(isinstance(v, (int, float)) for v in bbox_raw)):
            bbox = (float(bbox_raw[0]), float(bbox_raw[1]),
                    float(bbox_raw[2]), float(bbox_raw[3]))
        poly = cov.get("polygon")
        out.append(Deployment(
            name=child.name,
            root=child.resolve(),
            bbox=bbox,
            city=cov.get("city"),
            state=cov.get("state"),
            polygon=(_repo_root() / poly) if isinstance(poly, str) and poly else None,
        ))
    return tuple(out)


def pick_deployment(lat: float | None, lon: float | None) -> Deployment | None:
    """Return the deployment whose bbox contains the point, else None.

    With overlapping bboxes (won't happen for our five shipped cities,
    but is theoretically possible for a custom site), the first match in
    discovery order wins. Discovery order is alphabetical by directory
    name — deterministic across machines.
    """
    if lat is None or lon is None:
        return None
    for dep in discover_deployments():
        if dep.contains(lat, lon):
            return dep
    return None


def deployment_by_name(name: str) -> Deployment | None:
    """Lookup a deployment by its directory name (e.g. 'nyc')."""
    for dep in discover_deployments():
        if dep.name == name:
            return dep
    return None


def deployment_root(name: str | None) -> Path:
    """The directory of a deployment named by its short name ('boston'),
    a path, None (the RIPRAP_DEPLOYMENT env var, default deployments/nyc)
    or the out-of-coverage sentinel `__none__` (the federal sources still
    narrate). The one place this is decided."""
    import os

    if name == "__none__":
        name = "federal"
    if name is None:
        name = os.environ.get("RIPRAP_DEPLOYMENT", "deployments/nyc")
    dep = deployment_by_name(name)
    if dep is not None:
        return dep.root
    path = Path(name)
    return path if path.is_absolute() else _repo_root() / path
