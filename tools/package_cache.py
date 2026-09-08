"""Offline-package preflight CLI (roadmap #21).

Reports whether a real (e.g. NAS) cache directory holds everything a build needs
for one or more regions — and, when a DEM tile count is supplied, whether that
count fits the configured tile budget — so a cache can be vetted before it is
copied to an offline machine. All the logic lives in the pure, offline
:mod:`src.packaging`; this wrapper only builds the ``Settings`` + ``Cache`` and
prints the plan.

Usage::

    python tools/package_cache.py --region Oregon --cache-dir /Volumes/home/data/incoming
    python tools/package_cache.py --region Oregon Washington --cache-dir ./cache --tile-count 42

The optional ``--tile-count`` is the DEM tile count for the region (obtain it
offline from :func:`src.dem.count_tiles` over the region boundary); omit it to
skip the tile-budget preflight. Exit code is ``0`` when the cache is ready to
package and ``1`` otherwise. Reads a real cache, so it is not part of the offline
test suite.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cache import Cache
from src.cli import resolve_settings
from src.config import ConfigError
from src.packaging import format_plan, plan_package


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight a cache for offline packaging (roadmap #21)."
    )
    parser.add_argument(
        "--region", nargs="+", required=True, help="Region(s) to package for."
    )
    parser.add_argument(
        "--cache-dir", required=True, help="Cache root to inspect (may be a NAS mount)."
    )
    parser.add_argument("--config", default="config.yaml", help="YAML config path.")
    parser.add_argument(
        "--tile-count",
        type=int,
        default=None,
        help="DEM tile count (from src.dem.count_tiles); omit to skip the preflight.",
    )
    args = parser.parse_args(argv)

    forwarded = ["--region", *args.region, "--config", args.config]
    try:
        settings = resolve_settings(forwarded)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    cache = Cache(args.cache_dir)
    plan = plan_package(cache, settings, tile_count=args.tile_count)
    print(format_plan(plan))
    return 0 if plan.is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
