"""Tests for render performance instrumentation.

Offline — tests event recording for render timing.
"""

from __future__ import annotations

import pytest

from src.orders import OrderStore


def _order_payload(**overrides):
    base = {
        "email": "buyer@example.com",
        "product": "digital_image",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "18x24",
        "formats": ["png"],
    }
    base.update(overrides)
    return base


class TestRenderTimingEvents:
    def test_render_started_event_includes_detail(self, tmp_path):
        """render_started event can include queue wait time."""
        from src.orders import OrderEvent

        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        store.update_status(req.request_id, "accepted")
        store.update_status(req.request_id, "rendering")

        # Add a render_started event with timing detail
        store.add_event(req.request_id, "render_started", {"job_id": "job-001", "queue_wait_ms": 1200})
        fetched = store.get(req.request_id)
        started_events = [e for e in fetched.events if e["event"] == "render_started"]
        assert len(started_events) == 1
        assert started_events[0]["detail"]["job_id"] == "job-001"
        assert started_events[0]["detail"]["queue_wait_ms"] == 1200

    def test_render_completed_event_includes_duration(self, tmp_path):
        """render_completed event includes total duration."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        store.update_status(req.request_id, "accepted")
        store.update_status(req.request_id, "rendering")

        store.add_event(req.request_id, "render_completed", {
            "job_id": "job-001",
            "duration_s": 45.3,
            "stages": {"download": 5.1, "validate": 0.8, "render": 38.2, "export": 1.2},
        })
        fetched = store.get(req.request_id)
        completed = [e for e in fetched.events if e["event"] == "render_completed"]
        assert len(completed) == 1
        assert completed[0]["detail"]["duration_s"] == 45.3

    def test_queue_depth_tracked(self, tmp_path):
        """Multiple orders track independent render events."""
        store = OrderStore(tmp_path / "orders")
        r1 = store.create_request(_order_payload())
        r2 = store.create_request(_order_payload(county="King"))
        store.update_status(r1.request_id, "accepted")
        store.update_status(r1.request_id, "rendering")
        store.update_status(r2.request_id, "accepted")
        store.update_status(r2.request_id, "rendering")

        store.add_event(r1.request_id, "render_started", {"queue_depth": 2})
        store.add_event(r2.request_id, "render_started", {"queue_depth": 1})

        e1 = store.get(r1.request_id)
        e2 = store.get(r2.request_id)
        started1 = [e for e in e1.events if e["event"] == "render_started"]
        started2 = [e for e in e2.events if e["event"] == "render_started"]
        assert started1[0]["detail"]["queue_depth"] == 2
        assert started2[0]["detail"]["queue_depth"] == 1
