"""Tests for src/ledger_pg.py — PostgreSQL adapter (offline, mocked psycopg).

All tests use a fake connection/cursor to verify SQL building, validation,
and transaction semantics. No real database connection is made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.fulfillment import OrderError
from src.ledger import (
    Asset,
    Delivery,
    LedgerError,
    validate_delivery_access,
)

# ---------------------------------------------------------------------------
# Fake psycopg objects
# ---------------------------------------------------------------------------


class FakeCursor:
    """Mimics psycopg cursor with multi-query row support.

    Rows are consumed per-query: the first fetchone/fetchall after an execute
    returns from the queue. Each ``execute`` call shifts to the next result set.
    """

    def __init__(self, result_sets=None):
        # result_sets: list of list-of-tuples, one per query
        self._result_sets: list[list[tuple]] = list(result_sets or [])
        self._current: list[tuple] = []
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self._result_sets:
            self._current = self._result_sets.pop(0)
        else:
            self._current = []

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeConnection:
    """Mimics psycopg connection with commit/rollback and cursor factory."""

    def __init__(self, cursor=None):
        self._cursor = cursor or FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.autocommit = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _make_repo(conn=None, cursor=None):
    """Build a PgOrderRepository with a fake connection injected."""
    if conn is None:
        conn = FakeConnection(cursor=cursor or FakeCursor())

    fake_psycopg = MagicMock()
    fake_psycopg.connect.return_value = conn

    with patch.dict("sys.modules", {"psycopg": fake_psycopg}):
        from src.ledger_pg import PgOrderRepository
        repo = PgOrderRepository.__new__(PgOrderRepository)
        repo._conn = conn
        repo._url = "postgresql://localhost/test"
    return repo, conn


# A row matching the SELECT in PgOrderRepository.get():
# (request_id, email, product, status, place_id, payload,
#  created_at, updated_at)
_REQ_ROW = (
    "REQ-20260901-0001", "test@example.com", "neon-basin 18x24",
    "submitted", None, '{"region":"Washington"}',
    "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z",
)

_FULFILLED_ROW = (
    "REQ-20260901-0001", "test@example.com", "neon-basin 18x24",
    "fulfilled", None, '{}',
    "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPgLazyImport:
    def test_module_importable_without_psycopg(self):
        """src/ledger_pg.py can be imported even when psycopg is absent."""
        import importlib
        import sys
        had = "psycopg" in sys.modules
        saved = sys.modules.pop("psycopg", None)
        sys.modules.pop("src.ledger_pg", None)
        try:
            mod = importlib.import_module("src.ledger_pg")
            assert hasattr(mod, "PgOrderRepository")
        finally:
            if had and saved is not None:
                sys.modules["psycopg"] = saved


class TestCreateRequest:
    def test_insert_uses_parameterized_query(self):
        # create_request does: INSERT requests, INSERT events, commit,
        # then self.get() -> SELECT requests, SELECT events
        cursor = FakeCursor(result_sets=[
            [],           # INSERT requests
            [],           # INSERT events
            [_REQ_ROW],   # SELECT requests (from get())
            [],           # SELECT events (from get())
        ])
        repo, _conn = _make_repo(cursor=cursor)
        payload = {
            "email": "test@example.com",
            "product": "neon-basin 18x24",
            "region": "Washington",
            "county": "Clark",
            "style": "neon-basin",
            "size": "18x24",
            "formats": ["png"],
            "order_id": "REQ-20260901-0001",
        }
        repo.create_request(payload)
        # Should have executed INSERT statements
        assert any("INSERT" in sql for sql, _ in cursor.executed)
        # All queries with params must use %s placeholders
        for sql, params in cursor.executed:
            if params is not None:
                assert "%s" in sql

    def test_create_request_commits(self):
        cursor = FakeCursor(result_sets=[
            [], [], [_REQ_ROW], [],
        ])
        repo, conn = _make_repo(cursor=cursor)
        payload = {
            "email": "test@example.com",
            "product": "neon-basin 18x24",
            "order_id": "REQ-20260901-0001",
        }
        repo.create_request(payload)
        assert conn.committed


class TestGet:
    def test_get_builds_select(self):
        cursor = FakeCursor(result_sets=[
            [_REQ_ROW],  # SELECT requests
            [],          # SELECT events
        ])
        repo, _conn = _make_repo(cursor=cursor)
        result = repo.get("REQ-20260901-0001")
        # Should have issued a SELECT with parameterized query
        sel = [(sql, p) for sql, p in cursor.executed if "SELECT" in sql]
        assert len(sel) >= 1
        sql, params = sel[0]
        assert "%s" in sql
        assert params is not None
        assert result.request_id == "REQ-20260901-0001"

    def test_get_raises_key_error_when_missing(self):
        cursor = FakeCursor(result_sets=[
            [],  # SELECT returns no rows
        ])
        repo, _conn = _make_repo(cursor=cursor)
        with pytest.raises(KeyError):
            repo.get("REQ-99999999-0001")


class TestUpdateStatus:
    def test_validates_transition(self):
        """update_status checks the state machine before issuing UPDATE."""
        cursor = FakeCursor(result_sets=[
            [_FULFILLED_ROW],  # SELECT requests (from get())
            [],                # SELECT events (from get())
        ])
        repo, _conn = _make_repo(cursor=cursor)
        with pytest.raises(OrderError):
            # fulfilled -> accepted is not allowed
            repo.update_status("REQ-20260901-0001", "accepted")


class TestRecordAsset:
    def test_transactional_insert(self):
        """record_asset should INSERT asset + event in one commit."""
        cursor = FakeCursor()
        repo, conn = _make_repo(cursor=cursor)
        asset = Asset(
            asset_id="AST-ORD-20260901-0001-proof-r1",
            order_id="ORD-20260901-0001",
            render_job_id="JOB-001",
            role="proof",
            storage_key="library/proof.png",
            checksum_sha256="abc123",
            byte_count=1024,
            width_px=3600,
            height_px=4800,
            media_type="image/png",
            visibility="internal",
            rights_status="pending",
            source_attribution="USGS NHDPlus HR",
            created_at="2026-09-01T00:00:00Z",
            retention_class=None,
            retain_until=None,
            deleted_at=None,
        )
        repo.record_asset(asset)
        assert any("INSERT" in sql and "assets" in sql.lower()
                    for sql, _ in cursor.executed)
        # Event INSERT also fired
        assert any("INSERT" in sql and "events" in sql.lower()
                    for sql, _ in cursor.executed)
        assert conn.committed


class TestRecordDelivery:
    def test_inserts_and_commits(self):
        cursor = FakeCursor()
        repo, conn = _make_repo(cursor=cursor)
        delivery = Delivery(
            delivery_id="DLV-ORD-20260901-0001-1",
            order_id="ORD-20260901-0001",
            delivered_at="2026-09-01T00:00:00Z",
            access_expires_at="2026-11-30T00:00:00Z",
            access_revoked_at=None,
            asset_ids=("AST-ORD-20260901-0001-final-r1",),
            reason="initial delivery",
            fee_waived=False,
        )
        repo.record_delivery(delivery)
        assert any("INSERT" in sql and "deliveries" in sql.lower()
                    for sql, _ in cursor.executed)
        assert conn.committed


class TestGetAssetsForOrder:
    def test_returns_asset_list(self):
        asset_row = (
            "AST-ORD-20260901-0001-proof-r1", "ORD-20260901-0001",
            "JOB-001", "proof", "library/proof.png", "abc123",
            1024, 3600, 4800, "image/png", "internal", "pending",
            "USGS NHDPlus HR", "2026-09-01T00:00:00Z",
            None, None, None,
        )
        cursor = FakeCursor(result_sets=[
            [asset_row],
        ])
        repo, _conn = _make_repo(cursor=cursor)
        assets = repo.get_assets_for_order("ORD-20260901-0001")
        assert isinstance(assets, list)
        assert len(assets) == 1
        assert isinstance(assets[0], Asset)
        assert assets[0].asset_id == "AST-ORD-20260901-0001-proof-r1"


class TestDeliveryAccess:
    def test_active_delivery(self):
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

    def test_revoked_delivery(self):
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


class TestConnectionFailure:
    def test_connection_error_raises_ledger_error(self):
        fake_psycopg = MagicMock()
        fake_psycopg.connect.side_effect = Exception("connection refused")

        with patch.dict("sys.modules", {"psycopg": fake_psycopg}):
            import importlib
            import sys
            sys.modules.pop("src.ledger_pg", None)
            mod = importlib.import_module("src.ledger_pg")
            with pytest.raises(LedgerError, match="connection"):
                mod.PgOrderRepository("postgresql://bad-host/db")


class TestNoStringInterpolation:
    def test_all_queries_use_parameterized_placeholders(self):
        """Verify no f-string SQL building in the module source."""
        from pathlib import Path
        source = (Path(__file__).parent.parent / "src" / "ledger_pg.py").read_text()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith(("#", '"""')):
                continue
            sql_kws = ("INSERT", "SELECT", "UPDATE", "DELETE", "WHERE")
            has_sql = any(kw in line.upper() for kw in sql_kws)
            if has_sql:
                assert "f'" not in line and 'f"' not in line, (
                    f"Line {i} uses f-string with SQL: {line.strip()}"
                )
