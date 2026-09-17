"""Shipping address validation for print orders.

Pure and offline-testable — no GDAL, no network.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

__all__ = ["ShippingAddress", "ShippingError", "validate_address"]

#: US ZIP code pattern: 5 digits, optional -4 extension.
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


class ShippingError(Exception):
    """Raised for invalid shipping address fields."""


@dataclass(frozen=True)
class ShippingAddress:
    """A validated US shipping address."""

    name: str
    street: str
    city: str
    state: str
    zip: str
    line2: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_address(payload: dict[str, Any]) -> ShippingAddress:
    """Validate a shipping address payload.

    Args:
        payload: Dict with ``name``, ``street``, ``city``, ``state``, ``zip``,
                 and optional ``line2``.

    Returns:
        A validated :class:`ShippingAddress`.

    Raises:
        ShippingError: If any required field is missing or zip format is invalid.
    """
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ShippingError("Name is required.")

    street = str(payload.get("street", "")).strip()
    if not street:
        raise ShippingError("Street address is required.")

    city = str(payload.get("city", "")).strip()
    if not city:
        raise ShippingError("City is required.")

    state = str(payload.get("state", "")).strip()
    if not state:
        raise ShippingError("State is required.")

    zip_code = str(payload.get("zip", "")).strip()
    if not zip_code:
        raise ShippingError("Zip code is required.")
    if not _ZIP_RE.match(zip_code):
        raise ShippingError(
            f"Invalid zip code format: {zip_code!r}. "
            "Expected 5 digits or 5+4 format (e.g., 97201 or 97201-1234)."
        )

    line2 = payload.get("line2")
    if line2 is not None:
        line2 = str(line2).strip() or None

    return ShippingAddress(
        name=name,
        street=street,
        city=city,
        state=state,
        zip=zip_code,
        line2=line2,
    )
