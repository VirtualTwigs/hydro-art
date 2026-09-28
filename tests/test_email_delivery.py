"""Tests for the delivery email module.

Offline — uses a fake sender, never touches SMTP.
"""

from __future__ import annotations

from src.email_delivery import (
    _build_confirmation_message,
    _build_message,
    _build_proof_message,
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

    def test_delivery_plain_uses_riverglyph_brand(self):
        msg = _build_message("a@b.com", "REQ-001", "http://x")
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "Riverglyph" in plain
        assert "Hydro-Art" not in plain

    def test_delivery_html_uses_riverglyph_brand(self):
        msg = _build_message("a@b.com", "REQ-001", "http://x")
        html = msg.get_payload()[1].get_payload(decode=True).decode()
        assert "Riverglyph" in html
        assert "Hydro&#9671;Art" not in html

    def test_delivery_keeps_runde_strategies_footer(self):
        msg = _build_message("a@b.com", "REQ-001", "http://x")
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "Runde Strategies" in plain


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

    def test_proof_html_uses_riverglyph_brand(self):
        msg = _build_proof_message("a@b.com", "REQ-001", "http://x")
        html = msg.get_payload()[1].get_payload(decode=True).decode()
        assert "Riverglyph" in html
        assert "Hydro&#9671;Art" not in html

    def test_proof_plain_uses_riverglyph_brand(self):
        msg = _build_proof_message("a@b.com", "REQ-001", "http://x")
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "Riverglyph" in plain
        assert "Hydro-Art" not in plain


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
        assert sender.sent[0]["Subject"] == "We received your Riverglyph request — REQ-001"

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

    def test_confirmation_html_uses_riverglyph_brand(self):
        msg = _build_confirmation_message("a@b.com", "REQ-001")
        html = msg.get_payload()[1].get_payload(decode=True).decode()
        assert "Riverglyph" in html
        assert "Hydro&#9671;Art" not in html

    def test_confirmation_plain_uses_riverglyph_brand(self):
        msg = _build_confirmation_message("a@b.com", "REQ-001")
        plain = msg.get_payload()[0].get_payload(decode=True).decode()
        assert "Riverglyph" in plain
        assert "Hydro-Art" not in plain


# --- Coverage gap: SmtpSender.configured (line 45) ---------------------------

class TestSmtpSender:
    def test_configured_false_without_password(self):
        from src.email_delivery import SmtpSender

        sender = SmtpSender(app_password="")
        assert sender.configured is False

    def test_configured_true_with_password(self):
        from src.email_delivery import SmtpSender

        sender = SmtpSender(app_password="test-pass")
        assert sender.configured is True

    def test_send_returns_false_without_password(self):
        from email.mime.multipart import MIMEMultipart

        from src.email_delivery import SmtpSender

        sender = SmtpSender(app_password="")
        msg = MIMEMultipart()
        assert sender.send(msg) is False


# --- Coverage gap: send_*_email exception handling (lines 182-184, 254, 281)

class FakeExplodingSender:
    def send(self, msg):
        raise RuntimeError("boom")


class FakeRefusingSender:
    def send(self, msg):
        return False


class TestEmailFailurePaths:
    def test_send_confirmation_exception_returns_false(self):
        result = send_confirmation_email("a@b.com", "REQ-001", sender=FakeExplodingSender())
        assert result is False

    def test_send_proof_exception_returns_false(self):
        from src.email_delivery import send_proof_email

        result = send_proof_email("a@b.com", "REQ-001", "http://proof", sender=FakeExplodingSender())
        assert result is False

    def test_send_delivery_exception_returns_false(self):
        result = send_delivery_email("a@b.com", "ORD-001", "http://dl", sender=FakeExplodingSender())
        assert result is False

    def test_send_proof_returns_false_on_refusal(self):
        from src.email_delivery import send_proof_email

        result = send_proof_email("a@b.com", "REQ-001", "http://proof", sender=FakeRefusingSender())
        assert result is False

    def test_send_delivery_returns_false_on_refusal(self):
        result = send_delivery_email("a@b.com", "ORD-001", "http://dl", sender=FakeRefusingSender())
        assert result is False


# --- Coverage gap: sender=None fallback to SmtpSender (lines 250, 277) -------


def test_send_proof_email_default_sender_no_password(monkeypatch):
    """send_proof_email with sender=None falls back to SmtpSender (no password → False)."""
    from src.email_delivery import send_proof_email

    monkeypatch.delenv("HYDRO_ART_GMAIL_APP_PASSWORD", raising=False)
    result = send_proof_email("a@b.com", "REQ-001", "http://proof")
    assert result is False


def test_send_delivery_email_default_sender_no_password(monkeypatch):
    """send_delivery_email with sender=None falls back to SmtpSender (no password → False)."""
    monkeypatch.delenv("HYDRO_ART_GMAIL_APP_PASSWORD", raising=False)
    result = send_delivery_email("a@b.com", "ORD-001", "http://dl")
    assert result is False


# --- Coverage gap: SmtpSender.send with monkeypatched SMTP_SSL (lines 53-56) -


def test_smtp_sender_send_with_password(monkeypatch):
    """SmtpSender.send connects via SMTP_SSL and sends."""
    from src.email_delivery import SmtpSender

    monkeypatch.setenv("HYDRO_ART_GMAIL_APP_PASSWORD", "test-pass")

    sent_messages = []

    class FakeConnection:
        def login(self, user, password):
            self._user = user
            self._password = password

        def send_message(self, msg):
            sent_messages.append(msg)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("src.email_delivery.smtplib.SMTP_SSL", lambda host, port: FakeConnection())

    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg["To"] = "test@example.com"
    msg["Subject"] = "Test"

    sender = SmtpSender()
    assert sender.send(msg) is True
    assert len(sent_messages) == 1
