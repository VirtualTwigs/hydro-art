"""SVG optimization via SVGO (PRD section 21).

SVGO is a Node.js command-line tool, so running it depends on the host having
Node + ``svgo`` installed. To keep the pipeline pure and its tests fully offline,
optimization sits behind the :class:`SvgOptimizer` protocol (a dependency-
injection seam mirroring the ``Downloader``/``LayerLoader`` pattern): production
injects :class:`SvgoOptimizer` (a thin subprocess wrapper), while tests inject a
fake. The real optimizer **degrades gracefully** — if ``svgo`` is missing or
fails, it returns the SVG unchanged and warns, so a build never crashes on a
machine without SVGO.
"""

from __future__ import annotations

import subprocess
import warnings
from typing import Protocol, runtime_checkable

__all__ = ["SvgOptimizer", "SvgoOptimizer"]


@runtime_checkable
class SvgOptimizer(Protocol):
    """Optimizes an SVG document string, returning the optimized string."""

    def optimize(self, svg: str) -> str: ...


class SvgoOptimizer:
    """Optimize an SVG by shelling out to the ``svgo`` CLI (stdin -> stdout).

    Runs ``svgo -i - -o -``. If the executable is missing or exits non-zero the
    input is returned unchanged (with a warning) rather than raising, so the
    pipeline still produces output on hosts without SVGO installed.
    """

    def __init__(self, command: str = "svgo") -> None:
        self._command = command

    def optimize(self, svg: str) -> str:
        try:
            result = subprocess.run(
                [self._command, "-i", "-", "-o", "-"],
                input=svg,
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            warnings.warn(
                f"'{self._command}' not found; skipping SVG optimization.",
                stacklevel=2,
            )
            return svg
        except subprocess.CalledProcessError as exc:
            warnings.warn(
                f"SVG optimization failed ({self._command} exit "
                f"{exc.returncode}); using the unoptimized SVG.",
                stacklevel=2,
            )
            return svg
        return result.stdout or svg
