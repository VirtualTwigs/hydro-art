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
