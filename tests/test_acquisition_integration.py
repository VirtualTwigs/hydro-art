"""End-to-end acquisition integration tests (Item #2, Task Group 4).

Exercises resolve -> download -> verify -> cache -> extract through the real
pipeline stages, offline via a fake downloader.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console

from src.config import build_settings
from src.datasets import resolve_required_files
from src.pipeline import Pipeline


class CountingZipDownloader:
    """Writes a valid zip to the destination and counts fetches."""

    def __init__(self):
        self.calls = 0

    def fetch(self, descriptor, dest):
        self.calls += 1
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{descriptor.dataset_id}_{descriptor.huc4}.gdb", b"geo")
        dest.write_bytes(buf.getvalue())
        return dest


class NullLayerLoader:
    """Offline loader that yields no layers (fake extracts aren't real GDBs)."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        return []


def _pipeline(tmp_path, downloader):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=downloader,
        loader=NullLayerLoader(),
    )


def test_pipeline_downloads_and_extracts_all_required_files(tmp_path):
    settings = build_settings({"region": ["Washington"]})
    downloader = CountingZipDownloader()
    context = _pipeline(tmp_path, downloader).run(settings)

    expected = resolve_required_files(settings)
    assert downloader.calls == len(expected)
    # Every required file was cached and extracted.
    for descriptor in expected:
        assert (tmp_path / "cache" / descriptor.dataset_id / descriptor.huc4
                / descriptor.filename).exists()
        assert (tmp_path / "datasets" / descriptor.dataset_id
                / descriptor.huc4).exists()
    assert len(context.artifacts["dataset_dirs"]) == len(expected)


def test_second_run_reuses_cache_no_redownload(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    downloader = CountingZipDownloader()

    _pipeline(tmp_path, downloader).run(settings)
    first = downloader.calls
    assert first > 0

    _pipeline(tmp_path, downloader).run(settings)
    assert downloader.calls == first  # nothing re-downloaded on the second run


def test_metadata_index_persisted_after_run(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    _pipeline(tmp_path, CountingZipDownloader()).run(settings)
    index = tmp_path / "cache" / "index.json"
    assert index.exists()
    assert index.read_text().strip().startswith("{")
