"""Tests for resumable download, retry, and verification (Item #2, TG2).

All tests run offline against fake fetchers; none touch the network.
"""

import hashlib

import pytest

from src.datasets import AcquisitionError, FileDescriptor
from src.download import Downloader, FetchResponse


class FakeFetcher:
    """Serves a fixed payload, honoring the Range start offset."""

    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls: list[int] = []

    def open(self, url: str, start_byte: int = 0) -> FetchResponse:
        self.calls.append(start_byte)
        remaining = self.payload[start_byte:]
        return FetchResponse(chunks=[remaining], total_size=len(self.payload))


class FlakyFetcher:
    """Fails a set number of times before serving the payload."""

    def __init__(self, payload: bytes, fail_times: int):
        self.payload = payload
        self.fail_times = fail_times
        self.attempts = 0

    def open(self, url: str, start_byte: int = 0) -> FetchResponse:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise OSError("transient network error")
        return FetchResponse(chunks=[self.payload[start_byte:]])


def _descriptor(sha=None):
    return FileDescriptor("nhdplus_hr", "1709", "f.zip", "http://x/f.zip", sha)


def test_full_download_writes_bytes(tmp_path):
    payload = b"river-data" * 100
    fetcher = FakeFetcher(payload)
    dest = Downloader(fetcher, sleep=lambda _s: None).fetch(
        _descriptor(), tmp_path / "f.zip"
    )
    assert dest.read_bytes() == payload
    assert not (tmp_path / "f.zip.part").exists()  # temp cleaned up


def test_resume_continues_from_partial(tmp_path):
    payload = b"0123456789abcdef"
    part = tmp_path / "f.zip.part"
    part.write_bytes(payload[:6])  # pretend 6 bytes already downloaded
    fetcher = FakeFetcher(payload)
    dest = Downloader(fetcher, sleep=lambda _s: None).fetch(
        _descriptor(), tmp_path / "f.zip"
    )
    assert dest.read_bytes() == payload
    assert fetcher.calls == [6]  # requested from the resume offset


def test_retry_recovers_from_transient_failure(tmp_path):
    payload = b"payload"
    fetcher = FlakyFetcher(payload, fail_times=2)
    dest = Downloader(fetcher, retries=3, sleep=lambda _s: None).fetch(
        _descriptor(), tmp_path / "f.zip"
    )
    assert dest.read_bytes() == payload
    assert fetcher.attempts == 3


def test_fails_after_max_retries(tmp_path):
    fetcher = FlakyFetcher(b"x", fail_times=99)
    with pytest.raises(AcquisitionError, match="after 2 retries"):
        Downloader(fetcher, retries=2, sleep=lambda _s: None).fetch(
            _descriptor(), tmp_path / "f.zip"
        )


def test_checksum_mismatch_is_rejected(tmp_path):
    payload = b"payload"
    wrong_sha = hashlib.sha256(b"different").hexdigest()
    fetcher = FakeFetcher(payload)
    with pytest.raises(AcquisitionError, match="Checksum mismatch"):
        Downloader(fetcher, retries=0, sleep=lambda _s: None).fetch(
            _descriptor(wrong_sha), tmp_path / "f.zip"
        )
    assert not (tmp_path / "f.zip").exists()  # bad file not left behind
    assert not (tmp_path / "f.zip.part").exists()


def test_matching_checksum_passes(tmp_path):
    payload = b"payload"
    good_sha = hashlib.sha256(payload).hexdigest()
    dest = Downloader(FakeFetcher(payload), sleep=lambda _s: None).fetch(
        _descriptor(good_sha), tmp_path / "f.zip"
    )
    assert dest.read_bytes() == payload


# --- UrllibFetcher coverage (lines 62-91) -----------------------------------

class _FakeResponse:
    """Minimal fake for the object returned by urlopen."""

    def __init__(self, data, headers=None):
        self._data = data
        self._pos = 0
        self.headers = headers or {}
        self.closed = False

    def read(self, size=-1):
        if self._pos >= len(self._data):
            return b""
        end = self._pos + size if size > 0 else len(self._data)
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk

    def close(self):
        self.closed = True


def test_urllib_fetcher_basic_open(monkeypatch):
    """UrllibFetcher.open returns a FetchResponse with chunks."""
    from src.download import UrllibFetcher

    payload = b"hello"
    fake_resp = _FakeResponse(payload, {"Content-Length": "5"})
    monkeypatch.setattr("src.download.urlopen", lambda req, timeout=None: fake_resp)

    fetcher = UrllibFetcher(timeout=10, chunk_size=2)
    result = fetcher.open("http://example.com/data.zip")
    assert result.total_size == 5
    data = b"".join(result.chunks)
    assert data == payload
    assert fake_resp.closed


def test_urllib_fetcher_range_header(monkeypatch):
    """UrllibFetcher.open adds Range header when start_byte > 0."""
    from src.download import UrllibFetcher

    captured_request = {}

    def fake_urlopen(req, timeout=None):
        captured_request["headers"] = dict(req.headers)
        return _FakeResponse(b"tail", {"Content-Range": "bytes 5-8/10"})

    monkeypatch.setattr("src.download.urlopen", fake_urlopen)

    fetcher = UrllibFetcher()
    result = fetcher.open("http://example.com/data.zip", start_byte=5)
    assert captured_request["headers"].get("Range") == "bytes=5-"
    assert result.total_size == 10


def test_urllib_fetcher_content_range_unparseable(monkeypatch):
    """Content-Range with '*' total → total_size is None."""
    from src.download import UrllibFetcher

    fake_resp = _FakeResponse(b"x", {"Content-Range": "bytes 0-0/*"})
    monkeypatch.setattr("src.download.urlopen", lambda req, timeout=None: fake_resp)

    result = UrllibFetcher().open("http://example.com/f.zip")
    assert result.total_size is None


def test_urllib_fetcher_content_length_fallback(monkeypatch):
    """No Content-Range → falls back to Content-Length + start_byte."""
    from src.download import UrllibFetcher

    fake_resp = _FakeResponse(b"data", {"Content-Length": "4"})
    monkeypatch.setattr("src.download.urlopen", lambda req, timeout=None: fake_resp)

    result = UrllibFetcher().open("http://example.com/f.zip", start_byte=100)
    assert result.total_size == 104


def test_urllib_fetcher_no_size_headers(monkeypatch):
    """No Content-Range, no Content-Length → total_size is None."""
    from src.download import UrllibFetcher

    fake_resp = _FakeResponse(b"data", {})
    monkeypatch.setattr("src.download.urlopen", lambda req, timeout=None: fake_resp)

    result = UrllibFetcher().open("http://example.com/f.zip")
    assert result.total_size is None
