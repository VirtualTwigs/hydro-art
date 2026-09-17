"""Order store for the concierge ordering flow (internal testing).

JSON-file-backed persistence for customer requests/orders. Each request is
stored as a JSON file in a configurable directory (default ``orders/``).
The :class:`OrderStore` validates payloads through :func:`~src.fulfillment.build_order`
and manages a simple state machine for the order lifecycle.

Pure and offline-testable — no GDAL, no network. The store reads/writes JSON
files and delegates validation to the existing fulfillment boundary.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.fulfillment import OrderError, build_order

__all__ = [
    "STATUSES",
    "TRANSITIONS",
    "OrderEvent",
    "OrderStore",
    "Request",
]

#: Valid request statuses in lifecycle order.
STATUSES = (
    "submitted",
    "accepted",
    "rendering",
    "proof_ready",
    "approved",
    "fulfilled",
    "revision_requested",
    "render_failed",
    "payment_pending",
    "paid",
)

#: Allowed status transitions: current -> set of allowed next statuses.
TRANSITIONS: dict[str, frozenset[str]] = {
    "submitted": frozenset({"accepted"}),
    "accepted": frozenset({"rendering"}),
    "rendering": frozenset({"proof_ready", "render_failed"}),
    "proof_ready": frozenset({"approved", "revision_requested"}),
    "revision_requested": frozenset({"rendering"}),
    "approved": frozenset({"payment_pending", "fulfilled"}),
    "render_failed": frozenset({"rendering"}),
    "fulfilled": frozenset(),
    "payment_pending": frozenset({"paid"}),
    "paid": frozenset({"fulfilled"}),
}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _next_seq(store_dir: Path, date_str: str) -> int:
    """Find the next sequence number for a given date prefix."""
    prefix = f"REQ-{date_str}-"
    existing = [
        p.stem for p in store_dir.glob(f"{prefix}*.json")
    ]
    if not existing:
        return 1
    nums = []
    for name in existing:
        suffix = name[len(prefix):]
        if suffix.isdigit():
            nums.append(int(suffix))
    return max(nums, default=0) + 1


@dataclass
class OrderEvent:
    """A single event in the order's audit trail."""

    timestamp: str
    event: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "event": self.event, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrderEvent:
        return cls(
            timestamp=data["timestamp"],
            event=data["event"],
            detail=data.get("detail", {}),
        )


@dataclass
class Request:
    """A customer request wrapping a validated Order + lifecycle metadata."""

    request_id: str
    status: str
    email: str
    product: str
    created_at: str
    updated_at: str
    order: dict[str, Any]
    job_id: str | None = None
    delivery_url: str | None = None
    notes: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    stripe_session_id: str | None = None
    stripe_payment_intent: str | None = None
    amount_cents: int | None = None
    paid_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Request:
        return cls(**data)


class OrderStore:
    """JSON-file-backed order store with state machine enforcement.

    Args:
        store_dir: Directory for JSON request files (created on first write).
    """

    def __init__(self, store_dir: Path | str = "orders") -> None:
        self._dir = Path(store_dir)
        self._lock = threading.Lock()

    def create_request(self, payload: dict[str, Any]) -> Request:
        """Validate payload and create a new request.

        The ``payload`` must contain all fields required by
        :func:`~src.fulfillment.build_order` plus ``email`` and ``product``.
        An ``order_id`` is generated automatically (``REQ-YYYYMMDD-NNNN``).

        Raises:
            OrderError: If validation fails or email is missing.
        """
        email = str(payload.get("email", "")).strip()
        if not email:
            raise OrderError("email is required.")

        product = str(payload.get("product", "")).strip()
        if not product:
            raise OrderError("product is required.")

        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            date_str = time.strftime("%Y%m%d", time.gmtime())
            seq = _next_seq(self._dir, date_str)
            request_id = f"REQ-{date_str}-{seq:04d}"

        order_payload = dict(payload)
        order_payload["order_id"] = request_id
        # Remove non-order fields before validation.
        order_payload.pop("email", None)
        order_payload.pop("product", None)

        order = build_order(order_payload)

        now = _now_iso()
        initial_event = OrderEvent(
            timestamp=now,
            event="submitted",
            detail={"product": product, "email": email},
        ).to_dict()
        req = Request(
            request_id=request_id,
            status="submitted",
            email=email,
            product=product,
            created_at=now,
            updated_at=now,
            order=asdict(order),
            events=[initial_event],
        )
        self._write(req)
        return req

    def get(self, request_id: str) -> Request:
        """Load a request by ID. Raises ``KeyError`` if not found."""
        path = self._path(request_id)
        if not path.is_file():
            raise KeyError(request_id)
        data = json.loads(path.read_text("utf-8"))
        return Request.from_dict(data)

    def list_all(self) -> list[Request]:
        """Return all requests, newest first."""
        if not self._dir.is_dir():
            return []
        requests = []
        for path in sorted(self._dir.glob("REQ-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text("utf-8"))
                requests.append(Request.from_dict(data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
        return requests

    def update_status(self, request_id: str, new_status: str) -> Request:
        """Transition a request to a new status.

        Raises:
            KeyError: If the request doesn't exist.
            OrderError: If the transition is not allowed.
        """
        with self._lock:
            req = self.get(request_id)
            allowed = TRANSITIONS.get(req.status, frozenset())
            if new_status not in allowed:
                raise OrderError(
                    f"Cannot transition from {req.status!r} to {new_status!r}. "
                    f"Allowed: {sorted(allowed)}."
                )
            req.status = new_status
            now = _now_iso()
            req.updated_at = now
            req.events.append(
                OrderEvent(timestamp=now, event=new_status, detail={}).to_dict()
            )
            self._write(req)
        return req

    def set_job_id(self, request_id: str, job_id: str) -> Request:
        """Link a render job to a request."""
        with self._lock:
            req = self.get(request_id)
            req.job_id = job_id
            req.updated_at = _now_iso()
            self._write(req)
        return req

    def add_event(
        self, request_id: str, event: str, detail: dict[str, Any] | None = None,
    ) -> Request:
        """Append a custom event to a request's event log."""
        with self._lock:
            req = self.get(request_id)
            now = _now_iso()
            req.events.append(
                OrderEvent(timestamp=now, event=event, detail=detail or {}).to_dict()
            )
            req.updated_at = now
            self._write(req)
        return req

    def add_note(self, request_id: str, note: str) -> Request:
        """Append a note to a request's history."""
        with self._lock:
            req = self.get(request_id)
            req.notes.append(f"[{_now_iso()}] {note}")
            req.updated_at = _now_iso()
            self._write(req)
        return req

    def _path(self, request_id: str) -> Path:
        return self._dir / f"{request_id}.json"

    def _write(self, req: Request) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(req.request_id).write_text(
            json.dumps(req.to_dict(), indent=2, sort_keys=True), "utf-8"
        )
