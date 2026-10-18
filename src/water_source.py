"""National water-source normalization into the water-facility contract.

Pure, offline normalizers that turn raw source-family rows (FRS, SDWIS,
NPDES, DMR, CWNS, NID, USGS) into a common intermediate representation
(``NormalizedFacility``, ``NormalizedMeasurement``, ``SourceContext``)
retaining every raw source key and value.

Key invariants enforced here:
- NPDES/DMR discharge data remains ``discharged``, never ``withdrawal``.
- USGS county/state water-use and CWNS service-area data are ``SourceContext``
  — geographic context that cannot create a facility-level measurement.
- Same input + parser version produces identical output (idempotent).

No database driver, no GIS, no network at module load.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "NormalizedFacility",
    "NormalizedMeasurement",
    "SourceContext",
    "normalize_cwns",
    "normalize_dmr",
    "normalize_frs",
    "normalize_nid",
    "normalize_npdes",
    "normalize_sdwis",
    "normalize_usgs_water_use",
]


# ---------------------------------------------------------------------------
# Intermediate value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedFacility:
    """A facility record normalized from one source family."""

    source_family: str
    source_key: str
    snapshot_id: uuid.UUID
    name: str
    facility_class: str
    jurisdiction: str
    latitude: float | None = None
    longitude: float | None = None
    authority: str = ""
    external_id: str = ""
    authorized_capacity_mgd: float | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedMeasurement:
    """A water measurement normalized from a source record."""

    source_family: str
    facility_source_key: str
    snapshot_id: uuid.UUID
    measure_type: str
    quantity_status: str
    value: float | None
    source_unit: str
    period_end: str | None = None
    parameter_code: str | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceContext:
    """Aggregate or geographic context — cannot create facility measurements."""

    source_family: str
    context_type: str
    snapshot_id: uuid.UUID
    jurisdiction: str
    raw_fields: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FRS (EPA Facility Registry Service)
# ---------------------------------------------------------------------------


def normalize_frs(row: dict[str, Any], *, snapshot_id: uuid.UUID) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="FRS",
        source_key=str(row["REGISTRY_ID"]),
        snapshot_id=snapshot_id,
        name=row["PRIMARY_NAME"],
        facility_class=_frs_classify(row),
        jurisdiction=row["STATE_CODE"],
        latitude=row.get("LATITUDE83"),
        longitude=row.get("LONGITUDE83"),
        authority="EPA_FRS",
        external_id=str(row["REGISTRY_ID"]),
        raw_fields=dict(row),
    )


def _frs_classify(row: dict[str, Any]) -> str:
    naics = str(row.get("NAICS_CODES", ""))
    if naics.startswith("2213"):
        return "wastewater"
    if naics.startswith("2211"):
        return "drinking_water"
    if naics.startswith("5182"):
        return "data_center"
    return "other"


# ---------------------------------------------------------------------------
# SDWIS (Safe Drinking Water Information System)
# ---------------------------------------------------------------------------


def normalize_sdwis(row: dict[str, Any], *, snapshot_id: uuid.UUID) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="SDWIS",
        source_key=str(row["PWSID"]),
        snapshot_id=snapshot_id,
        name=row["PWS_NAME"],
        facility_class="drinking_water",
        jurisdiction=row["STATE_CODE"],
        authority="EPA_SDWIS",
        external_id=str(row["PWSID"]),
        raw_fields=dict(row),
    )


# ---------------------------------------------------------------------------
# NPDES (National Pollutant Discharge Elimination System)
# ---------------------------------------------------------------------------


def normalize_npdes(row: dict[str, Any], *, snapshot_id: uuid.UUID) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="NPDES",
        source_key=str(row["NPDES_ID"]),
        snapshot_id=snapshot_id,
        name=row["FACILITY_NAME"],
        facility_class=_npdes_classify(row),
        jurisdiction=row["STATE_CODE"],
        latitude=row.get("LATITUDE"),
        longitude=row.get("LONGITUDE"),
        authority="EPA_NPDES",
        external_id=str(row["NPDES_ID"]),
        raw_fields=dict(row),
    )


def _npdes_classify(row: dict[str, Any]) -> str:
    ftype = str(row.get("FACILITY_TYPE_INDICATOR", ""))
    if ftype == "POTW":
        return "wastewater"
    sic = str(row.get("SIC_CODES", ""))
    if sic.startswith("4952"):
        return "wastewater"
    if sic.startswith("4911"):
        return "power_generation"
    return "industrial"


# ---------------------------------------------------------------------------
# DMR (Discharge Monitoring Reports) — discharge, NEVER withdrawal
# ---------------------------------------------------------------------------


def normalize_dmr(
    row: dict[str, Any],
    *,
    facility_source_key: str,
    snapshot_id: uuid.UUID,
) -> NormalizedMeasurement:
    return NormalizedMeasurement(
        source_family="DMR",
        facility_source_key=facility_source_key,
        snapshot_id=snapshot_id,
        measure_type="discharged",  # INVARIANT: never "withdrawal"
        quantity_status="reported",
        value=row.get("DMR_VALUE_STANDARD_UNITS"),
        source_unit=row.get("STANDARD_UNIT_DESC", ""),
        period_end=row.get("MONITORING_PERIOD_END_DATE"),
        parameter_code=row.get("PARAMETER_CODE"),
        raw_fields=dict(row),
    )


# ---------------------------------------------------------------------------
# CWNS (Clean Watersheds Needs Survey)
# ---------------------------------------------------------------------------


def normalize_cwns(row: dict[str, Any], *, snapshot_id: uuid.UUID) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="CWNS",
        source_key=str(row["CWNS_NUMBER"]),
        snapshot_id=snapshot_id,
        name=row["FACILITY_NAME"],
        facility_class="wastewater",
        jurisdiction=row["STATE_CODE"],
        latitude=row.get("LATITUDE"),
        longitude=row.get("LONGITUDE"),
        authority="EPA_CWNS",
        external_id=str(row["CWNS_NUMBER"]),
        authorized_capacity_mgd=row.get("DESIGN_FLOW_MGD"),
        raw_fields=dict(row),
    )


# ---------------------------------------------------------------------------
# NID (National Inventory of Dams)
# ---------------------------------------------------------------------------


def normalize_nid(row: dict[str, Any], *, snapshot_id: uuid.UUID) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="NID",
        source_key=str(row["NID_ID"]),
        snapshot_id=snapshot_id,
        name=row["DAM_NAME"],
        facility_class="dam",
        jurisdiction=row["STATE"],
        latitude=row.get("LATITUDE"),
        longitude=row.get("LONGITUDE"),
        authority="USACE_NID",
        external_id=str(row["NID_ID"]),
        raw_fields=dict(row),
    )


# ---------------------------------------------------------------------------
# USGS water-use context — aggregate only, NOT facility-level
# ---------------------------------------------------------------------------


def normalize_usgs_water_use(
    row: dict[str, Any], *, snapshot_id: uuid.UUID
) -> SourceContext:
    return SourceContext(
        source_family="USGS",
        context_type="county_water_use",
        snapshot_id=snapshot_id,
        jurisdiction=row["state_cd"],
        raw_fields=dict(row),
    )
