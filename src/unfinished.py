"""Detect unfinished work between sessions (pure core).

Closing out a session in this repo leaves recurring, recognizable loose ends:
a spec whose ``tasks.md`` still has ``- [ ]`` items, an "implemented, commit
pending" bullet in ``HANDOFF.md``, or a completed epoch with no retrospective.
This module is the **pure, offline** half — string/data transforms over file
*contents* that a session-start check can run to surface a punch list. It never
commits or fixes anything (committing is a deliberate, explicit user step); it
only reports.

The filesystem walk, ``git`` reads, and printing live in the thin non-pure
wrapper ``tools/detect_unfinished.py``. Imports only stdlib, so it runs in the
offline suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "RoadmapItem",
    "TaskStatus",
    "closed_epochs",
    "commit_pending_bullets",
    "parse_roadmap_items",
    "parse_task_status",
    "render_report",
]

# A markdown checkbox line: ``- [ ] 1.1 Write tests`` / ``- [x] 2.0 Ship`` (indented ok).
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.*\S)?\s*$", re.MULTILINE)
# A top-level HANDOFF bullet header line: ``- **Epoch 14 DONE …``.
_BULLET_RE = re.compile(r"^[-*]\s+(.*\S)\s*$")
# A numbered/lettered roadmap item: ``10. [ ] Title`` / ``W1. [x] Title``.
_ROADMAP_RE = re.compile(r"^(\w+)\.\s*\[([ xX])\]\s*(.*\S)?\s*$", re.MULTILINE)
# An epoch header: ``## Epoch 14 — license-free climate · complete``.
_EPOCH_RE = re.compile(r"^#{1,4}\s*Epoch\s+([\w.]+)\s*—\s*(.*\S)\s*$", re.MULTILINE)
# Words in an epoch header (or its status suffix) that mean "closed".
_CLOSED_MARKERS = ("complete", "done", "closed", "shipped")


@dataclass(frozen=True)
class TaskStatus:
    """Checkbox tally for one ``tasks.md``."""

    total: int
    done: int
    open_items: tuple[str, ...]

    @property
    def all_done(self) -> bool:
        """True when there is at least one task and none remain open."""
        return self.total > 0 and not self.open_items


@dataclass(frozen=True)
class RoadmapItem:
    """One roadmap checklist entry."""

    number: str
    checked: bool
    title: str


def parse_task_status(tasks_md: str) -> TaskStatus:
    """Tally ``- [ ]``/``- [x]`` checkboxes in a ``tasks.md``.

    ``open_items`` holds the label text of each unchecked box (empty labels are
    dropped). An empty or checkbox-free document yields ``total == 0``.
    """
    total = 0
    done = 0
    open_items: list[str] = []
    for mark, label in _CHECKBOX_RE.findall(tasks_md):
        total += 1
        if mark in ("x", "X"):
            done += 1
        elif label:
            open_items.append(label.strip())
    return TaskStatus(total=total, done=done, open_items=tuple(open_items))


def commit_pending_bullets(handoff_md: str) -> tuple[str, ...]:
    """Return the header line of each HANDOFF bullet flagged "commit pending".

    HANDOFF bullets span multiple lines; this attributes a "commit pending"
    mention to the nearest preceding ``- `` bullet header, de-duplicated in order.
    """
    headers: list[str] = []
    current: str | None = None
    for line in handoff_md.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            current = m.group(1).strip()
        if "commit pending" in line.lower() and current and current not in headers:
            headers.append(current)
    return tuple(headers)


def parse_roadmap_items(roadmap_md: str) -> tuple[RoadmapItem, ...]:
    """Parse ``N. [ ] Title`` / ``W1. [x] Title`` roadmap entries."""
    items: list[RoadmapItem] = []
    for number, mark, title in _ROADMAP_RE.findall(roadmap_md):
        items.append(
            RoadmapItem(
                number=number,
                checked=mark in ("x", "X"),
                title=(title or "").strip(),
            )
        )
    return tuple(items)


def closed_epochs(roadmap_md: str) -> tuple[tuple[str, str], ...]:
    """Return ``(epoch_id, header_text)`` for epochs whose header reads as closed.

    An epoch is "closed" when its ``## Epoch N — …`` header (typically its
    ``· <status>`` suffix) contains a completion marker like ``complete``/``done``.
    """
    found: list[tuple[str, str]] = []
    for epoch_id, rest in _EPOCH_RE.findall(roadmap_md):
        if any(marker in rest.lower() for marker in _CLOSED_MARKERS):
            found.append((epoch_id, rest.strip()))
    return tuple(found)


def render_report(sections: dict[str, list[str]]) -> str:
    """Render a punch list from ``{section title: [lines]}`` (empty → clean note).

    Deterministic: sections keep insertion order; empty sections are omitted.
    """
    blocks: list[str] = []
    for title, lines in sections.items():
        if not lines:
            continue
        body = "\n".join(f"  - {line}" for line in lines)
        blocks.append(f"{title} ({len(lines)}):\n{body}")
    if not blocks:
        return "✓ No unfinished work detected."
    return "Unfinished work:\n\n" + "\n\n".join(blocks)
