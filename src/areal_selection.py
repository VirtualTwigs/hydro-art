"""Areal + point normalization & cartographic selection (Epoch 15, Item 62).

Takes the classified :class:`~src.areal_features.ArealFeature` polygons and
:class:`~src.point_features.PointFeature` points and runs them through the same
geometry semantics as flowlines/waterbodies — repair → reproject(EPSG:5070) →
region clip — then selects deterministically, producing reports that account for
*every* candidate as selected or excluded.

Design notes (mirroring :mod:`src.waterbody_selection`):

- Reuses :func:`src.geometry.repair_geometry` and
  :func:`src.clipping.clip_geometry` so areal/point features inherit identical
  repair/clip behavior (polygon holes and multipart membership are preserved by
  shapely ``make_valid``/``intersection``).
- Reprojection goes through an injectable ``reproject`` seam; the default lazily
  imports pyproj, so this module (and offline tests using EPSG:5070 inputs) never
  require pyproj/GDAL.
- Area is measured in EPSG:5070 (equal-area), so shapely's planar ``area`` is
  directly in m².
- **Areal selection** applies a per-class ``min_area_m2`` threshold; there is no
  coastal policy (these families are inland) and no pond-style relabeling.
- **Point selection** is binary-clip (a point is inside the region or not — no
  trimming) followed by a deterministic per-family minimum-spacing density cap:
  points are visited in source order and a candidate within ``min_spacing_m`` of
  an already-accepted point of the *same* family is dropped, so denser clusters
  thin predictably at small scale with a stable source-order tie-break.
- Exact-duplicate geometries (polygons or points) are deduped by normalized WKB.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

import shapely

from src.areal_features import AREAL_POLICY_VERSION, ArealFeature
from src.clipping import clip_geometry
from src.crs import INTERNAL_CRS
from src.geometry import repair_geometry
from src.point_features import POINT_POLICY_VERSION, PointFeature

__all__ = [
    "ArealSelectionPolicy",
    "ArealSelection",
    "process_areal_features",
    "PointSelectionPolicy",
    "PointSelection",
    "process_point_features",
]


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


# --- Areal selection -------------------------------------------------------


@dataclass(frozen=True)
class ArealSelectionPolicy:
    """Deterministic per-class inclusion thresholds for areal features.

    Attributes:
        min_area_m2: Per-class minimum projected area (m²). A class absent from
            the mapping uses ``default_min_area_m2``.
        default_min_area_m2: Fallback threshold for classes not in
            ``min_area_m2``; ``0`` keeps every valid feature (the safe default).
    """

    min_area_m2: dict[str, float] = field(default_factory=dict)
    default_min_area_m2: float = 0.0

    def threshold_for(self, ar_class: str) -> float:
        """Return the min-area threshold governing ``ar_class``."""
        return self.min_area_m2.get(ar_class, self.default_min_area_m2)


@dataclass(frozen=True)
class ArealSelection:
    """The result of an areal selection pass; every candidate lands in a bucket.

    Attributes:
        selected: Included features, in source order, with ``area_m2`` set and
            geometry repaired/clipped.
        excluded: Excluded features, each with a populated ``inclusion_reason``.
        policy: The policy that produced this selection.
        policy_version: Classification policy version (for reproducible reports).
        counts: Summary counts (``candidates``, ``selected``, ``excluded``, and
            ``by_class`` for the selected set).
    """

    selected: tuple[ArealFeature, ...]
    excluded: tuple[ArealFeature, ...]
    policy: ArealSelectionPolicy
    policy_version: str
    counts: dict[str, Any] = field(default_factory=dict)


def process_areal_features(
    features: Iterable[ArealFeature],
    *,
    boundary: Any | None = None,
    policy: ArealSelectionPolicy | None = None,
    target_crs: str = INTERNAL_CRS,
    reproject: Callable[[Any, str | None, str], Any] | None = None,
) -> ArealSelection:
    """Repair, reproject, clip, measure, and select classified areal features.

    Every input feature ends up in exactly one of ``selected``/``excluded``.
    Processing follows input order, so the result is deterministic.
    """
    policy = policy or ArealSelectionPolicy()
    reproject = reproject or _default_reproject

    selected: list[ArealFeature] = []
    excluded: list[ArealFeature] = []
    seen_wkb: dict[bytes, str] = {}

    def _exclude(feat: ArealFeature, reason: str) -> None:
        excluded.append(replace(feat, inclusion_reason=reason))

    for feat in features:
        # Features already excluded at classification pass straight through.
        if feat.ar_class == "excluded":
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
        threshold = policy.threshold_for(feat.ar_class)
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

        qa_flags = feat.qa_flags + (("clipped",) if was_clipped else ())
        selected.append(
            replace(
                feat,
                geometry=geom,
                source_crs=target_crs,
                area_m2=area_m2,
                qa_flags=qa_flags,
                inclusion_reason=f"selected as {feat.ar_class}: area {area_m2:.1f} m²",
            )
        )

    by_class: dict[str, int] = {}
    for feat in selected:
        by_class[feat.ar_class] = by_class.get(feat.ar_class, 0) + 1

    counts = {
        "candidates": len(selected) + len(excluded),
        "selected": len(selected),
        "excluded": len(excluded),
        "by_class": by_class,
    }

    return ArealSelection(
        selected=tuple(selected),
        excluded=tuple(excluded),
        policy=policy,
        policy_version=AREAL_POLICY_VERSION,
        counts=counts,
    )


# --- Point selection -------------------------------------------------------


@dataclass(frozen=True)
class PointSelectionPolicy:
    """Deterministic per-family density cap for point features.

    Attributes:
        min_spacing_m: Per-family minimum spacing (m) between selected points.
            A candidate within this distance of an already-accepted point of the
            *same* family is dropped. A family absent from the mapping uses
            ``default_min_spacing_m``.
        default_min_spacing_m: Fallback spacing for families not in
            ``min_spacing_m``; ``0`` disables thinning (keeps every point).
    """

    min_spacing_m: dict[str, float] = field(default_factory=dict)
    default_min_spacing_m: float = 0.0

    def spacing_for(self, pt_class: str) -> float:
        """Return the min-spacing threshold governing ``pt_class``."""
        return self.min_spacing_m.get(pt_class, self.default_min_spacing_m)


@dataclass(frozen=True)
class PointSelection:
    """The result of a point selection pass; every candidate lands in a bucket.

    Attributes:
        selected: Included points, in source order, geometry repaired/reprojected.
        excluded: Excluded points, each with a populated ``inclusion_reason``.
        policy: The policy that produced this selection.
        policy_version: Classification policy version (for reproducible reports).
        counts: Summary counts (``candidates``, ``selected``, ``excluded``, and
            ``by_class`` for the selected set).
    """

    selected: tuple[PointFeature, ...]
    excluded: tuple[PointFeature, ...]
    policy: PointSelectionPolicy
    policy_version: str
    counts: dict[str, Any] = field(default_factory=dict)


def process_point_features(
    features: Iterable[PointFeature],
    *,
    boundary: Any | None = None,
    policy: PointSelectionPolicy | None = None,
    target_crs: str = INTERNAL_CRS,
    reproject: Callable[[Any, str | None, str], Any] | None = None,
) -> PointSelection:
    """Repair, reproject, clip, and density-thin classified point features.

    A point is either inside the region (kept) or outside (dropped) — there is no
    trimming. Surviving points are thinned per family by a deterministic
    minimum-spacing pass in source order, and exact-duplicate coordinates are
    suppressed. Every input feature ends up in exactly one of
    ``selected``/``excluded``.
    """
    policy = policy or PointSelectionPolicy()
    reproject = reproject or _default_reproject

    selected: list[PointFeature] = []
    excluded: list[PointFeature] = []
    seen_wkb: dict[bytes, str] = {}
    accepted_by_class: dict[str, list[Any]] = {}

    def _exclude(feat: PointFeature, reason: str) -> None:
        excluded.append(replace(feat, inclusion_reason=reason))

    for feat in features:
        if feat.pt_class == "excluded":
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

        if boundary is not None and not geom.intersects(boundary):
            _exclude(feat, "excluded: outside region boundary")
            continue

        key = _normalized_wkb(geom)
        if key in seen_wkb:
            _exclude(feat, f"excluded: duplicate point of {seen_wkb[key]!r}")
            continue

        spacing = policy.spacing_for(feat.pt_class)
        if spacing > 0:
            neighbors = accepted_by_class.get(feat.pt_class, ())
            if any(geom.distance(other) < spacing for other in neighbors):
                _exclude(
                    feat,
                    f"excluded: within {spacing:.1f} m of a denser-priority "
                    f"{feat.pt_class} point (density cap)",
                )
                continue

        seen_wkb[key] = feat.source_id
        accepted_by_class.setdefault(feat.pt_class, []).append(geom)
        selected.append(
            replace(
                feat,
                geometry=geom,
                source_crs=target_crs,
                inclusion_reason=f"selected as {feat.pt_class}",
            )
        )

    by_class: dict[str, int] = {}
    for feat in selected:
        by_class[feat.pt_class] = by_class.get(feat.pt_class, 0) + 1

    counts = {
        "candidates": len(selected) + len(excluded),
        "selected": len(selected),
        "excluded": len(excluded),
        "by_class": by_class,
    }

    return PointSelection(
        selected=tuple(selected),
        excluded=tuple(excluded),
        policy=policy,
        policy_version=POINT_POLICY_VERSION,
        counts=counts,
    )
