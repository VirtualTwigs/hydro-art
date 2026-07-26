"""Tests for the build.py entry point and pipeline skeleton (Task Group 3)."""

import io
import zipfile
from pathlib import Path

from rich.console import Console

from build import main
from src.pipeline import PIPELINE_STAGES, Pipeline


class FakeZipDownloader:
    """Offline downloader that writes a small valid zip to the destination."""

    def fetch(self, descriptor, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{descriptor.huc4}.gdb", b"data")
        dest.write_bytes(buf.getvalue())
        return dest


class NullLayerLoader:
    """Offline loader that yields no layers (fake extracts aren't real GDBs)."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        return []


def _offline_pipeline(tmp_path):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        downloader=FakeZipDownloader(),
        loader=NullLayerLoader(),
    )


def test_main_with_defaults_exits_zero(tmp_path):
    # Nonexistent config -> defaults; fake downloader keeps it offline.
    code = main(
        ["--config", str(tmp_path / "none.yaml")],
        pipeline=_offline_pipeline(tmp_path),
    )
    assert code == 0


def test_main_with_invalid_region_exits_nonzero(tmp_path):
    assert main(["--config", str(tmp_path / "none.yaml"), "--region", "Idaho"]) == 1


def test_pipeline_stage_order_matches_prd_section_8():
    assert Pipeline().stage_names == tuple(s.name for s in PIPELINE_STAGES)
    assert Pipeline().stage_names[0] == "download"
    assert Pipeline().stage_names[-1] == "export"
