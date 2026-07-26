"""Persistent cache, metadata index, safe extraction, and acquisition.

The cache lives under ``cache/`` and persists between runs so already-fetched
archives are reused instead of re-downloaded. A JSON metadata index records
provenance (url, size, checksum, timestamps) for each cached file. Downloaded
zip archives are extracted into ``datasets/`` with a guard against path
traversal (zip-slip).
"""

from __future__ import annotations

import hashlib
import json
import time
import warnings
import zipfile
from pathlib import Path
from typing import Iterable, Protocol

from src.datasets import AcquisitionError, FileDescriptor

__all__ = [
    "Cache",
    "extract_archive",
    "ensure_cached",
    "extract_all",
    "acquire",
    "DownloaderLike",
]

_CHUNK = 1 << 16


class DownloaderLike(Protocol):
    """Anything that can fetch a descriptor to a destination path."""

    def fetch(self, descriptor: FileDescriptor, dest: str | Path) -> Path:
        ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Cache:
    """A persistent, content-keyed archive cache with a metadata index."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict[str, dict]:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            warnings.warn(
                f"Ignoring corrupt cache index {self.index_path}: {exc}",
                stacklevel=2,
            )
            return {}

    def path_for(self, descriptor: FileDescriptor) -> Path:
        """Return the stable cache path for ``descriptor``."""
        return self.root / descriptor.dataset_id / descriptor.huc4 / descriptor.filename

    def has(self, descriptor: FileDescriptor) -> bool:
        """Whether a cached file for ``descriptor`` exists and verifies."""
        path = self.path_for(descriptor)
        if not path.exists():
            return False
        if descriptor.expected_sha256:
            return _sha256(path) == descriptor.expected_sha256
        return True

    def record(self, descriptor: FileDescriptor, source_release: str | None = None) -> None:
        """Record metadata for a freshly cached file and persist the index."""
        path = self.path_for(descriptor)
        self._index[descriptor.key] = {
            "url": descriptor.url,
            "size": path.stat().st_size,
            "checksum": _sha256(path),
            "source_release": source_release,
            "downloaded_at": time.time(),
        }
        self.index_path.write_text(json.dumps(self._index, indent=2, sort_keys=True))

    def metadata(self, descriptor: FileDescriptor) -> dict | None:
        """Return recorded metadata for ``descriptor``, if any."""
        return self._index.get(descriptor.key)


def extract_archive(zip_path: str | Path, dest_dir: str | Path) -> list[Path]:
    """Extract a zip archive into ``dest_dir``, guarding against zip-slip.

    Raises:
        AcquisitionError: If the file is not a valid zip or a member would
            escape ``dest_dir``.
    """
    zip_path = Path(zip_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()

    if not zipfile.is_zipfile(zip_path):
        raise AcquisitionError(f"Not a valid zip archive: {zip_path}.")

    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                target = (dest_dir / member).resolve()
                if not str(target).startswith(str(dest_root)):
                    raise AcquisitionError(
                        f"Unsafe path in archive {zip_path.name}: {member!r} "
                        "would escape the target directory."
                    )
            archive.extractall(dest_dir)
            extracted = [dest_dir / name for name in archive.namelist()]
    except zipfile.BadZipFile as exc:
        raise AcquisitionError(f"Corrupt archive {zip_path}: {exc}") from exc
    return extracted


def _noop(_message: str) -> None:
    """Default logger that discards messages."""


def ensure_cached(
    descriptors: Iterable[FileDescriptor],
    cache: Cache,
    downloader: DownloaderLike,
    log=_noop,
) -> None:
    """Download and cache any descriptors not already cached and verified."""
    for descriptor in descriptors:
        if cache.has(descriptor):
            log(f"cached {descriptor.key}")
            continue
        log(f"downloading {descriptor.key}")
        downloader.fetch(descriptor, cache.path_for(descriptor))
        cache.record(descriptor)


def extract_all(
    descriptors: Iterable[FileDescriptor],
    cache: Cache,
    datasets_root: str | Path,
    log=_noop,
) -> list[Path]:
    """Extract each cached archive into ``datasets/``; skip if already present."""
    datasets_root = Path(datasets_root)
    extract_dirs: list[Path] = []
    for descriptor in descriptors:
        target = datasets_root / descriptor.dataset_id / descriptor.huc4
        if target.exists() and any(target.iterdir()):
            log(f"extracted (cached) {descriptor.key}")
        else:
            extract_archive(cache.path_for(descriptor), target)
            log(f"extracted {descriptor.key}")
        extract_dirs.append(target)
    return extract_dirs


def acquire(
    descriptors: Iterable[FileDescriptor],
    cache: Cache,
    downloader: DownloaderLike,
    datasets_root: str | Path,
    log=_noop,
) -> list[Path]:
    """Ensure every descriptor is cached and extracted; return extract dirs.

    For each descriptor: reuse the cached archive if present and verified,
    otherwise download and record it; then extract it into ``datasets/`` unless
    the extraction target already exists.
    """
    descriptors = tuple(descriptors)
    ensure_cached(descriptors, cache, downloader, log)
    return extract_all(descriptors, cache, datasets_root, log)
