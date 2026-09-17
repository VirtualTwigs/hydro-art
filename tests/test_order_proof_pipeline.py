"""Integration tests for the order → proof lifecycle.

Exercises the full submit → auto-accept → render → proof_ready cycle
with fake pipeline components. Offline — no GDAL, no network.
"""

from __future__ import annotations

import json

from src.orders import OrderStore
from src.proof import sign_proof_url, verify_proof_token
from src.server import handle_request


class FakeRunner:
    """Minimal runner that tracks submissions and allows completing jobs."""

    def __init__(self):
        self._jobs = {}
        self._counter = 0
        self.submitted = []

    def submit(self, payload):
        self._counter += 1
        job_id = f"job-{self._counter:04d}"
        self._jobs[job_id] = {"state": "running", "payload": payload}
        self.submitted.append((job_id, payload))
        return job_id

    def complete(self, job_id):
        self._jobs[job_id]["state"] = "succeeded"

    def status(self, job_id):
        if job_id not in self._jobs:
            raise KeyError(job_id)
        return self._jobs[job_id]


def _order_payload(**overrides):
    base = {
        "email": "buyer@example.com",
        "product": "digital_image",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "18x24",
        "formats": ["png"],
    }
    base.update(overrides)
    return base


def _submit_order(runner, store, tmp_path, secret, **overrides):
    """Submit an order via the server and return (response_data, request_id)."""
    payload = json.dumps(_order_payload(**overrides)).encode()
    resp = handle_request(
        runner, "POST", "/api/orders", payload,
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    data = json.loads(resp.body)
    return data, data.get("request_id")


class TestFullOrderToProofCycle:
    def test_submit_auto_dispatches_and_transitions(self, tmp_path):
        """submit → auto-accept → rendering (with job dispatched)."""
        store = OrderStore(tmp_path / "orders")
        runner = FakeRunner()
        secret = b"test-secret"

        data, request_id = _submit_order(runner, store, tmp_path, secret)

        assert data["status"] == "rendering"
        assert data["job_id"] is not None
        assert len(runner.submitted) == 1

        # Verify the request is persisted in rendering state
        req = store.get(request_id)
        assert req.status == "rendering"

    def test_proof_ready_after_render_complete(self, tmp_path):
        """After render completes, transition to proof_ready works."""
        store = OrderStore(tmp_path / "orders")
        runner = FakeRunner()
        secret = b"test-secret"

        _data, request_id = _submit_order(runner, store, tmp_path, secret)
        # Simulate render completion
        store.update_status(request_id, "proof_ready")
        req = store.get(request_id)
        assert req.status == "proof_ready"

        # Sign a proof token and verify it works
        token = sign_proof_url(request_id, secret, expires_in=3600)
        rid, valid = verify_proof_token(token, secret)
        assert valid is True
        assert rid == request_id


class TestRevisionCycle:
    def test_adjust_triggers_new_render(self, tmp_path):
        """submit → proof → adjust → re-render → new proof."""
        store = OrderStore(tmp_path / "orders")
        runner = FakeRunner()
        secret = b"test-secret"

        data, request_id = _submit_order(runner, store, tmp_path, secret)
        store.update_status(request_id, "proof_ready")

        # Generate proof token and adjust
        token = sign_proof_url(request_id, secret, expires_in=3600)
        resp = handle_request(
            runner, "POST", f"/api/proof/{token}/adjust", b"{}",
            web_root=str(tmp_path), order_store=store, proof_secret=secret,
        )
        assert resp.status == 202
        data = json.loads(resp.body)
        assert data["status"] == "rendering"
        assert len(runner.submitted) == 2  # Two renders dispatched

        # Complete second render, go to proof_ready again
        store.update_status(request_id, "proof_ready")
        req = store.get(request_id)
        assert req.status == "proof_ready"


class TestEventLogCompleteCycle:
    def test_all_events_present(self, tmp_path):
        """A full submit → proof → approve cycle produces ≥6 events."""
        store = OrderStore(tmp_path / "orders")
        runner = FakeRunner()
        secret = b"test-secret"

        _data, request_id = _submit_order(runner, store, tmp_path, secret)
        # submitted(1) + accepted(2) + rendering(3)
        store.update_status(request_id, "proof_ready")  # 4
        token = sign_proof_url(request_id, secret, expires_in=3600)

        resp = handle_request(
            runner, "POST", f"/api/proof/{token}/approve", b"",
            web_root=str(tmp_path), order_store=store, proof_secret=secret,
        )
        assert resp.status == 200

        req = store.get(request_id)
        assert req.status == "approved"
        # submitted, accepted, rendering, proof_ready, approved = 5 events minimum
        assert len(req.events) >= 5
        event_types = [e["event"] for e in req.events]
        assert "submitted" in event_types
        assert "accepted" in event_types
        assert "rendering" in event_types
        assert "proof_ready" in event_types
        assert "approved" in event_types


class TestConcurrentOrdersIsolated:
    def test_two_orders_independent(self, tmp_path):
        """Two orders don't interfere with each other."""
        store = OrderStore(tmp_path / "orders")
        runner = FakeRunner()
        secret = b"test-secret"

        data1, rid1 = _submit_order(runner, store, tmp_path, secret, county="Clark")
        data2, rid2 = _submit_order(runner, store, tmp_path, secret, county="King")

        assert rid1 != rid2
        assert data1["status"] == "rendering"
        assert data2["status"] == "rendering"

        # Advance only order 1
        store.update_status(rid1, "proof_ready")
        token1 = sign_proof_url(rid1, secret, expires_in=3600)
        handle_request(
            runner, "POST", f"/api/proof/{token1}/approve", b"",
            web_root=str(tmp_path), order_store=store, proof_secret=secret,
        )

        # Order 1 approved, order 2 still rendering
        assert store.get(rid1).status == "approved"
        assert store.get(rid2).status == "rendering"
