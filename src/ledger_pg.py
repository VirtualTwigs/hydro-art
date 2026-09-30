"""PostgreSQL implementation of the OrderRepository protocol.

Lazy-imports ``psycopg`` (v3) inside ``__init__`` — never at module top level —
so the offline test suite can import this module without a GDAL/database stack.
All writes are transactional; all queries use parameterized ``%s`` placeholders.

Pure parallel subsystem: not wired into ``PIPELINE_STAGES``.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from src.ledger import (
    Asset,
    Delivery,
    LedgerError,
    validate_asset_role,
    validate_rights_status,
    validate_visibility,
)

__all__ = ["PgOrderRepository"]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class PgOrderRepository:
    """PostgreSQL-backed order repository satisfying :class:`~src.ledger.OrderRepository`.

    ``psycopg`` is imported lazily inside ``__init__``; the class can be
    referenced (but not instantiated) without the driver installed.
    """

    def __init__(self, database_url: str) -> None:
        try:
            import psycopg  # lazy import — never at module top level
        except ImportError as exc:
            raise LedgerError(
                "PostgreSQL adapter requires psycopg. "
                "Install it: pip install psycopg[binary]"
            ) from exc

        self._url = database_url
        try:
            self._conn = psycopg.connect(database_url, autocommit=False)
        except Exception as exc:
            raise LedgerError(
                f"Failed to connect to database: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # OrderRepository protocol methods
    # ------------------------------------------------------------------

    def create_request(self, payload: dict[str, Any]) -> Any:
        """Validate payload and INSERT a new request row."""
        email = str(payload.get("email", "")).strip()
        product = str(payload.get("product", "")).strip()
        request_id = str(payload.get("order_id", "")).strip()

        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO requests "
            "(request_id, email, product, status, payload, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (request_id, email, product, "submitted",
             json.dumps(payload), now, now),
        )
        # Record the initial event
        cur.execute(
            "INSERT INTO events "
            "(entity_type, entity_id, occurred_at, event_name, actor, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("request", request_id, now, "submitted", "system",
             json.dumps({"product": product, "email": email})),
        )
        self._conn.commit()
        return self.get(request_id)

    def get(self, request_id: str) -> Any:
        """SELECT a request by ID. Raises ``KeyError`` if not found."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT request_id, email, product, status, place_id, payload, "
            "created_at, updated_at "
            "FROM requests WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(request_id)

        # Fetch events
        cur.execute(
            "SELECT occurred_at, event_name, detail "
            "FROM events WHERE entity_type = %s AND entity_id = %s "
            "ORDER BY occurred_at",
            ("request", request_id),
        )
        events = [
            {"timestamp": r[0], "event": r[1],
             "detail": json.loads(r[2]) if isinstance(r[2], str) else (r[2] or {})}
            for r in cur.fetchall()
        ]

        # Build a Request-compatible object
        from src.orders import Request
        payload_raw = row[5]
        payload_dict = (
            json.loads(payload_raw) if isinstance(payload_raw, str)
            else (payload_raw or {})
        )
        return Request(
            request_id=row[0],
            status=row[3],
            email=row[1],
            product=row[2],
            created_at=str(row[6]),
            updated_at=str(row[7]),
            order=payload_dict,
            events=events,
        )

    def list_all(self) -> list[Any]:
        """Return all requests, newest first."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT request_id FROM requests ORDER BY created_at DESC"
        )
        return [self.get(row[0]) for row in cur.fetchall()]

    def update_status(self, request_id: str, new_status: str) -> Any:
        """Transition a request to a new status with state-machine enforcement."""
        from src.orders import TRANSITIONS
        from src.fulfillment import OrderError

        req = self.get(request_id)
        allowed = TRANSITIONS.get(req.status, frozenset())
        if new_status not in allowed:
            raise OrderError(
                f"Cannot transition from {req.status!r} to {new_status!r}. "
                f"Allowed: {sorted(allowed)}."
            )

        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE requests SET status = %s, updated_at = %s "
            "WHERE request_id = %s",
            (new_status, now, request_id),
        )
        cur.execute(
            "INSERT INTO events "
            "(entity_type, entity_id, occurred_at, event_name, actor, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("request", request_id, now, new_status, "system",
             json.dumps({})),
        )
        self._conn.commit()
        return self.get(request_id)

    def set_job_id(self, request_id: str, job_id: str) -> Any:
        """Link a render job to a request (stored in payload jsonb)."""
        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE requests SET payload = payload || %s, updated_at = %s "
            "WHERE request_id = %s",
            (json.dumps({"job_id": job_id}), now, request_id),
        )
        self._conn.commit()
        return self.get(request_id)

    def add_event(
        self,
        request_id: str,
        event: str,
        detail: dict[str, Any] | None = None,
    ) -> Any:
        """Append an event to the events table for this request."""
        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO events "
            "(entity_type, entity_id, occurred_at, event_name, actor, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("request", request_id, now, event, "system",
             json.dumps(detail or {})),
        )
        self._conn.commit()
        return self.get(request_id)

    def add_note(self, request_id: str, note: str) -> Any:
        """Append a note as an event."""
        return self.add_event(request_id, "note", {"text": note})

    # ------------------------------------------------------------------
    # Extended methods (asset, delivery, analysis)
    # ------------------------------------------------------------------

    def record_asset(self, asset: Asset) -> None:
        """INSERT asset row + event in a single transaction."""
        validate_asset_role(asset.role)
        validate_visibility(asset.visibility)
        validate_rights_status(asset.rights_status)

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO assets "
            "(asset_id, order_id, render_job_id, role, storage_key, "
            "checksum_sha256, byte_count, width_px, height_px, media_type, "
            "visibility, rights_status, source_attribution, created_at, "
            "retention_class, retain_until, deleted_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s)",
            (asset.asset_id, asset.order_id, asset.render_job_id,
             asset.role, asset.storage_key, asset.checksum_sha256,
             asset.byte_count, asset.width_px, asset.height_px,
             asset.media_type, asset.visibility, asset.rights_status,
             asset.source_attribution, asset.created_at,
             asset.retention_class, asset.retain_until, asset.deleted_at),
        )
        # Append event
        cur.execute(
            "INSERT INTO events "
            "(entity_type, entity_id, occurred_at, event_name, actor, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("asset", asset.asset_id, asset.created_at,
             "asset_created", "system",
             json.dumps({"role": asset.role, "order_id": asset.order_id})),
        )
        self._conn.commit()

    def record_delivery(self, delivery: Delivery) -> None:
        """INSERT a delivery row."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO deliveries "
            "(delivery_id, order_id, delivered_at, access_expires_at, "
            "access_revoked_at, asset_ids, reason, fee_waived) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (delivery.delivery_id, delivery.order_id,
             delivery.delivered_at, delivery.access_expires_at,
             delivery.access_revoked_at, list(delivery.asset_ids),
             delivery.reason, delivery.fee_waived),
        )
        # Append event
        cur.execute(
            "INSERT INTO events "
            "(entity_type, entity_id, occurred_at, event_name, actor, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ("delivery", delivery.delivery_id, delivery.delivered_at,
             "delivery_created", "system",
             json.dumps({"order_id": delivery.order_id,
                         "asset_count": len(delivery.asset_ids)})),
        )
        self._conn.commit()

    def get_assets_for_order(self, order_id: str) -> list[Asset]:
        """SELECT all assets belonging to an order."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT asset_id, order_id, render_job_id, role, storage_key, "
            "checksum_sha256, byte_count, width_px, height_px, media_type, "
            "visibility, rights_status, source_attribution, created_at, "
            "retention_class, retain_until, deleted_at "
            "FROM assets WHERE order_id = %s "
            "ORDER BY created_at",
            (order_id,),
        )
        return [
            Asset(
                asset_id=row[0],
                order_id=row[1],
                render_job_id=row[2],
                role=row[3],
                storage_key=row[4],
                checksum_sha256=row[5],
                byte_count=row[6],
                width_px=row[7],
                height_px=row[8],
                media_type=row[9],
                visibility=row[10],
                rights_status=row[11],
                source_attribution=row[12],
                created_at=str(row[13]),
                retention_class=row[14],
                retain_until=str(row[15]) if row[15] else None,
                deleted_at=str(row[16]) if row[16] else None,
            )
            for row in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # Analysis methods
    # ------------------------------------------------------------------

    def record_analysis_run(
        self,
        run_id: str,
        place_id: str,
        *,
        recipe_digest: str | None = None,
        code_revision: str | None = None,
        input_sources: dict[str, Any] | None = None,
        start_year: int,
        end_year: int,
        metric_version: str,
        validation_status: str = "draft",
        reviewer: str | None = None,
        notes: str | None = None,
    ) -> None:
        """INSERT an analysis run."""
        valid_statuses = ("draft", "validated", "reference_only", "unvalidated")
        if validation_status not in valid_statuses:
            raise LedgerError(
                f"Invalid validation_status {validation_status!r}. "
                f"Valid: {', '.join(valid_statuses)}."
            )

        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO analysis_runs "
            "(run_id, place_id, recipe_digest, code_revision, input_sources, "
            "start_year, end_year, metric_version, validation_status, "
            "created_at, reviewer, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (run_id, place_id, recipe_digest, code_revision,
             json.dumps(input_sources or {}), start_year, end_year,
             metric_version, validation_status, now, reviewer, notes),
        )
        self._conn.commit()

    def record_analysis_metric(
        self,
        metric_id: str,
        run_id: str,
        *,
        name: str,
        units: str,
        method: str,
        method_version: str,
        value: Any,
        interpretation_status: str = "draft",
    ) -> None:
        """INSERT an analysis metric."""
        valid_statuses = ("draft", "validated", "unvalidated", "reference_only")
        if interpretation_status not in valid_statuses:
            raise LedgerError(
                f"Invalid interpretation_status {interpretation_status!r}. "
                f"Valid: {', '.join(valid_statuses)}."
            )

        now = _now_iso()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO analysis_metrics "
            "(metric_id, run_id, name, units, method, method_version, "
            "value, interpretation_status, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (metric_id, run_id, name, units, method, method_version,
             json.dumps(value), interpretation_status, now),
        )
        self._conn.commit()

    def get_analysis_for_place(self, place_id: str) -> list[dict[str, Any]]:
        """Return analysis runs and their metrics for a place."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT run_id, place_id, recipe_digest, code_revision, "
            "input_sources, start_year, end_year, metric_version, "
            "validation_status, created_at, reviewer, notes "
            "FROM analysis_runs WHERE place_id = %s "
            "ORDER BY created_at",
            (place_id,),
        )
        runs = []
        for row in cur.fetchall():
            run_id = row[0]
            # Fetch metrics for this run
            cur2 = self._conn.cursor()
            cur2.execute(
                "SELECT metric_id, run_id, name, units, method, "
                "method_version, value, interpretation_status, created_at "
                "FROM analysis_metrics WHERE run_id = %s "
                "ORDER BY created_at",
                (run_id,),
            )
            metrics = [
                {
                    "metric_id": m[0], "run_id": m[1], "name": m[2],
                    "units": m[3], "method": m[4], "method_version": m[5],
                    "value": (json.loads(m[6]) if isinstance(m[6], str)
                              else m[6]),
                    "interpretation_status": m[7], "created_at": str(m[8]),
                }
                for m in cur2.fetchall()
            ]
            input_src = row[4]
            if isinstance(input_src, str):
                input_src = json.loads(input_src)
            runs.append({
                "run_id": row[0],
                "place_id": row[1],
                "recipe_digest": row[2],
                "code_revision": row[3],
                "input_sources": input_src or {},
                "start_year": row[5],
                "end_year": row[6],
                "metric_version": row[7],
                "validation_status": row[8],
                "created_at": str(row[9]),
                "reviewer": row[10],
                "notes": row[11],
                "metrics": metrics,
            })
        return runs
