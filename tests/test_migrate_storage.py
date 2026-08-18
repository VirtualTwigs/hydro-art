"""Smoke tests for the tools/migrate_storage.py CLI (#29 TG4).

The migration CLI imports only stdlib + the GDAL-free src.storage, so it runs in
the offline suite even though a real invocation moves real files. These exercise
main() against a tmp_path "external drive": dry-run (no writes), a real move +
symlink, and the unmounted-drive guard.
"""

import os

from tools.migrate_storage import main
from src.storage import EXTERNAL_ROOT_ENV


def _populate(root, files):
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_missing_external_root_errors(monkeypatch, capsys):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    assert main([]) == 1
    assert "no external root" in capsys.readouterr().err


def test_dry_run_moves_nothing(tmp_path, capsys):
    local = tmp_path / "work"
    _populate(local / "output", {"a.svg": b"aaa", "sub/b.png": b"bbbb"})
    drive = tmp_path / "drive"
    drive.mkdir()

    code = main(
        ["--external-root", str(drive), "--local-root", str(local), "--dry-run"]
    )
    assert code == 0
    # Nothing moved: source intact, destination absent.
    assert (local / "output" / "a.svg").read_bytes() == b"aaa"
    assert not (drive / "output").exists()
    assert "2 file(s)" in capsys.readouterr().out


def test_real_move_and_symlink(tmp_path):
    local = tmp_path / "work"
    _populate(local / "output", {"a.svg": b"aaa", "sub/b.png": b"bbbb"})
    drive = tmp_path / "drive"
    drive.mkdir()

    code = main(["--external-root", str(drive), "--local-root", str(local)])
    assert code == 0
    # Files live on the drive now, and resolve back through the symlink.
    assert (drive / "output" / "a.svg").read_bytes() == b"aaa"
    assert (local / "output").is_symlink()
    assert (local / "output" / "sub" / "b.png").read_bytes() == b"bbbb"


def test_unmounted_drive_guard(tmp_path, capsys):
    local = tmp_path / "work"
    _populate(local / "output", {"a.svg": b"aaa"})
    # Neither the root nor its parent exists → not mounted.
    drive = tmp_path / "missing" / "drive"

    code = main(["--external-root", str(drive), "--local-root", str(local)])
    assert code == 1
    assert "not mounted" in capsys.readouterr().err
    # Source untouched.
    assert (local / "output" / "a.svg").read_bytes() == b"aaa"
