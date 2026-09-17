"""Proof URL signing, verification, and SVG watermarking.

Pure and offline-testable — no GDAL, no network.
Uses HMAC-SHA256 for tamper-proof, time-limited proof links.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import time

__all__ = [
    "sign_proof_url",
    "verify_proof_token",
    "sign_delivery_url",
    "verify_delivery_token",
    "watermark_svg",
]


def sign_proof_url(
    request_id: str,
    secret: bytes,
    expires_in: int = 604800,
) -> str:
    """Create a signed, time-limited proof token.

    Format: ``base64url(request_id + "." + expiry_ts + "." + hmac_hex)``

    Args:
        request_id: The order request identifier.
        secret: HMAC signing key.
        expires_in: Seconds until expiry (default 7 days).

    Returns:
        A URL-safe base64-encoded token string.
    """
    expiry = int(time.time()) + expires_in
    payload = f"{request_id}.{expiry}"
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_proof_token(
    token: str,
    secret: bytes,
) -> tuple[str, bool]:
    """Verify a proof token and check expiry.

    Returns:
        ``(request_id, True)`` if valid and not expired,
        ``(request_id, False)`` if expired but signature valid,
        ``("", False)`` if signature invalid or token malformed.
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
    except Exception:
        return ("", False)

    parts = raw.rsplit(".", 2)
    if len(parts) != 3:
        return ("", False)

    # request_id may contain dots (e.g. REQ-20260916-0001), so split from right
    payload_and_id, expiry_str, sig = parts[0], parts[1], parts[2]

    # Reconstruct: everything before the last two dots is the payload
    # Actually the format is request_id.expiry.sig — request_id has no dots
    # in the current scheme (REQ-YYYYMMDD-NNNN uses dashes), but be safe.
    request_id = payload_and_id
    payload = f"{request_id}.{expiry_str}"

    expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return ("", False)

    try:
        expiry = int(expiry_str)
    except ValueError:
        return ("", False)

    if time.time() > expiry:
        return (request_id, False)

    return (request_id, True)


#: 90-day default expiry for delivery links.
_DELIVERY_EXPIRY = 90 * 24 * 3600  # 7_776_000 seconds


def sign_delivery_url(
    request_id: str,
    secret: bytes,
    expires_in: int = _DELIVERY_EXPIRY,
) -> str:
    """Create a signed, 90-day delivery token. Same HMAC scheme as proofs."""
    return sign_proof_url(request_id, secret, expires_in=expires_in)


def verify_delivery_token(
    token: str,
    secret: bytes,
) -> tuple[str, bool]:
    """Verify a delivery token. Same HMAC scheme as proofs."""
    return verify_proof_token(token, secret)


def watermark_svg(svg_content: str, text: str) -> str:
    """Add a diagonal watermark text overlay to an SVG string.

    Inserts a semi-transparent ``<text>`` element with the given text
    before the closing ``</svg>`` tag. Original content is preserved.

    Args:
        svg_content: The source SVG markup.
        text: Watermark text (e.g. ``"PROOF"``).

    Returns:
        SVG markup with watermark added.
    """
    # Extract viewBox or width/height for centering
    width = 500
    height = 500
    w_match = re.search(r'width="(\d+)"', svg_content)
    h_match = re.search(r'height="(\d+)"', svg_content)
    if w_match:
        width = int(w_match.group(1))
    if h_match:
        height = int(h_match.group(1))

    cx, cy = width // 2, height // 2
    font_size = max(width, height) // 5

    watermark = (
        f'<text x="{cx}" y="{cy}" '
        f'font-size="{font_size}" '
        f'fill="white" fill-opacity="0.3" '
        f'text-anchor="middle" dominant-baseline="central" '
        f'transform="rotate(-45 {cx} {cy})" '
        f'font-family="sans-serif" font-weight="bold"'
        f'>{text}</text>'
    )

    # Insert before closing </svg>
    return svg_content.replace("</svg>", f"{watermark}</svg>")
