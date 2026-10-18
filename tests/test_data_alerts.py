"""Offline tests for data-quality alerts and caveat propagation.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: alert scope (authority/program/geography/period); active alerts
propagate to result caveats; expired/superseded alerts remain auditable
but not active; no alert silently changes a measurement or confidence
value.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_facility import DataAlert, WaterFacilityError
from src.data_alerts import (
    DataAlertError,
    active_alerts,
    apply_alerts_to_result,
    is_alert_active,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
_EARLIER = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_LATER = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _make_alert(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        authority="EPA",
        program="SDWIS",
        geography="TX",
        severity="warning",
        message="Data lag in reporting period.",
        source_url="https://epa.gov/alerts/2026-q3",
        effective_start=_EARLIER,
        effective_end=None,
        superseded_by=None,
        created_at=_EARLIER,
    )
    defaults.update(overrides)
    return DataAlert(**defaults)


# ---------------------------------------------------------------------------
# 1. An alert applies only to its authority/program/geography/period
# ---------------------------------------------------------------------------


def test_alert_matches_authority_program_geography():
    """An alert for EPA/SDWIS/TX does not match a query for EPA/NPDES/TX."""
    alert = _make_alert(program="SDWIS")
    result = active_alerts(
        [alert],
        authority="EPA",
        program="NPDES",
        geography="TX",
        as_of=_NOW,
    )
    assert len(result) == 0


def test_alert_matches_correct_scope():
    """An alert matches when all scope dimensions align."""
    alert = _make_alert()
    result = active_alerts(
        [alert],
        authority="EPA",
        program="SDWIS",
        geography="TX",
        as_of=_NOW,
    )
    assert len(result) == 1


def test_alert_outside_effective_period_not_active():
    """An alert whose effective_end has passed is not active."""
    alert = _make_alert(
        effective_start=_EARLIER,
        effective_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert not is_alert_active(alert, as_of=_NOW)


def test_alert_before_effective_start_not_active():
    """An alert queried before its effective_start is not active."""
    alert = _make_alert(
        effective_start=_LATER,
    )
    assert not is_alert_active(alert, as_of=_NOW)


# ---------------------------------------------------------------------------
# 2. Active alerts propagate to result caveats
# ---------------------------------------------------------------------------


def test_active_alert_adds_caveat_to_result():
    """An active alert attaches its message as a caveat on the result."""
    alert = _make_alert()
    result = {"facility_id": str(uuid.uuid4()), "value": 1500.0}
    updated = apply_alerts_to_result(result, [alert])
    assert "caveats" in updated
    assert any(alert.message in c for c in updated["caveats"])


def test_no_alerts_no_caveats():
    """When no alerts apply, the result has no caveats key added."""
    result = {"facility_id": str(uuid.uuid4()), "value": 200.0}
    updated = apply_alerts_to_result(result, [])
    assert "caveats" not in updated or len(updated.get("caveats", [])) == 0


# ---------------------------------------------------------------------------
# 3. Expired/superseded alerts auditable but not active
# ---------------------------------------------------------------------------


def test_expired_alert_not_active():
    """An expired alert is not returned by active_alerts."""
    alert = _make_alert(
        effective_end=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    result = active_alerts([alert], as_of=_NOW)
    assert len(result) == 0


def test_superseded_alert_not_active():
    """A superseded alert is not active even if within its period."""
    replacement_id = uuid.uuid4()
    alert = _make_alert(superseded_by=replacement_id)
    assert not is_alert_active(alert, as_of=_NOW)


def test_superseded_alert_still_exists():
    """A superseded alert retains all its fields for audit."""
    replacement_id = uuid.uuid4()
    alert = _make_alert(superseded_by=replacement_id)
    # The object itself is still intact and auditable
    assert alert.authority == "EPA"
    assert alert.message == "Data lag in reporting period."
    assert alert.superseded_by == replacement_id


# ---------------------------------------------------------------------------
# 4. No alert may silently change a measurement or confidence value
# ---------------------------------------------------------------------------


def test_alert_does_not_change_measurement_value():
    """apply_alerts_to_result must not modify the measurement value."""
    alert = _make_alert(severity="critical")
    original_value = 1500.0
    original_confidence = 0.95
    result = {
        "facility_id": str(uuid.uuid4()),
        "value": original_value,
        "confidence": original_confidence,
    }
    updated = apply_alerts_to_result(result, [alert])
    assert updated["value"] == original_value
    assert updated["confidence"] == original_confidence


def test_alert_preserves_all_existing_keys():
    """Applying alerts only adds caveats; does not remove or alter keys."""
    alert = _make_alert()
    result = {
        "facility_id": "abc",
        "value": 42.0,
        "unit": "m3/day",
        "extra_key": "preserved",
    }
    updated = apply_alerts_to_result(result, [alert])
    assert updated["facility_id"] == "abc"
    assert updated["value"] == 42.0
    assert updated["unit"] == "m3/day"
    assert updated["extra_key"] == "preserved"
