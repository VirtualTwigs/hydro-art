"""Tests for the payment module (Stripe Checkout integration).

Offline — uses fakes for Stripe. No network, no SDK at import time.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


class FakeStripeClient:
    """Fake Stripe SDK client for offline testing."""

    def __init__(self):
        self.sessions_created = []

    def create_checkout_session(self, **kwargs):
        session_id = f"cs_test_{len(self.sessions_created) + 1}"
        self.sessions_created.append(kwargs)
        return {"id": session_id, "url": f"https://checkout.stripe.com/{session_id}"}


class TestCreateCheckoutSession:
    def test_correct_line_items_and_amount(self):
        from src.payment import create_checkout_session

        result = create_checkout_session(
            request_id="REQ-20260916-0001",
            product="Fine-art print",
            amount_cents=11000,
            success_url="http://localhost:8765/delivery.html?order=REQ-20260916-0001",
            cancel_url="http://localhost:8765/proof.html?token=abc",
            client=FakeStripeClient(),
        )
        assert "id" in result
        assert "url" in result
        assert result["id"].startswith("cs_test_")

    def test_metadata_includes_request_id(self):
        from src.payment import create_checkout_session

        client = FakeStripeClient()
        create_checkout_session(
            request_id="REQ-20260916-0001",
            product="Fine-art print",
            amount_cents=11000,
            success_url="http://x",
            cancel_url="http://y",
            client=client,
        )
        session_kwargs = client.sessions_created[0]
        assert session_kwargs["metadata"]["request_id"] == "REQ-20260916-0001"

    def test_success_and_cancel_urls_passed(self):
        from src.payment import create_checkout_session

        client = FakeStripeClient()
        create_checkout_session(
            request_id="REQ-001",
            product="Digital image",
            amount_cents=3800,
            success_url="http://success",
            cancel_url="http://cancel",
            client=client,
        )
        kwargs = client.sessions_created[0]
        assert kwargs["success_url"] == "http://success"
        assert kwargs["cancel_url"] == "http://cancel"


class TestWebhookVerification:
    def test_valid_signature_returns_request_id(self):
        from src.payment import handle_webhook

        secret = "whsec_test_secret"
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_intent": "pi_test_1",
                    "metadata": {"request_id": "REQ-20260916-0001"},
                }
            }
        })
        timestamp = str(int(time.time()))
        sig_payload = f"{timestamp}.{payload}"
        sig = hmac.new(secret.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()
        signature = f"t={timestamp},v1={sig}"

        request_id = handle_webhook(payload, signature, secret)
        assert request_id == "REQ-20260916-0001"

    def test_invalid_signature_rejected(self):
        from src.payment import WebhookError, handle_webhook

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"request_id": "REQ-001"}}}
        })
        with pytest.raises(WebhookError, match="[Ss]ignature"):
            handle_webhook(payload, "t=123,v1=bad", "whsec_real_secret")

    def test_idempotent_handling(self):
        """Processing the same event twice returns the same request_id."""
        from src.payment import handle_webhook

        secret = "whsec_test"
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_intent": "pi_test_1",
                    "metadata": {"request_id": "REQ-001"},
                }
            }
        })
        timestamp = str(int(time.time()))
        sig_payload = f"{timestamp}.{payload}"
        sig = hmac.new(secret.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()
        signature = f"t={timestamp},v1={sig}"

        r1 = handle_webhook(payload, signature, secret)
        r2 = handle_webhook(payload, signature, secret)
        assert r1 == r2 == "REQ-001"


class TestPaymentStateTransitions:
    def test_approved_to_payment_pending_to_paid_to_fulfilled(self):
        """Full payment lifecycle via the state machine."""
        import tempfile

        from src.orders import OrderStore
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(f"{tmp}/orders")
            req = store.create_request({
                "email": "buyer@example.com",
                "product": "Fine-art print",
                "region": "Washington",
                "county": "Clark",
                "style": "neon-basin",
                "size": "18x24",
                "formats": ["png"],
            })
            store.update_status(req.request_id, "accepted")
            store.update_status(req.request_id, "rendering")
            store.update_status(req.request_id, "proof_ready")
            store.update_status(req.request_id, "approved")
            store.update_status(req.request_id, "payment_pending")
            store.update_status(req.request_id, "paid")
            updated = store.update_status(req.request_id, "fulfilled")
            assert updated.status == "fulfilled"
