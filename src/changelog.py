"""Changelog generator — pure/offline core (Epoch 23, #93).

Turns structured epoch data (or the roadmap Markdown it is parsed from) into a deterministic
``CHANGELOG.md`` document for the Generation-1 ``v1.0`` release. Pure string/data transforms
only (stdlib), mirroring :mod:`src.unfinished` / :mod:`src.status`: the file reads + write live
in ``tools/build_changelog.py``, so this module stays in the offline suite and is byte-stable
for equal inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "Epoch",
    "parse_roadmap_epochs",
    "render_changelog",
]

# Roadmap Markdown shapes (mirror src.unfinished): epoch headers + numbered roadmap items.
_EPOCH_RE = re.compile(r"^#{1,4}\s*Epoch\s+([\w.]+)\s*—\s*(.*\S)\s*$")
_ITEM_RE = re.compile(r"^(\w+)\.\s*\[[ xX]\]\s*(.*\S)?\s*$")
# A trailing size code like `` `S` `` / `` `M` `` / `` `L` `` on a roadmap item line.
_SIZE_RE = re.compile(r"\s*`[SML]`\s*$")


@dataclass(frozen=True)
class Epoch:
    """One epoch's changelog entry: identity + its short item titles."""

    number: str
    title: str
    items: tuple[tuple[str, str], ...]  # (item_id, short title)
    date: str | None = None


def _clean_title(raw: str) -> str:
    """Drop a trailing ``· <status>`` suffix from an epoch header title."""
    return raw.split("·")[0].strip()


def _item_title(raw: str) -> str:
    """The short title of a roadmap item: the lead phrase before the em dash, size-code stripped."""
    text = _SIZE_RE.sub("", raw).strip()
    # roadmap items read "Short title — long description"; keep the lead phrase.
    lead = re.split(r"\s+—\s+", text, maxsplit=1)[0]
    return lead.strip()


def parse_roadmap_epochs(text: str) -> tuple[Epoch, ...]:
    """Parse roadmap Markdown into ordered :class:`Epoch` entries.

    Each ``## Epoch N — Title`` header starts a section; numbered ``N. [ ] ...`` lines within it
    become ``(item_id, short_title)`` pairs (only the item's lead phrase is kept). Pure over the
    supplied text — no fs/network.
    """
    epochs: list[Epoch] = []
    number: str | None = None
    title = ""
    items: list[tuple[str, str]] = []

    def flush() -> None:
        if number is not None:
            epochs.append(Epoch(number=number, title=title, items=tuple(items)))

    for line in text.splitlines():
        m = _EPOCH_RE.match(line)
        if m:
            flush()
            number, title, items = m.group(1), _clean_title(m.group(2)), []
            continue
        if number is None:
            continue
        item = _ITEM_RE.match(line)
        if item and item.group(2):
            items.append((item.group(1), _item_title(item.group(2))))
    flush()
    return tuple(epochs)


def render_changelog(
    version: str,
    date: str,
    epochs,
    *,
    notes=None,
) -> str:
    """Render a deterministic Keep-a-Changelog-style ``CHANGELOG.md`` document.

    Sections: a title, a ``## v<version> — <date>`` release header, optional release notes, then
    one subsection per epoch listing its item ids + short titles. Byte-identical for equal inputs.
    """
    lines = [
        "# Changelog",
        "",
        "All notable changes to Hydro-Art. This project adheres to semantic versioning; the",
        "release history below is generated from the Agent-OS roadmap epochs.",
        "",
        f"## v{version} — {date}",
        "",
    ]
    for note in notes or []:
        lines.append(f"- {note}")
    if notes:
        lines.append("")
    for epoch in epochs:
        lines.append(f"### Epoch {epoch.number} — {epoch.title}")
        for item_id, item_title in epoch.items:
            lines.append(f"- **#{item_id}** {item_title}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
