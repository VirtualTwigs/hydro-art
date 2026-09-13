"""Tests for the order store (concierge ordering flow).

Offline — no GDAL, no network. Uses tmp_path for the JSON file store.
"""

from __future__ import annotations

import json

import pytest

from src.fulfillment import OrderError
from src.orders import STATUSES, TRANSITIONS, OrderStore, Request


def _valid_payload(**overrides):
    """A minimal valid order payload."""
    base = {
        "email": "buyer@example.com",
        "product": "Fine-art print",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "18x24",
        "formats": ["png"],
    }
    base.update(overrides)
    return base


class TestCreateRequest:
    def test_creates_request_with_valid_payload(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())

        assert req.request_id.startswith("REQ-")
        assert req.status == "submitted"
        assert req.email == "buyer@example.com"
        assert req.product == "Fine-art print"
        assert req.order["region"] == "Washington"
        assert req.order["county"] == "Clark"
        assert req.order["style"] == "neon-basin"

    def test_persists_to_json_file(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())

        path = tmp_path / "orders" / f"{req.request_id}.json"
        assert path.is_file()
        data = json.loads(path.read_text("utf-8"))
        assert data["request_id"] == req.request_id

    def test_sequential_ids(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        r1 = store.create_request(_valid_payload())
        r2 = store.create_request(_valid_payload())

        seq1 = int(r1.request_id.rsplit("-", 1)[-1])
        seq2 = int(r2.request_id.rsplit("-", 1)[-1])
        assert seq2 == seq1 + 1

    def test_rejects_missing_email(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(OrderError, match="email"):
            store.create_request(_valid_payload(email=""))

    def test_rejects_missing_product(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(OrderError, match="product"):
            store.create_request(_valid_payload(product=""))

    def test_rejects_invalid_region(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(OrderError, match="region"):
            store.create_request(_valid_payload(region="Alaska"))

    def test_rejects_invalid_style(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(OrderError, match="style"):
            store.create_request(_valid_payload(style="watercolor"))


class TestGetRequest:
    def test_retrieves_by_id(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        created = store.create_request(_valid_payload())
        fetched = store.get(created.request_id)

        assert fetched.request_id == created.request_id
        assert fetched.email == created.email

    def test_raises_key_error_for_unknown_id(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(KeyError):
            store.get("REQ-00000000-9999")


class TestListAll:
    def test_returns_all_requests(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        store.create_request(_valid_payload())
        store.create_request(_valid_payload(county="King"))

        results = store.list_all()
        assert len(results) == 2

    def test_returns_empty_for_no_orders(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        assert store.list_all() == []

    def test_returns_empty_for_missing_dir(self, tmp_path):
        store = OrderStore(tmp_path / "nonexistent")
        assert store.list_all() == []


class TestUpdateStatus:
    def test_valid_transition(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())

        updated = store.update_status(req.request_id, "accepted")
        assert updated.status == "accepted"

        # Verify persisted.
        fetched = store.get(req.request_id)
        assert fetched.status == "accepted"

    def test_invalid_transition_raises(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())

        with pytest.raises(OrderError, match="Cannot transition"):
            store.update_status(req.request_id, "fulfilled")

    def test_proof_ready_can_go_back_to_submitted(self, tmp_path):
        """Revision request sends order back to submitted."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())
        store.update_status(req.request_id, "accepted")
        store.update_status(req.request_id, "rendering")
        store.update_status(req.request_id, "proof_ready")
        updated = store.update_status(req.request_id, "submitted")
        assert updated.status == "submitted"

    def test_full_lifecycle(self, tmp_path):
        """Walk the entire happy path."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())
        for status in ("accepted", "rendering", "proof_ready", "approved", "fulfilled"):
            req = store.update_status(req.request_id, status)
        assert req.status == "fulfilled"

    def test_unknown_id_raises_key_error(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        with pytest.raises(KeyError):
            store.update_status("REQ-00000000-9999", "accepted")


class TestSetJobId:
    def test_links_job_to_request(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())
        updated = store.set_job_id(req.request_id, "job-abc123")

        assert updated.job_id == "job-abc123"
        fetched = store.get(req.request_id)
        assert fetched.job_id == "job-abc123"


class TestAddNote:
    def test_appends_timestamped_note(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())
        updated = store.add_note(req.request_id, "Accepted by coordinator")

        assert len(updated.notes) == 1
        assert "Accepted by coordinator" in updated.notes[0]


class TestRequestSerialization:
    def test_round_trip(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_valid_payload())
        d = req.to_dict()
        restored = Request.from_dict(d)

        assert restored.request_id == req.request_id
        assert restored.email == req.email
        assert restored.order == req.order


class TestTransitionTable:
    def test_all_statuses_have_transition_entry(self):
        for status in STATUSES:
            assert status in TRANSITIONS

    def test_fulfilled_is_terminal(self):
        assert TRANSITIONS["fulfilled"] == frozenset()
