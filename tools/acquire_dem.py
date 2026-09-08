"""Real (non-offline) DEM acquisition CLI (roadmap #21).

Gives the DEM subsystem a real entry point outside the test suite: for one or
more supported regions it discovers the USGS 3DEP 1-degree COG tiles covering the
region, downloads and caches them through the same injected download seam the
hydrography pipeline uses, and records each tile's provenance. All the logic lives
in the pure, offline :mod:`src.dem` (``region_bounds`` -> boundary,
``acquire_dem_for_settings`` -> discover/cache/record); this wrapper only builds
the ``Settings`` + ``Cache`` + real ``Downloader`` and prints the result.

The DEM subsystem is deliberately **not** part of ``PIPELINE_STAGES`` (see
CLAUDE.md) — it's a parallel data model with its own entry points, and this is one.

Usage::

    # Dry run: count the tiles a region needs, no network, no cache writes.
    python tools/acquire_dem.py --region Oregon --cache-dir ./cache --dry-run

    # Real acquisition against a NAS-staged cache (elevation is force-enabled).
    python tools/acquire_dem.py --region Oregon --cache-dir /Volumes/home/data/incoming
    python tools/acquire_dem.py --region Oregon Washington --cache-dir ./cache \
        --tier state --tile-budget 200

``--tier`` / ``--tile-budget`` override ``settings.elevation`` for this run;
``--refresh`` forces a redownload of already-cached tiles. Exit code is ``0`` on
success and ``1`` when a region's tile count exceeds the budget or a boundary/
config is invalid. Reads and writes a real cache (and, without ``--dry-run``, the
network), so it is not part of the offline test suite.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cache import Cache
from src.cli import resolve_settings
from src.config import ConfigError
from src.dem import (
    acquire_dem_for_settings,
    count_tiles,
    region_bounds,
)
from src.download import Downloader, UrllibFetcher
from src.elevation import ElevationError


def _settings_for_region(region: str, config: str, args: argparse.Namespace):
    """Build region ``Settings`` with elevation force-enabled + CLI overrides."""
    settings = resolve_settings(["--region", region, "--config", config])
    elevation = settings.elevation
    overrides = {"enabled": True, "cache_policy": elevation.cache_policy}
    if args.refresh:
        overrides["cache_policy"] = "refresh"
    if args.tier is not None:
        overrides["tier"] = args.tier
    if args.tile_budget is not None:
        overrides["tile_budget"] = args.tile_budget
    elevation = dataclasses.replace(elevation, **overrides)
    return dataclasses.replace(settings, elevation=elevation)


def _run_region(region: str, cache: Cache, args: argparse.Namespace) -> int:
    """Acquire (or dry-run count) one region's DEM tiles; return an exit code."""
    settings = _settings_for_region(region, args.config, args)
    tier = settings.elevation.tier
    budget = settings.elevation.tile_budget
    boundary = region_bounds(region)

    if args.dry_run:
        count = count_tiles(boundary, tier)
        fits = budget == 0 or count <= budget
        limit = "unlimited" if budget == 0 else str(budget)
        print(f"{region}: {count} {tier} tile(s); budget {limit} -> "
              f"{'OK' if fits else 'OVER BUDGET'}")
        return 0 if fits else 1

    downloader = Downloader(UrllibFetcher())
    assets = acquire_dem_for_settings(
        settings,
        boundary=boundary,
        cache=cache,
        downloader=downloader,
        log=lambda msg: print(f"  {msg}"),
    )
    print(f"{region}: acquired {len(assets)} {tier} tile(s):")
    for asset in assets:
        print(f"  {asset.tile.tile_id}  {asset.path}  {asset.provenance.checksum}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Acquire USGS 3DEP DEM tiles for a region (roadmap #21)."
    )
    parser.add_argument(
        "--region", nargs="+", required=True, help="Region(s) to acquire DEM for."
    )
    parser.add_argument(
        "--cache-dir", required=True, help="Cache root (may be a NAS mount)."
    )
    parser.add_argument("--config", default="config.yaml", help="YAML config path.")
    parser.add_argument(
        "--tier", default=None, help="Override elevation.tier (preview|state)."
    )
    parser.add_argument(
        "--tile-budget",
        type=int,
        default=None,
        help="Override elevation.tile_budget (0 = unlimited).",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Redownload already-cached tiles."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count tiles + check the budget without downloading anything.",
    )
    args = parser.parse_args(argv)

    cache = Cache(args.cache_dir)
    exit_code = 0
    try:
        for region in args.region:
            exit_code |= _run_region(region, cache, args)
    except (ConfigError, ElevationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
