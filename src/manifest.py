"""Portable cache manifests for offline packaging (roadmap #21).

The download stage caches large hydrography archives (on a NAS in real runs) and
records provenance in the :class:`~src.cache.Cache` JSON index. This module turns
that cache state into a *portable, deterministic* manifest so a cache can be
audited, moved between machines, verified for integrity, and reconciled against
another cache — all offline.

Design:

- **Deterministic**: entries are sorted by key and serialized with stable JSON;
  wall-clock timestamps are excluded, so identical cache state yields byte-
  identical manifest output.
- **Portable**: each entry stores a path *relative to the cache root*, so the
  manifest stays valid after the cache directory is copied elsewhere.
- **Offline**: imports only stdlib + ``src.datasets`` / ``src.config`` /
  ``src.cache`` — no numpy / geopandas / GDAL — so it runs in the offline suite.

Not wired into ``PIPELINE_STAGES``; it is an acquisition-domain packaging utility
(``ManifestError`` subclasses ``AcquisitionError``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.cache import Cache
from src.config import Settings
from src.datasets import AcquisitionError, FileDescriptor, resolve_required_files

__all__ = [
    "MANIFEST_VERSION",
    "ManifestError",
    "ManifestEntry",
    "CacheManifest",
    "ManifestVerification",
    "ManifestDiff",
    "build_manifest",
    "manifest_for_settings",
    "manifest_to_dict",
    "manifest_from_dict",
    "write_manifest",
    "read_manifest",
    "verify_manifest",
    "diff_manifests",
    "format_verification",
    "format_diff",
]

MANIFEST_VERSION = "1"

_CHUNK = 1 << 16
_ENTRY_FIELDS = (
    "key",
    "dataset_id",
    "huc4",
    "filename",
    "url",
    "checksum",
    "size",
    "relative_path",
    "source_release",
)


class ManifestError(AcquisitionError):
    """Raised for malformed manifest data or strict build misses.

    The message is intended to be shown directly to the user.
    """


@dataclass(frozen=True)
class ManifestEntry:
    """One cached archive, described portably.

    Attributes:
        key: Stable ``<dataset_id>/<huc4>/<filename>`` key (``FileDescriptor.key``).
        dataset_id: Owning dataset id.
        huc4: HUC unit code at the dataset's granularity.
        filename: Archive basename.
        url: Fully resolved download URL.
        checksum: SHA-256 hex of the cached file (from the cache index).
        size: File size in bytes (from the cache index).
        relative_path: POSIX path under the cache root (portable).
        source_release: Optional source release tag, if recorded.
    """

    key: str
    dataset_id: str
    huc4: str
    filename: str
    url: str
    checksum: str
    size: int
    relative_path: str
    source_release: str | None = None


@dataclass(frozen=True)
class CacheManifest:
    """A deterministic, portable manifest of cached archives (sorted by key)."""

    entries: tuple[ManifestEntry, ...]
    version: str = MANIFEST_VERSION


@dataclass(frozen=True)
class ManifestVerification:
    """Result of checking a cache directory against a manifest."""

    ok: tuple[str, ...]
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        """Whether every manifest entry is present and intact."""
        return not self.missing and not self.mismatched


@dataclass(frozen=True)
class ManifestDiff:
    """Key-wise difference between two manifests (old -> new)."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def is_synced(self) -> bool:
        """Whether new matches old (nothing added, removed, or changed)."""
        return not self.added and not self.removed and not self.changed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    cache: Cache,
    descriptors: Iterable[FileDescriptor],
    *,
    strict: bool = False,
) -> CacheManifest:
    """Build a manifest from a cache's recorded metadata for ``descriptors``.

    Descriptors with no recorded metadata are skipped, unless ``strict`` is set,
    in which case a :class:`ManifestError` is raised. Entries are sorted by key.
    """
    entries: list[ManifestEntry] = []
    for descriptor in descriptors:
        meta = cache.metadata(descriptor)
        if meta is None:
            if strict:
                raise ManifestError(
                    f"No cached metadata for {descriptor.key!r}; "
                    "cannot build a strict manifest."
                )
            continue
        relative = cache.path_for(descriptor).relative_to(cache.root).as_posix()
        entries.append(
            ManifestEntry(
                key=descriptor.key,
                dataset_id=descriptor.dataset_id,
                huc4=descriptor.huc4,
                filename=descriptor.filename,
                url=meta["url"],
                checksum=meta["checksum"],
                size=meta["size"],
                relative_path=relative,
                source_release=meta.get("source_release"),
            )
        )
    return CacheManifest(entries=tuple(sorted(entries, key=lambda e: e.key)))


def manifest_for_settings(
    cache: Cache,
    settings: Settings,
    *,
    strict: bool = False,
) -> CacheManifest:
    """Build a manifest for the files ``settings`` resolves to.

    The region -> manifest bridge: multi-state coverage (e.g. Oregon + Washington)
    round-trips through a single manifest.
    """
    return build_manifest(cache, resolve_required_files(settings), strict=strict)


def manifest_to_dict(manifest: CacheManifest) -> dict:
    """Serialize a manifest to a JSON-ready dict (entries in key order)."""
    return {
        "version": manifest.version,
        "entries": [
            {
                "key": e.key,
                "dataset_id": e.dataset_id,
                "huc4": e.huc4,
                "filename": e.filename,
                "url": e.url,
                "checksum": e.checksum,
                "size": e.size,
                "relative_path": e.relative_path,
                "source_release": e.source_release,
            }
            for e in manifest.entries
        ],
    }


def manifest_from_dict(data: dict) -> CacheManifest:
    """Reconstruct a manifest from a dict, validating structure at the boundary.

    Raises:
        ManifestError: If ``entries`` is not a list or an entry is missing a
            required field.
    """
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise ManifestError("Manifest 'entries' must be a list.")
    entries: list[ManifestEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ManifestError("Each manifest entry must be an object.")
        missing = [f for f in _ENTRY_FIELDS if f != "source_release" and f not in raw]
        if missing:
            raise ManifestError(
                f"Manifest entry missing required field(s): {', '.join(missing)}."
            )
        entries.append(
            ManifestEntry(
                key=raw["key"],
                dataset_id=raw["dataset_id"],
                huc4=raw["huc4"],
                filename=raw["filename"],
                url=raw["url"],
                checksum=raw["checksum"],
                size=raw["size"],
                relative_path=raw["relative_path"],
                source_release=raw.get("source_release"),
            )
        )
    version = data.get("version", MANIFEST_VERSION)
    return CacheManifest(
        entries=tuple(sorted(entries, key=lambda e: e.key)),
        version=version,
    )


def write_manifest(manifest: CacheManifest, path: str | Path) -> None:
    """Write a manifest as deterministic JSON (stable bytes for equal state)."""
    text = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
    Path(path).write_text(text)


def read_manifest(path: str | Path) -> CacheManifest:
    """Read a manifest written by :func:`write_manifest`.

    Raises:
        ManifestError: If the file is not valid JSON or is structurally invalid.
    """
    try:
        data = json.loads(Path(path).read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ManifestError(f"Cannot read manifest {path}: {exc}") from exc
    return manifest_from_dict(data)


def verify_manifest(
    manifest: CacheManifest,
    cache_root: str | Path,
) -> ManifestVerification:
    """Verify a cache directory against a manifest (never mutates the cache).

    Each entry's file is resolved at ``cache_root / relative_path``: absent files
    are ``missing``; present files whose recomputed SHA-256 or size differs are
    ``mismatched``; the rest are ``ok``.
    """
    root = Path(cache_root)
    ok: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    for e in manifest.entries:
        path = root / e.relative_path
        if not path.exists():
            missing.append(e.key)
        elif _sha256(path) != e.checksum or path.stat().st_size != e.size:
            mismatched.append(e.key)
        else:
            ok.append(e.key)
    return ManifestVerification(tuple(ok), tuple(missing), tuple(mismatched))


def diff_manifests(old: CacheManifest, new: CacheManifest) -> ManifestDiff:
    """Compare two manifests key-wise (from ``old`` to ``new``).

    ``changed`` = a key present in both with a different checksum; the remaining
    shared keys are ``unchanged``.
    """
    old_by_key = {e.key: e for e in old.entries}
    new_by_key = {e.key: e for e in new.entries}
    added = sorted(new_by_key.keys() - old_by_key.keys())
    removed = sorted(old_by_key.keys() - new_by_key.keys())
    changed: list[str] = []
    unchanged: list[str] = []
    for key in sorted(old_by_key.keys() & new_by_key.keys()):
        if old_by_key[key].checksum != new_by_key[key].checksum:
            changed.append(key)
        else:
            unchanged.append(key)
    return ManifestDiff(tuple(added), tuple(removed), tuple(changed), tuple(unchanged))


def _format_key_group(label: str, keys: tuple[str, ...]) -> list[str]:
    lines = [f"  {label} ({len(keys)}):"]
    lines.extend(f"    - {key}" for key in keys)
    return lines


def format_verification(verification: ManifestVerification) -> str:
    """Render a :class:`ManifestVerification` as a human-readable summary.

    The first line states COMPLETE/INCOMPLETE and the ``ok``/total count; any
    ``missing`` or ``mismatched`` keys are then listed under their own heading.
    """
    total = len(verification.ok) + len(verification.missing) + len(verification.mismatched)
    status = "COMPLETE" if verification.is_complete else "INCOMPLETE"
    lines = [f"Manifest verification: {status} ({len(verification.ok)}/{total} ok)"]
    if verification.missing:
        lines.extend(_format_key_group("missing", verification.missing))
    if verification.mismatched:
        lines.extend(_format_key_group("mismatched", verification.mismatched))
    return "\n".join(lines)


def format_diff(diff: ManifestDiff) -> str:
    """Render a :class:`ManifestDiff` as a human-readable summary.

    A synced diff collapses to one line; otherwise each non-empty
    added/removed/changed group is listed, followed by the unchanged count.
    """
    if diff.is_synced:
        return f"Manifests in sync ({len(diff.unchanged)} unchanged)."
    lines = ["Manifest diff:"]
    for label, keys in (
        ("added", diff.added),
        ("removed", diff.removed),
        ("changed", diff.changed),
    ):
        if keys:
            lines.extend(_format_key_group(label, keys))
    lines.append(f"  unchanged: {len(diff.unchanged)}")
    return "\n".join(lines)
