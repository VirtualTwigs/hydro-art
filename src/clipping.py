"""Clip hydrography to the configured region boundary (PRD section 8).

The region boundary is the union of the loaded WBD HUC polygon layers; flowline
layers are trimmed to it via shapely ``intersection`` (no simplification, PRD
section 11). Geometry entirely outside the boundary is dropped-and-counted;
partially-inside geometry is trimmed. Pure shapely — fully unit-testable with
hand-built geometries.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import Any, Iterable

from shapely.ops import unary_union

from src.loading import Layer

__all__ = [
    "ClipStats",
    "BOUNDARY_DATASET_ID",
    "is_boundary_layer",
    "region_boundary",
    "clip_geometry",
    "clip_layers",
]

#: Dataset id whose polygon layers define the region boundary.
BOUNDARY_DATASET_ID = "wbd"


@dataclass(frozen=True)
class ClipStats:
    """Immutable tally of a clip pass; merges across layers."""

    total_in: int = 0
    total_out: int = 0
    dropped_outside: int = 0
    clipped_partial: int = 0

    def merge(self, other: "ClipStats") -> "ClipStats":
        """Return the field-wise sum of this and ``other``."""
        return ClipStats(
            total_in=self.total_in + other.total_in,
            total_out=self.total_out + other.total_out,
            dropped_outside=self.dropped_outside + other.dropped_outside,
            clipped_partial=self.clipped_partial + other.clipped_partial,
        )


def is_boundary_layer(layer: Layer) -> bool:
    """Whether ``layer`` supplies region-boundary polygons (WBD)."""
    return layer.dataset_id == BOUNDARY_DATASET_ID


def region_boundary(layers: Iterable[Layer]) -> Any | None:
    """Union the WBD polygon layers into one boundary geometry, or ``None``."""
    geoms: list[Any] = []
    for layer in layers:
        if is_boundary_layer(layer):
            geoms.extend(layer.geometries)
    if not geoms:
        warnings.warn(
            "No WBD boundary layers found; hydrography will not be clipped.",
            stacklevel=2,
        )
        return None
    return unary_union(geoms)


def clip_geometry(geom: Any, boundary: Any) -> Any | None:
    """Intersect ``geom`` with ``boundary``; return ``None`` if nothing remains."""
    clipped = geom.intersection(boundary)
    if clipped.is_empty:
        return None
    return clipped


def clip_layers(
    layers: Iterable[Layer], boundary: Any | None
) -> tuple[list[Layer], ClipStats]:
    """Clip flowline layers to ``boundary``; pass boundary layers through.

    When ``boundary`` is ``None`` every layer passes through unchanged.
    """
    layers = list(layers)
    out_layers: list[Layer] = []
    stats = ClipStats()

    for layer in layers:
        if boundary is None or is_boundary_layer(layer):
            out_layers.append(layer)
            continue
        kept: list[Any] = []
        dropped = partial = 0
        for geom in layer.geometries:
            clipped = clip_geometry(geom, boundary)
            if clipped is None:
                dropped += 1
                continue
            if not clipped.equals(geom):
                partial += 1
            kept.append(clipped)
        stats = stats.merge(
            ClipStats(
                total_in=len(layer.geometries),
                total_out=len(kept),
                dropped_outside=dropped,
                clipped_partial=partial,
            )
        )
        out_layers.append(replace(layer, geometries=tuple(kept)))

    return out_layers, stats
