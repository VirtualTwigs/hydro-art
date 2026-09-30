"""Integration tests for the operations ledger wiring (Groups 3-7).

Verifies: JSON fallback works, PG selected when DATABASE_URL set (mocked),
order lifecycle works without DB, repository_factory returns correct types.

All offline — no database, no network, no GDAL.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ledger import LedgerError, OrderRepository, repository_factory
from src.orders import OrderStore


class TestJsonFallback:
    def test_factory_returns_order_store_without_url(self):
        """repository_factory(None) returns an OrderStore (JSON fallback)."""
        repo = repository_factory(None)
        assert isinstance(repo, OrderStore)

    def test_order_store_satisfies_protocol(self):
        """OrderStore is a valid OrderRepository."""
        store = OrderStore("fake_dir")
        assert isinstance(store, OrderRepository)

    def test_json_lifecycle_without_database(self, tmp_path):
        """Full order lifecycle works using JSON store, no database needed."""
        store = OrderStore(tmp_path / "orders")
        # Create
        req = store.create_request({
            "email": "test@example.com",
            "product": "neon-basin 18x24",
            "order_id": "test-lifecycle",
            "region": "Washington",
            "county": "Clark",
            "style": "neon-basin",
            "size": "18x24",
            "formats": ["png"],
        })
        assert req.status == "submitted"
        assert req.request_id.startswith("REQ-")

        # Transition
        req = store.update_status(req.request_id, "accepted")
        assert req.status == "accepted"

        # Add event
        req = store.add_event(req.request_id, "test_event", {"key": "val"})
        assert any(e["event"] == "test_event" for e in req.events)

        # List
        all_reqs = store.list_all()
        assert len(all_reqs) == 1


class TestPgSelection:
    def test_pg_selected_when_url_set(self):
        """repository_factory returns PgOrderRepository when DATABASE_URL is set.

        Uses a mocked psycopg to avoid real connection.
        """
        fake_conn = MagicMock()
        fake_psycopg = MagicMock()
        fake_psycopg.connect.return_value = fake_conn

        with patch.dict("sys.modules", {"psycopg": fake_psycopg}):
            # Clear cached module
            import sys
            sys.modules.pop("src.ledger_pg", None)
            repo = repository_factory("postgresql://localhost/test")
            # Should not be an OrderStore
            assert not isinstance(repo, OrderStore)
            # Should have connected
            fake_psycopg.connect.assert_called_once()

    def test_invalid_scheme_raises(self):
        """Non-postgresql URLs are rejected."""
        with pytest.raises(LedgerError, match="postgresql"):
            repository_factory("mysql://localhost/test")
