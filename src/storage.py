"""External-storage layout & data migration (roadmap #29).

Pure, deterministic, offline infrastructure for putting the large files a build
reads and writes — the extracted NHDPlus/WBD ``.gdb`` "database" datasets, the
downloaded archive cache, and the rendered image outputs — on a configurable
external drive instead of the size-limited local disk.

Two capabilities:

* :func:`resolve_storage` maps a single external-drive root into ``cache`` /
  ``datasets`` / ``output`` subdirectories, with per-kind explicit overrides and
  a **mount-aware** fallback to local paths so a build never crashes (or
  ``mkdir``s under an unmounted ``/Volumes`` mount point) when the drive is
  absent. Resolution is a pure function of its inputs — an availability probe is
  injected — so it is fully offline-testable.
* :func:`plan_migration` / :func:`apply_migration` move an existing local
  directory (e.g. ``output/``) onto the drive and leave a directory symlink
  behind, so paths that already reference the local location keep resolving.

Storage location never affects rendered bytes, so this module is *not* part of
``Settings`` or ``PIPELINE_STAGES``; the entry points (``build.py``,
``serve.py``, ``tools/migrate_storage.py``) resolve storage before constructing
the pipeline. Stdlib only — no numpy / GDAL.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DEFAULT_LOCAL_ROOTS",
    "EXTERNAL_ROOT_ENV",
    "MigrationItem",
    "MigrationPlan",
    "MigrationResult",
    "StorageError",
    "StorageRoots",
    "apply_migration",
    "drive_available",
    "move_file",
    "plan_migration",
    "resolve_storage",
]

#: The local sub-directory name for each storage kind (today's on-disk layout).
DEFAULT_LOCAL_ROOTS: dict[str, str] = {
    "cache": "cache",
    "datasets": "datasets",
    "output": "output",
}

#: Environment variable naming the external-drive root (a CLI flag still wins).
EXTERNAL_ROOT_ENV: str = "HYDRO_ART_EXTERNAL_ROOT"


class StorageError(Exception):
    """Raised when a storage migration cannot be performed safely."""


@dataclass(frozen=True)
class StorageRoots:
    """Resolved on-disk roots for a build.

    Attributes:
        cache: Where downloaded archives are staged/read.
        datasets: Where extracted GIS datasets live.
        output: Where rendered images are written.
        external_root: The configured external drive root, or ``None``.
        using_external: True iff at least one root resolved onto the drive.
        staging: An optional local working directory for output (a caller may
            render here first and move the finished artifact to ``output``).
    """

    cache: Path
    datasets: Path
    output: Path
    external_root: Path | None
    using_external: bool
    staging: Path | None = None


def drive_available(
    root: Path, *, probe: Callable[[Path], bool] = Path.exists
) -> bool:
    """Return whether an external drive ``root`` is mounted and usable.

    A drive is usable when the root path exists (the caller can write into it) or
    its parent — the mount point — exists (the root can be created under it).
    This mirrors ``serve._resolve_cache_dir`` and avoids ever treating an
    unmounted ``/Volumes/…`` path as available.
    """
    return probe(root) or probe(root.parent)


def resolve_storage(
    *,
    external_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    local_root: str | Path = ".",
    overrides: Mapping[str, str | Path] | None = None,
    staging: str | Path | None = None,
    available: Callable[[Path], bool] | None = None,
) -> StorageRoots:
    """Resolve the cache / datasets / output roots.

    Precedence per kind (highest first):

    1. an explicit ``overrides[kind]`` (a CLI ``--cache-dir`` etc.) — verbatim;
    2. ``external_root / kind`` — only when the drive is available;
    3. ``local_root / DEFAULT_LOCAL_ROOTS[kind]`` — the default (today's layout).

    The external root comes from ``external_root`` if given, else the
    :data:`EXTERNAL_ROOT_ENV` environment variable, else ``None``. When a root is
    configured but not available, every non-overridden kind falls back to its
    local default and ``using_external`` is ``False``. This function never raises
    and never creates directories.

    Args:
        external_root: Explicit external drive root (wins over the env var).
        env: Environment mapping to read :data:`EXTERNAL_ROOT_ENV` from
            (defaults to ``os.environ``).
        local_root: Base directory for the local default layout.
        overrides: Per-kind explicit directories (keys: ``cache``/``datasets``/
            ``output``).
        staging: Optional local working directory for output.
        available: Injectable drive-availability probe (defaults to
            :func:`drive_available`).
    """
    env = os.environ if env is None else env
    available = drive_available if available is None else available
    overrides = overrides or {}

    root_value = external_root if external_root is not None else env.get(
        EXTERNAL_ROOT_ENV
    )
    external = Path(root_value) if root_value else None
    usable = external is not None and available(external)

    local_base = Path(local_root)
    resolved: dict[str, Path] = {}
    for kind, default_name in DEFAULT_LOCAL_ROOTS.items():
        if kind in overrides:
            resolved[kind] = Path(overrides[kind])
        elif usable:
            resolved[kind] = external / kind
        else:
            resolved[kind] = local_base / default_name

    using_external = any(
        external is not None and resolved[kind] == external / kind
        for kind in DEFAULT_LOCAL_ROOTS
    )

    return StorageRoots(
        cache=resolved["cache"],
        datasets=resolved["datasets"],
        output=resolved["output"],
        external_root=external,
        using_external=using_external,
        staging=Path(staging) if staging is not None else None,
    )


@dataclass(frozen=True)
class MigrationItem:
    """A single file to move during a storage migration."""

    source: Path
    destination: Path
    size: int


@dataclass(frozen=True)
class MigrationPlan:
    """A deterministic plan for moving one directory tree onto another root."""

    source_dir: Path
    dest_dir: Path
    items: tuple[MigrationItem, ...]
    skipped: tuple[Path, ...]
    total_bytes: int

    @property
    def is_empty(self) -> bool:
        """True when there is nothing left to move."""
        return not self.items


@dataclass(frozen=True)
class MigrationResult:
    """The outcome of applying a :class:`MigrationPlan`."""

    moved: tuple[Path, ...]
    bytes_moved: int
    symlinked: Path | None


def plan_migration(source_dir: str | Path, dest_dir: str | Path) -> MigrationPlan:
    """Plan moving every file under ``source_dir`` to ``dest_dir``.

    Pure — performs no filesystem writes. Files are enumerated recursively in a
    deterministic sorted order. A file already present at the destination with
    the same size is treated as already-migrated and reported in ``skipped``
    (so a re-run after a partial move is idempotent). A missing ``source_dir``
    yields an empty plan rather than an error.
    """
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)
    items: list[MigrationItem] = []
    skipped: list[Path] = []
    if source_dir.is_dir():
        files = sorted(p for p in source_dir.rglob("*") if p.is_file())
        for path in files:
            rel = path.relative_to(source_dir)
            destination = dest_dir / rel
            size = path.stat().st_size
            if destination.exists() and destination.stat().st_size == size:
                skipped.append(path)
            else:
                items.append(MigrationItem(path, destination, size))
    total = sum(item.size for item in items)
    return MigrationPlan(
        source_dir=source_dir,
        dest_dir=dest_dir,
        items=tuple(items),
        skipped=tuple(skipped),
        total_bytes=total,
    )


def move_file(source: str, destination: str) -> None:
    """Move one file, tolerating cross-device and network-share filesystems.

    ``shutil.move`` falls back to :func:`shutil.copy2` when the source and
    destination are on different filesystems (always the case migrating onto an
    external drive), and ``copy2`` preserves BSD file flags via ``os.chflags`` —
    which some network shares (notably SMB/Synology) reject with
    ``OSError(EINVAL)``, aborting the move. Copy the bytes and best-effort the
    mode instead, skipping the flag/timestamp metadata the share may refuse, then
    remove the source. A same-device move still short-circuits to a fast
    ``os.rename``.
    """
    try:
        os.rename(source, destination)
        return
    except OSError:
        pass  # Cross-device (or otherwise un-renamable): fall back to copy.
    shutil.copyfile(source, destination)
    try:
        shutil.copymode(source, destination)
    except OSError:
        pass  # The share may also reject chmod; the bytes are what matter.
    os.unlink(source)


def apply_migration(
    plan: MigrationPlan,
    *,
    symlink: bool = True,
    mover: Callable[[str, str], object] = move_file,
    require_mounted: bool = True,
) -> MigrationResult:
    """Execute a :class:`MigrationPlan`, moving files onto the destination drive.

    When ``require_mounted`` (the default), the destination drive must be
    available (:func:`drive_available`) or a :class:`StorageError` is raised
    **before any file is moved**. Each file is moved with ``mover`` (default
    :func:`move_file`, which tolerates cross-device and SMB destinations) after
    its destination parent is created. When ``symlink`` and the source directory
    holds no remaining real files, the source directory is replaced by a symlink
    to the destination so paths that referenced the old location keep resolving.
    """
    if require_mounted and not drive_available(plan.dest_dir):
        raise StorageError(
            f"destination drive is not mounted: {plan.dest_dir} "
            "(mount it or pass require_mounted=False)"
        )

    moved: list[Path] = []
    for item in plan.items:
        item.destination.parent.mkdir(parents=True, exist_ok=True)
        mover(str(item.source), str(item.destination))
        moved.append(item.destination)
    bytes_moved = sum(item.size for item in plan.items)

    symlinked: Path | None = None
    source = plan.source_dir
    if symlink and source.is_dir() and not source.is_symlink():
        remaining = [p for p in source.rglob("*") if p.is_file()]
        if not remaining:
            shutil.rmtree(source)
            os.symlink(plan.dest_dir.resolve(), source)
            symlinked = source

    return MigrationResult(
        moved=tuple(moved),
        bytes_moved=bytes_moved,
        symlinked=symlinked,
    )
