"""Reprojection of hydrography layers to the internal CRS (PRD section 9).

Normalizes geometries to a target EPSG (default EPSG:5070; optionally
EPSG:4326/3857) using ``pyproj`` + ``shapely.ops.transform``. Reprojection
preserves every vertex — it never simplifies (PRD section 11). Transforms are
pure functions over shapely geometries, so they are fully unit-testable with
hand-built geometries and known CRS pairs (no GDAL, no real data).
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import Any

from pyproj import Transformer
from shapely.ops import transform as shapely_transform

from src.datasets import AcquisitionError
from src.loading import Layer

__all__ = ["ProjectionError", "reproject_geometry", "reproject_layer"]


class ProjectionError(AcquisitionError):
    """Raised when a layer cannot be reprojected (e.g. unknown source CRS)."""


@lru_cache(maxsize=None)
def _transformer(src_crs: str, dst_crs: str) -> Transformer:
    """Return a cached always-xy transformer between two CRS identifiers."""
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def reproject_geometry(geom: Any, transformer: Transformer) -> Any:
    """Reproject a single shapely geometry using ``transformer``."""
    return shapely_transform(transformer.transform, geom)


def reproject_layer(layer: Layer, target_crs: str) -> Layer:
    """Return a copy of ``layer`` with geometries normalized to ``target_crs``.

    Raises:
        ProjectionError: If the layer has no known source CRS.
    """
    if not layer.crs:
        raise ProjectionError(
            f"Layer {layer.name!r} ({layer.dataset_id}/{layer.huc4}) has no CRS; "
            "cannot reproject."
        )
    if layer.crs == target_crs:
        return layer
    transformer = _transformer(layer.crs, target_crs)
    geometries = tuple(
        reproject_geometry(geom, transformer) for geom in layer.geometries
    )
    return replace(layer, geometries=geometries, crs=target_crs)
