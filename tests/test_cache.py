"""Tests for cache, metadata index, and extraction (Item #2, TG3)."""

import io
import zipfile
from pathlib import Path

import pytest

from src.cache import Cache, acquire, ensure_cached, extract_archive
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


# --- Skip download when the dataset is already extracted (offline reuse) ------


def _extracted(datasets_root, desc):
    """Create a non-empty extracted dataset dir for ``desc``."""
    target = Path(datasets_root) / desc.dataset_id / desc.huc4
    target.mkdir(parents=True)
    (target / "layer.gdb").write_text("x")
    return target


def test_ensure_cached_skips_download_when_already_extracted(tmp_path):
    # The extracted GDB is on disk but NO archive is cached: we must not fetch,
    # since extract_all would reuse the existing directory anyway.
    cache = Cache(tmp_path / "cache")
    downloader = SpyDownloader()
    desc = _descriptor()
    datasets = tmp_path / "datasets"
    _extracted(datasets, desc)

    ensure_cached([desc], cache, downloader, datasets_root=datasets)

    assert downloader.calls == 0
    assert cache.metadata(desc) is None  # nothing recorded either


def test_ensure_cached_downloads_when_not_extracted(tmp_path):
    cache = Cache(tmp_path / "cache")
    downloader = SpyDownloader()
    desc = _descriptor()

    ensure_cached([desc], cache, downloader, datasets_root=tmp_path / "datasets")

    assert downloader.calls == 1


def test_ensure_cached_ignores_empty_extract_dir(tmp_path):
    # An existing but EMPTY dataset dir must not count as extracted.
    cache = Cache(tmp_path / "cache")
    downloader = SpyDownloader()
    desc = _descriptor()
    datasets = tmp_path / "datasets"
    (Path(datasets) / desc.dataset_id / desc.huc4).mkdir(parents=True)

    ensure_cached([desc], cache, downloader, datasets_root=datasets)

    assert downloader.calls == 1


def test_ensure_cached_without_datasets_root_downloads_uncached(tmp_path):
    # Back-compat: no datasets_root → old behavior (download when zip uncached).
    cache = Cache(tmp_path / "cache")
    downloader = SpyDownloader()
    desc = _descriptor()

    ensure_cached([desc], cache, downloader)

    assert downloader.calls == 1
