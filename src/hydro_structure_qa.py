"""Pure, offline QA over classified hydro structures (Epoch 16, Item 68).

Mirrors the ``src/determinism.py`` / ``src/flow_metrics.py`` pattern: pure,
deterministic functions the offline suite tests, while the heavy real-data reads
live in a companion ``tools/`` script. This module answers the three
infrastructure-QA questions from the roadmap over already-classified
:class:`~src.hydro_structures.HydroStructure` sequences plus the flowline
network and the natural-taxonomy features:

1. **On-network placement** — is each engineered structure ON/near the flowline
   network it belongs to, not floating in space?
   (:func:`structure_network_placement`)
2. **Cross-layer duplicate suppression** — is the same real-world structure
   classified from more than one source layer (e.g. a dam present as both an
   ``NHDLine`` and an ``NHDArea`` feature) a candidate to draw once, not twice?
   (:func:`cross_layer_duplicates`)
3. **Canal / natural separation** — do the engineered channels stay distinct
   from natural water, so no structure double-draws a natural feature?
   (:func:`canal_natural_separation`)

:func:`build_qa_report` folds the three into a :class:`HydroStructureQAReport`.

**Projection-free contract.** All distances/overlaps are computed in the
project's internal metric CRS (:data:`~src.crs.INTERNAL_CRS`, EPSG:5070). Inputs
are assumed to be *already* reprojected by the caller (the pipeline/tool
reprojects before QA), so this module does pure shapely ``distance``/
``intersects`` math and never reprojects. Top-level ``import shapely`` is allowed
here as in the sibling selection modules; no ``pyogrio``/``geopandas``/
``rasterio`` and no network.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

import shapely  # noqa: F401  (kept for the metric-geometry contract / parity)

from src.crs import INTERNAL_CRS
from src.hydro_structures import HydroStructure

__all__ = [
    "HydroStructureQAReport",
    "NetworkPlacement",
    "build_qa_report",
    "canal_natural_separation",
    "cross_layer_duplicates",
    "structure_network_placement",
]

#: Documents the metric-CRS contract these distances/areas assume. Inputs must
#: already be in this CRS; this module never reprojects.
QA_DISTANCE_CRS = INTERNAL_CRS


@dataclass(frozen=True)
class NetworkPlacement:
    """Summary of how well structures sit on the flowline network.

    Attributes:
        count: Number of structures evaluated (those carrying a geometry).
        on_network: How many sit within ``tolerance_m`` of some flowline.
        median_distance_m: Median nearest-flowline distance across ``count``
            structures (``0.0`` when there are none).
        max_distance_m: Maximum nearest-flowline distance (``0.0`` when none).
        off_network_ids: ``source_id`` of every structure beyond ``tolerance_m``,
            in input order.
    """

    count: int
    on_network: int
    median_distance_m: float
    max_distance_m: float
    off_network_ids: tuple[str, ...]


@dataclass(frozen=True)
class HydroStructureQAReport:
    """Aggregate verdict combining the three structure-QA checks.

    Attributes:
        on_network: The :class:`NetworkPlacement` summary.
        duplicate_groups: Cross-layer near-duplicate ``source_id`` groups, each a
            tuple of the members that likely represent one real-world structure.
        separation_ok: ``True`` when no structure coincides with a natural feature.
        overlaps: The offending ``(structure_source_id, natural_source_id)`` pairs
            when ``separation_ok`` is ``False``; empty otherwise.
    """

    on_network: NetworkPlacement
    duplicate_groups: tuple[tuple[str, ...], ...]
    separation_ok: bool
    overlaps: tuple[tuple[str, str], ...]


def _nearest_distance(geometry: Any, flowlines: Sequence[Any]) -> float | None:
    """Return the minimum distance from ``geometry`` to any flowline, or None."""
    best: float | None = None
    for line in flowlines:
        if line is None:
            continue
        dist = float(geometry.distance(line))
        if best is None or dist < best:
            best = dist
    return best


def structure_network_placement(
    structures: Iterable[HydroStructure],
    flowlines: Iterable[Any],
    *,
    tolerance_m: float,
) -> NetworkPlacement:
    """Summarize each structure's nearest-flowline distance.

    A structure whose nearest flowline is within ``tolerance_m`` is counted
    on-network; otherwise its ``source_id`` is reported off-network. The median
    and maximum nearest-flowline distances are computed over every structure that
    carries a geometry. Distances are planar metres in :data:`QA_DISTANCE_CRS`;
    no reprojection is performed. Structures without a geometry, and structures
    when there are no flowlines, are skipped (cannot be placed).
    """
    lines = [line for line in flowlines if line is not None]

    distances: list[float] = []
    on_network = 0
    off_network_ids: list[str] = []

    for structure in structures:
        geom = structure.geometry
        if geom is None:
            continue
        nearest = _nearest_distance(geom, lines)
        if nearest is None:
            continue
        distances.append(nearest)
        if nearest <= tolerance_m:
            on_network += 1
        else:
            off_network_ids.append(structure.source_id)

    if distances:
        median_distance = float(median(distances))
        max_distance = float(max(distances))
    else:
        median_distance = 0.0
        max_distance = 0.0

    return NetworkPlacement(
        count=len(distances),
        on_network=on_network,
        median_distance_m=median_distance,
        max_distance_m=max_distance,
        off_network_ids=tuple(off_network_ids),
    )


def cross_layer_duplicates(
    structures: Iterable[HydroStructure],
    *,
    tolerance_m: float,
) -> tuple[tuple[str, ...], ...]:
    """Group near-coincident structures that span DIFFERENT source layers.

    Two structures form a candidate duplicate when they share the same
    ``struct_class``, come from different ``source_layer``s, and lie within
    ``tolerance_m`` of one another (planar metres in :data:`QA_DISTANCE_CRS`).
    Members are linked transitively into groups keyed by ``source_id``, so a dam
    appearing on both ``NHDLine`` and ``NHDArea`` yields one group while two
    distinct dams (or two on the same layer) yield none. Group order and member
    order follow input order for determinism.
    """
    items = [s for s in structures if s.geometry is not None]
    n = len(items)

    # Union-find over indices for transitive grouping.
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            if a.struct_class != b.struct_class:
                continue
            if a.source_layer == b.source_layer:
                continue
            if float(a.geometry.distance(b.geometry)) <= tolerance_m:
                union(i, j)

    groups: dict[int, list[str]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(items[i].source_id)

    # Only groups with >1 member are cross-layer duplicates; preserve input order.
    result: list[tuple[str, ...]] = []
    for i in range(n):
        if find(i) == i and len(groups[i]) > 1:
            result.append(tuple(groups[i]))
    return tuple(result)


def _coincidence_fraction(structure_geom: Any, natural_geom: Any) -> float:
    """Fraction of a structure that is *coincident with* a natural geometry.

    Measured in the structure's own dimensionality so that mere boundary
    *adjacency* does not register: two polygons sharing an edge intersect in a
    zero-area line, so the area-based fraction is ``0``. A polygon structure that
    genuinely occupies the same footprint as a natural polygon yields a fraction
    near ``1``; a canal line running *through* a natural waterbody yields the
    fraction of its length inside; a point inside/on a natural feature yields
    ``1``. Returns ``0`` when the geometries do not intersect.
    """
    if structure_geom is None or natural_geom is None:
        return 0.0
    if not structure_geom.intersects(natural_geom):
        return 0.0
    inter = structure_geom.intersection(natural_geom)
    if inter.is_empty:
        return 0.0
    if structure_geom.area > 0:
        return inter.area / structure_geom.area
    if structure_geom.length > 0:
        return inter.length / structure_geom.length
    return 1.0  # point-like structure that intersects a natural feature


def canal_natural_separation(
    structures: Iterable[HydroStructure],
    natural_features: Iterable[Any],
    *,
    min_overlap_fraction: float = 0.5,
) -> tuple[bool, tuple[tuple[str, str], ...]]:
    """Assert engineered structures do not *coincide* with natural features.

    A violation is genuine geometric coincidence — a structure whose footprint is
    substantially the same as (or inside) a natural-taxonomy feature — not mere
    shared-boundary adjacency, which is normal and pervasive in real NHD data
    (engineered ``NHDArea`` polygons routinely touch adjacent natural polygons).
    Coincidence is measured by :func:`_coincidence_fraction` against
    ``min_overlap_fraction``; the complementary taxonomies (disjoint FType codes)
    mean true coincidence should never occur, so this is a leak detector, not an
    adjacency counter. ``natural_features`` are any value objects carrying a
    ``.geometry`` and a ``.source_id``. Returns ``(separation_ok,
    offending_pairs)`` with each pair ``(structure_source_id, natural_source_id)``
    in input order; disjoint (or merely adjacent) inputs return ``(True, ())``. No
    reprojection is performed.
    """
    naturals = [nf for nf in natural_features if getattr(nf, "geometry", None) is not None]

    overlaps: list[tuple[str, str]] = []
    for structure in structures:
        geom = structure.geometry
        if geom is None:
            continue
        for natural in naturals:
            if _coincidence_fraction(geom, natural.geometry) >= min_overlap_fraction:
                overlaps.append((structure.source_id, str(natural.source_id)))

    return (not overlaps, tuple(overlaps))


def build_qa_report(
    structures: Iterable[HydroStructure],
    flowlines: Iterable[Any],
    natural_features: Iterable[Any],
    *,
    tolerance_m: float,
) -> HydroStructureQAReport:
    """Run all three QA checks and aggregate them into one report.

    ``structures`` is materialized once since it feeds every check. Distances and
    overlaps are computed in :data:`QA_DISTANCE_CRS`; inputs must already be in
    that CRS (no reprojection here).
    """
    structures = list(structures)
    flowlines = list(flowlines)
    natural_features = list(natural_features)

    placement = structure_network_placement(
        structures, flowlines, tolerance_m=tolerance_m
    )
    duplicate_groups = cross_layer_duplicates(structures, tolerance_m=tolerance_m)
    separation_ok, overlaps = canal_natural_separation(structures, natural_features)

    return HydroStructureQAReport(
        on_network=placement,
        duplicate_groups=duplicate_groups,
        separation_ok=separation_ok,
        overlaps=overlaps,
    )
