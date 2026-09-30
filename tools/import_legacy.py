"""Import legacy JSON orders, manifests, and catalog entries into the ledger.

Reads existing ``Request`` JSON files, fulfillment manifests, and
``CatalogStore`` entries and creates corresponding records in the
operations ledger via the ``OrderRepository`` protocol.

Usage::

    python tools/import_legacy.py --orders-dir output/orders
    python tools/import_legacy.py --orders-dir output/orders --apply
    python tools/import_legacy.py --catalog-file catalog/catalog.json --apply

Default mode is ``--dry-run`` (report only, no mutations).
Idempotent: re-import produces no new records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Defer imports of src/ to function scope so this stays outside the test suite.


class ImportError(Exception):
    """Raised for import violations (rights gate, data integrity)."""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Import functions (pure, testable with fake repo)
# ---------------------------------------------------------------------------


def import_request(
    repo: Any,
    request_data: dict[str, Any],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Import a single Request JSON dict into the ledger.

    Returns a result dict with ``action`` and ``request_id``.
    Idempotent: if the request already exists, returns ``skipped``.
    """
    request_id = request_data.get("request_id", "")

    # Check if already exists
    try:
        repo.get(request_id)
        return {"action": "skipped", "request_id": request_id,
                "reason": "already exists"}
    except KeyError:
        pass

    if dry_run:
        return {"action": "would_create", "request_id": request_id}

    # Build payload compatible with OrderRepository.create_request
    payload = {
        "email": request_data.get("email", ""),
        "product": request_data.get("product", ""),
        "order_id": request_id,
        "request_id": request_id,
    }
    # Merge order fields
    order = request_data.get("order", {})
    payload.update(order)

    repo.create_request(payload)
    return {"action": "created", "request_id": request_id}


def import_manifest_assets(
    repo: Any,
    manifest: dict[str, Any],
    *,
    dry_run: bool = True,
    force_visibility: str = "internal",
    force_rights_status: str = "pending",
) -> dict[str, Any]:
    """Import assets from a fulfillment manifest into the ledger.

    Returns counts of created/skipped assets.
    Enforces rights gate: ``approved_public`` requires ``rights_status=cleared``.
    """
    # Rights gate
    if (force_visibility == "approved_public"
            and force_rights_status != "cleared"):
        raise ImportError(
            "Cannot set visibility=approved_public without "
            "rights_status=cleared. Clear rights first."
        )

    order_info = manifest.get("order", {})
    order_id = order_info.get("order_id", "")
    attribution = manifest.get("attribution", "")
    deliverables = manifest.get("deliverables", [])

    created = 0
    skipped = 0
    would_create = 0

    for i, deliv in enumerate(deliverables):
        asset_id = _build_asset_id(order_id, deliv.get("kind", "final"), i + 1)

        if dry_run:
            would_create += 1
            continue

        # Check idempotency by asset_id
        try:
            existing = repo.assets if hasattr(repo, "assets") else {}
            if asset_id in existing:
                skipped += 1
                continue
        except Exception:
            pass

        from src.ledger import Asset
        asset = Asset(
            asset_id=asset_id,
            order_id=order_id,
            render_job_id=None,
            role=_map_kind_to_role(deliv.get("kind", "final")),
            storage_key=deliv.get("filename", ""),
            checksum_sha256=deliv.get("sha256", ""),
            byte_count=0,
            width_px=deliv.get("width_px"),
            height_px=deliv.get("height_px"),
            media_type=_guess_media_type(deliv.get("fmt", "")),
            visibility=force_visibility,
            rights_status=force_rights_status,
            source_attribution=attribution or None,
            created_at=_now_iso(),
            retention_class=None,
            retain_until=None,
            deleted_at=None,
        )
        repo.record_asset(asset)
        created += 1

    if dry_run:
        return {"would_create": would_create, "skipped": skipped}
    return {"created": created, "skipped": skipped}


def import_catalog_entry(
    repo: Any,
    entry: dict[str, Any],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Import a CatalogStore entry as a sample asset record.

    Returns a result dict with ``action``.
    """
    entry_id = entry.get("entry_id", "")

    # Check idempotency
    try:
        existing = repo.assets if hasattr(repo, "assets") else {}
        if any(entry_id in str(getattr(a, "asset_id", a))
               for a in existing.values()):
            return {"action": "skipped", "entry_id": entry_id}
    except Exception:
        pass

    if dry_run:
        return {"action": "would_create", "entry_id": entry_id}

    # Create a sample asset from catalog entry
    asset_id = f"AST-SAMPLE-{entry_id}-r1"

    from src.ledger import Asset
    asset = Asset(
        asset_id=asset_id,
        order_id="",
        render_job_id=None,
        role="thumbnail",
        storage_key=entry.get("thumbnail") or "",
        checksum_sha256=entry.get("render_hash", ""),
        byte_count=0,
        width_px=None,
        height_px=None,
        media_type="image/png",
        visibility="internal",
        rights_status="pending",
        source_attribution=(
            ", ".join(entry.get("sources", []))
            if entry.get("sources") else None
        ),
        created_at=entry.get("rendered_at", _now_iso()),
        retention_class=None,
        retain_until=None,
        deleted_at=None,
    )
    repo.record_asset(asset)
    return {"action": "created", "entry_id": entry_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_asset_id(order_id: str, kind: str, seq: int) -> str:
    role = _map_kind_to_role(kind)
    return f"AST-{order_id}-{role}-r{seq}"


def _map_kind_to_role(kind: str) -> str:
    mapping = {
        "print": "print",
        "vector": "vector",
        "license": "license",
        "final": "final",
        "proof": "proof",
        "report": "report",
        "figure": "figure",
    }
    return mapping.get(kind, "final")


def _guess_media_type(fmt: str) -> str:
    mapping = {
        "png": "image/png",
        "pdf": "application/pdf",
        "svg": "image/svg+xml",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "txt": "text/plain",
    }
    return mapping.get(fmt.lower(), "application/octet-stream")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy orders and catalog into the operations ledger"
    )
    parser.add_argument(
        "--orders-dir",
        default="output/orders",
        help="Directory containing REQ-*.json files",
    )
    parser.add_argument(
        "--catalog-file",
        default=None,
        help="Path to catalog.json (CatalogStore format)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL (default: $DATABASE_URL; omit for JSON fallback)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create records (default: dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report only, no mutations (default)",
    )
    args = parser.parse_args(argv)

    dry_run = not args.apply

    # Build repository
    from src.ledger import repository_factory
    repo = repository_factory(args.database_url)

    orders_dir = Path(args.orders_dir)
    counts = {"created": 0, "skipped": 0, "would_create": 0, "conflicts": 0}

    # Import request JSON files
    if orders_dir.is_dir():
        for path in sorted(orders_dir.glob("REQ-*.json")):
            try:
                data = json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  WARN: {path.name}: {exc}", file=sys.stderr)
                counts["conflicts"] += 1
                continue

            result = import_request(repo, data, dry_run=dry_run)
            action = result["action"]
            counts[action] = counts.get(action, 0) + 1
            print(f"  {action}: {result.get('request_id', '?')}")

            # Look for companion manifest
            manifest_path = path.with_suffix(".manifest.json")
            if not manifest_path.is_file():
                # Try alternate naming
                stem = path.stem
                manifest_path = orders_dir / f"{stem}.manifest.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text("utf-8"))
                    m_result = import_manifest_assets(
                        repo, manifest, dry_run=dry_run
                    )
                    for k, v in m_result.items():
                        counts[k] = counts.get(k, 0) + v
                except (json.JSONDecodeError, OSError) as exc:
                    print(f"  WARN: {manifest_path.name}: {exc}", file=sys.stderr)
    else:
        print(f"Orders directory not found: {orders_dir}")

    # Import catalog entries
    if args.catalog_file:
        catalog_path = Path(args.catalog_file)
        if catalog_path.is_file():
            try:
                catalog_data = json.loads(catalog_path.read_text("utf-8"))
                for entry in catalog_data.get("entries", []):
                    result = import_catalog_entry(repo, entry, dry_run=dry_run)
                    action = result["action"]
                    counts[action] = counts.get(action, 0) + 1
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  WARN: catalog: {exc}", file=sys.stderr)
        else:
            print(f"Catalog file not found: {catalog_path}")

    # Summary
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\n[{mode}] Import summary:")
    for k, v in sorted(counts.items()):
        if v > 0:
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
