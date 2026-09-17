"""NHDPoint natural-feature classification contract (Epoch 15, Item 61).

Turns NHD ``NHDPoint`` features into classified :class:`PointFeature` value
objects. Classification is driven by the source **FType/FCode** codes (a
versioned policy table); the feature name is retained for provenance only and
is never the basis for a class. A feature whose FType is missing or unknown is
``excluded`` with a QA flag rather than guessed.

This mirrors :mod:`src.waterbodies` for point geometry: it performs no geometry
math and imports no GIS libraries, consuming the attribute dicts /
:class:`~src.loading.Layer` objects produced by the load seam so it runs fully
offline. Repair, reprojection, region-clipping, and density selection are left
to :mod:`src.areal_selection` (Item 62); every feature here is classified but
not yet selected.

FType codes are the real values confirmed against a live GDB (HUC4 1807); see
``agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.loading import Layer

__all__ = [
    "POINT_CLASSES",
    "POINT_FTYPE_CLASS",
    "POINT_FTYPE_LABELS",
    "POINT_POLICY_VERSION",
    "PointFeature",
    "classify_point_feature",
    "classify_point_layer",
]

#: Bumped whenever the classification policy table changes, so selection
#: reports and cached decisions remain auditable/reproducible.
POINT_POLICY_VERSION = "2026-09-01.1"

#: The normalized class vocabulary. ``excluded`` is a first-class outcome so
#: every candidate point is accounted for, not silently dropped. ``well`` and
#: ``sinkhole`` are represented in the FType table (labelled, so reports name
#: them) but map to ``excluded`` by default policy.
POINT_CLASSES: tuple[str, ...] = (
    "spring",
    "waterfall",
    "rapids",
    "excluded",
)

#: NHD FType code -> normalized class. In-scope natural point features map to a
#: named class; wells and sink/rises are listed explicitly (so they are
#: accounted for and named in reports) but map to ``excluded``. Every other
#: code — infrastructure (gaging station, gate, water intake), reservoir
#: points, rocks — is excluded by falling through to the default.
POINT_FTYPE_CLASS: dict[int, str] = {
    458: "spring",     # Spring/Seep
    487: "waterfall",  # Waterfall
    431: "rapids",     # Rapids
    488: "excluded",   # Well — classified-but-excluded
    450: "excluded",   # Sink/Rise — classified-but-excluded
}

#: Human-readable FType labels for selection reports (not used for logic).
#: Includes out-of-scope codes observed in real data so reports can name them.
POINT_FTYPE_LABELS: dict[int, str] = {
    458: "Spring/Seep",
    487: "Waterfall",
    431: "Rapids",
    488: "Well",
    450: "Sink/Rise",
    441: "Rock",
    367: "Gaging Station",
    369: "Gate",
    436: "Reservoir",
    485: "Water Intake/Outflow",
}


@dataclass(frozen=True)
class PointFeature:
    """A classified NHDPoint feature, with source provenance retained.

    Attributes:
        source_id: Stable per-feature source identifier
            (``Permanent_Identifier``/``ReachCode``), or ``""`` if absent.
        source_layer: Originating layer name (e.g. ``"NHDPoint"``).
        dataset_id: Owning dataset id (e.g. ``"nhdplus_hr"``).
        huc4: HUC4 code the feature was loaded under.
        geometry: The source shapely point (unmodified here).
        ftype: NHD FType code, or ``None`` if the source omitted it.
        fcode: NHD FCode code, or ``None`` if absent.
        name: GNIS name if present (human-readable only).
        pt_class: Normalized class (one of :data:`POINT_CLASSES`).
        source_crs: The feature's original CRS, or ``None`` if unknown.
        attributes: The retained source attribute subset.
        inclusion_reason: Human-readable explanation of the classification.
        qa_flags: Data-quality flags (e.g. ``("missing_ftype",)``).
    """

    source_id: str
    source_layer: str
    dataset_id: str
    huc4: str
    geometry: Any
    ftype: int | None
    fcode: int | None
    name: str | None
    pt_class: str
    source_crs: str | None = None
    attributes: dict = field(default_factory=dict)
    inclusion_reason: str = ""
    qa_flags: tuple[str, ...] = ()


def _lookup(attrs: dict, *keys: str) -> Any:
    """Case-insensitively return the first present, non-null attribute value."""
    lower = {str(k).lower(): v for k, v in attrs.items()}
    for key in keys:
        value = lower.get(key.lower())
        if value is not None:
            return value
    return None


def _as_int(value: Any) -> int | None:
    """Coerce a source code to ``int`` (NHD stores these as float/str), or None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def classify_point_feature(
    attributes: dict,
    *,
    source_layer: str,
    dataset_id: str,
    huc4: str,
    geometry: Any = None,
    source_crs: str | None = None,
) -> PointFeature:
    """Classify a single NHDPoint feature from its source attributes.

    The decision is keyed on FType (see :data:`POINT_FTYPE_CLASS`); the GNIS
    name is retained for provenance only and never determines a class. A feature
    whose FType is missing or unknown is classified ``excluded`` with a QA flag
    rather than guessed.
    """
    attrs = dict(attributes or {})
    ftype = _as_int(_lookup(attrs, "FType", "FTYPE", "ftype"))
    fcode = _as_int(_lookup(attrs, "FCode", "FCODE", "fcode"))
    name_raw = _lookup(attrs, "GNIS_Name", "gnis_name", "Name", "name")
    name = str(name_raw) if name_raw is not None else None
    source_id_raw = _lookup(
        attrs,
        "Permanent_Identifier",
        "permanent_identifier",
        "NHDPlusID",
        "nhdplusid",
        "ReachCode",
        "reachcode",
    )
    source_id = str(source_id_raw) if source_id_raw is not None else ""

    qa_flags: list[str] = []
    if ftype is None:
        qa_flags.append("missing_ftype")
        pt_class = "excluded"
        reason = "excluded: source FType missing; cannot classify by type/code"
    else:
        pt_class = POINT_FTYPE_CLASS.get(ftype, "excluded")
        label = POINT_FTYPE_LABELS.get(ftype, "unknown")
        if pt_class == "excluded":
            reason = (
                f"excluded: FType {ftype} ({label}) is not an included natural "
                f"point feature under policy {POINT_POLICY_VERSION}"
            )
        else:
            reason = f"classified as {pt_class}: FType {ftype} ({label})"

    return PointFeature(
        source_id=source_id,
        source_layer=source_layer,
        dataset_id=dataset_id,
        huc4=huc4,
        geometry=geometry,
        ftype=ftype,
        fcode=fcode,
        name=name,
        pt_class=pt_class,
        source_crs=source_crs,
        attributes=attrs,
        inclusion_reason=reason,
        qa_flags=tuple(qa_flags),
    )


def classify_point_layer(layer: Layer) -> list[PointFeature]:
    """Classify every geometry in a loaded NHDPoint :class:`~src.loading.Layer`.

    Pairs each geometry with its parallel attribute dict (falling back to an
    empty dict when attributes are absent) and returns one :class:`PointFeature`
    per source geometry, in source order.
    """
    attrs_seq = layer.attributes or ()
    features: list[PointFeature] = []
    for index, geometry in enumerate(layer.geometries):
        attrs = attrs_seq[index] if index < len(attrs_seq) else {}
        features.append(
            classify_point_feature(
                attrs,
                source_layer=layer.name,
                dataset_id=layer.dataset_id,
                huc4=layer.huc4,
                geometry=geometry,
                source_crs=layer.crs,
            )
        )
    return features
