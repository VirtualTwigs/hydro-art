"""Tests for src/notebook_report — notebook assembly + PDF converter seam."""

from __future__ import annotations

import base64
from pathlib import Path

import nbformat
import pytest

from src.notebook_report import (
    CANONICAL_SECTIONS,
    build_notebook,
    notebook_to_pdf,
    save_notebook,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_metrics() -> dict:
    """Minimal metrics dict matching the keys build_notebook expects."""
    return {
        "peak_month": "June",
        "peak_flow_cfs": 12500.0,
        "low_flow_month": "September",
        "low_flow_cfs": 42.3,
        "center_of_timing_doy": 152,
        "flashiness_index": 0.31,
    }


def _write_fake_png(directory: Path, name: str) -> Path:
    """Write a tiny fake PNG (valid 8-byte header) and return the path."""
    # Minimal PNG signature so we can recognize it round-trips.
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    p = directory / name
    p.write_bytes(data)
    return p


# ---------------------------------------------------------------------------
# 1. Valid notebook structure
# ---------------------------------------------------------------------------

def test_build_notebook_structure(tmp_path):
    """build_notebook produces correct cell count and cell types:
    title markdown + metrics markdown + N section cells + attribution markdown.
    """
    nb = build_notebook(
        ws_name="Clark Fork",
        years=(1990, 2020),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
    )
    assert nb.nbformat == 4
    cells = nb.cells

    # title + metrics + len(CANONICAL_SECTIONS) section cells + attribution
    expected_count = 2 + len(CANONICAL_SECTIONS) + 1
    assert len(cells) == expected_count

    # First two and last are markdown.
    assert cells[0].cell_type == "markdown"  # title
    assert cells[1].cell_type == "markdown"  # metrics
    assert cells[-1].cell_type == "markdown"  # attribution

    # All section cells exist (markdown notes since no PNGs).
    for cell in cells[2:-1]:
        assert cell.cell_type in ("markdown", "code")


# ---------------------------------------------------------------------------
# 2. Section filtering
# ---------------------------------------------------------------------------

def test_section_filtering(tmp_path):
    """sections={'map', 'long_record'} yields only title + those two + attribution,
    in canonical order."""
    nb = build_notebook(
        ws_name="Willamette",
        years=(2000, 2022),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
        sections={"map", "long_record"},
    )
    cells = nb.cells
    # title + metrics + 2 section cells + attribution
    assert len(cells) == 2 + 2 + 1

    # The two section cells should be in canonical order (map before long_record).
    section_cells = cells[2:-1]
    assert "map" in section_cells[0].source.lower()
    assert "long_record" in section_cells[1].source.lower() or \
           "long record" in section_cells[1].source.lower()


# ---------------------------------------------------------------------------
# 3. Unknown section raises ValueError
# ---------------------------------------------------------------------------

def test_unknown_section_raises(tmp_path):
    with pytest.raises(ValueError, match="bogus_section"):
        build_notebook(
            ws_name="Test",
            years=(2000, 2010),
            metrics=_sample_metrics(),
            figures_dir=tmp_path,
            sections={"map", "bogus_section"},
        )


# ---------------------------------------------------------------------------
# 4. Figure embedding (base64 display_data)
# ---------------------------------------------------------------------------

def test_figure_embedding(tmp_path):
    """Given a temp dir with a fake PNG, the corresponding cell contains
    base64-encoded image/png display_data output."""
    _write_fake_png(tmp_path, "map.png")
    nb = build_notebook(
        ws_name="Test",
        years=(2000, 2010),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
        sections={"map"},
    )
    # Section cell is cells[2] (after title + metrics).
    section_cell = nb.cells[2]
    assert section_cell.cell_type == "code"
    assert len(section_cell.outputs) == 1
    out = section_cell.outputs[0]
    assert out.output_type == "display_data"
    assert "image/png" in out.data

    # Verify the base64 round-trips to original bytes.
    raw = base64.b64decode(out.data["image/png"])
    assert raw == (tmp_path / "map.png").read_bytes()


# ---------------------------------------------------------------------------
# 5. Missing figure graceful skip
# ---------------------------------------------------------------------------

def test_missing_figure_graceful_skip(tmp_path):
    """Enabled section with no PNG produces a markdown note, not an error."""
    nb = build_notebook(
        ws_name="Test",
        years=(2000, 2010),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
        sections={"hydrographs"},
    )
    cell = nb.cells[2]
    assert cell.cell_type == "markdown"
    assert "not available" in cell.source.lower()


# ---------------------------------------------------------------------------
# 6. Headline metrics formatting
# ---------------------------------------------------------------------------

def test_headline_metrics_formatting(tmp_path):
    """The metrics cell contains expected formatted values."""
    metrics = _sample_metrics()
    nb = build_notebook(
        ws_name="Test",
        years=(2000, 2010),
        metrics=metrics,
        figures_dir=tmp_path,
        sections=set(),  # no sections, just title+metrics+attribution
    )
    metrics_cell = nb.cells[1]
    src = metrics_cell.source

    assert "12,500" in src or "12500" in src  # peak flow
    assert "42.3" in src  # low flow
    assert "June" in src  # peak month
    assert "September" in src  # low-flow month
    assert "152" in src  # center of timing
    assert "0.31" in src  # flashiness


# ---------------------------------------------------------------------------
# 7. save_notebook round-trip
# ---------------------------------------------------------------------------

def test_save_notebook_roundtrip(tmp_path):
    """Write then read back; nbformat.validate passes."""
    nb = build_notebook(
        ws_name="Test",
        years=(2000, 2010),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
        sections={"map"},
    )
    out_path = tmp_path / "report.ipynb"
    result = save_notebook(nb, out_path)
    assert result == out_path
    assert out_path.exists()

    # Read back and validate.
    with open(out_path) as f:
        loaded = nbformat.read(f, as_version=4)
    nbformat.validate(loaded)
    assert len(loaded.cells) == len(nb.cells)


# ---------------------------------------------------------------------------
# 8. PDF converter seam
# ---------------------------------------------------------------------------

def test_pdf_converter_seam(tmp_path):
    """FakeNotebookConverter injected into notebook_to_pdf is called with
    correct args and its return value forwarded."""
    nb = build_notebook(
        ws_name="Test",
        years=(2000, 2010),
        metrics=_sample_metrics(),
        figures_dir=tmp_path,
    )
    out_path = tmp_path / "report.pdf"
    calls: list[tuple] = []

    class FakeNotebookConverter:
        def to_pdf(self, nb_arg, output_path):
            calls.append((nb_arg, output_path))
            output_path.write_bytes(b"%PDF-fake")
            return output_path

    result = notebook_to_pdf(nb, out_path, converter=FakeNotebookConverter())
    assert result == out_path
    assert len(calls) == 1
    assert calls[0] == (nb, out_path)
