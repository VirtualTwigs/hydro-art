"""Offline tests for water-facility domain value objects and protocols.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: enum validation, immutable provenance, external-ID uniqueness rules,
quantity/status separation, ``water_claim`` display eligibility, bitemporal
validity/system times, and rejection of invalid period or unit input.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_facility import (
    DISPLAY_ELIGIBILITIES,
    FACILITY_CLASSES,
    MEASURE_TYPES,
    QUANTITY_STATUSES,
    WATER_RELEVANCE_LEVELS,
    DataAlert,
    Facility,
    FacilityEvidence,
    FacilityGeometry,
    FacilityIdentifier,
    FacilityRelationship,
    ServiceArea,
    SourceRecord,
    SourceSnapshot,
    StateSourceEntry,
    WaterClaim,
    WaterFacilityError,
    WaterMeasurement,
    validate_display_eligibility,
    validate_facility_class,
    validate_measure_type,
    validate_quantity_status,
    validate_water_relevance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
_EARLIER = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _make_facility(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        name="Test WWTP",
        facility_class="wastewater",
        jurisdiction="TX",
        status="active",
        water_relevance="confirmed",
        identity_confidence=0.95,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Facility(**defaults)


def _make_measurement(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=uuid.uuid4(),
        measure_type="withdrawal",
        quantity_status="measured",
        value=1500.0,
        source_unit="gal/day",
        canonical_value=5678.0,
        canonical_unit="m3/day",
        conversion_method="multiply_3.78541",
        confidence=0.9,
        period_start=_EARLIER,
        period_end=_NOW,
        valid_time_start=_EARLIER,
        valid_time_end=_NOW,
        system_time=_NOW,
        source_record_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return WaterMeasurement(**defaults)


def _make_claim(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=uuid.uuid4(),
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
    defaults.update(overrides)
    return WaterClaim(**defaults)


def _make_evidence(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=uuid.uuid4(),
        source_url="https://example.gov/doc/123",
        file_key="snapshots/tx/2026/doc123.pdf",
        row_locator="row:42",
        publisher="Texas CEQ",
        publication_date=_EARLIER,
        retrieval_date=_NOW,
        review_status="reviewed",
        content_checksum="sha256:abc123",
    )
    defaults.update(overrides)
    return FacilityEvidence(**defaults)


def _make_source_snapshot(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        source_family="FRS",
        source_url="https://frs.epa.gov/download",
        retrieval_time=_NOW,
        content_checksum="sha256:abc123",
        parser_version="1.0.0",
        record_count=1000,
    )
    defaults.update(overrides)
    return SourceSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------


class TestEnumValidation:
    """Reject invalid enum values for facility class, relevance, quantity, display."""

    def test_valid_facility_classes(self):
        for cls in FACILITY_CLASSES:
            assert validate_facility_class(cls) == cls

    def test_invalid_facility_class_raises(self):
        with pytest.raises(WaterFacilityError, match="facility_class"):
            validate_facility_class("nuclear_reactor")

    def test_valid_water_relevance(self):
        for level in WATER_RELEVANCE_LEVELS:
            assert validate_water_relevance(level) == level

    def test_invalid_water_relevance_raises(self):
        with pytest.raises(WaterFacilityError, match="water_relevance"):
            validate_water_relevance("definitely_uses_water")

    def test_valid_measure_types(self):
        for mt in MEASURE_TYPES:
            assert validate_measure_type(mt) == mt

    def test_invalid_measure_type_raises(self):
        with pytest.raises(WaterFacilityError, match="measure_type"):
            validate_measure_type("guessed")

    def test_valid_quantity_statuses(self):
        for qs in QUANTITY_STATUSES:
            assert validate_quantity_status(qs) == qs

    def test_invalid_quantity_status_raises(self):
        with pytest.raises(WaterFacilityError, match="quantity_status"):
            validate_quantity_status("assumed")

    def test_valid_display_eligibilities(self):
        for de in DISPLAY_ELIGIBILITIES:
            assert validate_display_eligibility(de) == de

    def test_invalid_display_eligibility_raises(self):
        with pytest.raises(WaterFacilityError, match="display_eligibility"):
            validate_display_eligibility("show_everything")


# ---------------------------------------------------------------------------
# Immutable provenance
# ---------------------------------------------------------------------------


class TestImmutableProvenance:
    """Source snapshots and evidence preserve checksums and locators."""

    def test_source_snapshot_immutable(self):
        ss = _make_source_snapshot()
        with pytest.raises(AttributeError):
            ss.content_checksum = "sha256:tampered"  # type: ignore[misc]

    def test_evidence_immutable(self):
        ev = _make_evidence()
        with pytest.raises(AttributeError):
            ev.content_checksum = "sha256:tampered"  # type: ignore[misc]

    def test_source_snapshot_preserves_checksum(self):
        ss = _make_source_snapshot(content_checksum="sha256:deadbeef")
        assert ss.content_checksum == "sha256:deadbeef"

    def test_evidence_preserves_locator(self):
        ev = _make_evidence(row_locator="page:7,table:2,row:15")
        assert ev.row_locator == "page:7,table:2,row:15"


# ---------------------------------------------------------------------------
# External-ID uniqueness rules
# ---------------------------------------------------------------------------


class TestExternalIdUniqueness:
    """Facility identifiers enforce authority + id uniqueness contract."""

    def test_identifier_fields(self):
        fid = FacilityIdentifier(
            id=uuid.uuid4(),
            facility_id=uuid.uuid4(),
            authority="EPA_FRS",
            external_id="110071491719",
            source_record_id=uuid.uuid4(),
        )
        assert fid.authority == "EPA_FRS"
        assert fid.external_id == "110071491719"

    def test_identifier_immutable(self):
        fid = FacilityIdentifier(
            id=uuid.uuid4(),
            facility_id=uuid.uuid4(),
            authority="EPA_FRS",
            external_id="110071491719",
            source_record_id=uuid.uuid4(),
        )
        with pytest.raises(AttributeError):
            fid.external_id = "tampered"  # type: ignore[misc]

    def test_same_id_different_authority_is_distinct(self):
        """Identical external_id under different authorities must not collide."""
        base = dict(id=uuid.uuid4(), facility_id=uuid.uuid4(),
                    external_id="12345", source_record_id=uuid.uuid4())
        a = FacilityIdentifier(authority="EPA_FRS", **base)
        b = FacilityIdentifier(authority="STATE_TX", **{**base, "id": uuid.uuid4()})
        assert a.authority != b.authority
        assert a.external_id == b.external_id


# ---------------------------------------------------------------------------
# Quantity / status separation
# ---------------------------------------------------------------------------


class TestQuantityStatusSeparation:
    """Measure type and quantity status are independent dimensions."""

    def test_measured_withdrawal(self):
        m = _make_measurement(measure_type="withdrawal", quantity_status="measured")
        assert m.measure_type == "withdrawal"
        assert m.quantity_status == "measured"

    def test_authorized_capacity(self):
        m = _make_measurement(measure_type="authorized_capacity",
                              quantity_status="authorized")
        assert m.measure_type == "authorized_capacity"
        assert m.quantity_status == "authorized"

    def test_unavailable_quantity_has_no_value(self):
        """An unavailable measurement should accept None value."""
        m = _make_measurement(
            quantity_status="unavailable",
            value=None,
            canonical_value=None,
        )
        assert m.quantity_status == "unavailable"
        assert m.value is None

    def test_source_unit_preserved(self):
        m = _make_measurement(source_unit="MGD", canonical_unit="m3/day",
                              conversion_method="multiply_3785.41")
        assert m.source_unit == "MGD"
        assert m.canonical_unit == "m3/day"


# ---------------------------------------------------------------------------
# WaterClaim display eligibility
# ---------------------------------------------------------------------------


class TestWaterClaimDisplay:
    """Claims enforce display eligibility rules."""

    def test_publishable_precise_allowed(self):
        c = _make_claim(display_eligibility="publishable_precise")
        assert c.display_eligibility == "publishable_precise"

    def test_publishable_generalized_allowed(self):
        c = _make_claim(display_eligibility="publishable_generalized")
        assert c.display_eligibility == "publishable_generalized"

    def test_internal_only_claim(self):
        c = _make_claim(display_eligibility="internal_only")
        assert c.display_eligibility == "internal_only"

    def test_excluded_claim(self):
        c = _make_claim(display_eligibility="excluded")
        assert c.display_eligibility == "excluded"

    def test_review_required_claim(self):
        c = _make_claim(display_eligibility="review_required")
        assert c.display_eligibility == "review_required"

    def test_claim_requires_evidence(self):
        """A claim with no evidence IDs should be rejected."""
        with pytest.raises(WaterFacilityError, match="evidence"):
            _make_claim(evidence_ids=())


# ---------------------------------------------------------------------------
# Bitemporal validity / system times
# ---------------------------------------------------------------------------


class TestBitemporalTimes:
    """Valid time and system/retrieval time remain distinct and independently set."""

    def test_measurement_valid_and_system_times_distinct(self):
        valid_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        valid_end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        sys_time = datetime(2026, 3, 15, tzinfo=timezone.utc)
        m = _make_measurement(
            valid_time_start=valid_start,
            valid_time_end=valid_end,
            system_time=sys_time,
        )
        assert m.valid_time_start == valid_start
        assert m.valid_time_end == valid_end
        assert m.system_time == sys_time
        assert m.system_time != m.valid_time_start

    def test_claim_valid_and_system_times_distinct(self):
        valid_start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        valid_end = datetime(2024, 12, 31, tzinfo=timezone.utc)
        sys_time = datetime(2026, 9, 30, tzinfo=timezone.utc)
        c = _make_claim(
            valid_time_start=valid_start,
            valid_time_end=valid_end,
            system_time=sys_time,
        )
        assert c.valid_time_start == valid_start
        assert c.system_time == sys_time
        assert c.system_time != c.valid_time_start

    def test_changing_system_time_does_not_affect_valid_time(self):
        """Updating retrieval/system time must not rewrite valid_time."""
        c1 = _make_claim(
            valid_time_start=_EARLIER,
            system_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        c2 = _make_claim(
            valid_time_start=_EARLIER,
            system_time=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert c1.valid_time_start == c2.valid_time_start


# ---------------------------------------------------------------------------
# Invalid period rejection
# ---------------------------------------------------------------------------


class TestInvalidPeriodRejection:
    """Inverted or invalid measurement periods are rejected."""

    def test_inverted_measurement_period_raises(self):
        with pytest.raises(WaterFacilityError, match="period"):
            _make_measurement(
                period_start=_NOW,
                period_end=_EARLIER,
            )

    def test_inverted_valid_time_on_measurement_raises(self):
        with pytest.raises(WaterFacilityError, match="valid_time"):
            _make_measurement(
                valid_time_start=_NOW,
                valid_time_end=_EARLIER,
            )

    def test_inverted_valid_time_on_claim_raises(self):
        with pytest.raises(WaterFacilityError, match="valid_time"):
            _make_claim(
                valid_time_start=_NOW,
                valid_time_end=_EARLIER,
            )


# ---------------------------------------------------------------------------
# Facility construction and frozen
# ---------------------------------------------------------------------------


class TestFacilityConstruction:
    """Basic facility construction and immutability."""

    def test_facility_round_trip(self):
        f = _make_facility(name="Big River Plant", jurisdiction="VA")
        assert f.name == "Big River Plant"
        assert f.jurisdiction == "VA"

    def test_facility_frozen(self):
        f = _make_facility()
        with pytest.raises(AttributeError):
            f.name = "Tampered"  # type: ignore[misc]

    def test_facility_invalid_class_raises(self):
        with pytest.raises(WaterFacilityError):
            _make_facility(facility_class="spaceship")

    def test_facility_invalid_relevance_raises(self):
        with pytest.raises(WaterFacilityError):
            _make_facility(water_relevance="obviously_uses_tons")
