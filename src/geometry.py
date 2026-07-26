"""Geometry validation and repair (PRD section 10).

Repairs invalid or degenerate hydrography geometries without simplifying valid
rivers (PRD section 11): invalid polygons and self-intersections are made
valid, consecutive duplicate vertices are removed, empty and collapsed
geometries are dropped, and singleton multiparts are normalized. Every fix and
drop is tallied in an immutable :class:`RepairStats` so the pipeline can report
what it cleaned.

This module operates purely on shapely geometries and has no file-format or
GDAL dependency, so it is fully unit-testable with hand-built geometries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from shapely import (
    get_num_coordinates,
    is_valid_reason,
    make_valid,
    remove_repeated_points,
)

__all__ = ["RepairStats", "RepairOutcome", "repair_geometry", "repair_layer"]


@dataclass(frozen=True)
class RepairStats:
    """Immutable tally of a repair pass; merges across layers."""

    total_in: int = 0
    total_out: int = 0
    invalid_fixed: int = 0
    self_intersections_fixed: int = 0
    empties_dropped: int = 0
    collapsed_dropped: int = 0
    duplicate_vertices_removed: int = 0
    multipart_normalized: int = 0

    def merge(self, other: "RepairStats") -> "RepairStats":
        """Return the field-wise sum of this and ``other``."""
        return RepairStats(
            total_in=self.total_in + other.total_in,
            total_out=self.total_out + other.total_out,
            invalid_fixed=self.invalid_fixed + other.invalid_fixed,
            self_intersections_fixed=self.self_intersections_fixed
            + other.self_intersections_fixed,
            empties_dropped=self.empties_dropped + other.empties_dropped,
            collapsed_dropped=self.collapsed_dropped + other.collapsed_dropped,
            duplicate_vertices_removed=self.duplicate_vertices_removed
            + other.duplicate_vertices_removed,
            multipart_normalized=self.multipart_normalized
            + other.multipart_normalized,
        )


@dataclass(frozen=True)
class RepairOutcome:
    """Result of repairing a single geometry."""

    geometry: Any | None
    invalid_fixed: bool = False
    self_intersection_fixed: bool = False
    duplicate_vertices_removed: int = 0
    multipart_normalized: bool = False
    dropped: str | None = None  # "empty" | "collapsed" | None


def _is_collapsed(geom: Any, original_kind: str) -> bool:
    """Whether a repaired geometry degenerated relative to its original type.

    Judged against the *original* geometry family: a line that ``make_valid``
    reduced to a point has collapsed even though a genuine point has not.
    """
    if "Line" in original_kind:
        return geom.length == 0
    if "Polygon" in original_kind:
        return geom.area == 0
    return False


def repair_geometry(geom: Any) -> RepairOutcome:
    """Repair one shapely geometry, reporting what was changed.

    Order: drop empty input, remove duplicate vertices, make invalid geometry
    valid, normalize singleton multiparts, then drop anything that collapsed.
    Never simplifies a valid geometry beyond removing exact-duplicate vertices.
    """
    if geom is None or geom.is_empty:
        return RepairOutcome(None, dropped="empty")

    original_kind = geom.geom_type
    before = get_num_coordinates(geom)
    geom = remove_repeated_points(geom)
    removed = before - get_num_coordinates(geom)

    invalid_fixed = False
    self_intersection = False
    if not geom.is_valid:
        reason = is_valid_reason(geom) or ""
        self_intersection = "Self-intersection" in reason
        geom = make_valid(geom)
        invalid_fixed = True

    multipart_normalized = False
    if geom.geom_type.startswith("Multi") and len(geom.geoms) == 1:
        geom = geom.geoms[0]
        multipart_normalized = True

    if geom.is_empty or _is_collapsed(geom, original_kind):
        return RepairOutcome(
            None,
            invalid_fixed=invalid_fixed,
            self_intersection_fixed=self_intersection,
            duplicate_vertices_removed=removed,
            multipart_normalized=multipart_normalized,
            dropped="collapsed",
        )

    return RepairOutcome(
        geom,
        invalid_fixed=invalid_fixed,
        self_intersection_fixed=self_intersection,
        duplicate_vertices_removed=removed,
        multipart_normalized=multipart_normalized,
    )


def repair_layer(geometries: Iterable[Any]) -> tuple[list[Any], RepairStats]:
    """Repair every geometry in a layer, returning survivors and statistics."""
    geometries = list(geometries)
    kept: list[Any] = []
    invalid_fixed = self_intersections = 0
    empties = collapsed = dup_removed = multipart = 0

    for geom in geometries:
        outcome = repair_geometry(geom)
        invalid_fixed += int(outcome.invalid_fixed)
        self_intersections += int(outcome.self_intersection_fixed)
        dup_removed += outcome.duplicate_vertices_removed
        multipart += int(outcome.multipart_normalized)
        if outcome.dropped == "empty":
            empties += 1
        elif outcome.dropped == "collapsed":
            collapsed += 1
        else:
            kept.append(outcome.geometry)

    stats = RepairStats(
        total_in=len(geometries),
        total_out=len(kept),
        invalid_fixed=invalid_fixed,
        self_intersections_fixed=self_intersections,
        empties_dropped=empties,
        collapsed_dropped=collapsed,
        duplicate_vertices_removed=dup_removed,
        multipart_normalized=multipart,
    )
    return kept, stats
