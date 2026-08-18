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

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Sequence

from rich.console import Console
from rich.table import Table

from src.cli import build_parser, settings_from_args
from src.config import ConfigError, Settings
from src.datasets import AcquisitionError
from src.pipeline import Pipeline
from src.storage import (
    EXTERNAL_ROOT_ENV,
    StorageRoots,
    drive_available,
    resolve_storage,
)

#: Downloaded-archive cache root. Points at the NAS share so the large
#: hydrography GDB zips are staged and reused off-machine rather than locally.
NAS_CACHE_DIR = "/Volumes/home/data/incoming"


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
    table.add_row("png_size", str(settings.png_size))
    table.add_row("outputs", ", ".join(sorted(settings.outputs)))
    console.print(table)


def _default_cache_dir(available: Callable[[Path], bool]) -> Path:
    """Today's cache default: the NAS share when mounted, else local ``cache``.

    Mirrors ``serve._resolve_cache_dir`` so a build never dies trying to write
    under an unmounted ``/Volumes`` mount point.
    """
    nas = Path(NAS_CACHE_DIR)
    return nas if available(nas) else Path("cache")


def _storage_roots(
    args: argparse.Namespace,
    *,
    available: Callable[[Path], bool] = drive_available,
) -> StorageRoots:
    """Resolve the cache/datasets/output roots from the parsed storage flags.

    Precedence follows :func:`src.storage.resolve_storage` (explicit dir >
    external-drive subdir when mounted > local default). To preserve today's
    behavior, when **no** external root is configured the cache falls back to the
    NAS share (when mounted) rather than local ``cache`` — the external root, when
    given and mounted, supplies ``<root>/cache`` instead.
    """
    overrides: dict[str, str] = {}
    if args.cache_dir:
        overrides["cache"] = args.cache_dir
    if args.datasets_dir:
        overrides["datasets"] = args.datasets_dir
    if args.output_dir:
        overrides["output"] = args.output_dir

    external = args.external_root or os.environ.get(EXTERNAL_ROOT_ENV)
    if "cache" not in overrides and not external:
        overrides["cache"] = str(_default_cache_dir(available))

    return resolve_storage(
        external_root=args.external_root,
        overrides=overrides,
        staging=args.staging,
        available=available,
    )


def main(argv: Sequence[str] | None = None, pipeline: Pipeline | None = None) -> int:
    """Run the CLI. Returns a process exit code.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).
        pipeline: Optional pipeline to run (injected in tests to avoid real
            network access). Defaults to a real :class:`Pipeline` whose storage
            roots come from :func:`_storage_roots`.
    """
    console = Console()
    args = build_parser().parse_args(argv)
    try:
        settings = settings_from_args(args)
    except ConfigError as exc:
        Console(stderr=True).print(f"[bold red]Configuration error:[/] {exc}")
        return 1

    _render_settings(settings, console)
    if pipeline is None:
        roots = _storage_roots(args)
        console.print(
            f"[dim]storage:[/] cache={roots.cache} datasets={roots.datasets} "
            f"output={roots.output}"
            + (" [green](external drive)[/]" if roots.using_external else "")
        )
        pipeline = Pipeline(
            console=console,
            cache_dir=roots.cache,
            datasets_dir=roots.datasets,
            output_dir=roots.output,
            staging_dir=roots.staging,
        )
    try:
        pipeline.run(settings)
    except AcquisitionError as exc:
        Console(stderr=True).print(f"[bold red]Acquisition error:[/] {exc}")
        return 2
    console.print("[bold green]Done.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
