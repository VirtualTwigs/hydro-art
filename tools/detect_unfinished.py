"""Detect unfinished work between sessions (report-only CLI).

A thin, non-offline wrapper over the pure :mod:`src.unfinished` transforms. It
walks ``agent-os/specs/``, reads ``HANDOFF.md`` / the roadmap / the
retrospectives folder, and inspects the ``git`` working tree, then prints a
punch list of loose ends a session left behind:

- specs whose ``tasks.md`` still has ``- [ ]`` items (open tasks);
- specs whose tasks are all done but have no ``implementation/report.md``;
- HANDOFF bullets flagged "commit pending";
- closed epochs with no ``agent-os/retrospectives/`` note;
- uncommitted tracked changes (scratch/output paths filtered out).

It **only reports** — it never commits or edits anything (committing is a
deliberate, explicit user step). Exit code is ``1`` when anything is found and
``0`` when the tree is clean, so it can back a session-start hook.

Usage::

    python -m tools.detect_unfinished            # human punch list
    python -m tools.detect_unfinished --quiet     # print nothing when clean
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from src.unfinished import (
    closed_epochs,
    commit_pending_bullets,
    parse_task_status,
    render_report,
)

# Untracked paths that are scratch/regenerable, not "unfinished work".
_IGNORE_PREFIXES = (
    "notebooks/",
    "market-analysis/",
    "output/",
    "datasets/",
    "cache/",
    "logs/",
    ".claude/scheduled_tasks.lock",
)
_IGNORE_SUFFIXES = (".lock",)
_IGNORE_SUBSTRINGS = (".ipynb_checkpoints", "Untitled.ipynb", ".DS_Store")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _is_noise(rel_path: str) -> bool:
    return (
        rel_path.startswith(_IGNORE_PREFIXES)
        or rel_path.endswith(_IGNORE_SUFFIXES)
        or any(s in rel_path for s in _IGNORE_SUBSTRINGS)
    )


def _open_tasks_and_undocumented(specs_dir: Path) -> tuple[list[str], list[str]]:
    """(open-task lines, all-done-but-undocumented spec names) across all specs."""
    open_lines: list[str] = []
    undocumented: list[str] = []
    for tasks_md in sorted(specs_dir.glob("*/tasks.md")):
        spec = tasks_md.parent.name
        status = parse_task_status(_read(tasks_md))
        if status.total == 0:
            continue
        if status.open_items:
            preview = ", ".join(status.open_items[:3])
            more = "" if len(status.open_items) <= 3 else f" (+{len(status.open_items) - 3} more)"
            open_lines.append(f"{spec}: {status.done}/{status.total} done — {preview}{more}")
        elif not (tasks_md.parent / "implementation" / "report.md").exists():
            undocumented.append(f"{spec}: all {status.total} tasks done, no implementation/report.md")
    return open_lines, undocumented


def _missing_retrospectives(roadmap_md: str, retro_dir: Path) -> list[str]:
    retro_text = " ".join(p.name for p in retro_dir.glob("*.md")) if retro_dir.exists() else ""
    missing: list[str] = []
    for epoch_id, header in closed_epochs(roadmap_md):
        needle = f"epoch-{epoch_id}"
        if needle not in retro_text.lower():
            missing.append(f"Epoch {epoch_id} closed ({header}) — no retrospective note")
    return missing


def _uncommitted(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    lines: list[str] = []
    for raw in out.splitlines():
        if not raw.strip():
            continue
        code, rel = raw[:2], raw[3:].strip().strip('"')
        # Untracked scratch is noise; tracked modifications are always real.
        if code == "??" and _is_noise(rel):
            continue
        lines.append(f"[{code.strip() or '?'}] {rel}")
    return lines


def build_sections(root: Path) -> dict[str, list[str]]:
    """Compose the punch-list sections by reading the repo at ``root``."""
    specs_dir = root / "agent-os" / "specs"
    roadmap_md = _read(root / "agent-os" / "product" / "roadmap.md")
    retro_dir = root / "agent-os" / "retrospectives"

    open_lines, undocumented = _open_tasks_and_undocumented(specs_dir)
    return {
        "Open spec tasks": open_lines,
        "Done but undocumented": undocumented,
        "Commit pending (HANDOFF)": list(commit_pending_bullets(_read(root / "HANDOFF.md"))),
        "Closed epochs missing a retrospective": _missing_retrospectives(roadmap_md, retro_dir),
        "Uncommitted changes": _uncommitted(root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report unfinished work left between sessions (never fixes)."
    )
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print nothing when the tree is clean (hook-friendly).",
    )
    args = parser.parse_args(argv)

    sections = build_sections(Path(args.root))
    any_found = any(sections.values())
    if any_found or not args.quiet:
        print(render_report(sections))
    return 1 if any_found else 0


if __name__ == "__main__":
    sys.exit(main())
