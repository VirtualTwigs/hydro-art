"""Move local storage directories onto an external drive (roadmap #29).

A thin CLI over the pure, offline :mod:`src.storage` migration helpers. It moves
one or more local storage kinds — ``output`` (default) and/or ``datasets`` — onto
a configured external-drive root (``<root>/output``, ``<root>/datasets``) and
leaves a directory symlink behind so paths that still reference the local
location keep resolving. The archive ``cache`` is intentionally not offered here:
it is regenerable and already staged on the NAS by ``build.py``.

Usage::

    # Preview what would move (no writes):
    python tools/migrate_storage.py --external-root /Volumes/Pro/hydro --dry-run

    # Move output/ (default) onto the drive and symlink it back:
    python tools/migrate_storage.py --external-root /Volumes/Pro/hydro

    # Move both output/ and datasets/, without leaving symlinks:
    python tools/migrate_storage.py --external-root /Volumes/Pro/hydro \
        --kind output --kind datasets --no-symlink

The external root may also come from the ``$HYDRO_ART_EXTERNAL_ROOT`` env var. The
drive must be mounted (:func:`src.storage.drive_available`); otherwise the command
prints the :class:`~src.storage.StorageError` message and exits non-zero **before
moving anything**. Moves real files, so it is not part of the offline test suite.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage import (
    DEFAULT_LOCAL_ROOTS,
    EXTERNAL_ROOT_ENV,
    StorageError,
    apply_migration,
    drive_available,
    plan_migration,
)

#: Kinds a user may migrate here (cache is regenerable / NAS-staged, so omitted).
MIGRATABLE_KINDS = ("output", "datasets")


def _format_bytes(n: int) -> str:
    """Render a byte count in human units (deterministic, base-1024)."""
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate local storage dirs onto an external drive (#29)."
    )
    parser.add_argument(
        "--external-root",
        default=None,
        help=f"External drive root (or the ${EXTERNAL_ROOT_ENV} env var). Required.",
    )
    parser.add_argument(
        "--kind",
        action="append",
        choices=MIGRATABLE_KINDS,
        default=None,
        help="Storage kind to migrate (repeatable; default: output).",
    )
    parser.add_argument(
        "--local-root",
        default=".",
        help="Base dir the local kinds live under (default: current dir).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan only; move nothing.",
    )
    parser.add_argument(
        "--no-symlink",
        action="store_true",
        help="Do not replace a drained source dir with a symlink to the drive.",
    )
    args = parser.parse_args(argv)

    external = args.external_root or os.environ.get(EXTERNAL_ROOT_ENV)
    if not external:
        print(
            "Configuration error: no external root "
            f"(pass --external-root or set ${EXTERNAL_ROOT_ENV}).",
            file=sys.stderr,
        )
        return 1
    external_root = Path(external)

    if not args.dry_run and not drive_available(external_root):
        print(
            f"Storage error: external drive is not mounted: {external_root}",
            file=sys.stderr,
        )
        return 1

    kinds = args.kind or ["output"]
    local_base = Path(args.local_root)

    exit_code = 0
    for kind in kinds:
        source_dir = local_base / DEFAULT_LOCAL_ROOTS[kind]
        dest_dir = external_root / kind
        plan = plan_migration(source_dir, dest_dir)
        print(
            f"[{kind}] {source_dir} -> {dest_dir}: "
            f"{len(plan.items)} file(s), {_format_bytes(plan.total_bytes)}"
            + (f", {len(plan.skipped)} already present" if plan.skipped else "")
        )
        if args.dry_run:
            continue
        try:
            result = apply_migration(plan, symlink=not args.no_symlink)
        except StorageError as exc:
            print(f"Storage error: {exc}", file=sys.stderr)
            exit_code = 1
            break
        moved = f"moved {len(result.moved)} file(s), {_format_bytes(result.bytes_moved)}"
        link = f"; symlinked {result.symlinked}" if result.symlinked else ""
        print(f"[{kind}] {moved}{link}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
