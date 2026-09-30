"""Offline tests for national source normalization into the water-facility contract.

Uses small checked-in synthetic rows only — no network, no GDAL, no database.
Each source family gets one fixture that normalizes to the common contract while
retaining raw source keys and values.

Key invariants:
- NPDES/DMR discharge remains ``discharged``, never ``withdrawal``.
- Service-area and USGS context records cannot create a facility measurement.
- Same fixture + parser version gives an identical result (idempotent).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_source import (
    NormalizedFacility,
    NormalizedMeasurement,
    SourceContext,
    normalize_cwns,
    normalize_dmr,
    normalize_frs,
    normalize_nid,
    normalize_npdes,
    normalize_sdwis,
    normalize_usgs_water_use,
)

_NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Synthetic fixtures (one per source family)
# ---------------------------------------------------------------------------

FRS_ROW = {
    "REGISTRY_ID": "110071491719",
    "PRIMARY_NAME": "City of Austin WWTP",
    "STATE_CODE": "TX",
    "LATITUDE83": 30.267,
    "LONGITUDE83": -97.743,
    "NAICS_CODES": "221320",
}

SDWIS_ROW = {
    "PWSID": "TX0190001",
    "PWS_NAME": "City of Austin Water",
    "STATE_CODE": "TX",
    "PWS_TYPE_CODE": "CWS",
    "POPULATION_SERVED_COUNT": 1000000,
    "SOURCE_TYPE_CODE": "SW",
}

NPDES_ROW = {
    "NPDES_ID": "TX0021458",
    "FACILITY_NAME": "South Austin WWTP",
    "STATE_CODE": "TX",
    "SIC_CODES": "4952",
    "FACILITY_TYPE_INDICATOR": "POTW",
    "LATITUDE": 30.200,
    "LONGITUDE": -97.750,
}

DMR_ROW = {
    "NPDES_ID": "TX0021458",
    "MONITORING_PERIOD_END_DATE": "2026-06-30",
    "PARAMETER_DESC": "Flow, in conduit or thru treatment plant",
    "PARAMETER_CODE": "50050",
    "DMR_VALUE_STANDARD_UNITS": 15.5,
    "STANDARD_UNIT_DESC": "MGD",
    "STATISTICAL_BASE_SHORT_DESC": "MO AVG",
}

CWNS_ROW = {
    "CWNS_NUMBER": "TX0021458001",
    "FACILITY_NAME": "South Austin Regional WWTP",
    "STATE_CODE": "TX",
    "FACILITY_TYPE": "POTW",
    "DESIGN_FLOW_MGD": 75.0,
    "LATITUDE": 30.200,
    "LONGITUDE": -97.750,
}

NID_ROW = {
    "NID_ID": "TX00001",
    "DAM_NAME": "Mansfield Dam",
    "STATE": "TX",
    "COUNTY": "Travis",
    "LATITUDE": 30.393,
    "LONGITUDE": -97.920,
    "DAM_HEIGHT": 266.0,
    "NORMAL_STORAGE": 1170000,
    "PURPOSES": "SR",
    "YEAR_COMPLETED": "1941",
}

USGS_ROW = {
    "state_cd": "TX",
    "county_cd": "453",
    "year": 2015,
    "Total_self-supplied_withdrawals_Mgal/d": 520.0,
    "Public_supply_total_self-supplied_withdrawals_Mgal/d": 310.0,
    "category": "Total",
}


# ---------------------------------------------------------------------------
# FRS
# ---------------------------------------------------------------------------


class TestFrsNormalization:
    def test_normalizes_to_facility(self):
        result = normalize_frs(FRS_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedFacility)
        assert result.source_family == "FRS"
        assert result.source_key == "110071491719"
        assert result.name == "City of Austin WWTP"
        assert result.jurisdiction == "TX"

    def test_retains_raw_source_key(self):
        result = normalize_frs(FRS_ROW, snapshot_id=uuid.uuid4())
        assert result.raw_fields["REGISTRY_ID"] == "110071491719"

    def test_idempotent(self):
        sid = uuid.uuid4()
        a = normalize_frs(FRS_ROW, snapshot_id=sid)
        b = normalize_frs(FRS_ROW, snapshot_id=sid)
        assert a.source_key == b.source_key
        assert a.name == b.name


# ---------------------------------------------------------------------------
# SDWIS
# ---------------------------------------------------------------------------


class TestSdwisNormalization:
    def test_normalizes_to_facility(self):
        result = normalize_sdwis(SDWIS_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedFacility)
        assert result.source_family == "SDWIS"
        assert result.source_key == "TX0190001"
        assert result.facility_class == "drinking_water"

    def test_retains_population(self):
        result = normalize_sdwis(SDWIS_ROW, snapshot_id=uuid.uuid4())
        assert result.raw_fields["POPULATION_SERVED_COUNT"] == 1000000


# ---------------------------------------------------------------------------
# NPDES
# ---------------------------------------------------------------------------


class TestNpdesNormalization:
    def test_normalizes_to_facility(self):
        result = normalize_npdes(NPDES_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedFacility)
        assert result.source_family == "NPDES"
        assert result.source_key == "TX0021458"
        assert result.facility_class == "wastewater"

    def test_retains_source_fields(self):
        result = normalize_npdes(NPDES_ROW, snapshot_id=uuid.uuid4())
        assert result.raw_fields["NPDES_ID"] == "TX0021458"


# ---------------------------------------------------------------------------
# DMR — the critical invariant: discharge remains discharged
# ---------------------------------------------------------------------------


class TestDmrNormalization:
    def test_dmr_produces_measurement(self):
        result = normalize_dmr(DMR_ROW, facility_source_key="TX0021458",
                               snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedMeasurement)
        assert result.value == 15.5
        assert result.source_unit == "MGD"

    def test_dmr_measure_type_is_discharged(self):
        """NPDES DMR discharge data must remain 'discharged', never 'withdrawal'."""
        result = normalize_dmr(DMR_ROW, facility_source_key="TX0021458",
                               snapshot_id=uuid.uuid4())
        assert result.measure_type == "discharged"
        assert result.measure_type != "withdrawal"

    def test_dmr_quantity_status_is_reported(self):
        result = normalize_dmr(DMR_ROW, facility_source_key="TX0021458",
                               snapshot_id=uuid.uuid4())
        assert result.quantity_status == "reported"


# ---------------------------------------------------------------------------
# CWNS — service-area records are context only
# ---------------------------------------------------------------------------


class TestCwnsNormalization:
    def test_normalizes_to_facility(self):
        result = normalize_cwns(CWNS_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedFacility)
        assert result.source_family == "CWNS"

    def test_design_flow_is_authorized_capacity(self):
        """CWNS design flow is authorized capacity, not a measured withdrawal."""
        result = normalize_cwns(CWNS_ROW, snapshot_id=uuid.uuid4())
        assert result.authorized_capacity_mgd == 75.0


# ---------------------------------------------------------------------------
# NID (National Inventory of Dams)
# ---------------------------------------------------------------------------


class TestNidNormalization:
    def test_normalizes_to_facility(self):
        result = normalize_nid(NID_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, NormalizedFacility)
        assert result.source_family == "NID"
        assert result.source_key == "TX00001"
        assert result.facility_class == "dam"

    def test_retains_source_fields(self):
        result = normalize_nid(NID_ROW, snapshot_id=uuid.uuid4())
        assert result.raw_fields["DAM_NAME"] == "Mansfield Dam"


# ---------------------------------------------------------------------------
# USGS water-use context — cannot create facility measurements
# ---------------------------------------------------------------------------


class TestUsgsWaterUseNormalization:
    def test_normalizes_to_context(self):
        """USGS water-use is county/state context, NOT a facility measurement."""
        result = normalize_usgs_water_use(USGS_ROW, snapshot_id=uuid.uuid4())
        assert isinstance(result, SourceContext)
        assert result.source_family == "USGS"
        assert result.context_type == "county_water_use"

    def test_cannot_create_facility_measurement(self):
        """USGS aggregate data must never produce a NormalizedMeasurement."""
        result = normalize_usgs_water_use(USGS_ROW, snapshot_id=uuid.uuid4())
        assert not isinstance(result, NormalizedMeasurement)

    def test_retains_values(self):
        result = normalize_usgs_water_use(USGS_ROW, snapshot_id=uuid.uuid4())
        assert result.raw_fields["Total_self-supplied_withdrawals_Mgal/d"] == 520.0
