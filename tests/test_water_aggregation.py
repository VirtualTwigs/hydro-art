"""Offline tests for water-facility aggregation and provenance queries.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``), Group 5.

Covers: no summing across measure types or quantity statuses, correct
period and geography filters, null quantity handling (retain unavailable
count), source-caveat/data-alert propagation, and correct state/county/HUC
grouping.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_aggregation import (
    AggregationResult,
    FacilitySummary,
    aggregate_measurements,
    apply_caveats,
    facility_detail,
)
from src.water_facility import (
    DataAlert,
    Facility,
    FacilityEvidence,
    WaterClaim,
    WaterFacilityError,
    WaterMeasurement,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
_EARLIER = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_MID = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

_FAC_ID_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
_FAC_ID_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
_FAC_ID_C = uuid.UUID("00000000-0000-0000-0000-000000000003")


def _measurement(
    *,
    facility_id: uuid.UUID = _FAC_ID_A,
    measure_type: str = "withdrawal",
    quantity_status: str = "measured",
    value: float | None = 100.0,
    canonical_value: float | None = 378.5,
    period_start: datetime = _EARLIER,
    period_end: datetime = _NOW,
    jurisdiction: str = "TX",
    geography_type: str = "state",
    geography_id: str = "TX",
) -> WaterMeasurement:
    return WaterMeasurement(
        id=uuid.uuid4(),
        facility_id=facility_id,
        measure_type=measure_type,
        quantity_status=quantity_status,
        value=value,
        source_unit="gal/day",
        canonical_value=canonical_value,
        canonical_unit="m3/day",
        conversion_method="multiply_3.78541",
        confidence=0.9,
        period_start=period_start,
        period_end=period_end,
        valid_time_start=_EARLIER,
        valid_time_end=_NOW,
        system_time=_NOW,
        source_record_id=uuid.uuid4(),
    )


def _facility(
    fac_id: uuid.UUID = _FAC_ID_A,
    jurisdiction: str = "TX",
) -> Facility:
    return Facility(
        id=fac_id,
        name="Test Facility",
        facility_class="drinking_water",
        jurisdiction=jurisdiction,
        status="active",
        water_relevance="confirmed",
        identity_confidence=0.95,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _evidence(fac_id: uuid.UUID = _FAC_ID_A) -> FacilityEvidence:
    return FacilityEvidence(
        id=uuid.uuid4(),
        facility_id=fac_id,
        source_url="https://example.gov/doc/123",
        file_key="snapshots/tx/2026/doc123.pdf",
        row_locator="row:42",
        publisher="Texas CEQ",
        publication_date=_EARLIER,
        retrieval_date=_NOW,
        review_status="reviewed",
        content_checksum="sha256:abc123",
    )


def _claim(fac_id: uuid.UUID = _FAC_ID_A) -> WaterClaim:
    return WaterClaim(
        id=uuid.uuid4(),
        facility_id=fac_id,
        subject="water_use",
        predicate="withdraws",
        value=1500.0,
        unit="m3/day",
        measure_type="withdrawal",
        quantity_status="measured",
        display_eligibility="publishable_precise",
        confidence=0.9,
        valid_time_start=_EARLIER,
        valid_time_end=_NOW,
        system_time=_NOW,
        reviewer=None,
        review_time=None,
        evidence_ids=(uuid.uuid4(),),
    )


def _alert(
    *,
    authority: str = "EPA",
    program: str = "SDWIS",
    geography: str | None = "TX",
    severity: str = "warning",
    message: str = "Data may be incomplete for Q3 2026",
) -> DataAlert:
    return DataAlert(
        id=uuid.uuid4(),
        authority=authority,
        program=program,
        geography=geography,
        severity=severity,
        message=message,
        source_url="https://epa.gov/alerts/123",
        effective_start=_EARLIER,
        effective_end=_NOW,
        superseded_by=None,
        created_at=_NOW,
    )


# ---------------------------------------------------------------------------
# 1. No summing across different measure types
# ---------------------------------------------------------------------------


def test_reject_mixed_measure_types():
    """aggregate_measurements rejects mixing withdrawal and discharged."""
    m1 = _measurement(measure_type="withdrawal")
    m2 = _measurement(measure_type="discharged")
    with pytest.raises(WaterFacilityError, match="measure_type"):
        aggregate_measurements(
            [m1, m2],
            measure_type="withdrawal",
            quantity_status="measured",
        )


# ---------------------------------------------------------------------------
# 2. No summing across different quantity statuses
# ---------------------------------------------------------------------------


def test_reject_mixed_quantity_statuses():
    """aggregate_measurements rejects mixing measured and authorized."""
    m1 = _measurement(quantity_status="measured")
    m2 = _measurement(quantity_status="authorized")
    with pytest.raises(WaterFacilityError, match="quantity_status"):
        aggregate_measurements(
            [m1, m2],
            measure_type="withdrawal",
            quantity_status="measured",
        )


# ---------------------------------------------------------------------------
# 3. Correct aggregation of matching measurements
# ---------------------------------------------------------------------------


def test_aggregate_sums_canonical_values():
    """Matching measurements are summed by canonical_value."""
    m1 = _measurement(facility_id=_FAC_ID_A, canonical_value=100.0)
    m2 = _measurement(facility_id=_FAC_ID_B, canonical_value=250.0)
    result = aggregate_measurements(
        [m1, m2],
        measure_type="withdrawal",
        quantity_status="measured",
    )
    assert isinstance(result, AggregationResult)
    assert result.total_value == pytest.approx(350.0)
    assert result.facility_count == 2
    assert result.measure_type == "withdrawal"
    assert result.quantity_status == "measured"


# ---------------------------------------------------------------------------
# 4. Null quantity handling — retain unavailable count, don't zero-fill
# ---------------------------------------------------------------------------


def test_null_quantity_counted_as_unavailable():
    """Measurements with value=None are counted as unavailable, not zero."""
    m1 = _measurement(canonical_value=100.0, facility_id=_FAC_ID_A)
    m2 = _measurement(
        canonical_value=None,
        value=None,
        facility_id=_FAC_ID_B,
    )
    result = aggregate_measurements(
        [m1, m2],
        measure_type="withdrawal",
        quantity_status="measured",
    )
    assert result.total_value == pytest.approx(100.0)
    assert result.facility_count == 2
    assert result.unavailable_count == 1


# ---------------------------------------------------------------------------
# 5. Period filter
# ---------------------------------------------------------------------------


def test_period_filter():
    """Only measurements within the requested period are included."""
    m_in = _measurement(
        period_start=_EARLIER,
        period_end=_MID,
        canonical_value=100.0,
    )
    m_out = _measurement(
        period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2025, 6, 1, tzinfo=timezone.utc),
        canonical_value=999.0,
    )
    result = aggregate_measurements(
        [m_in, m_out],
        measure_type="withdrawal",
        quantity_status="measured",
        period_start=_EARLIER,
        period_end=_NOW,
    )
    assert result.total_value == pytest.approx(100.0)
    assert result.facility_count == 1


# ---------------------------------------------------------------------------
# 6. Geography filter
# ---------------------------------------------------------------------------


def test_geography_filter():
    """geography_filter restricts by facility_id set."""
    m1 = _measurement(facility_id=_FAC_ID_A, canonical_value=100.0)
    m2 = _measurement(facility_id=_FAC_ID_B, canonical_value=200.0)
    result = aggregate_measurements(
        [m1, m2],
        measure_type="withdrawal",
        quantity_status="measured",
        geography_filter={_FAC_ID_A},
    )
    assert result.total_value == pytest.approx(100.0)
    assert result.facility_count == 1


# ---------------------------------------------------------------------------
# 7. Source-caveat / data-alert propagation
# ---------------------------------------------------------------------------


def test_apply_caveats_attaches_alerts():
    """apply_caveats attaches matching alerts to the result."""
    result = AggregationResult(
        jurisdiction="TX",
        geography_type="state",
        geography_id="TX",
        measure_type="withdrawal",
        quantity_status="measured",
        total_value=350.0,
        facility_count=2,
        unavailable_count=0,
        period_start=_EARLIER,
        period_end=_NOW,
        source_dates=[_NOW],
        caveats=[],
    )
    alert = _alert(geography="TX")
    updated = apply_caveats(result, [alert])
    assert len(updated.caveats) == 1
    assert updated.caveats[0].message == "Data may be incomplete for Q3 2026"


def test_apply_caveats_filters_irrelevant_alerts():
    """Alerts for a different geography are not attached."""
    result = AggregationResult(
        jurisdiction="TX",
        geography_type="state",
        geography_id="TX",
        measure_type="withdrawal",
        quantity_status="measured",
        total_value=100.0,
        facility_count=1,
        unavailable_count=0,
        period_start=_EARLIER,
        period_end=_NOW,
        source_dates=[_NOW],
        caveats=[],
    )
    alert = _alert(geography="VA")
    updated = apply_caveats(result, [alert])
    assert len(updated.caveats) == 0


# ---------------------------------------------------------------------------
# 8. facility_detail returns provenance-rich dict
# ---------------------------------------------------------------------------


def test_facility_detail_returns_provenance():
    """facility_detail returns a dict with facility, measurements, claims,
    and evidence."""
    fac = _facility()
    meas = [_measurement()]
    claims = [_claim()]
    evid = [_evidence()]
    detail = facility_detail(fac, meas, claims, evid)
    assert detail["facility_id"] == _FAC_ID_A
    assert detail["facility_name"] == "Test Facility"
    assert detail["jurisdiction"] == "TX"
    assert len(detail["measurements"]) == 1
    assert len(detail["claims"]) == 1
    assert len(detail["evidence"]) == 1


# ---------------------------------------------------------------------------
# 9. FacilitySummary frozen dataclass
# ---------------------------------------------------------------------------


def test_facility_summary_is_frozen():
    """FacilitySummary is a frozen dataclass."""
    summary = FacilitySummary(
        facility_id=_FAC_ID_A,
        facility_name="Test",
        jurisdiction="TX",
        measure_type="withdrawal",
        quantity_status="measured",
        total_value=100.0,
        measurement_count=1,
        unavailable_count=0,
        period_start=_EARLIER,
        period_end=_NOW,
    )
    with pytest.raises(AttributeError):
        summary.total_value = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 10. Empty input
# ---------------------------------------------------------------------------


def test_aggregate_empty_list():
    """Aggregating an empty measurement list returns zero totals."""
    result = aggregate_measurements(
        [],
        measure_type="withdrawal",
        quantity_status="measured",
    )
    assert result.total_value == 0.0
    assert result.facility_count == 0
    assert result.unavailable_count == 0
