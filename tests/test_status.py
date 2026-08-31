"""Tests for the status-stamping pure core (roadmap #43).

Offline string transforms over fixed HANDOFF/roadmap snippets; the file
read/rewrite + diff lives in tools/update_status.py (smoke-tested separately).
"""

from __future__ import annotations

import pytest

from src.status import (
    StatusError,
    format_last_updated,
    stamp_epoch_status,
    stamp_last_updated,
    tick_roadmap_item,
)


def test_format_last_updated_with_and_without_note() -> None:
    assert format_last_updated("2026-08-30", "closed Epoch 10") == (
        "_Last updated: 2026-08-30, closed Epoch 10_"
    )
    assert format_last_updated("2026-08-30") == "_Last updated: 2026-08-30_"


def test_stamp_last_updated_replaces_multiline_block() -> None:
    text = (
        "# Handoff\n\n"
        "_Last updated: 2026-08-25, after Epoch 9\n"
        "closed with a retrospective note._\n\n"
        "## Current state\n"
    )
    out = stamp_last_updated(text, "2026-08-30", "closed Epoch 10")
    assert "_Last updated: 2026-08-30, closed Epoch 10_" in out
    assert "after Epoch 9" not in out
    # The prose after the block is untouched.
    assert "## Current state" in out


def test_stamp_last_updated_is_idempotent() -> None:
    text = "_Last updated: 2026-01-01_\n"
    once = stamp_last_updated(text, "2026-08-30", "note")
    twice = stamp_last_updated(once, "2026-08-30", "note")
    assert once == twice


def test_stamp_last_updated_missing_block_raises() -> None:
    with pytest.raises(StatusError):
        stamp_last_updated("# Handoff\n", "2026-08-30", "x")


def test_tick_roadmap_item_checks_and_is_idempotent() -> None:
    text = "39. [ ] Determinism verifier `S`\n40. [ ] Golden fixtures `M`\n"
    out = tick_roadmap_item(text, 39)
    assert "39. [x] Determinism verifier `S`" in out
    assert "40. [ ] Golden fixtures `M`" in out  # untouched
    assert tick_roadmap_item(out, 39) == out  # idempotent


def test_tick_roadmap_item_can_uncheck() -> None:
    text = "42. [x] DEM alignment invariant `S`\n"
    out = tick_roadmap_item(text, 42, checked=False)
    assert "42. [ ] DEM alignment invariant `S`" in out


def test_tick_roadmap_item_missing_raises() -> None:
    with pytest.raises(StatusError):
        tick_roadmap_item("39. [ ] x\n", 999)


def test_stamp_epoch_status_adds_then_replaces_suffix() -> None:
    text = "## Epoch 10 — Verification & real-data confidence\n\nbody\n"
    added = stamp_epoch_status(text, 10, "complete")
    assert "## Epoch 10 — Verification & real-data confidence · complete" in added
    # Replacing an existing suffix does not double-stamp.
    replaced = stamp_epoch_status(added, 10, "complete")
    assert replaced == added
    assert replaced.count("· complete") == 1


def test_stamp_epoch_status_leaves_other_epochs_untouched() -> None:
    text = "## Epoch 9 — Codebase health · complete\n## Epoch 10 — Verification\n"
    out = stamp_epoch_status(text, 10, "complete")
    assert "## Epoch 9 — Codebase health · complete" in out
    assert "## Epoch 10 — Verification · complete" in out


def test_stamp_epoch_status_missing_raises() -> None:
    with pytest.raises(StatusError):
        stamp_epoch_status("## Epoch 1 — foo\n", 77, "complete")
