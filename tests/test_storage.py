"""Tests for src/storage.py (roadmap #29 — external-storage layout & migration).

Pure/offline: storage resolution takes an injectable availability probe so no
real mount is touched; migration is exercised against ``tmp_path`` with a real
``shutil.move`` (and a fake mover for the unmounted guard). Stdlib only — safe in
the offline suite.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.storage import (
    EXTERNAL_ROOT_ENV,
    StorageError,
    apply_migration,
    drive_available,
    move_file,
    plan_migration,
    resolve_storage,
)

# --- TG1: root resolution ---------------------------------------------------

_ALWAYS = lambda _p: True
_NEVER = lambda _p: False


def test_default_roots_are_local_and_byte_identical():
    roots = resolve_storage(local_root=".")
    assert roots.cache == Path("cache")
    assert roots.datasets == Path("datasets")
    assert roots.output == Path("output")
    assert roots.external_root is None
    assert roots.using_external is False


def test_external_root_expands_to_kind_subdirs_when_available():
    roots = resolve_storage(external_root="/Volumes/Pro/hydro", available=_ALWAYS)
    assert roots.cache == Path("/Volumes/Pro/hydro/cache")
    assert roots.datasets == Path("/Volumes/Pro/hydro/datasets")
    assert roots.output == Path("/Volumes/Pro/hydro/output")
    assert roots.external_root == Path("/Volumes/Pro/hydro")
    assert roots.using_external is True


def test_unmounted_external_root_falls_back_to_local():
    roots = resolve_storage(
        external_root="/Volumes/Pro/hydro", local_root=".", available=_NEVER
    )
    assert roots.cache == Path("cache")
    assert roots.datasets == Path("datasets")
    assert roots.output == Path("output")
    # The configured drive is remembered, but nothing resolved onto it.
    assert roots.external_root == Path("/Volumes/Pro/hydro")
    assert roots.using_external is False


def test_per_kind_override_wins_over_external_and_local():
    roots = resolve_storage(
        external_root="/Volumes/Pro/hydro",
        overrides={"output": "/tmp/custom-out"},
        available=_ALWAYS,
    )
    assert roots.output == Path("/tmp/custom-out")
    # The other kinds still resolve onto the external drive.
    assert roots.datasets == Path("/Volumes/Pro/hydro/datasets")
    assert roots.using_external is True


def test_env_var_supplies_root_and_arg_beats_env():
    env = {EXTERNAL_ROOT_ENV: "/Volumes/FromEnv"}
    from_env = resolve_storage(env=env, available=_ALWAYS)
    assert from_env.datasets == Path("/Volumes/FromEnv/datasets")

    from_arg = resolve_storage(
        external_root="/Volumes/FromArg", env=env, available=_ALWAYS
    )
    assert from_arg.datasets == Path("/Volumes/FromArg/datasets")


def test_staging_surfaces_on_storage_roots():
    roots = resolve_storage(staging="/tmp/work")
    assert roots.staging == Path("/tmp/work")
    assert resolve_storage().staging is None


def test_drive_available_true_when_root_or_parent_exists(tmp_path):
    existing = tmp_path / "drive"
    existing.mkdir()
    assert drive_available(existing) is True
    # Root missing but its parent (the mount point) exists → available.
    assert drive_available(tmp_path / "drive2") is True
    # Neither the root nor its parent exists → unmounted.
    assert drive_available(tmp_path / "missing" / "hydro") is False


def test_storage_error_is_exception():
    assert issubclass(StorageError, Exception)


# --- TG2: migration ---------------------------------------------------------


def _populate(root: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_plan_enumerates_files_sorted_with_total_bytes(tmp_path):
    src = tmp_path / "output"
    _populate(src, {"b.svg": b"12345", "sub/a.png": b"67", "c.pdf": b"890"})
    dest = tmp_path / "drive" / "output"

    plan = plan_migration(src, dest)

    assert [item.source.relative_to(src).as_posix() for item in plan.items] == [
        "b.svg",
        "c.pdf",
        "sub/a.png",
    ]
    assert plan.items[0].destination == dest / "b.svg"
    assert plan.total_bytes == 5 + 3 + 2
    assert plan.skipped == ()
    assert plan.is_empty is False


def test_plan_skips_files_already_present_with_same_size(tmp_path):
    src = tmp_path / "output"
    _populate(src, {"a.svg": b"aaaa", "b.svg": b"bb"})
    dest = tmp_path / "drive" / "output"
    _populate(dest, {"a.svg": b"XXXX"})  # same size (4) → skipped

    plan = plan_migration(src, dest)

    moved = [item.source.name for item in plan.items]
    assert moved == ["b.svg"]
    assert (src / "a.svg") in plan.skipped


def test_missing_source_dir_yields_empty_plan(tmp_path):
    plan = plan_migration(tmp_path / "nope", tmp_path / "drive" / "output")
    assert plan.is_empty is True
    assert plan.items == ()
    assert plan.total_bytes == 0


def test_apply_moves_files_and_symlinks_source_dir(tmp_path):
    src = tmp_path / "output"
    _populate(src, {"oregon.svg": b"<svg/>", "sub/wa.png": b"PNG"})
    dest = tmp_path / "drive" / "output"

    plan = plan_migration(src, dest)
    result = apply_migration(plan, require_mounted=False)

    # Files physically moved to the drive.
    assert (dest / "oregon.svg").read_bytes() == b"<svg/>"
    assert (dest / "sub" / "wa.png").read_bytes() == b"PNG"
    assert result.bytes_moved == len(b"<svg/>") + len(b"PNG")
    # The local path is now a symlink to the drive, so old references resolve.
    assert src.is_symlink()
    assert src.resolve() == dest.resolve()
    assert (src / "oregon.svg").read_bytes() == b"<svg/>"
    assert result.symlinked == src


def test_apply_refuses_when_destination_unmounted(tmp_path):
    src = tmp_path / "output"
    _populate(src, {"a.svg": b"a"})
    # Destination two levels below a non-existent mount point → unavailable.
    dest = tmp_path / "unmounted-drive" / "sub" / "output"
    plan = plan_migration(src, dest)

    calls: list = []

    def _fake_mover(s, d):  # must never be called
        calls.append((s, d))

    with pytest.raises(StorageError):
        apply_migration(plan, mover=_fake_mover, require_mounted=True)
    assert calls == []
    assert not src.is_symlink()  # source untouched


def test_apply_is_resumable_after_partial_move(tmp_path):
    src = tmp_path / "output"
    _populate(src, {"a.svg": b"aaaa", "b.svg": b"bb"})
    dest = tmp_path / "drive" / "output"
    _populate(dest, {"a.svg": b"aaaa"})  # a.svg already migrated
    (src / "a.svg").unlink()  # simulate a prior partial move

    plan = plan_migration(src, dest)
    result = apply_migration(plan, require_mounted=False)

    assert (dest / "b.svg").read_bytes() == b"bb"
    assert result.bytes_moved == 2  # only b.svg moved this run
    assert src.is_symlink()
    assert (src / "a.svg").read_bytes() == b"aaaa"


def test_move_file_falls_back_to_copy_when_rename_fails(tmp_path, monkeypatch):
    # Simulates a cross-device destination (e.g. an SMB share): os.rename raises
    # EXDEV, so move_file must copy the bytes and unlink the source rather than
    # abort. Guards the regression where shutil.move's copy2 fallback called
    # os.chflags and was rejected (EINVAL) by a Synology SMB mount.
    src = tmp_path / "a.svg"
    src.write_bytes(b"<svg/>")
    dest = tmp_path / "drive" / "a.svg"
    dest.parent.mkdir(parents=True)

    real_rename = os.rename

    def _cross_device(s, d):
        raise OSError(18, "Cross-device link")

    monkeypatch.setattr(os, "rename", _cross_device)
    move_file(str(src), str(dest))
    monkeypatch.setattr(os, "rename", real_rename)

    assert dest.read_bytes() == b"<svg/>"
    assert not src.exists()  # source removed after a successful copy
