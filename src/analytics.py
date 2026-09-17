"""Product analytics computed from order event logs.

Pure functions over event data — no database dependency, no GDAL, no network.
Accepts a list of order dicts (each with ``product``, ``region``, ``county``,
and ``events`` list) and returns an analytics report dict.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

__all__ = ["compute_analytics"]


def compute_analytics(orders: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate analytics from a list of order records.

    Each order dict should have:
    - ``product``: str
    - ``region``: str
    - ``county``: str
    - ``events``: list of ``{"timestamp", "event", "detail"}`` dicts

    Returns:
        Dict with analytics metrics:
        - ``orders_by_product``: dict of product → count
        - ``orders_by_region``: dict of region → count
        - ``proof_acceptance_rate``: float (approved / total proofs)
        - ``average_render_time_s``: float (mean render duration)
        - ``payment_conversion_rate``: float (paid / approved)
        - ``top_counties``: list of (county, count) tuples, descending
        - ``total_orders``: int
    """
    product_counts: Counter[str] = Counter()
    region_counts: Counter[str] = Counter()
    county_counts: Counter[str] = Counter()

    total_proofs = 0
    total_approved = 0
    total_paid = 0
    render_durations: list[float] = []

    for order in orders:
        product = order.get("product", "unknown")
        region = order.get("region", "unknown")
        county = order.get("county", "unknown")
        events = order.get("events", [])

        product_counts[product] += 1
        region_counts[region] += 1
        county_counts[county] += 1

        event_types = {e["event"] for e in events}

        # Count proofs (proof_ready implies a proof was generated)
        if "proof_ready" in event_types:
            total_proofs += 1

        if "approved" in event_types:
            total_approved += 1

        if "paid" in event_types:
            total_paid += 1

        # Extract render durations from render_completed events
        for e in events:
            if e["event"] == "render_completed":
                duration = e.get("detail", {}).get("duration_s")
                if duration is not None:
                    render_durations.append(float(duration))

    proof_rate = total_approved / total_proofs if total_proofs > 0 else 0.0
    payment_rate = total_paid / total_approved if total_approved > 0 else 0.0
    avg_render = (
        sum(render_durations) / len(render_durations)
        if render_durations else 0.0
    )

    top_counties = county_counts.most_common()

    return {
        "total_orders": len(orders),
        "orders_by_product": dict(product_counts),
        "orders_by_region": dict(region_counts),
        "proof_acceptance_rate": proof_rate,
        "average_render_time_s": avg_render,
        "payment_conversion_rate": payment_rate,
        "top_counties": top_counties,
    }
