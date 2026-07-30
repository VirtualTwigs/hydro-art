"""Areal-water classification contract (Item W1, Task Group 1).

Turns NHD waterbody/area polygons into classified :class:`WaterbodyFeature`
value objects. Classification is driven by the source **FType/FCode** codes
(a versioned policy table), with the feature name used only as *secondary*
evidence to split otherwise-ambiguous codes (e.g. bay vs. inlet) — never as
the sole basis for a class, per the spec.

This module performs no geometry math and imports no GIS libraries: it consumes
the attribute dicts / :class:`~src.loading.Layer` objects produced by the load
seam, so it runs fully offline. Repair, reprojection, area measurement, and
threshold-based selection are deliberately left to later phases (W2); every
feature here is classified but not yet selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.loading import Layer

__all__ = [
    "WATERBODY_POLICY_VERSION",
    "WATERBODY_CLASSES",
    "FTYPE_CLASS",
    "FTYPE_LABELS",
    "WaterbodyFeature",
    "classify_waterbody",
    "classify_layer",
]

#: Bumped whenever the classification policy table changes, so selection
#: reports and cached decisions remain auditable/reproducible.
WATERBODY_POLICY_VERSION = "2026-07-29.1"

#: The normalized class vocabulary (spec taxonomy). ``excluded`` is a first-
#: class outcome so every candidate feature is accounted for, not silently
#: dropped.
WATERBODY_CLASSES: tuple[str, ...] = (
    "lake",
    "pond",
    "reservoir",
    "bay",
    "inlet",
    "coastal",
    "excluded",
)

#: NHD FType code -> base normalized class. The lake/pond split is an
#: area-based refinement handled in W2 (LakePond has a single FType); the
#: bay/inlet split is refined by name below. Codes absent from this table are
#: excluded. Open ocean (SeaOcean) and river/wetland/canal area types are
#: explicitly excluded under the conservative coast policy.
FTYPE_CLASS: dict[int, str] = {
    390: "lake",       # LakePond (area may refine to pond in W2)
    436: "reservoir",  # Reservoir
    493: "coastal",    # Estuary
    312: "bay",        # BayInlet (name may refine to inlet)
    445: "excluded",   # SeaOcean — open ocean, conservative coast policy
    460: "excluded",   # StreamRiver (areal) — rendered as flowlines instead
    466: "excluded",   # SwampMarsh — wetland, not open water
    361: "excluded",   # Playa
    378: "excluded",   # Ice Mass
    336: "excluded",   # CanalDitch
}

#: Human-readable FType labels for selection reports (not used for logic).
FTYPE_LABELS: dict[int, str] = {
    390: "LakePond",
    436: "Reservoir",
    493: "Estuary",
    312: "BayInlet",
    445: "SeaOcean",
    460: "StreamRiver",
    466: "SwampMarsh",
    361: "Playa",
    378: "IceMass",
    336: "CanalDitch",
}


@dataclass(frozen=True)
class WaterbodyFeature:
    """A classified areal-water feature, with source provenance retained.

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
        wb_class: Normalized class (one of :data:`WATERBODY_CLASSES`).
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
    wb_class: str
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


def classify_waterbody(
    attributes: dict,
    *,
    source_layer: str,
    dataset_id: str,
    huc4: str,
    geometry: Any = None,
    source_crs: str | None = None,
) -> WaterbodyFeature:
    """Classify a single areal-water feature from its source attributes.

    The decision is keyed on FType (see :data:`FTYPE_CLASS`); the GNIS name may
    only refine an already-coastal ``bay`` code into ``bay`` vs. ``inlet``. A
    feature whose FType is missing or unknown is classified ``excluded`` with a
    QA flag rather than guessed.
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
        wb_class = "excluded"
        reason = "excluded: source FType missing; cannot classify by type/code"
    else:
        wb_class = FTYPE_CLASS.get(ftype, "excluded")
        label = FTYPE_LABELS.get(ftype, "unknown")
        if wb_class == "bay" and name:
            low = name.lower()
            if "inlet" in low:
                wb_class = "inlet"
            elif "bay" in low:
                wb_class = "bay"
        if wb_class == "excluded":
            reason = (
                f"excluded: FType {ftype} ({label}) is not an included water "
                f"class under policy {WATERBODY_POLICY_VERSION}"
            )
        else:
            reason = f"classified as {wb_class}: FType {ftype} ({label})"

    return WaterbodyFeature(
        source_id=source_id,
        source_layer=source_layer,
        dataset_id=dataset_id,
        huc4=huc4,
        geometry=geometry,
        ftype=ftype,
        fcode=fcode,
        name=name,
        wb_class=wb_class,
        source_crs=source_crs,
        attributes=attrs,
        inclusion_reason=reason,
        qa_flags=tuple(qa_flags),
    )


def classify_layer(layer: Layer) -> list[WaterbodyFeature]:
    """Classify every geometry in a loaded waterbody :class:`~src.loading.Layer`.

    Pairs each geometry with its parallel attribute dict (falling back to an
    empty dict when attributes are absent) and returns one
    :class:`WaterbodyFeature` per source geometry, in source order.
    """
    attrs_seq = layer.attributes or ()
    features: list[WaterbodyFeature] = []
    for index, geometry in enumerate(layer.geometries):
        attrs = attrs_seq[index] if index < len(attrs_seq) else {}
        features.append(
            classify_waterbody(
                attrs,
                source_layer=layer.name,
                dataset_id=layer.dataset_id,
                huc4=layer.huc4,
                geometry=geometry,
                source_crs=layer.crs,
            )
        )
    return features
