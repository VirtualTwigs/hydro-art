"""HANDOFF/roadmap status-stamp CLI (roadmap #43).

A thin, idempotent wrapper over the pure :mod:`src.status` transforms that stamps
the mechanical bookkeeping an epoch close repeats: bump ``HANDOFF.md``'s
``_Last updated: …_`` line, tick roadmap checkboxes, and set an epoch header's
``· <status>`` suffix — printing a unified diff of exactly what changed. Re-running
with the same inputs is a no-op.

This CLI imports only stdlib + the GDAL-free :mod:`src.status`, so its ``main`` is
smoke-tested in the offline suite even though a real run rewrites tracked files.

Usage::

    python -m tools.update_status --note "closed Epoch 10" --epoch 10 --status complete \\
        --tick 39 --tick 40 --tick 41 --tick 42 --tick 43
    python -m tools.update_status --note "wip" --dry-run
"""

from __future__ import annotations

import argparse
import difflib
import sys
from datetime import date as _date
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.status import (
    StatusError,
    stamp_epoch_status,
    stamp_last_updated,
    tick_roadmap_item,
)


def _diff(old: str, new: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stamp HANDOFF/roadmap timestamps + status (roadmap #43)."
    )
    parser.add_argument("--handoff", default="HANDOFF.md", help="HANDOFF path.")
    parser.add_argument(
        "--roadmap", default="agent-os/product/roadmap.md", help="Roadmap path."
    )
    parser.add_argument(
        "--date", default=None, help="Date for the last-updated line (default today)."
    )
    parser.add_argument("--note", default="", help="One-line last-updated note.")
    parser.add_argument(
        "--epoch", type=int, default=None, help="Epoch number to stamp a status on."
    )
    parser.add_argument(
        "--status", default="", help="Epoch status suffix (e.g. 'complete')."
    )
    parser.add_argument(
        "--tick",
        type=int,
        action="append",
        default=[],
        help="Roadmap item number to tick [x] (repeatable).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the diff without writing."
    )
    args = parser.parse_args(argv)

    stamp_date = args.date or _date.today().isoformat()
    handoff_path = Path(args.handoff)
    roadmap_path = Path(args.roadmap)

    try:
        # HANDOFF: always stamp the last-updated line.
        handoff_old = handoff_path.read_text(encoding="utf-8")
        handoff_new = stamp_last_updated(handoff_old, stamp_date, args.note)

        # Roadmap: optional epoch-status + checkbox ticks.
        roadmap_old = roadmap_path.read_text(encoding="utf-8")
        roadmap_new = roadmap_old
        if args.epoch is not None:
            roadmap_new = stamp_epoch_status(roadmap_new, args.epoch, args.status)
        for number in args.tick:
            roadmap_new = tick_roadmap_item(roadmap_new, number)
    except (StatusError, OSError) as exc:
        print(f"status error: {exc}", file=sys.stderr)
        return 1

    changed = False
    for path, old, new in (
        (handoff_path, handoff_old, handoff_new),
        (roadmap_path, roadmap_old, roadmap_new),
    ):
        if old == new:
            continue
        changed = True
        print(_diff(old, new, str(path)))
        if not args.dry_run:
            path.write_text(new, encoding="utf-8")

    if not changed:
        print("status: already up to date (no changes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
