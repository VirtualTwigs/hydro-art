#!/usr/bin/env python3
"""Operator CLI for gallery catalog management (Epoch 33).

Usage:
    python tools/catalog.py ingest --output-dir output/wa-clark/ --style neon-basin --endpoint digital_image
    python tools/catalog.py list [--status STATUS] [--region REGION] [--section SECTION] [--tag TAG]
    python tools/catalog.py review ENTRY_ID [--version N]
    python tools/catalog.py publish ENTRY_ID [--version N] [--section SECTION]
    python tools/catalog.py reject ENTRY_ID [--version N]
    python tools/catalog.py archive ENTRY_ID [--version N]
    python tools/catalog.py update ENTRY_ID [--version N] [--title T] [--description D] [--tags a,b] [--section S] [--sort-order N]
    python tools/catalog.py export-public [--output PATH]
    python tools/catalog.py seed
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing src/ from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.catalog import (
    DEFAULT_SECTIONS,
    CatalogEntry,
    CatalogError,
    CatalogStore,
    artwork_key,
    build_entry_id,
    public_gallery,
    seed_from_gallery_matrix,
    validate_entry,
)

CATALOG_PATH = Path("catalog/catalog.json")
PUBLIC_PATH = Path("web/data/gallery.json")
THUMB_DIR = Path("catalog/thumbnails")
THUMB_SIZE = (400, 400)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
DELIVERABLE_EXTENSIONS = {".png", ".svg", ".pdf", ".tiff", ".eps"}


def _load_store() -> CatalogStore:
    if CATALOG_PATH.exists():
        return CatalogStore.load(CATALOG_PATH)
    return CatalogStore(sections=DEFAULT_SECTIONS)


def _save_store(store: CatalogStore) -> None:
    store.save(CATALOG_PATH)
    print(f"Saved → {CATALOG_PATH}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _generate_thumbnail(source: Path, entry_id: str) -> str | None:
    """Generate a thumbnail from an image file. Returns relative path or None."""
    if source.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    try:
        from PIL import Image
    except ImportError:
        print(f"  PIL not available — skipping thumbnail for {source.name}")
        return None

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = THUMB_DIR / f"{entry_id}.png"
    img = Image.open(source)
    img.thumbnail(THUMB_SIZE)
    img.save(thumb_path, "PNG")
    print(f"  Thumbnail → {thumb_path}")
    return str(thumb_path)


def _find_primary_image(files: list[Path]) -> Path | None:
    """Find the best candidate for thumbnail generation."""
    for ext in (".png", ".jpg", ".jpeg", ".tiff"):
        for f in files:
            if f.suffix.lower() == ext:
                return f
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_ingest(args: argparse.Namespace) -> None:
    """Scan an output directory and create draft catalog entries."""
    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    store = _load_store()
    files = [f for f in sorted(output_dir.iterdir()) if f.suffix.lower() in DELIVERABLE_EXTENSIONS]
    if not files:
        print(f"No deliverables found in {output_dir}.")
        return

    entry_id = args.entry_id or build_entry_id(
        args.region, args.county, args.style, args.endpoint, args.size,
    )

    # Hash primary deliverable
    render_hash = _sha256(files[0])
    deliverables = tuple(str(f) for f in files)

    entry = CatalogEntry(
        entry_id=entry_id,
        version=store.next_version(CatalogEntry(
            entry_id=entry_id, version=1,
            region=args.region, county=args.county,
            style=args.style, endpoint=args.endpoint, size=args.size,
            rendered_at="", render_hash="", sources=(), status="draft",
            title="", description="", tags=(), section=None, sort_order=0,
            deliverables=(), thumbnail=None,
        )),
        region=args.region,
        county=args.county,
        style=args.style,
        endpoint=args.endpoint,
        size=args.size,
        rendered_at=datetime.now(timezone.utc).isoformat(),
        render_hash=render_hash,
        sources=("NHDPlus HR",),
        status="draft",
        title=args.title or f"{args.county or args.region} — {args.style}",
        description="",
        tags=tuple(args.tags.split(",")) if args.tags else (),
        section=None,
        sort_order=0,
        deliverables=deliverables,
        thumbnail=None,
    )

    validate_entry(entry)

    # Generate thumbnail
    primary = _find_primary_image(files)
    if primary:
        thumb = _generate_thumbnail(primary, entry_id)
        if thumb:
            entry = CatalogEntry(**{**entry.__dict__, "thumbnail": thumb})

    store.add(entry, auto_archive_prior=True)
    _save_store(store)
    print(f"Ingested: {entry.entry_id} v{entry.version} (draft)")


def cmd_list(args: argparse.Namespace) -> None:
    """List catalog entries with optional filters."""
    store = _load_store()
    entries = store.list_entries(
        status=args.status, region=args.region,
        section=args.section, tag=args.tag,
    )
    if not entries:
        print("No entries found.")
        return
    print(f"{'ID':<40} {'V':>2} {'Status':<10} {'Region':<15} {'Section':<15}")
    print("-" * 85)
    for e in entries:
        print(f"{e.entry_id:<40} {e.version:>2} {e.status:<10} {e.region:<15} {(e.section or '—'):<15}")


def cmd_transition(args: argparse.Namespace, to_status: str) -> None:
    """Transition an entry to a new status."""
    store = _load_store()
    version = args.version or _latest_version(store, args.entry_id)
    if hasattr(args, "section") and args.section and to_status == "published":
        entry = store.get(args.entry_id, version)
        updated = CatalogEntry(**{**entry.__dict__, "section": args.section})
        store._entries[(entry.entry_id, entry.version)] = updated
    store.transition(args.entry_id, version, to_status)
    _save_store(store)
    print(f"{args.entry_id} v{version} → {to_status}")


def cmd_update(args: argparse.Namespace) -> None:
    """Update display metadata on an entry."""
    store = _load_store()
    version = args.version or _latest_version(store, args.entry_id)
    entry = store.get(args.entry_id, version)
    updates = {}
    if args.title is not None:
        updates["title"] = args.title
    if args.description is not None:
        updates["description"] = args.description
    if args.tags is not None:
        updates["tags"] = tuple(args.tags.split(","))
    if args.section is not None:
        updates["section"] = args.section
    if args.sort_order is not None:
        updates["sort_order"] = args.sort_order
    if updates:
        updated = CatalogEntry(**{**entry.__dict__, **updates})
        store._entries[(entry.entry_id, entry.version)] = updated
        _save_store(store)
        print(f"Updated {args.entry_id} v{version}: {', '.join(updates)}")
    else:
        print("Nothing to update.")


def cmd_export_public(args: argparse.Namespace) -> None:
    """Export the public gallery JSON."""
    import json

    store = _load_store()
    gallery = public_gallery(store)
    output = Path(args.output) if args.output else PUBLIC_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(gallery, indent=2, sort_keys=True) + "\n")
    entry_count = sum(len(s["entries"]) for s in gallery["sections"])
    print(f"Exported {entry_count} published entries → {output}")


def cmd_seed(args: argparse.Namespace) -> None:
    """Seed catalog from GALLERY_MATRIX."""
    store = _load_store()
    before = len(store.list_entries())
    seed_from_gallery_matrix(store)
    after = len(store.list_entries())
    added = after - before
    _save_store(store)
    print(f"Seeded {added} entries from GALLERY_MATRIX ({after} total).")


def _latest_version(store: CatalogStore, entry_id: str) -> int:
    """Find the latest version of an entry_id."""
    versions = [e.version for e in store.list_entries() if e.entry_id == entry_id]
    if not versions:
        raise CatalogError(f"No entry with id {entry_id!r}.")
    return max(versions)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Gallery catalog management")
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest render output as draft")
    p_ingest.add_argument("--output-dir", required=True)
    p_ingest.add_argument("--region", required=True)
    p_ingest.add_argument("--county", default=None)
    p_ingest.add_argument("--style", required=True)
    p_ingest.add_argument("--endpoint", required=True)
    p_ingest.add_argument("--size", default=None)
    p_ingest.add_argument("--entry-id", default=None)
    p_ingest.add_argument("--title", default=None)
    p_ingest.add_argument("--tags", default=None, help="Comma-separated tags")

    # list
    p_list = sub.add_parser("list", help="List catalog entries")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--region", default=None)
    p_list.add_argument("--section", default=None)
    p_list.add_argument("--tag", default=None)

    # transitions
    for cmd_name in ("review", "publish", "reject", "archive"):
        p = sub.add_parser(cmd_name, help=f"Transition entry to {cmd_name}")
        p.add_argument("entry_id")
        p.add_argument("--version", type=int, default=None)
        if cmd_name == "publish":
            p.add_argument("--section", default=None)

    # update
    p_update = sub.add_parser("update", help="Update entry metadata")
    p_update.add_argument("entry_id")
    p_update.add_argument("--version", type=int, default=None)
    p_update.add_argument("--title", default=None)
    p_update.add_argument("--description", default=None)
    p_update.add_argument("--tags", default=None, help="Comma-separated tags")
    p_update.add_argument("--section", default=None)
    p_update.add_argument("--sort-order", type=int, default=None)

    # export-public
    p_export = sub.add_parser("export-public", help="Export public gallery JSON")
    p_export.add_argument("--output", default=None)

    # seed
    sub.add_parser("seed", help="Seed from GALLERY_MATRIX")

    args = parser.parse_args()

    try:
        if args.command == "ingest":
            cmd_ingest(args)
        elif args.command == "list":
            cmd_list(args)
        elif args.command in ("review", "publish", "reject", "archive"):
            status_map = {"review": "review", "publish": "published", "reject": "rejected", "archive": "archived"}
            cmd_transition(args, status_map[args.command])
        elif args.command == "update":
            cmd_update(args)
        elif args.command == "export-public":
            cmd_export_public(args)
        elif args.command == "seed":
            cmd_seed(args)
    except CatalogError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
