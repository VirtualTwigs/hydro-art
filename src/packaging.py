"""Offline-package preflight planning (roadmap #21).

Answers a single question for a given :class:`~src.config.Settings`: *is this
cache ready to package and ship to an offline machine?* It composes the primitives
already built for #21 — :func:`~src.datasets.resolve_required_files` (what a build
needs), :func:`~src.manifest.build_manifest` / :func:`~src.manifest.verify_manifest`
(what the cache holds, intact), and ``settings.elevation.tile_budget`` (the DEM
tile preflight) — into one deterministic :class:`PackagePlan`.

The DEM tile count is *injected* (a real count comes from
:func:`src.dem.count_tiles` over a region boundary at the CLI layer), so this
module imports only stdlib + ``src.manifest`` / ``src.datasets`` / ``src.config`` /
``src.cache`` — no numpy / geopandas / GDAL / shapely — and stays fully
offline-testable. Not wired into ``PIPELINE_STAGES``; an acquisition-domain
packaging utility (``PackagingError`` subclasses ``AcquisitionError``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.cache import Cache
from src.config import Settings
from src.datasets import AcquisitionError, resolve_required_files
from src.manifest import build_manifest, verify_manifest

__all__ = [
    "PackagingError",
    "PackagePlan",
    "plan_package",
    "format_plan",
]


class PackagingError(AcquisitionError):
    """Raised for packaging-preflight errors (user-facing message)."""


@dataclass(frozen=True)
class PackagePlan:
    """A deterministic readiness report for packaging a cache offline.

    ``present``/``missing``/``corrupt`` are disjoint subsets that partition
    ``required``. ``tile_count`` is ``None`` when the DEM preflight was skipped.
    """

    required: tuple[str, ...]
    present: tuple[str, ...]
    missing: tuple[str, ...]
    corrupt: tuple[str, ...]
    total_bytes: int
    tile_count: int | None
    tile_budget: int

    @property
    def is_complete(self) -> bool:
        """Whether every required file is present and intact."""
        return not self.missing and not self.corrupt

    @property
    def within_tile_budget(self) -> bool:
        """Whether the DEM tile preflight is within budget (or not applicable)."""
        if self.tile_count is None or self.tile_budget == 0:
            return True
        return self.tile_count <= self.tile_budget

    @property
    def is_ready(self) -> bool:
        """Whether the cache can be packaged: complete and within tile budget."""
        return self.is_complete and self.within_tile_budget


def plan_package(
    cache: Cache,
    settings: Settings,
    *,
    cache_root: str | Path | None = None,
    tile_count: int | None = None,
) -> PackagePlan:
    """Plan whether ``cache`` covers everything ``settings`` needs, offline.

    Resolves the required files, builds a manifest of the cached subset, and
    verifies it against ``cache_root`` (defaults to ``cache.root``). A required key
    is ``present`` if its file verifies, ``corrupt`` if cached-but-mismatched, else
    ``missing``. ``tile_count`` (from :func:`src.dem.count_tiles`) is compared
    against ``settings.elevation.tile_budget`` when supplied.
    """
    required = resolve_required_files(settings)
    required_keys = tuple(d.key for d in required)

    manifest = build_manifest(cache, required)
    root = Path(cache_root) if cache_root is not None else cache.root
    verification = verify_manifest(manifest, root)

    cached = {e.key for e in manifest.entries}
    ok = set(verification.ok)
    mismatched = set(verification.mismatched)
    gone = set(verification.missing)  # recorded, but file absent on disk

    present = tuple(k for k in required_keys if k in ok)
    corrupt = tuple(k for k in required_keys if k in mismatched)
    missing = tuple(k for k in required_keys if k not in cached or k in gone)
    total_bytes = sum(e.size for e in manifest.entries)

    return PackagePlan(
        required=required_keys,
        present=present,
        missing=missing,
        corrupt=corrupt,
        total_bytes=total_bytes,
        tile_count=tile_count,
        tile_budget=settings.elevation.tile_budget,
    )


def format_plan(plan: PackagePlan) -> str:
    """Render a human-readable one-block summary of a :class:`PackagePlan`."""
    lines = [
        f"Package readiness: {'READY' if plan.is_ready else 'NOT READY'}",
        f"  required: {len(plan.required)}  present: {len(plan.present)}  "
        f"missing: {len(plan.missing)}  corrupt: {len(plan.corrupt)}",
        f"  cached size: {plan.total_bytes} bytes",
    ]
    if plan.tile_count is None:
        lines.append("  DEM tile preflight: skipped")
    else:
        budget = "unlimited" if plan.tile_budget == 0 else str(plan.tile_budget)
        verdict = "within budget" if plan.within_tile_budget else "OVER BUDGET"
        lines.append(
            f"  DEM tiles: {plan.tile_count} (budget {budget}) — {verdict}"
        )
    for key in plan.missing:
        lines.append(f"  - missing: {key}")
    for key in plan.corrupt:
        lines.append(f"  - corrupt: {key}")
    return "\n".join(lines)
