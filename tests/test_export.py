"""Unit tests for the export seam (Item #10, TG2)."""

import pytest

from src.export import Exporter, FileExporter


def test_svg_is_written_natively_without_a_tool(tmp_path):
    exporter = FileExporter(command="hydro-no-such-converter")
    dest = tmp_path / "art.svg"
    svg = "<svg><g/></svg>"
    result = exporter.export(svg, dest, "svg", png_size=4096)
    assert result == dest
    assert dest.read_text(encoding="utf-8") == svg


def test_missing_converter_skips_nonsvg_with_warning(tmp_path):
    exporter = FileExporter(command="hydro-no-such-converter")
    dest = tmp_path / "art.pdf"
    with pytest.warns(UserWarning, match="not found"):
        result = exporter.export("<svg/>", dest, "pdf", png_size=4096)
    assert result is None
    assert not dest.exists()


def test_file_exporter_satisfies_protocol():
    assert isinstance(FileExporter(), Exporter)
