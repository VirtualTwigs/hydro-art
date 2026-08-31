"""HANDOFF/roadmap status stamping (roadmap #43, pure core).

Closing an epoch repeats the same mechanical bookkeeping: bump ``HANDOFF.md``'s
``_Last updated: …_`` line, tick a roadmap checkbox, and stamp an epoch header's
``· <status>`` suffix. That churn used to cost 3–4 hand-edit commits per epoch.

This module is the **pure, offline** half: string transforms over the file
*contents* (compose the last-updated line, tick a numbered roadmap item, set an
epoch header's status suffix). Each transform is idempotent — re-applying the same
inputs yields the same text — and touches only timestamps/status lines, never the
hand-authored prose bullets. The file read/rewrite + diff printing is the thin
non-pure wrapper in ``tools/update_status.py``. Imports only stdlib, so it runs in
the offline suite.
"""

from __future__ import annotations

import re

__all__ = [
    "StatusError",
    "format_last_updated",
    "stamp_last_updated",
    "tick_roadmap_item",
    "stamp_epoch_status",
]

_LAST_UPDATED_RE = re.compile(r"_Last updated:.*?_", re.DOTALL)


class StatusError(ValueError):
    """A status transform could not find the line/item it was asked to update."""


def format_last_updated(date: str, note: str = "") -> str:
    """Compose the ``_Last updated: <date>[, <note>]_`` italic line."""
    note = note.strip()
    return f"_Last updated: {date}, {note}_" if note else f"_Last updated: {date}_"


def stamp_last_updated(text: str, date: str, note: str = "") -> str:
    """Replace the ``_Last updated: …_`` block (may span lines) with a fresh line.

    Raises:
        StatusError: If no ``_Last updated: …_`` block is present.
    """
    if not _LAST_UPDATED_RE.search(text):
        raise StatusError("No '_Last updated: …_' block found to stamp.")
    replacement = format_last_updated(date, note)
    # A lambda replacement avoids backreference interpretation in the note text.
    return _LAST_UPDATED_RE.sub(lambda _m: replacement, text, count=1)


def tick_roadmap_item(text: str, number: int, *, checked: bool = True) -> str:
    """Set the ``N. [ ]``/``N. [x]`` checkbox for roadmap item ``number``.

    Idempotent: ticking an already-ticked item is a no-op. Raises:
        StatusError: If no ``N. [ ]``/``N. [x]`` line exists.
    """
    mark = "x" if checked else " "
    pattern = re.compile(rf"^({re.escape(str(number))}\.)\s+\[[ xX]\]", re.MULTILINE)
    if not pattern.search(text):
        raise StatusError(f"No roadmap item '{number}. [ ]' found to tick.")
    return pattern.sub(rf"\1 [{mark}]", text, count=1)


def stamp_epoch_status(text: str, epoch: int | str, status: str) -> str:
    """Set (or replace) the ``· <status>`` suffix on an epoch header.

    Matches ``## Epoch <epoch> — …`` and replaces any existing trailing
    ``· <status>`` (idempotent). An empty ``status`` strips the suffix.

    Raises:
        StatusError: If the epoch header is not found.
    """
    header_re = re.compile(rf"^## Epoch {re.escape(str(epoch))} —[^\n]*$", re.MULTILINE)
    m = header_re.search(text)
    if not m:
        raise StatusError(f"No '## Epoch {epoch} — …' header found to stamp.")
    line = m.group(0)
    base = re.sub(r"\s+·\s+[^\n]*$", "", line)
    new_line = f"{base} · {status.strip()}" if status.strip() else base
    return text[: m.start()] + new_line + text[m.end() :]
