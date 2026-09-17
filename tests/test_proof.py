"""Tests for proof URL signing, verification, and watermarking.

Offline — no GDAL, no network. Pure crypto + string operations.
"""

from __future__ import annotations

import pytest


class TestSignAndVerify:
    def test_roundtrip(self):
        """Sign a request_id, verify returns (id, True)."""
        from src.proof import sign_proof_url, verify_proof_token

        secret = b"test-secret-key"
        token = sign_proof_url("REQ-20260916-0001", secret, expires_in=3600)
        request_id, valid = verify_proof_token(token, secret)
        assert valid is True
        assert request_id == "REQ-20260916-0001"

    def test_expired_token_rejected(self):
        """Sign with expires_in=0, verify returns (id, False)."""
        from src.proof import sign_proof_url, verify_proof_token

        secret = b"test-secret-key"
        token = sign_proof_url("REQ-20260916-0001", secret, expires_in=0)
        request_id, valid = verify_proof_token(token, secret)
        assert valid is False
        assert request_id == "REQ-20260916-0001"

    def test_tampered_token_rejected(self):
        """Flip a byte in the token — verify returns ('', False)."""
        from src.proof import sign_proof_url, verify_proof_token

        secret = b"test-secret-key"
        token = sign_proof_url("REQ-20260916-0001", secret, expires_in=3600)
        # Tamper with a character in the middle of the token
        chars = list(token)
        idx = len(chars) // 2
        chars[idx] = "X" if chars[idx] != "X" else "Y"
        tampered = "".join(chars)
        request_id, valid = verify_proof_token(tampered, secret)
        assert valid is False

    def test_different_secret_rejected(self):
        """Sign with key A, verify with key B → False."""
        from src.proof import sign_proof_url, verify_proof_token

        token = sign_proof_url("REQ-20260916-0001", b"key-a", expires_in=3600)
        request_id, valid = verify_proof_token(token, b"key-b")
        assert valid is False


class TestDeliveryLinks:
    """Epoch 29: signed delivery URLs with 90-day expiry."""

    def test_delivery_url_roundtrip(self):
        """Sign and verify a delivery URL."""
        from src.proof import sign_delivery_url, verify_delivery_token

        secret = b"delivery-secret"
        token = sign_delivery_url("REQ-20260916-0001", secret)
        request_id, valid = verify_delivery_token(token, secret)
        assert valid is True
        assert request_id == "REQ-20260916-0001"

    def test_delivery_default_90_day_expiry(self):
        """Default expiry is 90 days (7776000 seconds)."""
        from src.proof import sign_delivery_url, verify_delivery_token

        secret = b"delivery-secret"
        # Should be valid now (within 90 days)
        token = sign_delivery_url("REQ-001", secret)
        _, valid = verify_delivery_token(token, secret)
        assert valid is True

    def test_delivery_expired_link_rejected(self):
        """Expired delivery link returns (id, False)."""
        from src.proof import sign_delivery_url, verify_delivery_token

        secret = b"delivery-secret"
        token = sign_delivery_url("REQ-001", secret, expires_in=0)
        request_id, valid = verify_delivery_token(token, secret)
        assert valid is False
        assert request_id == "REQ-001"

    def test_delivery_tampered_link_rejected(self):
        """Tampered delivery link returns ('', False)."""
        from src.proof import sign_delivery_url, verify_delivery_token

        secret = b"delivery-secret"
        token = sign_delivery_url("REQ-001", secret)
        chars = list(token)
        idx = len(chars) // 2
        chars[idx] = "X" if chars[idx] != "X" else "Y"
        tampered = "".join(chars)
        _, valid = verify_delivery_token(tampered, secret)
        assert valid is False


class TestWatermark:
    def test_watermark_adds_text_element(self):
        """SVG output contains <text> with 'PROOF'."""
        from src.proof import watermark_svg

        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M0 0 L100 100"/></svg>'
        result = watermark_svg(svg, "PROOF")
        assert "<text" in result
        assert "PROOF" in result

    def test_watermark_preserves_original_paths(self):
        """Original <path> elements are unchanged."""
        from src.proof import watermark_svg

        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M0 0 L100 100"/></svg>'
        result = watermark_svg(svg, "PROOF")
        assert 'd="M0 0 L100 100"' in result
