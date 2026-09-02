"""Multi-format export of the finished SVG (PRD sections 22-23).

SVG is the one required format and is written with pure stdlib — no external
tool. The optional formats (PDF/PNG/TIFF/EPS) are produced by converting the
SVG through an external CLI, which depends on the host having a rasterizer
installed. To keep the pipeline pure and its tests fully offline, export sits
behind the :class:`Exporter` protocol (the dependency-injection seam mirroring
``Downloader``/``SvgOptimizer``): production injects :class:`FileExporter`
(a thin subprocess wrapper), while tests inject a fake. The real exporter
**degrades gracefully** — if the converter is missing or fails it warns and
skips that format, so a build never crashes and always produces the SVG.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = ["Exporter", "FileExporter", "RASTER_FORMATS", "write_verified"]

#: Formats rendered as pixels (sized by ``png_size``); the rest are vector.
RASTER_FORMATS: frozenset[str] = frozenset({"png", "tiff"})

#: I/O chunk size for large-file writes and read-back verification.
_CHUNK = 8 << 20  # 8 MiB


def _verify(path: Path, data: bytes) -> bool:
    """Return ``True`` iff ``path`` on disk is byte-for-byte equal to ``data``.

    Re-reads the file (a fresh handle, so it is not served from the write-side
    page cache) and streams a comparison, catching both truncation and the
    zero-page *holes* that large writes to some network filesystems (SMB/NAS)
    silently produce.
    """
    try:
        if path.stat().st_size != len(data):
            return False
        with open(path, "rb") as f:
            pos = 0
            while pos < len(data):
                chunk = f.read(_CHUNK)
                if not chunk:
                    return False
                if chunk != data[pos : pos + len(chunk)]:
                    return False
                pos += len(chunk)
        return True
    except OSError:
        return False


def write_verified(dest: Path, data: bytes, *, retries: int = 3) -> None:
    """Write ``data`` to ``dest`` intact, verifying the on-disk result.

    A single large write to a network filesystem (e.g. an SMB-mounted NAS) can
    *silently* leave zero-page holes — the write returns success but ~pages of
    the file are zeros — corrupting the artifact. Because the failure is silent,
    the only reliable guarantee is to read the bytes back and compare. This helper
    writes to a sibling temp file in chunks (``flush`` + ``fsync``), byte-verifies
    the re-read, retries on mismatch, then atomically replaces ``dest``. On small
    local writes this is effectively free; on a large NAS write it costs a
    read-back but guarantees a faithful file.

    Raises:
        OSError: If the file cannot be written intact after ``retries`` attempts
            (e.g. a filesystem that persistently corrupts large writes).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    detail = "unknown error"
    for attempt in range(1, retries + 1):
        fd, tmp_name = tempfile.mkstemp(
            dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp"
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as f:
                for i in range(0, len(data), _CHUNK):
                    f.write(data[i : i + _CHUNK])
                f.flush()
                os.fsync(f.fileno())
            if _verify(tmp, data):
                os.replace(tmp, dest)
                return
            detail = f"on-disk content did not match source (attempt {attempt})"
        finally:
            if tmp.exists():
                tmp.unlink()
    raise OSError(
        f"Failed to write {dest} intact after {retries} attempts ({detail}). "
        "The destination filesystem may be silently corrupting large writes "
        "(e.g. an SMB/NAS mount); write to a local --output-dir instead."
    )


@runtime_checkable
class Exporter(Protocol):
    """Writes an SVG document to ``dest`` in ``fmt``; returns the path or None."""

    def export(
        self, svg: str, dest: Path, fmt: str, *, png_size: int
    ) -> Path | None: ...


class FileExporter:
    """Write SVG natively and convert other formats via the ``rsvg-convert`` CLI.

    ``svg`` is written directly (no tool needed). Any other format shells out to
    ``rsvg-convert -f <fmt> -o <dest>`` (reading the SVG on stdin), passing
    ``--width <png_size>`` for raster formats. If the executable is missing or
    exits non-zero, the format is skipped (with a warning) and ``None`` is
    returned rather than raising, so export still produces the SVG on hosts
    without a converter installed.
    """

    def __init__(self, command: str = "rsvg-convert") -> None:
        self._command = command

    def export(
        self, svg: str, dest: Path, fmt: str, *, png_size: int
    ) -> Path | None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "svg":
            write_verified(dest, svg.encode("utf-8"))
            return dest

        args = [self._command, "-f", fmt, "-o", str(dest)]
        if fmt in RASTER_FORMATS:
            args += ["--width", str(png_size)]
        args.append("-")  # read the SVG from stdin
        try:
            subprocess.run(
                args, input=svg.encode("utf-8"), capture_output=True, check=True
            )
        except FileNotFoundError:
            warnings.warn(
                f"'{self._command}' not found; skipping {fmt} export.",
                stacklevel=2,
            )
            return None
        except subprocess.CalledProcessError as exc:
            warnings.warn(
                f"{fmt} export failed ({self._command} exit {exc.returncode}); "
                f"skipping {fmt}.",
                stacklevel=2,
            )
            return None
        return dest
