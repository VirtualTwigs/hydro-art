"""Tests for the product analytics module.

Offline — pure functions over event log data. No GDAL, no network.
"""

from __future__ import annotations

import pytest


def _make_events(*event_dicts):
    """Build a list of order event lists for analytics."""
    return [event_dicts]


def _order_events(product="digital_image", region="Washington", county="Clark",
                  approved=True, paid=True, render_duration=30.0):
    """Build a realistic event log for one order."""
    events = [
        {"timestamp": "2026-09-16T10:00:00Z", "event": "submitted",
         "detail": {"product": product, "email": "b@x.com"}},
        {"timestamp": "2026-09-16T10:00:01Z", "event": "accepted", "detail": {}},
        {"timestamp": "2026-09-16T10:00:02Z", "event": "rendering", "detail": {}},
        {"timestamp": "2026-09-16T10:00:03Z", "event": "render_started",
         "detail": {"job_id": "j1"}},
        {"timestamp": "2026-09-16T10:00:33Z", "event": "render_completed",
         "detail": {"job_id": "j1", "duration_s": render_duration}},
        {"timestamp": "2026-09-16T10:00:34Z", "event": "proof_ready", "detail": {}},
    ]
    if approved:
        events.append({"timestamp": "2026-09-16T11:00:00Z", "event": "approved", "detail": {}})
    if paid:
        events.append({"timestamp": "2026-09-16T11:01:00Z", "event": "payment_pending", "detail": {}})
        events.append({"timestamp": "2026-09-16T11:02:00Z", "event": "paid", "detail": {}})
        events.append({"timestamp": "2026-09-16T11:03:00Z", "event": "fulfilled", "detail": {}})

    return {
        "product": product,
        "region": region,
        "county": county,
        "events": events,
    }


class TestOrdersByProductType:
    def test_correct_counts(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(product="digital_image"),
            _order_events(product="digital_image"),
            _order_events(product="Fine-art print"),
        ]
        report = compute_analytics(orders)
        assert report["orders_by_product"]["digital_image"] == 2
        assert report["orders_by_product"]["Fine-art print"] == 1


class TestOrdersByRegion:
    def test_correct_distribution(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(region="Washington"),
            _order_events(region="Washington"),
            _order_events(region="Oregon"),
        ]
        report = compute_analytics(orders)
        assert report["orders_by_region"]["Washington"] == 2
        assert report["orders_by_region"]["Oregon"] == 1


class TestProofAcceptanceRate:
    def test_approved_over_total(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(approved=True, paid=True),
            _order_events(approved=True, paid=True),
            _order_events(approved=False, paid=False),
        ]
        report = compute_analytics(orders)
        # 2 approved out of 3 proofs
        assert report["proof_acceptance_rate"] == pytest.approx(2 / 3, abs=0.01)


class TestAverageRenderTime:
    def test_mean_of_durations(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(render_duration=20.0),
            _order_events(render_duration=40.0),
        ]
        report = compute_analytics(orders)
        assert report["average_render_time_s"] == pytest.approx(30.0, abs=0.01)


class TestPaymentConversionRate:
    def test_paid_over_approved(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(approved=True, paid=True),
            _order_events(approved=True, paid=False),
        ]
        report = compute_analytics(orders)
        # 1 paid out of 2 approved
        assert report["payment_conversion_rate"] == pytest.approx(0.5, abs=0.01)


class TestTopCounties:
    def test_most_requested(self):
        from src.analytics import compute_analytics

        orders = [
            _order_events(county="Clark"),
            _order_events(county="Clark"),
            _order_events(county="King"),
            _order_events(county="Clark"),
        ]
        report = compute_analytics(orders)
        assert report["top_counties"][0] == ("Clark", 3)
