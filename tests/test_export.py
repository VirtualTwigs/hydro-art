"""Unit tests for the export seam (Item #10, TG2)."""

import subprocess

import pytest

from src import export as export_mod
from src.export import Exporter, FileExporter, write_verified


def test_svg_is_written_natively_without_a_tool(tmp_path):
    exporter = FileExporter(command="hydro-no-such-converter")
    dest = tmp_path / "art.svg"
    svg = "<svg><g/></svg>"
    result = exporter.export(svg, dest, "svg", png_size=4096)
    assert result == dest
    assert dest.read_text(encoding="utf-8") == svg


def test_svg_write_roundtrips_across_multiple_chunks(tmp_path):
    # Content larger than the 8 MiB I/O chunk exercises the chunked write path.
    svg = "<svg>" + "a" * (20 << 20) + "</svg>"
    dest = tmp_path / "big.svg"
    FileExporter(command="hydro-no-such-converter").export(
        svg, dest, "svg", png_size=4096
    )
    assert dest.read_text(encoding="utf-8") == svg


def test_write_verified_leaves_no_temp_files(tmp_path):
    dest = tmp_path / "art.svg"
    write_verified(dest, b"<svg/>")
    assert dest.read_bytes() == b"<svg/>"
    # The sibling temp file must be cleaned up on success.
    assert [p.name for p in tmp_path.iterdir()] == ["art.svg"]


def test_write_verified_raises_and_cleans_up_on_persistent_corruption(
    tmp_path, monkeypatch
):
    # Simulate a filesystem that silently corrupts every write.
    monkeypatch.setattr(export_mod, "_verify", lambda path, data: False)
    dest = tmp_path / "art.svg"
    with pytest.raises(OSError, match="intact after 3 attempts"):
        write_verified(dest, b"<svg/>", retries=3)
    assert not dest.exists()
    # No leftover temp files from the failed attempts.
    assert list(tmp_path.iterdir()) == []


def test_verify_detects_truncation_and_holes(tmp_path):
    data = b"<svg>" + b"x" * 1000 + b"</svg>"
    good = tmp_path / "good.bin"
    good.write_bytes(data)
    assert export_mod._verify(good, data) is True

    holed = tmp_path / "holed.bin"
    holed.write_bytes(data[:500] + b"\x00" * 500 + data[1000:])
    assert export_mod._verify(holed, data) is False

    short = tmp_path / "short.bin"
    short.write_bytes(data[:-3])
    assert export_mod._verify(short, data) is False


def test_missing_converter_skips_nonsvg_with_warning(tmp_path):
    exporter = FileExporter(command="hydro-no-such-converter")
    dest = tmp_path / "art.pdf"
    with pytest.warns(UserWarning, match="not found"):
        result = exporter.export("<svg/>", dest, "pdf", png_size=4096)
    assert result is None
    assert not dest.exists()


def test_file_exporter_satisfies_protocol():
    assert isinstance(FileExporter(), Exporter)


def test_verify_nonexistent_file_returns_false(tmp_path):
    assert export_mod._verify(tmp_path / "missing.bin", b"data") is False


def test_verify_early_eof_returns_false(tmp_path):
    """File on disk is shorter than expected (read returns empty mid-stream)."""
    path = tmp_path / "short.bin"
    path.write_bytes(b"ab")
    assert export_mod._verify(path, b"abcd") is False


def test_converter_failure_skips_format_with_warning(tmp_path, monkeypatch):
    """CalledProcessError from rsvg-convert → skips with warning, returns None."""
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "rsvg-convert")

    monkeypatch.setattr(subprocess, "run", fake_run)
    exporter = FileExporter(command="rsvg-convert")
    dest = tmp_path / "art.pdf"
    with pytest.warns(UserWarning, match="export failed"):
        result = exporter.export("<svg/>", dest, "pdf", png_size=4096)
    assert result is None


def test_raster_format_passes_width_flag(tmp_path, monkeypatch):
    """PNG format includes --width flag with png_size."""
    captured_args = {}

    def fake_run(args, **kwargs):
        captured_args["args"] = args

    monkeypatch.setattr(subprocess, "run", fake_run)
    exporter = FileExporter(command="rsvg-convert")
    exporter.export("<svg/>", tmp_path / "art.png", "png", png_size=2048)
    assert "--width" in captured_args["args"]
    assert "2048" in captured_args["args"]
