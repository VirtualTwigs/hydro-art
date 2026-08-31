"""Smoke tests for the tools/update_status.py CLI (roadmap #43).

The CLI imports only stdlib + the GDAL-free src.status, so it runs in the offline
suite even though a real run rewrites tracked files. These exercise main()
against tmp_path copies: a real stamp, --dry-run (no writes), and idempotency.
"""

from __future__ import annotations

from tools.update_status import main

_HANDOFF = "# Handoff\n\n_Last updated: 2026-01-01, old note._\n\n## State\nbody\n"
_ROADMAP = (
    "## Epoch 10 — Verification\n\n"
    "39. [ ] Determinism verifier `S`\n"
    "40. [ ] Golden fixtures `M`\n"
)


def _write(tmp_path):
    h = tmp_path / "HANDOFF.md"
    r = tmp_path / "roadmap.md"
    h.write_text(_HANDOFF, encoding="utf-8")
    r.write_text(_ROADMAP, encoding="utf-8")
    return h, r


def _args(h, r, *extra):
    return ["--handoff", str(h), "--roadmap", str(r), *extra]


def test_stamps_handoff_epoch_and_ticks(tmp_path, capsys):
    h, r = _write(tmp_path)
    code = main(
        _args(
            h, r,
            "--date", "2026-08-30",
            "--note", "closed Epoch 10",
            "--epoch", "10",
            "--status", "complete",
            "--tick", "39",
        )
    )
    assert code == 0
    assert "_Last updated: 2026-08-30, closed Epoch 10_" in h.read_text()
    roadmap = r.read_text()
    assert "## Epoch 10 — Verification · complete" in roadmap
    assert "39. [x] Determinism verifier `S`" in roadmap
    assert "40. [ ] Golden fixtures `M`" in roadmap  # untouched
    assert "@@" in capsys.readouterr().out  # printed a diff


def test_dry_run_writes_nothing(tmp_path, capsys):
    h, r = _write(tmp_path)
    code = main(_args(h, r, "--date", "2026-08-30", "--note", "x", "--dry-run"))
    assert code == 0
    assert h.read_text() == _HANDOFF  # unchanged
    assert "@@" in capsys.readouterr().out


def test_idempotent_second_run_no_changes(tmp_path, capsys):
    h, r = _write(tmp_path)
    common = ["--date", "2026-08-30", "--note", "n", "--epoch", "10", "--status", "complete", "--tick", "39"]
    main(_args(h, r, *common))
    capsys.readouterr()
    code = main(_args(h, r, *common))
    assert code == 0
    assert "already up to date" in capsys.readouterr().out
