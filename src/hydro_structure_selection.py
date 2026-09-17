"""Engineered-structure normalization & cartographic selection (Epoch 16, #67).

Takes the classified :class:`~src.hydro_structures.HydroStructure` features from
#65 and runs them through the same geometry semantics as flowlines/waterbodies —
repair → reproject(EPSG:5070) → region clip — then selects deterministically,
producing a report that accounts for *every* candidate as selected or excluded.

Design notes (mirroring :mod:`src.areal_selection`):

- Reuses :func:`src.geometry.repair_geometry` and
  :func:`src.clipping.clip_geometry`, so structures inherit identical
  repair/clip behavior.
- Reprojection goes through an injectable ``reproject`` seam; the default lazily
  imports pyproj, so this module (and offline tests using EPSG:5070 inputs) never
  require pyproj/GDAL.
- Area is measured in EPSG:5070 (equal-area), so shapely's planar ``area`` is
  directly in m².

The one thing that makes this module different from the Epoch 15 selectors is
that engineered structures span THREE geometry kinds in a single taxonomy, so
selection **branches on geometry type** rather than on a single family:

- **Polygon** structures (spillway/lock/canal/area intakes): per-class
  ``min_area_m2`` threshold in EPSG:5070; below-threshold → excluded.
- **Point** structures (gaging/intake/gate): per-family ``min_spacing_m``
  deterministic density thinning in source order.
- **Line** structures (dam/weir/gate): clip only (no threshold in v1); a
  clipped line is kept and flagged, never dropped.

Exact-duplicate geometries are deduped by normalized WKB, matching the sibling
selectors so a re-run of the same source is byte-stable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Any

import shapely

from src.clipping import clip_geometry
from src.crs import INTERNAL_CRS
from src.geometry import repair_geometry
from src.hydro_structures import HYDRO_STRUCTURE_POLICY_VERSION, HydroStructure

__all__ = [
    "HydroStructureSelection",
    "HydroStructureSelectionPolicy",
    "process_hydro_structures",
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


def _geometry_kind(geom: Any) -> str:
    """Classify a shapely geometry as ``"polygon"``/``"point"``/``"line"``.

    Multipart geometries map to the kind of their members; anything else falls
    through to ``"other"`` and is treated as a line (clip-only) so no feature is
    silently invented or dropped.
    """
    gtype = getattr(geom, "geom_type", "")
    if gtype in ("Polygon", "MultiPolygon"):
        return "polygon"
    if gtype in ("Point", "MultiPoint"):
        return "point"
    if gtype in ("LineString", "MultiLineString", "LinearRing"):
        return "line"
    return "other"


@dataclass(frozen=True)
class HydroStructureSelectionPolicy:
    """Deterministic inclusion thresholds for engineered structures.

    Selection branches on geometry kind:

    Attributes:
        min_area_m2: Per-class minimum projected area (m²) for polygon
            structures. A class absent from the mapping uses
            ``default_min_area_m2``.
        default_min_area_m2: Fallback polygon threshold; ``0`` keeps every valid
            polygon (the safe default).
        min_spacing_m: Per-class minimum spacing (m) between selected point
            structures of the same class. A class absent from the mapping uses
            ``default_min_spacing_m``.
        default_min_spacing_m: Fallback point spacing; ``0`` disables thinning.

    Line structures (dam/weir/gate) are clip-only in v1 — there is no line
    threshold — so a line that survives the region clip is always kept.
    """

    min_area_m2: dict[str, float] = field(default_factory=dict)
    default_min_area_m2: float = 0.0
    min_spacing_m: dict[str, float] = field(default_factory=dict)
    default_min_spacing_m: float = 0.0

    def area_threshold_for(self, struct_class: str) -> float:
        """Return the min-area threshold governing polygon ``struct_class``."""
        return self.min_area_m2.get(struct_class, self.default_min_area_m2)

    def spacing_for(self, struct_class: str) -> float:
        """Return the min-spacing threshold governing point ``struct_class``."""
        return self.min_spacing_m.get(struct_class, self.default_min_spacing_m)


@dataclass(frozen=True)
class HydroStructureSelection:
    """The result of a structure selection pass; every candidate lands in a bucket.

    Attributes:
        selected: Included structures, in source order, geometry
            repaired/reprojected/clipped, ``clipped`` flagged in ``qa_flags``.
        excluded: Excluded structures, each with a populated ``inclusion_reason``.
        policy: The policy that produced this selection.
        policy_version: Classification policy version (for reproducible reports).
        counts: Summary counts (``candidates``, ``selected``, ``excluded``, and
            ``by_class`` for the selected set).
    """

    selected: tuple[HydroStructure, ...]
    excluded: tuple[HydroStructure, ...]
    policy: HydroStructureSelectionPolicy
    policy_version: str
    counts: dict[str, Any] = field(default_factory=dict)


def process_hydro_structures(
    features: Iterable[HydroStructure],
    *,
    boundary: Any | None = None,
    policy: HydroStructureSelectionPolicy | None = None,
    target_crs: str = INTERNAL_CRS,
    reproject: Callable[[Any, str | None, str], Any] | None = None,
) -> HydroStructureSelection:
    """Repair, reproject, clip, and geometry-type-aware select structures.

    Each feature is repaired, reprojected to ``target_crs`` (EPSG:5070) through
    the injectable ``reproject`` seam, and clipped to ``boundary`` (dropped if
    fully outside, flagged if clipped). Surviving features are then selected by
    geometry kind: polygons by per-class ``min_area_m2``, points by per-class
    ``min_spacing_m`` density thinning in source order, lines by clip-only.
    Every input feature ends up in exactly one of ``selected``/``excluded``, so
    the result is deterministic.
    """
    policy = policy or HydroStructureSelectionPolicy()
    reproject = reproject or _default_reproject

    selected: list[HydroStructure] = []
    excluded: list[HydroStructure] = []
    seen_wkb: dict[bytes, str] = {}
    accepted_points: dict[str, list[Any]] = {}

    def _exclude(feat: HydroStructure, reason: str) -> None:
        excluded.append(replace(feat, inclusion_reason=reason))

    for feat in features:
        # Features already excluded at classification pass straight through.
        if feat.struct_class == "excluded":
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

        kind = _geometry_kind(geom)

        # Polygon structures: per-class minimum-area threshold in EPSG:5070.
        if kind == "polygon":
            area_m2 = float(geom.area)
            threshold = policy.area_threshold_for(feat.struct_class)
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

        # Point structures: deterministic per-class minimum-spacing density cap.
        if kind == "point":
            spacing = policy.spacing_for(feat.struct_class)
            if spacing > 0:
                neighbors = accepted_points.get(feat.struct_class, ())
                if any(geom.distance(other) < spacing for other in neighbors):
                    _exclude(
                        feat,
                        f"excluded: within {spacing:.1f} m of a denser-priority "
                        f"{feat.struct_class} structure (density cap)",
                    )
                    continue
            accepted_points.setdefault(feat.struct_class, []).append(geom)

        # Line structures fall through: clip-only, always kept once clipped.

        seen_wkb[key] = feat.source_id
        qa_flags = feat.qa_flags + (("clipped",) if was_clipped else ())
        selected.append(
            replace(
                feat,
                geometry=geom,
                source_crs=target_crs,
                qa_flags=qa_flags,
                inclusion_reason=f"selected as {feat.struct_class} ({kind})",
            )
        )

    by_class: dict[str, int] = {}
    for feat in selected:
        by_class[feat.struct_class] = by_class.get(feat.struct_class, 0) + 1

    counts = {
        "candidates": len(selected) + len(excluded),
        "selected": len(selected),
        "excluded": len(excluded),
        "by_class": by_class,
    }

    return HydroStructureSelection(
        selected=tuple(selected),
        excluded=tuple(excluded),
        policy=policy,
        policy_version=HYDRO_STRUCTURE_POLICY_VERSION,
        counts=counts,
    )
