"""Data-quality alert filtering and caveat propagation.

Pure, offline module for determining active alerts, filtering by scope,
and attaching caveats to query results without modifying measurement or
confidence values.  No database driver, no GIS imports, no network at
module load time.  Nothing enters ``PIPELINE_STAGES``.

See ``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
spec.md`` and task group 8 (#119).
"""

from __future__ import annotations

from datetime import datetime

from src.water_facility import DataAlert

__all__ = [
    "DataAlertError",
    "active_alerts",
    "apply_alerts_to_result",
    "is_alert_active",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class DataAlertError(Exception):
    """Raised for invalid data-alert operations."""


# ---------------------------------------------------------------------------
# Active-alert determination
# ---------------------------------------------------------------------------


def is_alert_active(alert: DataAlert, as_of: datetime) -> bool:
    """Return whether *alert* is active at the given point in time.

    An alert is **not** active when:
    - ``as_of`` is before ``effective_start``.
    - ``effective_end`` is set and ``as_of`` is at or after that time.
    - The alert has been superseded (``superseded_by`` is not ``None``).
    """
    if alert.superseded_by is not None:
        return False
    if as_of < alert.effective_start:
        return False
    if alert.effective_end is not None and as_of >= alert.effective_end:
        return False
    return True


def active_alerts(
    alerts: list[DataAlert],
    *,
    authority: str | None = None,
    program: str | None = None,
    geography: str | None = None,
    as_of: datetime,
) -> list[DataAlert]:
    """Return alerts that are active and match the given scope filters.

    Each filter dimension is optional; when ``None`` that dimension is
    not checked (matches all).  An alert must pass **all** supplied
    filters and be active at *as_of*.
    """
    result: list[DataAlert] = []
    for alert in alerts:
        if not is_alert_active(alert, as_of):
            continue
        if authority is not None and alert.authority != authority:
            continue
        if program is not None and alert.program != program:
            continue
        if geography is not None and alert.geography != geography:
            continue
        result.append(alert)
    return result


# ---------------------------------------------------------------------------
# Caveat propagation
# ---------------------------------------------------------------------------


def apply_alerts_to_result(
    result_dict: dict,
    alerts: list[DataAlert],
) -> dict:
    """Attach applicable alert caveats to a result dict.

    Returns a **new** dict (shallow copy) with a ``"caveats"`` key
    listing each alert's message.  Existing keys — especially
    ``"value"`` and ``"confidence"`` — are **never** modified or
    removed.  If *alerts* is empty the result is returned unchanged
    (no ``"caveats"`` key added).
    """
    if not alerts:
        return dict(result_dict)

    updated = dict(result_dict)
    caveats = [a.message for a in alerts]
    updated["caveats"] = caveats
    return updated
