"""Operations ledger domain model — entity dataclasses, ID helpers, validation.

Defines the repository protocol (:class:`OrderRepository`) that both the JSON
:class:`~src.orders.OrderStore` and the PostgreSQL ``PgOrderRepository`` satisfy,
plus frozen value objects for assets, deliveries, render jobs, analysis runs,
and append-only events.

Pure and offline: no database driver imports, no GDAL, no network.
Nothing enters ``PIPELINE_STAGES``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ASSET_ROLES",
    "RIGHTS_STATUSES",
    "VISIBILITY_VALUES",
    "AnalysisMetric",
    "AnalysisRun",
    "Asset",
    "AssetLineage",
    "BriefRevision",
    "Delivery",
    "LedgerError",
    "LedgerEvent",
    "OrderRepository",
    "Place",
    "RenderJob",
    "repository_factory",
    "validate_asset_id",
    "validate_asset_role",
    "validate_delivery_access",
    "validate_delivery_id",
    "validate_order_id",
    "validate_request_id",
    "validate_rights_status",
    "validate_visibility",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class LedgerError(Exception):
    """Raised for invalid ledger operations (IDs, roles, access, connection)."""


# ---------------------------------------------------------------------------
# Constants (closed value sets)
# ---------------------------------------------------------------------------

ASSET_ROLES: frozenset[str] = frozenset({
    "source_reference",
    "recipe",
    "run_log",
    "proof",
    "final",
    "print",
    "vector",
    "report",
    "figure",
    "animation",
    "thumbnail",
    "bundle",
    "license",
    "customer_reference",
})

VISIBILITY_VALUES: frozenset[str] = frozenset({
    "internal",
    "approved_public",
})

RIGHTS_STATUSES: frozenset[str] = frozenset({
    "pending",
    "cleared",
    "restricted",
})


# ---------------------------------------------------------------------------
# Entity dataclasses (all frozen)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Place:
    """Geographic identity for a rendered artwork or analysis scope."""

    place_id: str
    region: str
    county: str | None
    huc4: str | None
    display_name: str


@dataclass(frozen=True)
class Asset:
    """One immutable generated file tracked in the ledger."""

    asset_id: str
    order_id: str
    render_job_id: str | None
    role: str
    storage_key: str
    checksum_sha256: str
    byte_count: int
    width_px: int | None
    height_px: int | None
    media_type: str
    visibility: str
    rights_status: str
    source_attribution: str | None
    created_at: str
    retention_class: str | None
    retain_until: str | None
    deleted_at: str | None


@dataclass(frozen=True)
class AssetLineage:
    """A directed edge linking a parent asset to a derived child asset."""

    parent_asset_id: str
    child_asset_id: str
    relationship: str


@dataclass(frozen=True)
class RenderJob:
    """One render attempt for an order."""

    job_id: str
    order_id: str
    brief_revision: str | None
    status: str
    recipe_digest: str | None
    started_at: str
    finished_at: str | None
    error_message: str | None


@dataclass(frozen=True)
class BriefRevision:
    """An immutable snapshot of the order brief at a given revision."""

    brief_id: str
    order_id: str
    revision: int
    recipe: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class Delivery:
    """One delivery event granting time-limited access to selected assets."""

    delivery_id: str
    order_id: str
    delivered_at: str
    access_expires_at: str
    access_revoked_at: str | None
    asset_ids: tuple[str, ...]
    reason: str
    fee_waived: bool


@dataclass(frozen=True)
class AnalysisRun:
    """A scoped analysis execution with provenance metadata."""

    run_id: str
    place_id: str
    recipe_digest: str | None
    code_revision: str | None
    input_sources: dict[str, Any]
    start_year: int
    end_year: int
    metric_version: str
    validation_status: str
    created_at: str
    reviewer: str | None
    notes: str | None


@dataclass(frozen=True)
class AnalysisMetric:
    """A single named result from an analysis run."""

    metric_id: str
    run_id: str
    name: str
    units: str
    method: str
    method_version: str
    value: Any
    interpretation_status: str
    created_at: str


@dataclass(frozen=True)
class LedgerEvent:
    """An append-only audit event linked to any entity."""

    event_id: str
    entity_type: str
    entity_id: str
    occurred_at: str
    event_name: str
    actor: str
    detail: dict[str, Any]


# ---------------------------------------------------------------------------
# ID format patterns (from docs/data-management-strategy.md)
# ---------------------------------------------------------------------------

_REQUEST_ID_RE = re.compile(r"^REQ-\d{8}-\d{4}$")
_ORDER_ID_RE = re.compile(r"^ORD-\d{8}-\d{4}$")
_ASSET_ID_RE = re.compile(
    r"^AST-ORD-\d{8}-\d{4}-[a-z][a-z_]*-r\d+$"
)
_DELIVERY_ID_RE = re.compile(r"^DLV-ORD-\d{8}-\d{4}-\d+$")


def validate_request_id(request_id: str) -> None:
    """Validate request ID format ``REQ-YYYYMMDD-####``. Raises LedgerError."""
    if not _REQUEST_ID_RE.match(request_id):
        raise LedgerError(
            f"Invalid request ID {request_id!r}. "
            "Expected format: REQ-YYYYMMDD-####."
        )


def validate_order_id(order_id: str) -> None:
    """Validate order ID format ``ORD-YYYYMMDD-####``. Raises LedgerError."""
    if not _ORDER_ID_RE.match(order_id):
        raise LedgerError(
            f"Invalid order ID {order_id!r}. "
            "Expected format: ORD-YYYYMMDD-####."
        )


def validate_asset_id(asset_id: str) -> None:
    """Validate asset ID format ``AST-<order>-<role>-rN``. Raises LedgerError."""
    if not _ASSET_ID_RE.match(asset_id):
        raise LedgerError(
            f"Invalid asset ID {asset_id!r}. "
            "Expected format: AST-ORD-YYYYMMDD-####-<role>-rN."
        )


def validate_delivery_id(delivery_id: str) -> None:
    """Validate delivery ID format ``DLV-<order>-N``. Raises LedgerError."""
    if not _DELIVERY_ID_RE.match(delivery_id):
        raise LedgerError(
            f"Invalid delivery ID {delivery_id!r}. "
            "Expected format: DLV-ORD-YYYYMMDD-####-N."
        )


# ---------------------------------------------------------------------------
# Value validators
# ---------------------------------------------------------------------------


def validate_asset_role(role: str) -> None:
    """Validate that ``role`` is in the closed asset role set. Raises LedgerError."""
    if role not in ASSET_ROLES:
        raise LedgerError(
            f"Invalid asset role {role!r}. "
            f"Valid: {', '.join(sorted(ASSET_ROLES))}."
        )


def validate_visibility(visibility: str) -> None:
    """Validate visibility value. Raises LedgerError."""
    if visibility not in VISIBILITY_VALUES:
        raise LedgerError(
            f"Invalid visibility {visibility!r}. "
            f"Valid: {', '.join(sorted(VISIBILITY_VALUES))}."
        )


def validate_rights_status(rights_status: str) -> None:
    """Validate rights status value. Raises LedgerError."""
    if rights_status not in RIGHTS_STATUSES:
        raise LedgerError(
            f"Invalid rights status {rights_status!r}. "
            f"Valid: {', '.join(sorted(RIGHTS_STATUSES))}."
        )


def validate_delivery_access(delivery: Delivery) -> str:
    """Determine delivery access status: ``'active'``, ``'expired'``, or ``'revoked'``.

    Checks ``access_revoked_at`` first (revoked wins), then compares
    ``access_expires_at`` against the current UTC time.
    """
    if delivery.access_revoked_at is not None:
        return "revoked"
    # Parse ISO timestamp and compare to now
    expires = datetime.fromisoformat(
        delivery.access_expires_at.replace("Z", "+00:00")
    )
    now = datetime.now(timezone.utc)
    if now >= expires:
        return "expired"
    return "active"


# ---------------------------------------------------------------------------
# Repository protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class OrderRepository(Protocol):
    """Protocol satisfied by both JSON OrderStore and PgOrderRepository.

    Defines the minimal contract for order persistence. Methods match
    :class:`~src.orders.OrderStore` public API.
    """

    def create_request(self, payload: dict[str, Any]) -> Any: ...

    def get(self, request_id: str) -> Any: ...

    def list_all(self) -> list[Any]: ...

    def update_status(self, request_id: str, new_status: str) -> Any: ...

    def set_job_id(self, request_id: str, job_id: str) -> Any: ...

    def add_event(
        self,
        request_id: str,
        event: str,
        detail: dict[str, Any] | None = None,
    ) -> Any: ...

    def add_note(self, request_id: str, note: str) -> Any: ...


# ---------------------------------------------------------------------------
# Repository factory
# ---------------------------------------------------------------------------


def repository_factory(
    database_url: str | None = None,
) -> OrderRepository:
    """Return the appropriate repository implementation.

    When ``database_url`` is ``None`` (default), returns a JSON-file-backed
    :class:`~src.orders.OrderStore`. When a PostgreSQL URL is provided,
    lazily imports and returns a ``PgOrderRepository``.

    Raises:
        LedgerError: If the URL scheme is not ``postgresql`` or the driver
            cannot be imported.
    """
    if database_url is None:
        from src.orders import OrderStore
        return OrderStore()

    if not database_url.startswith("postgresql"):
        raise LedgerError(
            f"Unsupported database URL scheme. "
            f"Expected postgresql://, got {database_url.split('://')[0]}://."
        )

    try:
        from src.ledger_pg import PgOrderRepository
    except ImportError as exc:
        raise LedgerError(
            "PostgreSQL adapter requires psycopg. "
            "Install it: pip install psycopg[binary]"
        ) from exc

    return PgOrderRepository(database_url)
