"""Determinism verifier CLI (roadmap #39, non-offline).

Renders a region (optionally a single county) **twice** through the real
GDAL-backed :class:`~src.pipeline.Pipeline` and proves the 2D-default output is
deterministic:

- **run-to-run**: the two renders' ``svg_sha256`` must be byte-identical on this
  machine (the deterministic-output invariant this epoch exists to make provable);
- **against golden**: both must equal the committed per-region golden hash
  (roadmap #40's fixture registry). A region with no recorded golden is a soft
  "record me" prompt — pass ``--record`` to write it.
- **rasterized PNG** (best effort): each run's SVG is rasterized with
  ``SOURCE_DATE_EPOCH=0`` and the PNG bytes are byte-compared; if ``resvg`` is
  unavailable or errors, this **degrades to a warning** and the ``svg_sha256``
  check stands.

All the comparison/registry/formatting logic lives in the pure, offline
:mod:`src.determinism`; this wrapper only does the (non-offline) double render and
the optional PNG rasterization. Reads real datasets (via the real ``Pipeline``),
so it is not part of the offline test suite.

Usage::

    python tools/verify_determinism.py --region Oregon
    python tools/verify_determinism.py --region Washington --county Clark
    python tools/verify_determinism.py --region Oregon --golden tests/fixtures/golden/registry.json --record
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from rich.console import Console

from build import _storage_roots
from src.cli import resolve_settings
from src.config import ConfigError, Settings
from src.datasets import AcquisitionError
from src.determinism import (
    DeterminismError,
    evaluate,
    format_verdict,
    load_registry,
    record_golden,
    registry_key,
)
from src.pipeline import Pipeline

#: Default golden registry path (a ``{key: svg_sha256}`` JSON map).
DEFAULT_GOLDEN = "tests/fixtures/golden/registry.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify deterministic 2D output (roadmap #39)."
    )
    parser.add_argument("--region", required=True, help="Region to render.")
    parser.add_argument("--county", default=None, help="Optional county scope.")
    parser.add_argument(
        "--golden",
        default=DEFAULT_GOLDEN,
        help=f"Golden registry JSON path (default {DEFAULT_GOLDEN}).",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record this run's sha as the golden when none exists (or --force).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --record, overwrite an existing golden entry.",
    )
    parser.add_argument("--config", default="config.yaml", help="YAML config path.")
    # Storage flags mirrored from build.py so _storage_roots can wire the Pipeline.
    parser.add_argument("--external-root", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--datasets-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--staging", default=None)
    return parser


def _render_once(settings: Settings, args: argparse.Namespace, console: Console) -> tuple[str, list[Path]]:
    """Run the real pipeline once; return (svg_sha256, export_paths)."""
    roots = _storage_roots(args)
    pipeline = Pipeline(
        console=console,
        cache_dir=roots.cache,
        datasets_dir=roots.datasets,
        output_dir=roots.output,
        staging_dir=roots.staging,
    )
    ctx = pipeline.run(settings)
    return ctx.artifacts["svg_sha256"], list(ctx.artifacts.get("export_paths", []))


def _png_bytes(svg_paths: Sequence[Path]) -> bytes | None:
    """Rasterize the first SVG export to PNG bytes with SOURCE_DATE_EPOCH=0.

    Returns ``None`` (degrade to a warning) if there is no SVG or ``resvg`` is
    unavailable/errors — the svg_sha256 check remains authoritative.
    """
    svgs = [p for p in svg_paths if p.suffix.lower() == ".svg"]
    if not svgs:
        return None
    env = {**os.environ, "SOURCE_DATE_EPOCH": "0"}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "render.png"
        try:
            subprocess.run(
                ["resvg", str(svgs[0]), str(out)],
                check=True,
                capture_output=True,
                env=env,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return out.read_bytes()


def main(argv: Sequence[str] | None = None) -> int:
    console = Console()
    args = _build_parser().parse_args(argv)

    forwarded = ["--region", args.region, "--config", args.config]
    if args.county:
        forwarded += ["--county", args.county]
    try:
        settings = resolve_settings(forwarded)
        key = registry_key(args.region, args.county)
    except (ConfigError, DeterminismError) as exc:
        console.print(f"[bold red]Configuration error:[/] {exc}")
        return 1

    try:
        sha1, paths1 = _render_once(settings, args, console)
        sha2, paths2 = _render_once(settings, args, console)
    except AcquisitionError as exc:
        console.print(f"[bold red]Acquisition error:[/] {exc}")
        return 2

    registry = load_registry(args.golden)
    verdict = evaluate(key, [sha1, sha2], registry)
    console.print(format_verdict(verdict))

    # Best-effort rasterized-PNG determinism (degrades to a warning).
    png1, png2 = _png_bytes(paths1), _png_bytes(paths2)
    if png1 is None or png2 is None:
        console.print("[yellow]  png: skipped (resvg unavailable) — svg_sha256 stands[/]")
    elif png1 == png2:
        console.print("[green]  png: OK (byte-identical rasterization)[/]")
    else:
        console.print("[bold red]  png: DRIFT — rasterized PNGs differ[/]")
        return 1

    if args.record and verdict.run_to_run_ok and (verdict.golden_sha is None or args.force):
        updated = record_golden(registry, verdict)
        golden_path = Path(args.golden)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        golden_path.write_text(
            json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        console.print(f"[green]  recorded golden for {key} -> {golden_path}[/]")

    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
