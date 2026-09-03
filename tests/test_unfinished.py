"""Offline tests for the unfinished-work detector core (src.unfinished)."""

from __future__ import annotations

from src.unfinished import (
    closed_epochs,
    commit_pending_bullets,
    parse_roadmap_items,
    parse_task_status,
    render_report,
)


def test_task_status_all_done() -> None:
    md = "- [x] 1.1 write tests\n  - [x] 1.2 implement\n- [X] 1.3 run\n"
    status = parse_task_status(md)
    assert status.total == 3
    assert status.done == 3
    assert status.open_items == ()
    assert status.all_done is True


def test_task_status_with_open_items() -> None:
    md = "- [x] 1.1 done thing\n- [ ] 5.2 render frame set\n- [ ] 6.4 write retro\n"
    status = parse_task_status(md)
    assert status.total == 3
    assert status.done == 1
    assert status.open_items == ("5.2 render frame set", "6.4 write retro")
    assert status.all_done is False


def test_task_status_empty_document() -> None:
    status = parse_task_status("# Just a heading, no checkboxes\n")
    assert status.total == 0
    assert status.all_done is False  # nothing to do is not "done"


def test_commit_pending_attributes_to_bullet_header() -> None:
    handoff = (
        "- **Epoch 14 DONE** — license-free climate.\n"
        "  Suite 666 passing; commit pending — separate `commit item #60`.\n"
        "- **#40 DONE** — golden fixtures, committed `abc1234`.\n"
        "- **#56 core** implemented, commit pending.\n"
    )
    assert commit_pending_bullets(handoff) == (
        "**Epoch 14 DONE** — license-free climate.",
        "**#56 core** implemented, commit pending.",
    )


def test_parse_roadmap_items_handles_numbers_and_letters() -> None:
    md = "1. [x] Config foundation `S`\n10. [ ] Multi-format export `L`\nW1. [x] Waterbodies `M`\n"
    items = parse_roadmap_items(md)
    assert [(i.number, i.checked) for i in items] == [
        ("1", True),
        ("10", False),
        ("W1", True),
    ]
    assert items[1].title.startswith("Multi-format export")


def test_closed_epochs_reads_status_suffix() -> None:
    md = (
        "## Epoch 1 — foundation · complete\n"
        "## Epoch 7 — external storage\n"  # no closed marker
        "## Epoch 12 — watershed report · DONE\n"
    )
    assert closed_epochs(md) == (
        ("1", "foundation · complete"),
        ("12", "watershed report · DONE"),
    )


def test_render_report_empty_and_populated() -> None:
    assert render_report({"Open tasks": [], "Commit pending": []}) == (
        "✓ No unfinished work detected."
    )
    report = render_report({"Open tasks": ["spec-x: 5.2 render frames"]})
    assert "Unfinished work:" in report
    assert "Open tasks (1):" in report
    assert "  - spec-x: 5.2 render frames" in report
