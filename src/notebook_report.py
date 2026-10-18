"""Jupyter notebook assembly and PDF export for watershed reports.

Assembles ``.ipynb`` notebooks from pre-computed metrics and figure PNGs
produced by :mod:`tools.report_common`. Converts notebooks to PDF via an
injectable :class:`NotebookConverter` seam (production: :class:`NbconvertPdfConverter`;
tests: a fake). Pure Python, no GDAL — ``nbformat`` is a stdlib-weight
dependency declared in ``pyproject.toml``.

This module is a **parallel subsystem** — it is NOT wired into
``PIPELINE_STAGES`` and does not affect the 2D default build.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

import nbformat
from nbformat.v4 import new_markdown_cell, new_notebook, new_output

__all__ = [
    "CANONICAL_SECTIONS",
    "NotebookConverter",
    "NbconvertPdfConverter",
    "build_notebook",
    "notebook_to_pdf",
    "save_notebook",
]

#: Ordered section names matching ``web/report.html`` toggles.
CANONICAL_SECTIONS: tuple[str, ...] = (
    "map",
    "hydrographs",
    "long_record",
    "typical_year",
    "low_flow",
    "validation",
    "enso",
    "timing_drift",
    "analog_years",
    "record_book",
    "decade_fdc",
    "composites",
)

#: Human-readable titles for each section.
_SECTION_TITLES: dict[str, str] = {
    "map": "Watershed Map",
    "hydrographs": "Hydrographs",
    "long_record": "Long Record",
    "typical_year": "Typical Year",
    "low_flow": "Low-Flow Analysis",
    "validation": "Validation",
    "enso": "ENSO Influence",
    "timing_drift": "Timing Drift",
    "analog_years": "Analog Years",
    "record_book": "Record Book",
    "decade_fdc": "Decade Flow-Duration Curves",
    "composites": "Composites",
}


def _format_metrics_cell(metrics: dict) -> str:
    """Build markdown for the headline metrics cell."""
    lines = ["## Headline Metrics", ""]

    peak_month = metrics.get("peak_month", "N/A")
    peak_flow = metrics.get("peak_flow_cfs")
    low_month = metrics.get("low_flow_month", "N/A")
    low_flow = metrics.get("low_flow_cfs")
    cot = metrics.get("center_of_timing_doy")
    flash = metrics.get("flashiness_index")

    if peak_flow is not None:
        lines.append(
            f"- **Peak flow month:** {peak_month} "
            f"({peak_flow:,.1f} cfs)"
        )
    else:
        lines.append(f"- **Peak flow month:** {peak_month}")

    if low_flow is not None:
        lines.append(
            f"- **Low-flow month:** {low_month} "
            f"({low_flow:,.1f} cfs)"
        )
    else:
        lines.append(f"- **Low-flow month:** {low_month}")

    if cot is not None:
        lines.append(f"- **Center of timing:** day {cot}")

    if flash is not None:
        lines.append(f"- **Flashiness index:** {flash}")

    return "\n".join(lines)


def _build_figure_cell(
    section: str,
    figures_dir: Path,
    fig_prefix: str,
) -> nbformat.NotebookNode:
    """Return a code cell with embedded PNG output, or a markdown note."""
    png_path = figures_dir / f"{fig_prefix}{section}.png"
    title = _SECTION_TITLES.get(section, section.replace("_", " ").title())

    if not png_path.exists():
        return new_markdown_cell(
            f"### {title}\n\n*Figure not available.*"
        )

    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    cell = nbformat.v4.new_code_cell("")
    cell.outputs = [
        new_output(
            output_type="display_data",
            data={"image/png": b64, "text/plain": [f"{title} figure"]},
        )
    ]
    # Mark as already-executed so Jupyter doesn't prompt to re-run.
    cell.execution_count = None
    # Prepend a markdown heading via the cell source comment.
    cell.source = f"# {title}"
    return cell


def build_notebook(
    ws_name: str,
    years: tuple[int, int],
    metrics: dict,
    figures_dir: Path | str,
    *,
    sections: set[str] | None = None,
    fig_prefix: str = "",
) -> nbformat.v4.NotebookNode:
    """Assemble a Jupyter notebook from pre-computed report data.

    Parameters
    ----------
    ws_name:
        Human-readable watershed name (used in the title cell).
    years:
        ``(start_year, end_year)`` for the analysis period.
    metrics:
        Summary dict (peak, low-flow, center-of-timing, flashiness).
    figures_dir:
        Directory containing ``{fig_prefix}{section}.png`` figures.
    sections:
        If *None*, include all canonical sections. Otherwise, a set of
        section names to include (in canonical order). Unknown names
        raise :class:`ValueError`.
    fig_prefix:
        Filename prefix before the section name (default ``""``).

    Returns
    -------
    nbformat.v4.NotebookNode
        A validated notebook ready for :func:`save_notebook`.
    """
    figures_dir = Path(figures_dir)

    # Validate section names.
    if sections is not None:
        unknown = sections - set(CANONICAL_SECTIONS)
        if unknown:
            raise ValueError(
                f"Unknown section name(s): {', '.join(sorted(unknown))}. "
                f"Valid sections: {', '.join(CANONICAL_SECTIONS)}"
            )
        active = [s for s in CANONICAL_SECTIONS if s in sections]
    else:
        active = list(CANONICAL_SECTIONS)

    nb = new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }

    # Title cell.
    nb.cells.append(new_markdown_cell(
        f"# {ws_name} — Watershed Report\n\n"
        f"**Period:** {years[0]}–{years[1]}"
    ))

    # Metrics cell.
    nb.cells.append(new_markdown_cell(_format_metrics_cell(metrics)))

    # Section cells.
    for section in active:
        nb.cells.append(
            _build_figure_cell(section, figures_dir, fig_prefix)
        )

    # Attribution cell.
    nb.cells.append(new_markdown_cell(
        "---\n\n"
        "*Data: USGS National Hydrography Dataset & National Water "
        "Information System. Generated by hydro-art.*"
    ))

    return nb


def save_notebook(
    nb: nbformat.v4.NotebookNode,
    output_path: Path | str,
) -> Path:
    """Validate and write a notebook to disk.

    Parameters
    ----------
    nb:
        The notebook node to write.
    output_path:
        Destination ``.ipynb`` path.

    Returns
    -------
    Path
        The resolved output path.
    """
    output_path = Path(output_path)
    nbformat.validate(nb)
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    return output_path


# ---------------------------------------------------------------------------
# PDF conversion seam
# ---------------------------------------------------------------------------


@runtime_checkable
class NotebookConverter(Protocol):
    """Injectable seam for notebook-to-PDF conversion."""

    def to_pdf(
        self,
        nb: nbformat.v4.NotebookNode,
        output_path: Path,
    ) -> Path:
        """Convert *nb* to PDF at *output_path* and return the path."""
        ...


class NbconvertPdfConverter:
    """Production converter: nbconvert HTML exporter + weasyprint PDF.

    Lazy-imports ``nbconvert`` and ``weasyprint`` on construction so the
    module can be imported without those heavy optional deps installed.
    """

    def __init__(self) -> None:
        try:
            import nbconvert  # noqa: F401
        except ImportError:  # pragma: no cover
            raise ImportError(
                "nbconvert is required for PDF export. "
                "Install it with: pip install nbconvert"
            )
        try:
            import weasyprint  # noqa: F401
        except ImportError:  # pragma: no cover
            raise ImportError(
                "weasyprint is required for PDF export. "
                "Install it with: pip install weasyprint"
            )

    def to_pdf(
        self,
        nb: nbformat.v4.NotebookNode,
        output_path: Path,
    ) -> Path:  # pragma: no cover
        """Render *nb* as HTML then convert to PDF with weasyprint."""
        from nbconvert import HTMLExporter
        from weasyprint import HTML

        exporter = HTMLExporter()
        html_body, _resources = exporter.from_notebook_node(nb)

        # Dark-theme CSS matching the neon report aesthetic.
        dark_css = (
            "<style>"
            "body { background: #0a0a0a; color: #e0e0e0; "
            "font-family: 'Helvetica Neue', sans-serif; "
            "max-width: 900px; margin: auto; padding: 2em; } "
            "h1, h2, h3 { color: #00e5ff; } "
            "img { max-width: 100%; } "
            "table { border-collapse: collapse; } "
            "td, th { border: 1px solid #333; padding: 4px 8px; } "
            "</style>"
        )
        full_html = f"<!DOCTYPE html><html><head>{dark_css}</head>"
        full_html += f"<body>{html_body}</body></html>"

        # Respect SOURCE_DATE_EPOCH for deterministic output.
        pdf_bytes = HTML(string=full_html).write_pdf(
            presentational_hints=True,
        )
        output_path = Path(output_path)
        output_path.write_bytes(pdf_bytes)
        return output_path


def notebook_to_pdf(
    nb: nbformat.v4.NotebookNode,
    output_path: Path | str,
    *,
    converter: NotebookConverter | None = None,
) -> Path:
    """Convert a notebook to PDF.

    Parameters
    ----------
    nb:
        The notebook to convert.
    output_path:
        Destination PDF path.
    converter:
        Injectable converter; defaults to :class:`NbconvertPdfConverter`.

    Returns
    -------
    Path
        The resolved output path.
    """
    output_path = Path(output_path)
    if converter is None:
        converter = NbconvertPdfConverter()
    return converter.to_pdf(nb, output_path)
