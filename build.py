"""Command-line entry point for the Hydrographic Vector Art Generator.

Resolves configuration (defaults < YAML < CLI), logs the resolved settings,
and runs the (currently stubbed) pipeline. Exits 0 on success and non-zero
with a user-friendly message on any configuration error.

Usage examples::

    python build.py
    python build.py --region washington
    python build.py --palette neon
    python build.py --glow
    python build.py --output svg pdf png
"""

from __future__ import annotations

import sys
from typing import Sequence

from rich.console import Console
from rich.table import Table

from src.cli import resolve_settings
from src.config import ConfigError, Settings
from src.datasets import AcquisitionError
from src.pipeline import Pipeline


def _render_settings(settings: Settings, console: Console) -> None:
    """Print the resolved settings as a table."""
    table = Table(title="Resolved settings", show_header=False, title_justify="left")
    table.add_row("regions", ", ".join(settings.regions))
    table.add_row("projection", settings.projection)
    table.add_row("stream_order", settings.stream_order)
    table.add_row("stream_method", settings.stream_method)
    table.add_row("huc_level", settings.huc_level)
    table.add_row("background", settings.background)
    table.add_row("line_width", str(settings.line_width))
    table.add_row("palette", settings.palette)
    table.add_row("glow", str(settings.glow))
    table.add_row("glow_mode", settings.glow_mode)
    table.add_row("glow_radius", str(settings.glow_radius))
    table.add_row("outputs", ", ".join(sorted(settings.outputs)))
    console.print(table)


def main(argv: Sequence[str] | None = None, pipeline: Pipeline | None = None) -> int:
    """Run the CLI. Returns a process exit code.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).
        pipeline: Optional pipeline to run (injected in tests to avoid real
            network access). Defaults to a real :class:`Pipeline`.
    """
    console = Console()
    try:
        settings = resolve_settings(argv)
    except ConfigError as exc:
        Console(stderr=True).print(f"[bold red]Configuration error:[/] {exc}")
        return 1

    _render_settings(settings, console)
    try:
        (pipeline or Pipeline(console=console)).run(settings)
    except AcquisitionError as exc:
        Console(stderr=True).print(f"[bold red]Acquisition error:[/] {exc}")
        return 2
    console.print("[bold green]Done.[/] (downstream stages are stubs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
