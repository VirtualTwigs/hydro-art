"""Integration tests for the water-facility intelligence pipeline.

Exercises the cross-module chain: normalization → matching → aggregation.
Each module is tested in isolation elsewhere; here we verify they compose.

Pure and offline: no network, no GDAL, no database driver.
"""

from __future__ import annotations

from datetime import datetime

from src.water_source_normalization import (
    NormalizationResult,
    normalize_frs_row,
)
from src.water_facility_matching import (
    MatchCandidate,
    match_by_authority_id,
    match_by_name_address_geo,
    HIGH_CONFIDENCE_THRESHOLD,
)
from src.water_facility_aggregation import (
    AggregationQuery,
    aggregate_measurements,
)
from src.water_facilities import WaterMeasurement


def _frs_row(**overrides):
    base = {
        "REGISTRY_ID": "110000001234",
        "PRIMARY_NAME": "Loudoun Water Treatment",
        "CITY_NAME": "Leesburg",
        "STATE_CODE": "VA",
        "LATITUDE83": "39.115",
        "LONGITUDE83": "-77.563",
        "NAICS_CODES": "221310",
    }
    base.update(overrides)
    return base


class TestNormalizationToMatching:
    """Verify that normalized FRS output feeds into the matching layer."""

    def test_frs_normalized_to_match_candidate(self):
        result = normalize_frs_row(_frs_row())
        # NormalizationResult → MatchCandidate
        candidate = MatchCandidate(
            authority=result.authority,
            external_id=result.external_id,
            name=result.facility.name if result.facility else "",
            address="Leesburg",
            jurisdiction="VA",
            latitude=result.latitude or 0.0,
            longitude=result.longitude or 0.0,
        )
        assert candidate.authority == "EPA_FRS"
        assert candidate.external_id == "110000001234"
        assert candidate.latitude == 39.115

    def test_authority_id_match_across_normalized_rows(self):
        """Two FRS rows with the same REGISTRY_ID match by authority ID."""
        r1 = normalize_frs_row(_frs_row())
        r2 = normalize_frs_row(_frs_row(PRIMARY_NAME="Loudoun WTP (Duplicate)"))

        c1 = MatchCandidate(
            authority=r1.authority, external_id=r1.external_id,
            name=r1.facility.name if r1.facility else "",
            address="Leesburg", jurisdiction="VA",
            latitude=r1.latitude or 0, longitude=r1.longitude or 0,
        )
        c2 = MatchCandidate(
            authority=r2.authority, external_id=r2.external_id,
            name=r2.facility.name if r2.facility else "",
            address="Leesburg", jurisdiction="VA",
            latitude=r2.latitude or 0, longitude=r2.longitude or 0,
        )
        result = match_by_authority_id(c1, [c2])
        assert result is not None
        assert result.matched is True
        assert result.confidence == 1.0

    def test_name_geo_match_same_facility_different_source(self):
        """Two candidates at nearly the same location with similar names match."""
        c1 = MatchCandidate(
            authority="EPA_FRS", external_id="A1",
            name="Loudoun Water Treatment Plant",
            address="Leesburg VA", jurisdiction="VA",
            latitude=39.115, longitude=-77.563,
        )
        c2 = MatchCandidate(
            authority="SDWIS", external_id="B2",
            name="Loudoun Water Treatment",
            address="Leesburg VA", jurisdiction="VA",
            latitude=39.115, longitude=-77.563,
        )
        result = match_by_name_address_geo(c1, [c2])
        assert result is not None
        assert result.confidence >= HIGH_CONFIDENCE_THRESHOLD


class TestNormalizationToAggregation:
    """Verify that normalized measurements aggregate correctly."""

    def _make_measurement(self, facility_id, measure_type, value, start, end):
        return WaterMeasurement(
            measurement_id=f"{facility_id}-{start}",
            facility_id=facility_id,
            period_start=start,
            period_end=end,
            measure_type=measure_type,
            quantity_status="measured",
            value_numeric=value,
            source_unit="MGD",
            canonical_unit="MGD",
            canonical_value=value,
            conversion_method="identity",
            confidence=1.0,
            evidence_id="ev1",
        )

    def test_aggregate_normalized_measurements_by_type(self):
        """Measurements from normalized rows aggregate by type."""
        m1 = self._make_measurement(
            "F1", "discharged", 5.0,
            datetime(2024, 1, 1), datetime(2024, 6, 30),
        )
        m2 = self._make_measurement(
            "F1", "discharged", 3.0,
            datetime(2024, 7, 1), datetime(2024, 12, 31),
        )
        m3 = self._make_measurement(
            "F1", "withdrawal", 10.0,
            datetime(2024, 1, 1), datetime(2024, 12, 31),
        )
        query = AggregationQuery(measure_type="discharged")
        result = aggregate_measurements([m1, m2, m3], query)
        assert result.total_value == 8.0
        assert result.count == 2

    def test_aggregate_with_period_filter(self):
        m1 = self._make_measurement(
            "F1", "withdrawal", 100.0,
            datetime(2023, 1, 1), datetime(2023, 12, 31),
        )
        m2 = self._make_measurement(
            "F1", "withdrawal", 200.0,
            datetime(2024, 1, 1), datetime(2024, 12, 31),
        )
        query = AggregationQuery(
            measure_type="withdrawal",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 12, 31),
        )
        result = aggregate_measurements([m1, m2], query)
        assert result.total_value == 200.0
        assert result.count == 1

    def test_aggregate_group_by_facility(self):
        m1 = self._make_measurement(
            "F1", "discharged", 5.0,
            datetime(2024, 1, 1), datetime(2024, 6, 30),
        )
        m2 = self._make_measurement(
            "F2", "discharged", 3.0,
            datetime(2024, 1, 1), datetime(2024, 6, 30),
        )
        query = AggregationQuery(measure_type="discharged", group_by_facility=True)
        result = aggregate_measurements([m1, m2], query)
        assert len(result.facility_summaries) == 2
        ids = {s.facility_id for s in result.facility_summaries}
        assert ids == {"F1", "F2"}


class TestFullChain:
    """End-to-end: normalize → match → aggregate."""

    def test_normalize_match_aggregate(self):
        # 1. Normalize two FRS rows for the same facility
        row1 = _frs_row(REGISTRY_ID="110000001234")
        row2 = _frs_row(REGISTRY_ID="110000001234", PRIMARY_NAME="Loudoun WTP v2")
        n1 = normalize_frs_row(row1)
        n2 = normalize_frs_row(row2)

        # 2. Match — same authority ID should match
        c1 = MatchCandidate(
            authority=n1.authority, external_id=n1.external_id,
            name=n1.facility.name if n1.facility else "",
            address="Leesburg", jurisdiction="VA",
            latitude=n1.latitude or 0, longitude=n1.longitude or 0,
        )
        c2 = MatchCandidate(
            authority=n2.authority, external_id=n2.external_id,
            name=n2.facility.name if n2.facility else "",
            address="Leesburg", jurisdiction="VA",
            latitude=n2.latitude or 0, longitude=n2.longitude or 0,
        )
        match_result = match_by_authority_id(c1, [c2])
        assert match_result is not None and match_result.matched

        # 3. Aggregate measurements under the resolved facility ID
        fac_id = n1.external_id  # resolved identity
        m = WaterMeasurement(
            measurement_id=f"{fac_id}-2024Q1",
            facility_id=fac_id,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
            measure_type="withdrawal",
            quantity_status="measured",
            value_numeric=42.0,
            source_unit="MGD",
            canonical_unit="MGD",
            canonical_value=42.0,
            conversion_method="identity",
            confidence=1.0,
            evidence_id="ev1",
        )
        result = aggregate_measurements([m], AggregationQuery(measure_type="withdrawal"))
        assert result.total_value == 42.0
        assert result.count == 1
