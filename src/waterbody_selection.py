"""Waterbody normalization & cartographic selection (Item W2, Task Group 2).

Takes the classified :class:`~src.waterbodies.WaterbodyFeature` objects from
W1 and runs them through the same geometry semantics as flowlines — repair →
reproject(EPSG:5070) → region clip — then measures projected area and applies
deterministic inclusion policy, producing a :class:`WaterbodySelection` report
that accounts for *every* candidate as selected or excluded.

Design notes:

- Reuses :func:`src.geometry.repair_geometry` and :func:`src.clipping.clip_geometry`
  so waterbodies inherit identical repair/clip behavior (holes and multipart
  membership are preserved by shapely ``make_valid``/``intersection``).
- Reprojection goes through an injectable ``reproject`` seam; the default lazily
  imports pyproj, so this module (and offline tests using EPSG:5070 inputs)
  never require pyproj/GDAL.
- Area is measured in EPSG:5070, an equal-area projection, so shapely's planar
  ``area`` is directly in m².
- **Conservative coast policy**: a coastal-class feature (bay/inlet/coastal)
  whose geometry was trimmed by the region clip is a "clip-boundary fragment"
  and is excluded, to avoid portraying truncated sea as a closed shape. Open
  ocean (SeaOcean) is already excluded upstream at classification (W1).
- No simplification. Selection changes only which features/area survive; it
  does not touch flowlines, stream order, or watershed colors.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

import shapely

from src.clipping import clip_geometry
from src.geometry import repair_geometry
from src.waterbodies import WATERBODY_POLICY_VERSION, WaterbodyFeature

__all__ = [
    "INLAND_CLASSES",
    "COASTAL_CLASSES",
    "WaterbodySelectionPolicy",
    "WaterbodySelection",
    "process_waterbodies",
]

#: Inland areal-water classes, governed by ``min_inland_area_m2``.
INLAND_CLASSES: tuple[str, ...] = ("lake", "pond", "reservoir")

#: Coastal areal-water classes, governed by ``min_coastal_area_m2`` and the
#: coast policy.
COASTAL_CLASSES: tuple[str, ...] = ("bay", "inlet", "coastal")


@dataclass(frozen=True)
class WaterbodySelectionPolicy:
    """Deterministic inclusion thresholds and coast handling (Item W2).

    Attributes:
        min_inland_area_m2: Minimum projected area (m²) for inland classes;
            ``0`` keeps every valid inland feature (the approved default).
        min_coastal_area_m2: Minimum projected area (m²) for coastal classes,
            applied only after the coast policy.
        pond_max_area_m2: If > 0, a ``lake`` (LakePond) below this area is
            relabeled ``pond``. ``0`` disables the split (all stay ``lake``),
            avoiding a baked-in art-direction number.
        coastal_mode: ``"conservative"`` excludes coastal clip-boundary
            fragments; any other value treats coastal features like inland.
    """

    min_inland_area_m2: float = 0.0
    min_coastal_area_m2: float = 0.0
    pond_max_area_m2: float = 0.0
    coastal_mode: str = "conservative"


@dataclass(frozen=True)
class WaterbodySelection:
    """The result of a selection pass; every candidate lands in one bucket.

    Attributes:
        selected: Included features, in source order, with ``area_m2`` set and
            geometry repaired/clipped.
        excluded: Excluded features, each with a populated ``inclusion_reason``.
        policy: The policy that produced this selection.
        policy_version: Classification policy version (for reproducible reports).
        counts: Summary counts (``candidates``, ``selected``, ``excluded``, and
            ``by_class`` for the selected set).
        shared_edge_pairs: Number of selected feature pairs that share a
            coincident boundary segment (informs W3 stroke de-duplication).
    """

    selected: tuple[WaterbodyFeature, ...]
    excluded: tuple[WaterbodyFeature, ...]
    policy: WaterbodySelectionPolicy
    policy_version: str
    counts: dict[str, Any] = field(default_factory=dict)
    shared_edge_pairs: int = 0


def _default_reproject(geom: Any, src_crs: str | None, dst_crs: str) -> Any:
    """Reproject ``geom`` to ``dst_crs``; a no-op when the CRS already matches.

    pyproj is imported lazily so importing this module never requires it, and
    offline tests that supply EPSG:5070 geometries skip the import entirely.
    """
    if not src_crs or src_crs == dst_crs:
        return geom
    from src.projection import _transformer, reproject_geometry  # pragma: no cover

    return reproject_geometry(geom, _transformer(src_crs, dst_crs))  # pragma: no cover


def _normalized_wkb(geom: Any) -> bytes:
    """A canonical WKB key for exact-duplicate detection (ring order normalized)."""
    return shapely.to_wkb(shapely.normalize(geom))


def _count_shared_edges(features: list[WaterbodyFeature]) -> tuple[int, set[int]]:
    """Count pairs of features whose polygon boundaries share a 1-D segment.

    Returns the pair count and the set of feature indices involved, so callers
    can flag them. Uses an STRtree so only spatially-near candidates are tested.
    """
    geoms = [f.geometry for f in features]
    if len(geoms) < 2:
        return 0, set()
    tree = shapely.STRtree(geoms)
    pairs = 0
    involved: set[int] = set()
    seen: set[tuple[int, int]] = set()
    for i, geom in enumerate(geoms):
        for j in tree.query(geom):
            j = int(j)
            if j <= i:
                continue
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            shared = geom.boundary.intersection(geoms[j].boundary)
            if not shared.is_empty and shared.length > 0:
                pairs += 1
                involved.add(i)
                involved.add(j)
    return pairs, involved


def process_waterbodies(
    features: Iterable[WaterbodyFeature],
    *,
    boundary: Any | None = None,
    policy: WaterbodySelectionPolicy | None = None,
    target_crs: str = "EPSG:5070",
    reproject: Callable[[Any, str | None, str], Any] | None = None,
) -> WaterbodySelection:
    """Repair, reproject, clip, measure, and select classified waterbodies.

    Every input feature ends up in exactly one of ``selected``/``excluded``.
    Processing order follows input order, so the result is deterministic.
    """
    policy = policy or WaterbodySelectionPolicy()
    reproject = reproject or _default_reproject

    selected: list[WaterbodyFeature] = []
    excluded: list[WaterbodyFeature] = []
    seen_wkb: dict[bytes, str] = {}

    def _exclude(feat: WaterbodyFeature, reason: str) -> None:
        excluded.append(replace(feat, inclusion_reason=reason))

    for feat in features:
        # Features already excluded at classification (e.g. SeaOcean, unknown
        # FType) pass straight through, keeping their reason.
        if feat.wb_class == "excluded":
            excluded.append(feat)
            continue

        if feat.geometry is None:
            _exclude(feat, "excluded: no geometry")
            continue

        outcome = repair_geometry(feat.geometry)
        if outcome.geometry is None:
            _exclude(feat, f"excluded: geometry dropped in repair ({outcome.dropped})")
            continue
        geom = reproject(outcome.geometry, feat.source_crs, target_crs)

        was_clipped = False
        if boundary is not None:
            if not geom.intersects(boundary):
                _exclude(feat, "excluded: outside region boundary")
                continue
            if not boundary.covers(geom):
                clipped = clip_geometry(geom, boundary)
                if clipped is None:
                    _exclude(feat, "excluded: outside region boundary")
                    continue
                geom = clipped
                was_clipped = True

        area_m2 = float(geom.area)
        wb_class = feat.wb_class

        # LakePond → pond refinement is purely area-based (optional).
        if wb_class == "lake" and policy.pond_max_area_m2 > 0 and area_m2 < policy.pond_max_area_m2:
            wb_class = "pond"

        qa_flags = feat.qa_flags + (("clipped",) if was_clipped else ())

        is_coastal = wb_class in COASTAL_CLASSES
        if is_coastal and policy.coastal_mode == "conservative" and was_clipped:
            _exclude(
                feat,
                "excluded: coastal clip-boundary fragment (conservative coast policy)",
            )
            continue

        threshold = policy.min_coastal_area_m2 if is_coastal else policy.min_inland_area_m2
        if area_m2 < threshold:
            _exclude(
                feat,
                f"excluded: area {area_m2:.1f} m² below min {threshold:.1f} m²",
            )
            continue

        key = _normalized_wkb(geom)
        if key in seen_wkb:
            _exclude(feat, f"excluded: duplicate geometry of {seen_wkb[key]!r}")
            continue
        seen_wkb[key] = feat.source_id

        selected.append(
            replace(
                feat,
                geometry=geom,
                wb_class=wb_class,
                source_crs=target_crs,
                area_m2=area_m2,
                qa_flags=qa_flags,
                inclusion_reason=f"selected as {wb_class}: area {area_m2:.1f} m²",
            )
        )

    shared_pairs, involved = _count_shared_edges(selected)
    if involved:
        selected = [
            replace(f, qa_flags=f.qa_flags + ("shared_edge",)) if i in involved else f
            for i, f in enumerate(selected)
        ]

    by_class: dict[str, int] = {}
    for feat in selected:
        by_class[feat.wb_class] = by_class.get(feat.wb_class, 0) + 1

    counts = {
        "candidates": len(selected) + len(excluded),
        "selected": len(selected),
        "excluded": len(excluded),
        "by_class": by_class,
    }

    return WaterbodySelection(
        selected=tuple(selected),
        excluded=tuple(excluded),
        policy=policy,
        policy_version=WATERBODY_POLICY_VERSION,
        counts=counts,
        shared_edge_pairs=shared_pairs,
    )
