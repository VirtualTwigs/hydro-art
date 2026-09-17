"""Tests for the delivery email module.

Offline — uses a fake sender, never touches SMTP.
"""

from __future__ import annotations

from src.email_delivery import (
    _build_confirmation_message,
    _build_message,
    send_confirmation_email,
    send_delivery_email,
)


class FakeSender:
    def __init__(self, *, fail=False):
        self.sent = []
        self._fail = fail

    def send(self, msg):
        if self._fail:
            raise ConnectionError("SMTP unavailable")
        self.sent.append(msg)


class TestBuildMessage:
    def test_subject_contains_order_id(self):
        msg = _build_message("a@b.com", "REQ-001", "http://x", product="Print", location="Clark, WA")
        assert "REQ-001" in msg["Subject"]

    def test_to_and_from(self):
        msg = _build_message("buyer@example.com", "REQ-001", "http://x")
        assert msg["To"] == "buyer@example.com"
        assert msg["From"] == "neiljrunde@gmail.com"

    def test_has_plain_and_html_parts(self):
        msg = _build_message("a@b.com", "REQ-001", "http://x")
        payloads = msg.get_payload()
        types = [p.get_content_type() for p in payloads]
        assert "text/plain" in types
        assert "text/html" in types

    def test_delivery_url_in_body(self):
        msg = _build_message("a@b.com", "REQ-001", "http://localhost:8765/delivery.html?order=REQ-001")
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "http://localhost:8765/delivery.html?order=REQ-001" in plain


class TestSendDeliveryEmail:
    def test_sends_via_fake_sender(self):
        sender = FakeSender()
        result = send_delivery_email(
            "buyer@example.com", "REQ-001", "http://x",
            product="Print", location="Clark, WA", sender=sender,
        )
        assert result is True
        assert len(sender.sent) == 1
        assert sender.sent[0]["To"] == "buyer@example.com"

    def test_returns_false_on_failure(self):
        sender = FakeSender(fail=True)
        result = send_delivery_email(
            "buyer@example.com", "REQ-001", "http://x", sender=sender,
        )
        assert result is False

    def test_includes_product_and_location(self):
        sender = FakeSender()
        send_delivery_email(
            "a@b.com", "REQ-001", "http://x",
            product="Fine-art print", location="Skamania County, Washington",
            sender=sender,
        )
        plain = sender.sent[0].get_payload()[0].get_payload(decode=True).decode()
        assert "Fine-art print" in plain
        assert "Skamania County, Washington" in plain


class TestSendProofEmail:
    def test_sends_proof_email_with_signed_url(self):
        from src.email_delivery import send_proof_email

        sender = FakeSender()
        result = send_proof_email(
            "buyer@example.com",
            "REQ-001",
            "http://localhost:8765/proof.html?token=abc123",
            title="Clark County Watersheds",
            sender=sender,
        )
        assert result is True
        assert len(sender.sent) == 1
        msg = sender.sent[0]
        assert msg["To"] == "buyer@example.com"
        assert "REQ-001" in msg["Subject"]

    def test_proof_email_contains_proof_url(self):
        from src.email_delivery import send_proof_email

        sender = FakeSender()
        proof_url = "http://localhost:8765/proof.html?token=xyz"
        send_proof_email("a@b.com", "REQ-001", proof_url, sender=sender)
        plain = sender.sent[0].get_payload()[0].get_payload(decode=True).decode()
        assert proof_url in plain

    def test_proof_email_degrades_gracefully(self):
        from src.email_delivery import send_proof_email

        sender = FakeSender(fail=True)
        result = send_proof_email("a@b.com", "REQ-001", "http://x", sender=sender)
        assert result is False


class TestSendConfirmationEmail:
    def test_sends_via_fake_sender(self):
        sender = FakeSender()
        result = send_confirmation_email(
            "buyer@example.com",
            "REQ-001",
            product="Fine-art print",
            location="Clark County, Washington",
            sender=sender,
        )
        assert result is True
        assert len(sender.sent) == 1
        assert sender.sent[0]["Subject"] == "We received your Hydro-Art request — REQ-001"

    def test_confirmation_includes_request_details(self):
        msg = _build_confirmation_message(
            "buyer@example.com",
            "REQ-001",
            product="Fine-art print",
            location="Clark County, Washington",
        )
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "REQ-001" in plain
        assert "Fine-art print" in plain
        assert "Clark County, Washington" in plain
