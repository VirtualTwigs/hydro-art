"""Resumable, verified downloading behind an injectable fetcher.

All network I/O is funneled through the :class:`Fetcher` protocol so the
download logic can be exercised offline with a fake. :class:`UrllibFetcher`
is the standard-library implementation used in production.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.datasets import AcquisitionError, FileDescriptor

__all__ = [
    "ChecksumError",
    "Downloader",
    "FetchResponse",
    "Fetcher",
    "UrllibFetcher",
]

_CHUNK = 1 << 16  # 64 KiB


class ChecksumError(AcquisitionError):
    """Raised when a downloaded file fails checksum verification."""


@dataclass
class FetchResponse:
    """A streamed response.

    Attributes:
        chunks: Iterable of byte chunks for the requested byte range.
        total_size: Full size of the resource in bytes, if known.
    """

    chunks: Iterable[bytes]
    total_size: int | None = None


@runtime_checkable
class Fetcher(Protocol):
    """Abstraction over range-aware HTTP streaming."""

    def open(self, url: str, start_byte: int = 0) -> FetchResponse:
        """Open ``url`` for streaming, starting at ``start_byte`` (Range)."""
        ...


class UrllibFetcher:
    """Standard-library :class:`Fetcher` backed by ``urllib``."""

    def __init__(self, timeout: float = 60.0, chunk_size: int = _CHUNK) -> None:
        self._timeout = timeout
        self._chunk_size = chunk_size

    def open(self, url: str, start_byte: int = 0) -> FetchResponse:
        request = Request(url)
        if start_byte:
            request.add_header("Range", f"bytes={start_byte}-")
        response = urlopen(request, timeout=self._timeout)

        total: int | None = None
        content_range = response.headers.get("Content-Range")
        if content_range and "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[-1])
            except ValueError:
                total = None
        elif response.headers.get("Content-Length"):
            total = int(response.headers["Content-Length"]) + start_byte

        def _iter() -> Iterable[bytes]:
            try:
                while True:
                    chunk = response.read(self._chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()

        return FetchResponse(chunks=_iter(), total_size=total)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Downloader:
    """Downloads files with resume, retry/backoff, and verification."""

    def __init__(
        self,
        fetcher: Fetcher,
        retries: int = 3,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._fetcher = fetcher
        self._retries = retries
        self._backoff = backoff
        self._sleep = sleep

    def fetch(self, descriptor: FileDescriptor, dest: str | Path) -> Path:
        """Download ``descriptor`` to ``dest``, returning the final path.

        Streams to a ``.part`` temp file, resuming from any existing partial
        via an HTTP Range request, then atomically moves it into place once the
        download verifies.

        Raises:
            AcquisitionError: If the download fails after all retries or a
                checksum cannot be satisfied.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")

        attempt = 0
        while True:
            try:
                offset = part.stat().st_size if part.exists() else 0
                response = self._fetcher.open(descriptor.url, start_byte=offset)
                mode = "ab" if offset else "wb"
                with open(part, mode) as fh:
                    fh.writelines(response.chunks)

                if descriptor.expected_sha256:
                    actual = _sha256(part)
                    if actual != descriptor.expected_sha256:
                        part.unlink(missing_ok=True)  # discard; re-download fresh
                        raise ChecksumError(
                            f"Checksum mismatch for {descriptor.filename}: "
                            f"expected {descriptor.expected_sha256}, got {actual}."
                        )

                part.replace(dest)  # atomic move on success
                return dest
            except (OSError, URLError, ChecksumError) as exc:
                attempt += 1
                if attempt > self._retries:
                    raise AcquisitionError(
                        f"Failed to download {descriptor.url} after "
                        f"{self._retries} retries: {exc}"
                    ) from exc
                self._sleep(self._backoff * (2 ** (attempt - 1)))
