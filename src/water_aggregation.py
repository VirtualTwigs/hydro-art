"""Water-facility aggregation and provenance query helpers.

Pure, offline module for summing water measurements by type/status,
filtering by period and geography, propagating data-alert caveats,
and producing per-facility provenance detail.

No database driver, no GIS imports, no network at module load time.
Nothing enters ``PIPELINE_STAGES``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from src.water_facility import (
    DataAlert,
    Facility,
    FacilityEvidence,
    WaterClaim,
    WaterFacilityError,
    WaterMeasurement,
)

__all__ = [
    "AggregationResult",
    "FacilitySummary",
    "aggregate_measurements",
    "apply_caveats",
    "facility_detail",
]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AggregationResult:
    """Aggregated measurement summary for a jurisdiction/geography."""

    jurisdiction: str | None
    geography_type: str | None
    geography_id: str | None
    measure_type: str
    quantity_status: str
    total_value: float
    facility_count: int
    unavailable_count: int
    period_start: datetime | None
    period_end: datetime | None
    source_dates: list[datetime] = field(default_factory=list)
    caveats: list[DataAlert] = field(default_factory=list)


@dataclass(frozen=True)
class FacilitySummary:
    """Per-facility measurement rollup."""

    facility_id: uuid.UUID
    facility_name: str
    jurisdiction: str
    measure_type: str
    quantity_status: str
    total_value: float
    measurement_count: int
    unavailable_count: int
    period_start: datetime | None
    period_end: datetime | None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_measurements(
    measurements: Sequence[WaterMeasurement],
    *,
    measure_type: str,
    quantity_status: str,
    geography_filter: set[uuid.UUID] | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> AggregationResult:
    """Sum measurements matching *measure_type* and *quantity_status*.

    Raises :class:`WaterFacilityError` if any measurement in the input
    has a different ``measure_type`` or ``quantity_status`` than requested
    (prevents accidental cross-type summation).

    Parameters
    ----------
    measurements:
        Sequence of :class:`WaterMeasurement` to aggregate.
    measure_type:
        Required measure type (e.g. ``"withdrawal"``).
    quantity_status:
        Required quantity status (e.g. ``"measured"``).
    geography_filter:
        If provided, only include measurements whose ``facility_id``
        is in this set.
    period_start / period_end:
        If provided, only include measurements whose period overlaps
        this window.
    """
    # Validate that all measurements match the requested type/status
    for m in measurements:
        if m.measure_type != measure_type:
            raise WaterFacilityError(
                f"Cannot aggregate across measure_type values: "
                f"expected {measure_type!r}, got {m.measure_type!r}"
            )
        if m.quantity_status != quantity_status:
            raise WaterFacilityError(
                f"Cannot aggregate across quantity_status values: "
                f"expected {quantity_status!r}, got {m.quantity_status!r}"
            )

    # Filter by geography and period
    filtered: list[WaterMeasurement] = []
    for m in measurements:
        if geography_filter is not None and m.facility_id not in geography_filter:
            continue
        if period_start is not None and m.period_end < period_start:
            continue
        if period_end is not None and m.period_start > period_end:
            continue
        filtered.append(m)

    # Sum canonical values; track nulls
    total = 0.0
    unavailable = 0
    facility_ids: set[uuid.UUID] = set()
    source_dates: list[datetime] = []

    for m in filtered:
        facility_ids.add(m.facility_id)
        source_dates.append(m.system_time)
        if m.canonical_value is None:
            unavailable += 1
        else:
            total += m.canonical_value

    return AggregationResult(
        jurisdiction=None,
        geography_type=None,
        geography_id=None,
        measure_type=measure_type,
        quantity_status=quantity_status,
        total_value=total,
        facility_count=len(facility_ids),
        unavailable_count=unavailable,
        period_start=period_start,
        period_end=period_end,
        source_dates=source_dates,
        caveats=[],
    )


# ---------------------------------------------------------------------------
# Caveat application
# ---------------------------------------------------------------------------


def apply_caveats(
    result: AggregationResult,
    alerts: Sequence[DataAlert],
) -> AggregationResult:
    """Return a new result with applicable data alerts attached.

    An alert is applicable when its ``geography`` matches the result's
    ``jurisdiction`` or ``geography_id``, or when the alert has no
    geography constraint (``geography is None``).
    """
    applicable: list[DataAlert] = []
    for alert in alerts:
        if alert.geography is None:
            applicable.append(alert)
        elif (
            alert.geography == result.jurisdiction
            or alert.geography == result.geography_id
        ):
            applicable.append(alert)

    # Build a new frozen instance with updated caveats
    return AggregationResult(
        jurisdiction=result.jurisdiction,
        geography_type=result.geography_type,
        geography_id=result.geography_id,
        measure_type=result.measure_type,
        quantity_status=result.quantity_status,
        total_value=result.total_value,
        facility_count=result.facility_count,
        unavailable_count=result.unavailable_count,
        period_start=result.period_start,
        period_end=result.period_end,
        source_dates=result.source_dates,
        caveats=list(result.caveats) + applicable,
    )


# ---------------------------------------------------------------------------
# Facility detail (provenance-rich)
# ---------------------------------------------------------------------------


def facility_detail(
    facility: Facility,
    measurements: Sequence[WaterMeasurement],
    claims: Sequence[WaterClaim],
    evidence: Sequence[FacilityEvidence],
) -> dict:
    """Return a provenance-rich detail dict for a single facility.

    The returned dict contains the facility identity, all associated
    measurements, claims, and evidence records — suitable for rendering
    a facility detail page or report section.
    """
    return {
        "facility_id": facility.id,
        "facility_name": facility.name,
        "facility_class": facility.facility_class,
        "jurisdiction": facility.jurisdiction,
        "status": facility.status,
        "water_relevance": facility.water_relevance,
        "identity_confidence": facility.identity_confidence,
        "measurements": [
            {
                "id": m.id,
                "measure_type": m.measure_type,
                "quantity_status": m.quantity_status,
                "value": m.value,
                "source_unit": m.source_unit,
                "canonical_value": m.canonical_value,
                "canonical_unit": m.canonical_unit,
                "period_start": m.period_start,
                "period_end": m.period_end,
                "confidence": m.confidence,
            }
            for m in measurements
        ],
        "claims": [
            {
                "id": c.id,
                "subject": c.subject,
                "predicate": c.predicate,
                "value": c.value,
                "unit": c.unit,
                "measure_type": c.measure_type,
                "quantity_status": c.quantity_status,
                "display_eligibility": c.display_eligibility,
                "confidence": c.confidence,
                "evidence_ids": list(c.evidence_ids),
            }
            for c in claims
        ],
        "evidence": [
            {
                "id": e.id,
                "source_url": e.source_url,
                "publisher": e.publisher,
                "publication_date": e.publication_date,
                "review_status": e.review_status,
            }
            for e in evidence
        ],
    }
