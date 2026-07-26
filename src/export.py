"""Multi-format export of the finished SVG (PRD sections 22-23).

SVG is the one required format and is written with pure stdlib — no external
tool. The optional formats (PDF/PNG/TIFF/EPS) are produced by converting the
SVG through an external CLI, which depends on the host having a rasterizer
installed. To keep the pipeline pure and its tests fully offline, export sits
behind the :class:`Exporter` protocol (the dependency-injection seam mirroring
``Downloader``/``SvgOptimizer``): production injects :class:`FileExporter`
(a thin subprocess wrapper), while tests inject a fake. The real exporter
**degrades gracefully** — if the converter is missing or fails it warns and
skips that format, so a build never crashes and always produces the SVG.
"""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = ["Exporter", "FileExporter", "RASTER_FORMATS"]

#: Formats rendered as pixels (sized by ``png_size``); the rest are vector.
RASTER_FORMATS: frozenset[str] = frozenset({"png", "tiff"})


@runtime_checkable
class Exporter(Protocol):
    """Writes an SVG document to ``dest`` in ``fmt``; returns the path or None."""

    def export(
        self, svg: str, dest: Path, fmt: str, *, png_size: int
    ) -> Path | None: ...


class FileExporter:
    """Write SVG natively and convert other formats via the ``rsvg-convert`` CLI.

    ``svg`` is written directly (no tool needed). Any other format shells out to
    ``rsvg-convert -f <fmt> -o <dest>`` (reading the SVG on stdin), passing
    ``--width <png_size>`` for raster formats. If the executable is missing or
    exits non-zero, the format is skipped (with a warning) and ``None`` is
    returned rather than raising, so export still produces the SVG on hosts
    without a converter installed.
    """

    def __init__(self, command: str = "rsvg-convert") -> None:
        self._command = command

    def export(
        self, svg: str, dest: Path, fmt: str, *, png_size: int
    ) -> Path | None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "svg":
            dest.write_text(svg, encoding="utf-8")
            return dest

        args = [self._command, "-f", fmt, "-o", str(dest)]
        if fmt in RASTER_FORMATS:
            args += ["--width", str(png_size)]
        args.append("-")  # read the SVG from stdin
        try:
            subprocess.run(
                args, input=svg.encode("utf-8"), capture_output=True, check=True
            )
        except FileNotFoundError:
            warnings.warn(
                f"'{self._command}' not found; skipping {fmt} export.",
                stacklevel=2,
            )
            return None
        except subprocess.CalledProcessError as exc:
            warnings.warn(
                f"{fmt} export failed ({self._command} exit {exc.returncode}); "
                f"skipping {fmt}.",
                stacklevel=2,
            )
            return None
        return dest
