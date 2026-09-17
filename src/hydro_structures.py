"""Engineered-water structure classification contract (Epoch 16, Item 65).

Turns NHD engineered-water infrastructure features — dams/weirs, gates, lock
chambers, spillways, gaging stations, water intakes/outflows, and canals/ditches
— into classified :class:`HydroStructure` value objects. These structures arrive
across THREE source layers (``NHDLine``, ``NHDPoint``, ``NHDArea``) but a single
FType code carries the same meaning on every layer, so one policy table serves
all three (e.g. ``343`` DamWeir is a dam/weir whether it comes in as a line or an
area). This is a COMPLEMENTARY taxonomy to :mod:`src.waterbodies`,
:mod:`src.point_features`, and :mod:`src.areal_features`: the included FType codes
here are disjoint from the included codes there, so each NHD feature is owned by
exactly one taxonomy and never double-classified.

Classification is driven by the source **FType/FCode** codes (a versioned policy
table); the GNIS name is retained for provenance only and never determines a
class. A feature whose FType is missing or unknown is ``excluded`` with a QA flag
rather than guessed.

Like the sibling taxonomies, this module performs no geometry math and imports no
GIS libraries, consuming the attribute dicts / :class:`~src.loading.Layer`
objects produced by the load seam so it runs fully offline. Repair, reprojection,
region-clipping, and selection/rendering are left to a later item (#67); every
feature here is classified but not yet selected.

**Reservoir stays with waterbodies:** ``436 Reservoir`` is intentionally NOT in
this table — :mod:`src.waterbodies` owns it (a reservoir is a body of water, not
an engineered line/point structure). Keeping 436 out preserves the
non-overlapping invariant.

FType codes were domain-verified against a live GDB (HUC4 1807) — decode the
embedded ``NHDFCode`` domain table, not memory; see
``agent-os/specs/2026-09-03-hydro-structure-taxonomy/planning/group0-findings.md``.
Confirmed present in 1807: ``343`` DamWeir (NHDLine+NHDArea), ``336`` CanalDitch,
``455`` Spillway, ``485`` Water Intake/Outflow (NHDArea), ``367`` Gaging Station,
``369`` Gate (NHDPoint, Epoch 15).

**UNCONFIRMED:** ``398`` LockChamber is absent from NHDLine/NHDArea/NHDPoint in
1807 (a coastal HUC4 with no navigation locks); the ``398 -> lock_chamber``
mapping uses the standard NHD code and awaits confirmation against a lock-bearing
HUC4. ``369`` Gate is confirmed on NHDPoint but untested against real line/area
geometry. The classification RULE is fixed regardless of which literal codes
appear in any given HUC4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.loading import Layer

__all__ = [
    "HYDRO_STRUCTURE_CLASSES",
    "HYDRO_STRUCTURE_FTYPE_CLASS",
    "HYDRO_STRUCTURE_FTYPE_LABELS",
    "HYDRO_STRUCTURE_POLICY_VERSION",
    "HydroStructure",
    "classify_hydro_structure",
    "classify_hydro_structure_layer",
]

#: Bumped whenever the classification policy table changes, so selection reports
#: and cached decisions remain auditable/reproducible.
HYDRO_STRUCTURE_POLICY_VERSION = "2026-09-03.1"

#: The normalized class vocabulary. ``excluded`` is a first-class outcome so every
#: candidate feature is accounted for, not silently dropped.
HYDRO_STRUCTURE_CLASSES: tuple[str, ...] = (
    "dam_weir",
    "gate",
    "lock_chamber",
    "gaging_station",
    "water_intake_outflow",
    "spillway",
    "canal_ditch",
    "excluded",
)

#: NHD FType code -> normalized structure class. One code carries the same meaning
#: across ``NHDLine``/``NHDPoint``/``NHDArea``, so this single table serves all
#: three source layers. Every other code (open water, natural features, non-water
#: line types) falls through to the default ``excluded``. ``436 Reservoir`` is
#: intentionally absent (waterbodies owns it). ``398`` is UNCONFIRMED (see module
#: docstring).
HYDRO_STRUCTURE_FTYPE_CLASS: dict[int, str] = {
    343: "dam_weir",              # DamWeir (NHDLine + NHDArea, confirmed 1807)
    369: "gate",                  # Gate (NHDPoint confirmed; line/area untested)
    398: "lock_chamber",          # LockChamber (UNCONFIRMED — absent from 1807)
    367: "gaging_station",        # Gaging Station (NHDPoint, confirmed Epoch 15)
    485: "water_intake_outflow",  # Water Intake/Outflow (NHDArea+NHDPoint)
    455: "spillway",              # Spillway (NHDArea, confirmed 1807)
    336: "canal_ditch",           # CanalDitch (NHDArea, confirmed 1807)
}

#: Human-readable FType labels for selection reports (not used for logic).
#: Includes out-of-scope codes observed in real data so reports can name them.
HYDRO_STRUCTURE_FTYPE_LABELS: dict[int, str] = {
    343: "DamWeir",
    369: "Gate",
    398: "LockChamber",
    367: "Gaging Station",
    485: "Water Intake/Outflow",
    455: "Spillway",
    336: "CanalDitch",
    436: "Reservoir",  # owned by waterbodies; labelled so reports can name it
}


@dataclass(frozen=True)
class HydroStructure:
    """A classified engineered-water structure, with source provenance retained.

    Attributes:
        source_id: Stable per-feature source identifier
            (``Permanent_Identifier``/``ReachCode``), or ``""`` if absent.
        source_layer: Originating layer name (``"NHDLine"``/``"NHDPoint"``/
            ``"NHDArea"``).
        dataset_id: Owning dataset id (e.g. ``"nhdplus_hr"``).
        huc4: HUC4 code the feature was loaded under.
        geometry: The source shapely geometry (unmodified here).
        ftype: NHD FType code, or ``None`` if the source omitted it.
        fcode: NHD FCode code, or ``None`` if absent.
        name: GNIS name if present (human-readable only).
        struct_class: Normalized class (one of :data:`HYDRO_STRUCTURE_CLASSES`).
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
    struct_class: str
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


def classify_hydro_structure(
    attributes: dict,
    *,
    source_layer: str,
    dataset_id: str,
    huc4: str,
    geometry: Any = None,
    source_crs: str | None = None,
) -> HydroStructure:
    """Classify a single engineered-water structure from its source attributes.

    The decision is keyed on FType (see :data:`HYDRO_STRUCTURE_FTYPE_CLASS`); the
    GNIS name is retained for provenance only and never determines a class. A
    feature whose FType is missing or unknown is classified ``excluded`` with a QA
    flag rather than guessed.
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
        struct_class = "excluded"
        reason = "excluded: source FType missing; cannot classify by type/code"
    else:
        struct_class = HYDRO_STRUCTURE_FTYPE_CLASS.get(ftype, "excluded")
        label = HYDRO_STRUCTURE_FTYPE_LABELS.get(ftype, "unknown")
        if struct_class == "excluded":
            reason = (
                f"excluded: FType {ftype} ({label}) is not an included hydro "
                f"structure under policy {HYDRO_STRUCTURE_POLICY_VERSION}"
            )
        else:
            reason = f"classified as {struct_class}: FType {ftype} ({label})"

    return HydroStructure(
        source_id=source_id,
        source_layer=source_layer,
        dataset_id=dataset_id,
        huc4=huc4,
        geometry=geometry,
        ftype=ftype,
        fcode=fcode,
        name=name,
        struct_class=struct_class,
        source_crs=source_crs,
        attributes=attrs,
        inclusion_reason=reason,
        qa_flags=tuple(qa_flags),
    )


def classify_hydro_structure_layer(layer: Layer) -> list[HydroStructure]:
    """Classify every geometry in a loaded structure :class:`~src.loading.Layer`.

    Works uniformly across ``NHDLine``/``NHDPoint``/``NHDArea`` layers. Pairs each
    geometry with its parallel attribute dict (falling back to an empty dict when
    attributes are absent) and returns one :class:`HydroStructure` per source
    geometry, in source order.
    """
    attrs_seq = layer.attributes or ()
    features: list[HydroStructure] = []
    for index, geometry in enumerate(layer.geometries):
        attrs = attrs_seq[index] if index < len(attrs_seq) else {}
        features.append(
            classify_hydro_structure(
                attrs,
                source_layer=layer.name,
                dataset_id=layer.dataset_id,
                huc4=layer.huc4,
                geometry=geometry,
                source_crs=layer.crs,
            )
        )
    return features
