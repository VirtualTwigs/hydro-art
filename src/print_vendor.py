"""Print vendor integration (Printful/Prodigi API).

Pure and offline-testable — vendor SDK is lazy-imported, never at module load.
All logic is testable with a fake client implementing the ``PrintVendorLike``
protocol. The real vendor client wraps the SDK and is wired in ``serve.py``.
"""

from __future__ import annotations

from typing import Any, Protocol

__all__ = [
    "PrintVendorLike",
    "build_print_order_payload",
    "submit_print_order",
    "check_shipment",
    "calculate_print_cost",
]


class PrintVendorLike(Protocol):
    """Anything that can submit a print order and check shipment status."""

    def submit_print_order(
        self, file_url: str, spec: dict[str, Any], address: dict[str, Any],
    ) -> str: ...

    def check_shipment(self, vendor_order_id: str) -> dict[str, Any]: ...


#: Base print costs in cents by size.
_PRINT_COSTS: dict[str, int] = {
    "12x16": 2500,
    "18x24": 3500,
    "24x36": 5500,
}

#: Paper surcharge in cents (over base).
_PAPER_SURCHARGE: dict[str, int] = {
    "matte": 0,
    "glossy": 500,
    "canvas": 1500,
}


def build_print_order_payload(
    *,
    file_url: str,
    product_spec: dict[str, Any],
    address: dict[str, Any],
) -> dict[str, Any]:
    """Build the payload for a print vendor API call.

    Returns:
        Dict with ``file_url``, ``spec``, and ``address`` ready for submission.
    """
    return {
        "file_url": file_url,
        "spec": dict(product_spec),
        "address": dict(address),
    }


def submit_print_order(
    *,
    file_url: str,
    product_spec: dict[str, Any],
    address: dict[str, Any],
    client: Any,
) -> str:
    """Submit a print order to the vendor.

    Args:
        file_url: URL of the print-ready file.
        product_spec: Product specification (size, paper, etc.).
        address: Shipping address dict.
        client: A vendor client (real or fake).

    Returns:
        The vendor's order ID.
    """
    return client.submit_print_order(file_url, product_spec, address)


def check_shipment(vendor_order_id: str, *, client: Any) -> dict[str, Any]:
    """Check the shipment status for a vendor order.

    Returns:
        Dict with ``status``, and optionally ``tracking`` and ``carrier``.
    """
    return client.check_shipment(vendor_order_id)


def calculate_print_cost(*, size: str, paper: str = "matte") -> int:
    """Calculate the print cost in cents.

    Args:
        size: Print size (e.g., "24x36").
        paper: Paper type (e.g., "matte", "glossy", "canvas").

    Returns:
        Total print cost in cents.
    """
    base = _PRINT_COSTS.get(size, 3500)  # default to 18x24 if unknown
    surcharge = _PAPER_SURCHARGE.get(paper, 0)
    return base + surcharge
