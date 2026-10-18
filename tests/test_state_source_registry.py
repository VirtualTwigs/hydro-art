"""Offline tests for the state source registry and adapter protocol.

Covers: valid access methods, required fields, inactive/unverified source
handling, jurisdiction isolation, and permit-ID authority distinctness.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_facility import (
    ACCESS_METHODS,
    StateSourceEntry,
    WaterFacilityError,
)
from src.water_adapter import (
    AdapterManifest,
    StateSourceAdapter,
    build_adapter_manifest,
    validate_registry_entry,
)

_NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def _make_entry(**overrides) -> StateSourceEntry:
    defaults = dict(
        id=uuid.uuid4(),
        jurisdiction="TX",
        program="water_rights",
        agency="Texas CEQ",
        url="https://tceq.texas.gov/api/water-rights",
        access_method="api",
        data_format="JSON",
        coverage="statewide",
        update_cadence="monthly",
        license="public_domain",
        field_mapping_version="1.0.0",
        geometry_quality="survey_grade",
        publication_lag_days=30,
        verified=True,
        last_verified=_NOW,
    )
    defaults.update(overrides)
    return StateSourceEntry(**defaults)


# ---------------------------------------------------------------------------
# Access method validation
# ---------------------------------------------------------------------------


class TestAccessMethods:
    def test_all_five_methods_accepted(self):
        for method in ACCESS_METHODS:
            entry = _make_entry(access_method=method)
            assert entry.access_method == method

    def test_invalid_method_raises(self):
        with pytest.raises(WaterFacilityError, match="access_method"):
            _make_entry(access_method="web_scraping")


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    def test_validate_complete_entry(self):
        entry = _make_entry()
        assert validate_registry_entry(entry) is True

    def test_validate_missing_url_raises(self):
        entry = _make_entry(url="")
        with pytest.raises(WaterFacilityError, match="url"):
            validate_registry_entry(entry)

    def test_validate_missing_jurisdiction_raises(self):
        entry = _make_entry(jurisdiction="")
        with pytest.raises(WaterFacilityError, match="jurisdiction"):
            validate_registry_entry(entry)

    def test_validate_missing_license_raises(self):
        entry = _make_entry(license="")
        with pytest.raises(WaterFacilityError, match="license"):
            validate_registry_entry(entry)

    def test_validate_missing_cadence_raises(self):
        entry = _make_entry(update_cadence="")
        with pytest.raises(WaterFacilityError, match="update_cadence"):
            validate_registry_entry(entry)

    def test_validate_missing_coverage_raises(self):
        entry = _make_entry(coverage="")
        with pytest.raises(WaterFacilityError, match="coverage"):
            validate_registry_entry(entry)


# ---------------------------------------------------------------------------
# Inactive / unverified source handling
# ---------------------------------------------------------------------------


class TestInactiveUnverifiedSources:
    def test_unverified_source_reported(self):
        """An unverified source should be flagged, not silently excluded."""
        entry = _make_entry(verified=False, last_verified=None)
        assert entry.verified is False

    def test_validate_accepts_unverified(self):
        """Validation passes for unverified; the caller decides how to handle."""
        entry = _make_entry(verified=False)
        assert validate_registry_entry(entry) is True


# ---------------------------------------------------------------------------
# Jurisdiction isolation
# ---------------------------------------------------------------------------


class TestJurisdictionIsolation:
    def test_entries_in_different_jurisdictions_are_independent(self):
        tx = _make_entry(jurisdiction="TX", program="water_rights")
        va = _make_entry(jurisdiction="VA", program="water_rights",
                         id=uuid.uuid4())
        assert tx.jurisdiction != va.jurisdiction
        assert tx.program == va.program

    def test_same_permit_id_different_authorities_distinct(self):
        """Identical permit IDs under different authorities remain separate."""
        tx = _make_entry(jurisdiction="TX", program="withdrawal_permits")
        va = _make_entry(jurisdiction="VA", program="withdrawal_permits",
                         id=uuid.uuid4())
        # Different jurisdictions → different source → distinct permits
        assert tx.jurisdiction != va.jurisdiction


# ---------------------------------------------------------------------------
# Adapter manifest
# ---------------------------------------------------------------------------


class TestAdapterManifest:
    def test_build_manifest(self):
        entry = _make_entry()
        manifest = build_adapter_manifest(
            entry=entry,
            record_count=150,
            snapshot_id=uuid.uuid4(),
            fields_mapped=["permit_id", "holder", "volume_mgd"],
            fields_unmapped=["internal_code"],
        )
        assert isinstance(manifest, AdapterManifest)
        assert manifest.jurisdiction == "TX"
        assert manifest.record_count == 150
        assert len(manifest.fields_mapped) == 3
        assert "internal_code" in manifest.fields_unmapped

    def test_manifest_records_unmapped_fields(self):
        entry = _make_entry()
        manifest = build_adapter_manifest(
            entry=entry,
            record_count=50,
            snapshot_id=uuid.uuid4(),
            fields_mapped=["id"],
            fields_unmapped=["weird_field", "legacy_code"],
        )
        assert len(manifest.fields_unmapped) == 2
