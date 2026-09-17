"""Areal natural-feature classification contract (Epoch 15, Item 62).

Turns NHD ``NHDWaterbody`` polygons into classified :class:`ArealFeature` value
objects for the *natural water feature* families that are NOT open water:
wetlands (Swamp/Marsh), playas, and perennial ice (glacier/snowfield). These
share the ``NHDWaterbody`` layer (and its existing load seam) with the Epoch 1.5
waterbodies, but form a COMPLEMENTARY taxonomy: :mod:`src.waterbodies` maps FType
466/361/378 to ``excluded``, so a polygon is classified by exactly one taxonomy,
never double-counted.

Classification is driven by the source **FType/FCode** codes (a versioned policy
table); the GNIS name is retained for provenance only and never determines a
class. A feature whose FType is missing or unknown is ``excluded`` with a QA flag
rather than guessed.

Like :mod:`src.waterbodies` and :mod:`src.point_features`, this module performs
no geometry math and imports no GIS libraries, consuming the attribute dicts /
:class:`~src.loading.Layer` objects produced by the load seam so it runs fully
offline. Repair, reprojection, region-clipping, and area-threshold selection are
left to :mod:`src.areal_selection`; every feature here is classified but not yet
selected.

FType codes are the real values confirmed against a live GDB (HUC4 1807); see
``agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.loading import Layer

__all__ = [
    "AREAL_CLASSES",
    "AREAL_FTYPE_CLASS",
    "AREAL_FTYPE_LABELS",
    "AREAL_POLICY_VERSION",
    "ArealFeature",
    "classify_areal_feature",
    "classify_areal_layer",
]

#: Bumped whenever the classification policy table changes, so selection
#: reports and cached decisions remain auditable/reproducible.
AREAL_POLICY_VERSION = "2026-09-01.1"

#: The normalized class vocabulary. ``excluded`` is a first-class outcome so
#: every candidate polygon is accounted for, not silently dropped.
AREAL_CLASSES: tuple[str, ...] = (
    "wetland",
    "playa",
    "perennial_ice",
    "excluded",
)

#: NHD FType code -> normalized class. Exactly the three ``NHDWaterbody`` FTypes
#: that :mod:`src.waterbodies` excludes, so the two taxonomies are complementary.
#: Every other code (open water, canal, stream area) falls through to the
#: default ``excluded``.
AREAL_FTYPE_CLASS: dict[int, str] = {
    466: "wetland",        # SwampMarsh
    361: "playa",          # Playa
    378: "perennial_ice",  # Ice Mass (glacier/snowfield)
}

#: Human-readable FType labels for selection reports (not used for logic).
AREAL_FTYPE_LABELS: dict[int, str] = {
    466: "SwampMarsh",
    361: "Playa",
    378: "IceMass",
}


@dataclass(frozen=True)
class ArealFeature:
    """A classified areal natural-water feature, with provenance retained.

    Attributes:
        source_id: Stable per-feature source identifier
            (``Permanent_Identifier``/``ReachCode``), or ``""`` if absent.
        source_layer: Originating layer name (e.g. ``"NHDWaterbody"``).
        dataset_id: Owning dataset id (e.g. ``"nhdplus_hr"``).
        huc4: HUC4 code the feature was loaded under.
        geometry: The source shapely polygon/multipolygon (unmodified here).
        ftype: NHD FType code, or ``None`` if the source omitted it.
        fcode: NHD FCode code, or ``None`` if absent.
        name: GNIS name if present (human-readable only).
        ar_class: Normalized class (one of :data:`AREAL_CLASSES`).
        source_crs: The feature's original CRS, or ``None`` if unknown.
        attributes: The retained source attribute subset.
        area_m2: Projected area in m² (EPSG:5070), or ``None`` until measured
            during selection.
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
    ar_class: str
    source_crs: str | None = None
    attributes: dict = field(default_factory=dict)
    area_m2: float | None = None
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


def classify_areal_feature(
    attributes: dict,
    *,
    source_layer: str,
    dataset_id: str,
    huc4: str,
    geometry: Any = None,
    source_crs: str | None = None,
) -> ArealFeature:
    """Classify a single areal natural-water feature from its source attributes.

    The decision is keyed on FType (see :data:`AREAL_FTYPE_CLASS`); the GNIS name
    is retained for provenance only and never determines a class. A feature whose
    FType is missing or unknown is classified ``excluded`` with a QA flag rather
    than guessed.
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
        ar_class = "excluded"
        reason = "excluded: source FType missing; cannot classify by type/code"
    else:
        ar_class = AREAL_FTYPE_CLASS.get(ftype, "excluded")
        label = AREAL_FTYPE_LABELS.get(ftype, "unknown")
        if ar_class == "excluded":
            reason = (
                f"excluded: FType {ftype} ({label}) is not an included areal "
                f"natural feature under policy {AREAL_POLICY_VERSION}"
            )
        else:
            reason = f"classified as {ar_class}: FType {ftype} ({label})"

    return ArealFeature(
        source_id=source_id,
        source_layer=source_layer,
        dataset_id=dataset_id,
        huc4=huc4,
        geometry=geometry,
        ftype=ftype,
        fcode=fcode,
        name=name,
        ar_class=ar_class,
        source_crs=source_crs,
        attributes=attrs,
        inclusion_reason=reason,
        qa_flags=tuple(qa_flags),
    )


def classify_areal_layer(layer: Layer) -> list[ArealFeature]:
    """Classify every geometry in a loaded ``NHDWaterbody`` :class:`~src.loading.Layer`.

    Pairs each geometry with its parallel attribute dict (falling back to an
    empty dict when attributes are absent) and returns one :class:`ArealFeature`
    per source geometry, in source order.
    """
    attrs_seq = layer.attributes or ()
    features: list[ArealFeature] = []
    for index, geometry in enumerate(layer.geometries):
        attrs = attrs_seq[index] if index < len(attrs_seq) else {}
        features.append(
            classify_areal_feature(
                attrs,
                source_layer=layer.name,
                dataset_id=layer.dataset_id,
                huc4=layer.huc4,
                geometry=geometry,
                source_crs=layer.crs,
            )
        )
    return features
