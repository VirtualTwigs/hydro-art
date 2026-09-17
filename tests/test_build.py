"""Tests for the build.py entry point and pipeline skeleton (Task Group 3)."""

import io
import zipfile
from pathlib import Path

from rich.console import Console

from build import NAS_CACHE_DIR, _storage_roots, main
from src.cli import build_parser, cli_overrides
from src.pipeline import PIPELINE_STAGES, Pipeline
from src.storage import EXTERNAL_ROOT_ENV

_ALWAYS = lambda _p: True
_NEVER = lambda _p: False


def _args(argv):
    return build_parser().parse_args(argv)


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
        output_dir=tmp_path / "output",
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
    assert main(["--config", str(tmp_path / "none.yaml"), "--region", "Atlantis"]) == 1


def test_pipeline_stage_order_matches_prd_section_8():
    assert Pipeline().stage_names == tuple(s.name for s in PIPELINE_STAGES)
    assert Pipeline().stage_names[0] == "download"
    assert Pipeline().stage_names[-1] == "export"


# --- storage wiring (roadmap #29) -------------------------------------------


def test_storage_defaults_local_when_nas_unmounted(monkeypatch):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    roots = _storage_roots(_args([]), available=_NEVER)
    assert roots.cache == Path("cache")
    assert roots.datasets == Path("datasets")
    assert roots.output == Path("output")
    assert roots.using_external is False


def test_storage_cache_defaults_to_nas_when_mounted(monkeypatch):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    roots = _storage_roots(_args([]), available=_ALWAYS)
    # No external root: cache keeps today's NAS default, datasets/output local.
    assert roots.cache == Path(NAS_CACHE_DIR)
    assert roots.datasets == Path("datasets")
    assert roots.output == Path("output")


def test_storage_external_root_expands_all_kinds(monkeypatch):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    roots = _storage_roots(
        _args(["--external-root", "/Volumes/Pro/hydro"]), available=_ALWAYS
    )
    assert roots.cache == Path("/Volumes/Pro/hydro/cache")
    assert roots.datasets == Path("/Volumes/Pro/hydro/datasets")
    assert roots.output == Path("/Volumes/Pro/hydro/output")
    assert roots.using_external is True


def test_storage_explicit_dir_overrides_external(monkeypatch):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    roots = _storage_roots(
        _args(["--external-root", "/Volumes/Pro", "--output-dir", "/tmp/o"]),
        available=_ALWAYS,
    )
    assert roots.output == Path("/tmp/o")
    assert roots.datasets == Path("/Volumes/Pro/datasets")


# --- Flowline channel CLI flags (Item #66) ----------------------------------


def test_flowline_channels_cli_flag():
    """--flowline-channels sets enabled=True in overrides."""
    args = _args(["--flowline-channels"])
    ov = cli_overrides(args)
    assert ov["flowline_channels"]["enabled"] is True


def test_flowline_channels_cli_preset():
    """--flowline-channel-preset screen applies the preset."""
    args = _args(["--flowline-channel-preset", "screen"])
    ov = cli_overrides(args)
    assert ov["flowline_channels"]["preset"] == "screen"


def test_flowline_channels_cli_no_flag_no_override():
    """Without --flowline-channels, no flowline_channels key in overrides."""
    args = _args([])
    ov = cli_overrides(args)
    assert "flowline_channels" not in ov
