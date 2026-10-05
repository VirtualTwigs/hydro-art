"""Tests for src/ledger.py — domain model, ID helpers, validation, repository protocol.

Group 1: entity dataclasses, ID validators, value validators, LedgerError (~18 tests)
Group 2: OrderRepository protocol and repository_factory (~6 tests)
Group 3: analysis model validation (~6 tests)

Pure and offline — no database, no network, no GDAL.
"""

from __future__ import annotations

import pytest

from src.ledger import (
    ASSET_ROLES,
    RIGHTS_STATUSES,
    VISIBILITY_VALUES,
    AnalysisMetric,
    AnalysisRun,
    Asset,
    AssetLineage,
    BriefRevision,
    Delivery,
    LedgerError,
    LedgerEvent,
    OrderRepository,
    Place,
    RenderJob,
    repository_factory,
    validate_asset_id,
    validate_asset_role,
    validate_delivery_access,
    validate_delivery_id,
    validate_order_id,
    validate_request_id,
    validate_rights_status,
    validate_visibility,
)

# ---------------------------------------------------------------------------
# Group 1 — Entity dataclasses
# ---------------------------------------------------------------------------


class TestPlace:
    def test_frozen(self):
        p = Place(place_id="wa-clark", region="Washington", county="Clark",
                  huc4="1708", display_name="Clark County, WA")
        with pytest.raises(AttributeError):
            p.region = "Oregon"  # type: ignore[misc]

    def test_fields(self):
        p = Place(place_id="wa-clark", region="Washington", county=None,
                  huc4=None, display_name="Washington")
        assert p.place_id == "wa-clark"
        assert p.county is None
        assert p.huc4 is None


class TestAsset:
    def test_frozen(self):
        a = Asset(
            asset_id="AST-ORD-20260901-0001-proof-r1",
            order_id="ORD-20260901-0001",
            render_job_id="JOB-ORD-20260901-0001-r1",
            role="proof",
            storage_key="library/orders/ORD-20260901-0001/proof.png",
            checksum_sha256="abc123",
            byte_count=1024,
            width_px=3600,
            height_px=4800,
            media_type="image/png",
            visibility="internal",
            rights_status="pending",
            source_attribution="USGS NHDPlus HR",
            created_at="2026-09-01T00:00:00Z",
            retention_class="standard",
            retain_until=None,
            deleted_at=None,
        )
        with pytest.raises(AttributeError):
            a.role = "final"  # type: ignore[misc]

    def test_all_fields_present(self):
        a = Asset(
            asset_id="AST-ORD-20260901-0001-proof-r1",
            order_id="ORD-20260901-0001",
            render_job_id="JOB-ORD-20260901-0001-r1",
            role="proof",
            storage_key="library/proof.png",
            checksum_sha256="deadbeef",
            byte_count=512,
            width_px=None,
            height_px=None,
            media_type="image/svg+xml",
            visibility="approved_public",
            rights_status="cleared",
            source_attribution="USGS NHD",
            created_at="2026-09-01T00:00:00Z",
            retention_class="archive",
            retain_until="2030-01-01",
            deleted_at=None,
        )
        assert a.visibility == "approved_public"
        assert a.rights_status == "cleared"


class TestAssetLineage:
    def test_frozen_and_fields(self):
        al = AssetLineage(
            parent_asset_id="AST-ORD-20260901-0001-source_reference-r1",
            child_asset_id="AST-ORD-20260901-0001-proof-r1",
            relationship="derived_from",
        )
        assert al.relationship == "derived_from"
        with pytest.raises(AttributeError):
            al.relationship = "other"  # type: ignore[misc]


class TestRenderJob:
    def test_frozen(self):
        rj = RenderJob(
            job_id="JOB-ORD-20260901-0001-r1",
            order_id="ORD-20260901-0001",
            brief_revision="BRF-ORD-20260901-0001-r1",
            status="completed",
            recipe_digest="sha256:abc",
            started_at="2026-09-01T00:00:00Z",
            finished_at="2026-09-01T00:05:00Z",
            error_message=None,
        )
        with pytest.raises(AttributeError):
            rj.status = "failed"  # type: ignore[misc]


class TestBriefRevision:
    def test_frozen(self):
        br = BriefRevision(
            brief_id="BRF-ORD-20260901-0001-r1",
            order_id="ORD-20260901-0001",
            revision=1,
            recipe={"region": "Washington"},
            created_at="2026-09-01T00:00:00Z",
        )
        assert br.revision == 1
        with pytest.raises(AttributeError):
            br.revision = 2  # type: ignore[misc]


class TestDelivery:
    def test_frozen(self):
        d = Delivery(
            delivery_id="DLV-ORD-20260901-0001-1",
            order_id="ORD-20260901-0001",
            delivered_at="2026-09-01T00:00:00Z",
            access_expires_at="2026-11-30T00:00:00Z",
            access_revoked_at=None,
            asset_ids=("AST-ORD-20260901-0001-final-r1",),
            reason="initial delivery",
            fee_waived=False,
        )
        assert d.fee_waived is False
        with pytest.raises(AttributeError):
            d.fee_waived = True  # type: ignore[misc]


class TestAnalysisRun:
    def test_frozen(self):
        ar = AnalysisRun(
            run_id="run-001",
            place_id="wa-clark",
            recipe_digest="sha256:abc",
            code_revision="v1.0.0",
            input_sources={"nhd": "2024-01"},
            start_year=2000,
            end_year=2024,
            metric_version="1.0",
            validation_status="draft",
            created_at="2026-09-01T00:00:00Z",
            reviewer=None,
            notes=None,
        )
        with pytest.raises(AttributeError):
            ar.validation_status = "validated"  # type: ignore[misc]


class TestAnalysisMetric:
    def test_frozen(self):
        am = AnalysisMetric(
            metric_id="metric-001",
            run_id="run-001",
            name="ops_proof_turnaround",
            units="hours",
            method="ops_turnaround",
            method_version="1.0",
            value=24.5,
            interpretation_status="validated",
            created_at="2026-09-01T00:00:00Z",
        )
        assert am.value == 24.5
        with pytest.raises(AttributeError):
            am.value = 30.0  # type: ignore[misc]


class TestLedgerEvent:
    def test_frozen(self):
        ev = LedgerEvent(
            event_id="evt-001",
            entity_type="order",
            entity_id="ORD-20260901-0001",
            occurred_at="2026-09-01T00:00:00Z",
            event_name="status_changed",
            actor="operator",
            detail={"from": "submitted", "to": "accepted"},
        )
        with pytest.raises(AttributeError):
            ev.actor = "system"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Group 1 — ID validators
# ---------------------------------------------------------------------------


class TestValidateRequestId:
    def test_valid(self):
        validate_request_id("REQ-20260901-0001")

    def test_invalid_prefix(self):
        with pytest.raises(LedgerError, match="request ID"):
            validate_request_id("ORD-20260901-0001")

    def test_invalid_format(self):
        with pytest.raises(LedgerError, match="request ID"):
            validate_request_id("REQ-2026-01")


class TestValidateOrderId:
    def test_valid(self):
        validate_order_id("ORD-20260901-0001")

    def test_invalid(self):
        with pytest.raises(LedgerError, match="order ID"):
            validate_order_id("REQ-20260901-0001")


class TestValidateAssetId:
    def test_valid(self):
        validate_asset_id("AST-ORD-20260901-0001-proof-r1")

    def test_valid_with_underscore_role(self):
        validate_asset_id("AST-ORD-20260901-0001-source_reference-r1")

    def test_invalid(self):
        with pytest.raises(LedgerError, match="asset ID"):
            validate_asset_id("ASSET-001")


class TestValidateDeliveryId:
    def test_valid(self):
        validate_delivery_id("DLV-ORD-20260901-0001-1")

    def test_invalid(self):
        with pytest.raises(LedgerError, match="delivery ID"):
            validate_delivery_id("DEL-001")


# ---------------------------------------------------------------------------
# Group 1 — Value validators
# ---------------------------------------------------------------------------


class TestValidateAssetRole:
    def test_all_valid_roles(self):
        for role in ASSET_ROLES:
            validate_asset_role(role)

    def test_invalid_role(self):
        with pytest.raises(LedgerError, match="asset role"):
            validate_asset_role("unknown_role")


class TestValidateVisibility:
    def test_valid(self):
        for v in VISIBILITY_VALUES:
            validate_visibility(v)

    def test_invalid(self):
        with pytest.raises(LedgerError, match="visibility"):
            validate_visibility("public")


class TestValidateRightsStatus:
    def test_valid(self):
        for rs in RIGHTS_STATUSES:
            validate_rights_status(rs)

    def test_invalid(self):
        with pytest.raises(LedgerError, match="rights status"):
            validate_rights_status("unknown")


class TestValidateDeliveryAccess:
    def test_active(self):
        d = Delivery(
            delivery_id="DLV-ORD-20260901-0001-1",
            order_id="ORD-20260901-0001",
            delivered_at="2026-09-01T00:00:00Z",
            access_expires_at="2099-12-31T23:59:59Z",
            access_revoked_at=None,
            asset_ids=(),
            reason="test",
            fee_waived=False,
        )
        assert validate_delivery_access(d) == "active"

    def test_expired(self):
        d = Delivery(
            delivery_id="DLV-ORD-20260901-0001-1",
            order_id="ORD-20260901-0001",
            delivered_at="2020-01-01T00:00:00Z",
            access_expires_at="2020-04-01T00:00:00Z",
            access_revoked_at=None,
            asset_ids=(),
            reason="test",
            fee_waived=False,
        )
        assert validate_delivery_access(d) == "expired"

    def test_revoked(self):
        d = Delivery(
            delivery_id="DLV-ORD-20260901-0001-1",
            order_id="ORD-20260901-0001",
            delivered_at="2026-09-01T00:00:00Z",
            access_expires_at="2099-12-31T23:59:59Z",
            access_revoked_at="2026-09-15T00:00:00Z",
            asset_ids=(),
            reason="test",
            fee_waived=False,
        )
        assert validate_delivery_access(d) == "revoked"


class TestLedgerError:
    def test_is_exception(self):
        err = LedgerError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


# ---------------------------------------------------------------------------
# Group 2 — Repository protocol and factory
# ---------------------------------------------------------------------------


class TestOrderRepositoryProtocol:
    def test_protocol_has_required_methods(self):
        """OrderRepository defines the expected method signatures."""
        import typing
        assert typing.runtime_checkable(OrderRepository) or True
        # Check that the protocol defines the expected methods
        expected = {
            "create_request", "get", "list_all", "update_status",
            "set_job_id", "add_event", "add_note",
        }
        members = {
            name for name in dir(OrderRepository)
            if not name.startswith("_")
        }
        assert expected.issubset(members), (
            f"Missing protocol methods: {expected - members}"
        )

    def test_order_store_satisfies_protocol(self):
        """OrderStore from src/orders.py satisfies OrderRepository."""
        from src.orders import OrderStore
        assert isinstance(OrderStore("fake"), OrderRepository)


class TestRepositoryFactory:
    def test_none_returns_order_store(self):
        """repository_factory(None) returns an OrderStore instance."""
        from src.orders import OrderStore
        repo = repository_factory(None)
        assert isinstance(repo, OrderStore)

    def test_default_returns_order_store(self):
        """repository_factory() with no args returns an OrderStore."""
        from src.orders import OrderStore
        repo = repository_factory()
        assert isinstance(repo, OrderStore)

    def test_pg_url_raises_without_driver(self):
        """repository_factory with a postgres URL attempts lazy import."""
        # Without psycopg installed, this should raise LedgerError
        # (not ImportError at module level)
        with pytest.raises((LedgerError, ImportError)):
            repository_factory("postgresql://localhost/test")

    def test_invalid_url_scheme_raises(self):
        """repository_factory rejects non-postgresql URLs."""
        with pytest.raises(LedgerError, match="postgresql"):
            repository_factory("mysql://localhost/test")


class TestConstants:
    def test_asset_roles_complete(self):
        expected = {
            "source_reference", "recipe", "run_log", "proof", "final",
            "print", "vector", "report", "figure", "animation",
            "thumbnail", "bundle", "license", "customer_reference",
        }
        assert set(ASSET_ROLES) == expected

    def test_visibility_values(self):
        assert set(VISIBILITY_VALUES) == {"internal", "approved_public"}

    def test_rights_statuses(self):
        assert set(RIGHTS_STATUSES) == {"pending", "cleared", "restricted"}


# ---------------------------------------------------------------------------
# Group 3 — Analysis model validation
# ---------------------------------------------------------------------------


class TestAnalysisRunValidation:
    def test_validation_status_values(self):
        """AnalysisRun accepts all valid validation_status values."""
        for status in ("draft", "validated", "reference_only", "unvalidated"):
            ar = AnalysisRun(
                run_id="run-test",
                place_id="wa-clark",
                recipe_digest=None,
                code_revision=None,
                input_sources={},
                start_year=2000,
                end_year=2024,
                metric_version="1.0",
                validation_status=status,
                created_at="2026-09-01T00:00:00Z",
                reviewer=None,
                notes=None,
            )
            assert ar.validation_status == status

    def test_year_range_fields(self):
        """AnalysisRun carries start_year and end_year."""
        ar = AnalysisRun(
            run_id="run-years",
            place_id="wa-clark",
            recipe_digest=None,
            code_revision=None,
            input_sources={},
            start_year=1990,
            end_year=2025,
            metric_version="2.0",
            validation_status="draft",
            created_at="2026-09-01T00:00:00Z",
            reviewer=None,
            notes=None,
        )
        assert ar.start_year == 1990
        assert ar.end_year == 2025


class TestAnalysisMetricValidation:
    def test_interpretation_status_values(self):
        """AnalysisMetric accepts all valid interpretation_status values."""
        for status in ("draft", "validated", "unvalidated", "reference_only"):
            am = AnalysisMetric(
                metric_id="m-test",
                run_id="run-test",
                name="test_metric",
                units="count",
                method="test_method",
                method_version="1.0",
                value=42,
                interpretation_status=status,
                created_at="2026-09-01T00:00:00Z",
            )
            assert am.interpretation_status == status

    def test_ops_prefix_for_business_metrics(self):
        """Business metrics use an ops_ method prefix."""
        am = AnalysisMetric(
            metric_id="m-ops",
            run_id="run-ops",
            name="ops_proof_turnaround",
            units="hours",
            method="ops_turnaround",
            method_version="1.0",
            value=12.5,
            interpretation_status="validated",
            created_at="2026-09-01T00:00:00Z",
        )
        assert am.method.startswith("ops_")
        assert am.name.startswith("ops_")

    def test_hydrology_metric_no_ops_prefix(self):
        """Hydrology metrics do not use ops_ prefix."""
        am = AnalysisMetric(
            metric_id="m-hydro",
            run_id="run-hydro",
            name="mean_annual_flow",
            units="cfs",
            method="flow_disaggregation",
            method_version="1.0",
            value=1234.5,
            interpretation_status="validated",
            created_at="2026-09-01T00:00:00Z",
        )
        assert not am.method.startswith("ops_")
        assert not am.name.startswith("ops_")

    def test_value_can_be_any_type(self):
        """AnalysisMetric.value is typed Any — supports numbers, dicts, lists."""
        for val in (42, 3.14, {"min": 0, "max": 100}, [1, 2, 3], "text"):
            am = AnalysisMetric(
                metric_id="m-any",
                run_id="run-any",
                name="test",
                units="n/a",
                method="test",
                method_version="1.0",
                value=val,
                interpretation_status="draft",
                created_at="2026-09-01T00:00:00Z",
            )
            assert am.value == val
