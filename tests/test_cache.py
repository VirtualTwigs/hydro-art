"""Tests for cache, metadata index, and extraction (Item #2, TG3)."""

import io
import zipfile

import pytest

from src.cache import Cache, acquire, extract_archive
from src.datasets import AcquisitionError, FileDescriptor


def _descriptor(name="f.zip"):
    return FileDescriptor("wbd", "1709", name, f"http://x/{name}")


def _make_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


class SpyDownloader:
    """Records fetch calls and writes a valid zip to the destination."""

    def __init__(self):
        self.calls = 0

    def fetch(self, descriptor, dest):
        self.calls += 1
        from pathlib import Path

        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("layer.gdb", b"data")
        dest.write_bytes(buf.getvalue())
        return dest


def test_metadata_index_round_trips(tmp_path):
    cache = Cache(tmp_path / "cache")
    desc = _descriptor()
    cache.path_for(desc).parent.mkdir(parents=True, exist_ok=True)
    cache.path_for(desc).write_bytes(b"hello")
    cache.record(desc, source_release="2024-01")

    reopened = Cache(tmp_path / "cache")  # persists between runs
    meta = reopened.metadata(desc)
    assert meta is not None
    assert meta["url"] == desc.url
    assert meta["size"] == 5
    assert meta["source_release"] == "2024-01"
    assert "checksum" in meta


def test_extract_produces_files(tmp_path):
    zip_path = tmp_path / "a.zip"
    _make_zip(zip_path, {"rivers.gdb": b"x", "meta.txt": b"y"})
    extracted = extract_archive(zip_path, tmp_path / "out")
    assert (tmp_path / "out" / "rivers.gdb").exists()
    assert len(extracted) == 2


def test_extract_rejects_zip_slip(tmp_path):
    zip_path = tmp_path / "evil.zip"
    _make_zip(zip_path, {"../escape.txt": b"pwned"})
    with pytest.raises(AcquisitionError, match="escape the target"):
        extract_archive(zip_path, tmp_path / "out")


def test_acquire_reuses_cache_on_second_run(tmp_path):
    cache = Cache(tmp_path / "cache")
    downloader = SpyDownloader()
    desc = _descriptor()

    acquire([desc], cache, downloader, tmp_path / "datasets")
    assert downloader.calls == 1

    # Second run: cached archive + extracted output already present.
    acquire([desc], cache, downloader, tmp_path / "datasets")
    assert downloader.calls == 1  # NOT called again
