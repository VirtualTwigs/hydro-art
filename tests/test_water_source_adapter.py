"""Tests for src/water_source_adapter.py — adapter protocol and registry manager.

Convention-compliant mirror of test_state_source_registry.py (which covers the
same module under a different name).  This file focuses on AdapterResult field
access and SourceRegistryManager edge cases not yet covered.

Pure and offline: no network, no GDAL, no database driver.
"""

from __future__ import annotations

from src.water_facilities import StateSourceEntry
from src.water_source_adapter import (
    AdapterProtocol,
    AdapterResult,
    ApiAdapter,
    ArcGisAdapter,
    BulkFileAdapter,
    SourceRegistryManager,
)


def _entry(**overrides):
    base = dict(
        jurisdiction="Virginia",
        program="DEQ Water Withdrawal Reporting",
        source_url="https://example.com",
        access_method="api",
        data_format="json",
        coverage="statewide",
        update_cadence="annual",
        license="public_domain",
        field_mapping={"id": "FACILITY_ID"},
        geometry_quality="high",
        publication_lag_days=30,
        verified=True,
    )
    base.update(overrides)
    return StateSourceEntry(**base)


class TestAdapterResultFields:
    def test_source_key_and_raw_row_accessible(self):
        r = AdapterResult(source_key="API:42", raw_row={"id": "42", "name": "Plant"})
        assert r.source_key == "API:42"
        assert r.raw_row["name"] == "Plant"

    def test_frozen(self):
        import pytest
        r = AdapterResult(source_key="X:1", raw_row={})
        with pytest.raises(AttributeError):
            r.source_key = "Y:2"  # type: ignore[misc]


class TestAdapterProtocolConformance:
    def test_api_adapter_is_protocol(self):
        assert isinstance(ApiAdapter(fixture_rows=[{"id": "1"}]), AdapterProtocol)

    def test_bulk_adapter_is_protocol(self):
        assert isinstance(BulkFileAdapter(fixture_rows=[{"id": "1"}]), AdapterProtocol)

    def test_arcgis_adapter_is_protocol(self):
        assert isinstance(ArcGisAdapter(fixture_rows=[{"id": "1"}]), AdapterProtocol)


class TestAdapterKeyPrefixes:
    def test_api_prefix(self):
        results = ApiAdapter(fixture_rows=[{"id": "A1"}]).fetch()
        assert results[0].source_key == "API:A1"

    def test_bulk_prefix(self):
        results = BulkFileAdapter(fixture_rows=[{"id": "B2"}]).fetch()
        assert results[0].source_key == "BULK:B2"

    def test_arcgis_prefix(self):
        results = ArcGisAdapter(fixture_rows=[{"id": "C3"}]).fetch()
        assert results[0].source_key == "ARCGIS:C3"


class TestRegistryManagerEdgeCases:
    def test_empty_registry(self):
        mgr = SourceRegistryManager()
        assert mgr.all_entries() == []
        assert mgr.get_by_jurisdiction("Virginia") == []

    def test_register_adds_entry(self):
        mgr = SourceRegistryManager()
        e = _entry()
        mgr.register(e)
        assert len(mgr.all_entries()) == 1

    def test_all_entries_returns_copy(self):
        mgr = SourceRegistryManager()
        mgr.register(_entry())
        entries = mgr.all_entries()
        entries.clear()
        assert len(mgr.all_entries()) == 1

    def test_verified_and_unverified_partition(self):
        v = _entry(verified=True, jurisdiction="VA")
        u = _entry(verified=False, jurisdiction="VA")
        mgr = SourceRegistryManager()
        mgr.register(v)
        mgr.register(u)
        assert len(mgr.get_verified()) == 1
        assert len(mgr.get_unverified()) == 1
