"""Stripe Checkout integration for payment capture.

Pure and offline-testable — Stripe SDK is lazy-imported, never at module load.
All logic is testable with fake clients. The webhook verification uses stdlib
HMAC so it works without the SDK.

The real Stripe client is wired in ``serve.py``; tests inject :class:`FakeStripeClient`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Protocol

__all__ = [
    "WebhookError",
    "create_checkout_session",
    "handle_webhook",
]


class WebhookError(Exception):
    """Raised when a Stripe webhook signature is invalid."""


class StripeClientLike(Protocol):
    """Anything that can create a Stripe Checkout Session."""

    def create_checkout_session(self, **kwargs: Any) -> dict[str, Any]: ...


def create_checkout_session(
    *,
    request_id: str,
    product: str,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
    client: Any,
) -> dict[str, Any]:
    """Build and submit a Stripe Checkout Session.

    Args:
        request_id: The order request identifier (stored in session metadata).
        product: Human-readable product name for the line item.
        amount_cents: Total price in cents.
        success_url: Redirect URL after successful payment.
        cancel_url: Redirect URL if the customer cancels.
        client: A Stripe client (real or fake) with ``create_checkout_session``.

    Returns:
        Dict with ``id`` (session ID) and ``url`` (checkout page URL).
    """
    return client.create_checkout_session(
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": product},
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"request_id": request_id},
    )


def handle_webhook(
    payload: str,
    signature: str,
    secret: str,
    *,
    tolerance: int = 300,
) -> str:
    """Verify a Stripe webhook signature and extract the request_id.

    Uses the same HMAC-SHA256 scheme as Stripe's ``v1`` signatures:
    ``t=<timestamp>,v1=<hmac_hex>``.

    Args:
        payload: Raw request body string.
        signature: The ``Stripe-Signature`` header value.
        secret: The webhook signing secret (``whsec_...``).
        tolerance: Maximum age in seconds (default 5 minutes).

    Returns:
        The ``request_id`` from the event's session metadata.

    Raises:
        WebhookError: If the signature is invalid, expired, or malformed.
    """
    # Parse the signature header
    parts = {}
    for item in signature.split(","):
        key, _, value = item.partition("=")
        parts[key.strip()] = value.strip()

    timestamp = parts.get("t", "")
    their_sig = parts.get("v1", "")

    if not timestamp or not their_sig:
        raise WebhookError("Signature header missing t or v1 fields.")

    # Verify timestamp tolerance
    try:
        ts = int(timestamp)
    except ValueError:
        raise WebhookError("Invalid timestamp in signature.")

    if abs(time.time() - ts) > tolerance:
        raise WebhookError("Signature timestamp outside tolerance window.")

    # Compute expected signature
    sig_payload = f"{timestamp}.{payload}"
    expected = hmac.new(
        secret.encode(), sig_payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(their_sig, expected):
        raise WebhookError("Signature verification failed.")

    # Extract request_id from the event
    try:
        event = json.loads(payload)
    except (ValueError, TypeError):
        raise WebhookError("Invalid JSON payload.")

    session = event.get("data", {}).get("object", {})
    request_id = session.get("metadata", {}).get("request_id", "")
    if not request_id:
        raise WebhookError("No request_id in session metadata.")

    return request_id
