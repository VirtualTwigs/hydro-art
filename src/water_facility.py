"""Water-facility and data-center intelligence domain model.

Pure, offline value objects, enum allowlists, validators, and repository
protocols for the Epoch 27 water-facility subsystem (#112-#119).

This module is **standalone**: no database driver, no GIS imports, no network
at module load time.  Nothing enters ``PIPELINE_STAGES``.  The PostGIS
adapter and source-snapshot tools live elsewhere and lazy-import their
dependencies.

See ``docs/water-facilities-database.md`` and
``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/spec.md``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

__all__ = [
    # Constants
    "DISPLAY_ELIGIBILITIES",
    "FACILITY_CLASSES",
    "MEASURE_TYPES",
    "QUANTITY_STATUSES",
    "WATER_RELEVANCE_LEVELS",
    "ACCESS_METHODS",
    # Error
    "WaterFacilityError",
    # Validators
    "validate_display_eligibility",
    "validate_facility_class",
    "validate_measure_type",
    "validate_quantity_status",
    "validate_water_relevance",
    # Entities
    "DataAlert",
    "Facility",
    "FacilityEvidence",
    "FacilityGeometry",
    "FacilityIdentifier",
    "FacilityRelationship",
    "ServiceArea",
    "SourceRecord",
    "SourceSnapshot",
    "StateSourceEntry",
    "WaterClaim",
    "WaterMeasurement",
    # Protocols
    "WaterFacilityRepository",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class WaterFacilityError(Exception):
    """Raised for invalid water-facility operations."""


# ---------------------------------------------------------------------------
# Closed enum sets
# ---------------------------------------------------------------------------

FACILITY_CLASSES: frozenset[str] = frozenset({
    "drinking_water",
    "wastewater",
    "industrial",
    "power_generation",
    "data_center",
    "agriculture",
    "mining",
    "dam",
    "other",
})

WATER_RELEVANCE_LEVELS: frozenset[str] = frozenset({
    "candidate",
    "permitted_or_committed",
    "confirmed",
    "unknown",
})

MEASURE_TYPES: frozenset[str] = frozenset({
    "withdrawal",
    "delivered",
    "consumed",
    "discharged",
    "authorized_capacity",
})

QUANTITY_STATUSES: frozenset[str] = frozenset({
    "measured",
    "reported",
    "authorized",
    "unavailable",
})

DISPLAY_ELIGIBILITIES: frozenset[str] = frozenset({
    "internal_only",
    "review_required",
    "publishable_precise",
    "publishable_generalized",
    "excluded",
})

ACCESS_METHODS: frozenset[str] = frozenset({
    "api",
    "bulk_file",
    "arcgis_service",
    "html_download",
    "manual_record_request",
})


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_facility_class(value: str) -> str:
    if value not in FACILITY_CLASSES:
        raise WaterFacilityError(
            f"Invalid facility_class {value!r}; allowed: {sorted(FACILITY_CLASSES)}"
        )
    return value


def validate_water_relevance(value: str) -> str:
    if value not in WATER_RELEVANCE_LEVELS:
        raise WaterFacilityError(
            f"Invalid water_relevance {value!r}; "
            f"allowed: {sorted(WATER_RELEVANCE_LEVELS)}"
        )
    return value


def validate_measure_type(value: str) -> str:
    if value not in MEASURE_TYPES:
        raise WaterFacilityError(
            f"Invalid measure_type {value!r}; allowed: {sorted(MEASURE_TYPES)}"
        )
    return value


def validate_quantity_status(value: str) -> str:
    if value not in QUANTITY_STATUSES:
        raise WaterFacilityError(
            f"Invalid quantity_status {value!r}; "
            f"allowed: {sorted(QUANTITY_STATUSES)}"
        )
    return value


def validate_display_eligibility(value: str) -> str:
    if value not in DISPLAY_ELIGIBILITIES:
        raise WaterFacilityError(
            f"Invalid display_eligibility {value!r}; "
            f"allowed: {sorted(DISPLAY_ELIGIBILITIES)}"
        )
    return value


def _validate_period(start: datetime | None, end: datetime | None,
                     label: str) -> None:
    if start is not None and end is not None and start > end:
        raise WaterFacilityError(
            f"Inverted {label}: start {start} > end {end}"
        )


# ---------------------------------------------------------------------------
# Entity dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Facility:
    """One real-world water facility site."""

    id: uuid.UUID
    name: str
    facility_class: str
    jurisdiction: str
    status: str
    water_relevance: str
    identity_confidence: float
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        validate_facility_class(self.facility_class)
        validate_water_relevance(self.water_relevance)


@dataclass(frozen=True)
class FacilityIdentifier:
    """One authority + external identifier for a facility."""

    id: uuid.UUID
    facility_id: uuid.UUID
    authority: str
    external_id: str
    source_record_id: uuid.UUID


@dataclass(frozen=True)
class FacilityGeometry:
    """Versioned point or polygon geometry with provenance."""

    id: uuid.UUID
    facility_id: uuid.UUID
    geometry_wkt: str
    crs: str
    method: str
    accuracy_m: float | None
    source_record_id: uuid.UUID
    valid_time_start: datetime
    valid_time_end: datetime | None = None


@dataclass(frozen=True)
class WaterMeasurement:
    """One quantity value for one period and measure type."""

    id: uuid.UUID
    facility_id: uuid.UUID
    measure_type: str
    quantity_status: str
    value: float | None
    source_unit: str
    canonical_value: float | None
    canonical_unit: str
    conversion_method: str
    confidence: float
    period_start: datetime
    period_end: datetime
    valid_time_start: datetime
    valid_time_end: datetime
    system_time: datetime
    source_record_id: uuid.UUID

    def __post_init__(self) -> None:
        validate_measure_type(self.measure_type)
        validate_quantity_status(self.quantity_status)
        _validate_period(self.period_start, self.period_end, "period")
        _validate_period(self.valid_time_start, self.valid_time_end,
                         "valid_time")


@dataclass(frozen=True)
class FacilityEvidence:
    """One source document or record backing a facility claim."""

    id: uuid.UUID
    facility_id: uuid.UUID
    source_url: str
    file_key: str
    row_locator: str
    publisher: str
    publication_date: datetime
    retrieval_date: datetime
    review_status: str
    content_checksum: str


@dataclass(frozen=True)
class WaterClaim:
    """One reviewed assertion extracted from evidence."""

    id: uuid.UUID
    facility_id: uuid.UUID
    subject: str
    predicate: str
    value: float | None
    unit: str
    measure_type: str
    quantity_status: str
    display_eligibility: str
    confidence: float
    valid_time_start: datetime
    valid_time_end: datetime
    system_time: datetime
    reviewer: str | None
    review_time: datetime | None
    evidence_ids: tuple[uuid.UUID, ...]

    def __post_init__(self) -> None:
        validate_measure_type(self.measure_type)
        validate_quantity_status(self.quantity_status)
        validate_display_eligibility(self.display_eligibility)
        _validate_period(self.valid_time_start, self.valid_time_end,
                         "valid_time")
        if not self.evidence_ids:
            raise WaterFacilityError(
                "A WaterClaim requires at least one evidence ID"
            )


@dataclass(frozen=True)
class FacilityRelationship:
    """Directed, evidence-backed relationship between facilities."""

    id: uuid.UUID
    source_facility_id: uuid.UUID
    target_facility_id: uuid.UUID
    relationship_type: str
    evidence_id: uuid.UUID
    valid_time_start: datetime
    valid_time_end: datetime | None = None


@dataclass(frozen=True)
class ServiceArea:
    """Versioned provider area geometry."""

    id: uuid.UUID
    facility_id: uuid.UUID
    geometry_wkt: str
    crs: str
    method: str  # "published" or "modeled"
    source_record_id: uuid.UUID
    valid_time_start: datetime
    valid_time_end: datetime | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    """Immutable retrieval provenance for one source download."""

    id: uuid.UUID
    source_family: str
    source_url: str
    retrieval_time: datetime
    content_checksum: str
    parser_version: str
    record_count: int


@dataclass(frozen=True)
class SourceRecord:
    """One row/record from a source snapshot."""

    id: uuid.UUID
    snapshot_id: uuid.UUID
    source_key: str
    content_checksum: str
    raw_payload: str


@dataclass(frozen=True)
class StateSourceEntry:
    """One versioned source configuration for a jurisdiction/program."""

    id: uuid.UUID
    jurisdiction: str
    program: str
    agency: str
    url: str
    access_method: str
    data_format: str
    coverage: str
    update_cadence: str
    license: str
    field_mapping_version: str
    geometry_quality: str
    publication_lag_days: int | None
    verified: bool
    last_verified: datetime | None

    def __post_init__(self) -> None:
        if self.access_method not in ACCESS_METHODS:
            raise WaterFacilityError(
                f"Invalid access_method {self.access_method!r}; "
                f"allowed: {sorted(ACCESS_METHODS)}"
            )


@dataclass(frozen=True)
class DataAlert:
    """Source-quality alert for an authority/program/geography/period."""

    id: uuid.UUID
    authority: str
    program: str
    geography: str | None
    severity: str
    message: str
    source_url: str
    effective_start: datetime
    effective_end: datetime | None
    superseded_by: uuid.UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Repository protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WaterFacilityRepository(Protocol):
    """Abstract repository for the water-facility subsystem."""

    def get_facility(self, facility_id: uuid.UUID) -> Facility | None: ...

    def list_facilities(
        self, *, jurisdiction: str | None = None,
        facility_class: str | None = None,
    ) -> list[Facility]: ...

    def save_facility(self, facility: Facility) -> None: ...

    def save_identifier(self, identifier: FacilityIdentifier) -> None: ...

    def save_measurement(self, measurement: WaterMeasurement) -> None: ...

    def save_evidence(self, evidence: FacilityEvidence) -> None: ...

    def save_claim(self, claim: WaterClaim) -> None: ...

    def save_snapshot(self, snapshot: SourceSnapshot) -> None: ...
