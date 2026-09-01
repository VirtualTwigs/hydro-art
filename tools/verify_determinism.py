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
    dump_registry,
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
    # DEM mosaic checksum (roadmap #40) — opt-in; fingerprints the real GDAL
    # warp/mosaic path the offline fakes only simulate. Same-host regression.
    parser.add_argument(
        "--check-dem",
        action="store_true",
        help="Also fingerprint the region's DEM mosaic (real 3DEP warp/mosaic).",
    )
    parser.add_argument(
        "--dem",
        default=None,
        help="Supplied normalized DEM grid (.npy) to checksum instead of "
        "auto-acquiring 3DEP relief; implies --check-dem.",
    )
    parser.add_argument(
        "--dem-region",
        default=None,
        help="Region to acquire the DEM for (default: --region).",
    )
    parser.add_argument("--dem-cellsize", type=float, default=10.0, help="DEM cell metres for a supplied .npy.")
    parser.add_argument("--dem-nodata", type=float, default=None, help="Nodata for a supplied .npy.")
    parser.add_argument("--dem-tier", default=None, help="Override elevation.tier.")
    parser.add_argument(
        "--dem-tile-budget", type=int, default=None,
        help="Override elevation.tile_budget (0 = unlimited).",
    )
    parser.add_argument(
        "--dem-refresh", action="store_true", help="Redownload already-cached tiles."
    )
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
    # export_paths artifacts are strings; coerce so _png_bytes can use .suffix.
    paths = [Path(p) for p in ctx.artifacts.get("export_paths", [])]
    return ctx.artifacts["svg_sha256"], paths


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


def _dem_mosaic_sha(args: argparse.Namespace, console: Console) -> str | None:
    """Compute the region's DEM mosaic checksum, or ``None`` (degrade to a skip).

    Two sources, mirroring ``tools/render_terrain_print.py``:

    - ``--dem <path.npy>``: load a pre-normalized grid (cellsize transform) and
      fingerprint it — fast, for same-host experiments.
    - otherwise: auto-acquire real 3DEP relief for the region
      (``acquire_dem_for_settings``), reproject/mosaic to EPSG:5070 through the
      concrete ``raster_io`` seams (``normalize_dem``), clipped to the region's
      EPSG:5070 envelope, then ``grid_checksum`` the mosaic.

    Any DEM error degrades to ``None`` (a clear "skipped" line) so the SVG
    determinism check is never held hostage to the DEM subsystem.
    """
    import numpy as np

    from src.raster import GridTransform, RasterGrid, grid_checksum, normalize_dem

    try:
        if args.dem:
            values = np.load(args.dem).astype(float)
            grid = RasterGrid(
                values=values,
                transform=GridTransform(0.0, values.shape[0] * args.dem_cellsize,
                                        args.dem_cellsize, args.dem_cellsize),
                crs="EPSG:5070",
                nodata=args.dem_nodata,
            )
            return grid_checksum(grid)

        import dataclasses

        from pyproj import Transformer

        from src.cache import Cache
        from src.cli import resolve_settings
        from src.dem import acquire_dem_for_settings, region_bounds
        from src.download import Downloader, UrllibFetcher
        from src.raster_io import RasterioRasterReader, RasterioReprojector

        region = args.dem_region or args.region
        settings = resolve_settings(["--region", region])
        overrides: dict = {"enabled": True}
        if args.dem_refresh:
            overrides["cache_policy"] = "refresh"
        if args.dem_tier is not None:
            overrides["tier"] = args.dem_tier
        if args.dem_tile_budget is not None:
            overrides["tile_budget"] = args.dem_tile_budget
        settings = dataclasses.replace(
            settings, elevation=dataclasses.replace(settings.elevation, **overrides)
        )

        roots = _storage_roots(args)
        # Scope the DEM to the *county* when one is given (so a county golden
        # doesn't over-acquire the whole state's 3DEP): clip to the county polygon
        # bounds; else the state envelope. `clip` is EPSG:5070, `wgs` is EPSG:4326
        # (the CRS `acquire_dem_for_settings` discovers tiles in).
        if args.county and not args.dem_region:
            from src.counties import CensusCountyProvider, county_boundary

            poly = county_boundary(
                CensusCountyProvider(),
                region=region,
                county=args.county,
                target_crs="EPSG:5070",
            )
            clip = tuple(poly.bounds)  # (min_x, min_y, max_x, max_y) in 5070
            to4326 = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
            lons, lats = to4326.transform(
                [clip[0], clip[2], clip[0], clip[2]],
                [clip[1], clip[1], clip[3], clip[3]],
            )
            wgs = (min(lons), min(lats), max(lons), max(lats))
        else:
            wgs = region_bounds(region)  # (min_lon, min_lat, max_lon, max_lat)
            to5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
            xs, ys = to5070.transform(
                [wgs[0], wgs[2], wgs[0], wgs[2]], [wgs[1], wgs[1], wgs[3], wgs[3]]
            )
            clip = (min(xs), min(ys), max(xs), max(ys))

        assets = acquire_dem_for_settings(
            settings,
            boundary=wgs,
            cache=Cache(roots.cache),
            downloader=Downloader(UrllibFetcher()),
            log=lambda msg: console.print(f"  dem: {msg}"),
        )
        dem = normalize_dem(
            assets=assets,
            boundary=clip,
            reader=RasterioRasterReader(),
            reprojector=RasterioReprojector(),
        )
        return grid_checksum(dem.base)
    except Exception as exc:  # noqa: BLE001 — DEM is best-effort; never block SVG.
        console.print(f"[yellow]  dem: skipped ({type(exc).__name__}: {exc})[/]")
        return None


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

    # DEM mosaic checksum (roadmap #40) — opt-in, best-effort.
    dem_sha = None
    if args.check_dem or args.dem:
        dem_sha = _dem_mosaic_sha(args, console)

    registry = load_registry(args.golden)
    verdict = evaluate(key, [sha1, sha2], registry, dem_sha=dem_sha)
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

    if args.record and verdict.run_to_run_ok and (verdict.needs_recording or args.force):
        updated = record_golden(registry, verdict)
        golden_path = Path(args.golden)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        golden_path.write_text(
            json.dumps(dump_registry(updated), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        console.print(f"[green]  recorded golden for {key} -> {golden_path}[/]")

    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
