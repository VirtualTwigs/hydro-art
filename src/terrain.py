"""Terrain sampling service (Item 14, Epoch 3 Phase 3.1).

Provides an injectable bilinear sampler over a normalized DEM plus flowline
densification, so downstream Z-attribution (item 15) can read a ground
elevation at *every* vertex of a river line — including interpolated vertices
inserted at a spacing tied to the active DEM cell size.

- :func:`densify_line` inserts vertices along a polyline so no gap exceeds a
  given spacing, while preserving every original vertex (and thus the exact 2D
  path). Spacing is normally :func:`dem_cell_size` so sampling never skips a
  cell.
- :class:`TerrainSampler` wraps any injected
  :class:`~src.elevation.ElevationSampler` (e.g. a
  :class:`~src.raster.GridSampler` from :func:`sampler_for_dem`) and returns a
  :class:`SampledLine` — the densified points with their
  :class:`~src.elevation.ElevationSample`s and coverage/nodata diagnostics.
- :func:`dem_cell_size` / :func:`sampler_for_dem` select a pyramid level so a
  caller can sample coarse levels for interactive preview and the finest level
  on commit.

Pure geometry over coordinate tuples; no GDAL, no shapely required. The DEM is
already normalized to EPSG:5070 (item 13), so points and raster share a CRS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from src.elevation import ElevationSample, ElevationSampler
from src.raster import GridSampler, NormalizedDem

__all__ = [
    "SampledPoint",
    "SampledLine",
    "TerrainSampler",
    "densify_line",
    "dem_cell_size",
    "sampler_for_dem",
]

Coord = tuple[float, float]


def densify_line(coords: Sequence[Coord], spacing: float) -> tuple[Coord, ...]:
    """Insert vertices so no segment gap exceeds ``spacing``.

    Every original vertex is preserved (endpoints and interior), so the returned
    path is geometrically identical to the input — only sampled more densely.
    Each segment is split into ``ceil(length / spacing)`` equal parts.

    Raises:
        ValueError: If ``spacing`` <= 0.
    """
    if spacing <= 0:
        raise ValueError(f"densify spacing must be > 0, got {spacing}.")
    pts = [(float(x), float(y)) for x, y in coords]
    if len(pts) < 2:
        return tuple(pts)

    out: list[Coord] = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, math.ceil(dist / spacing))
        for i in range(1, steps + 1):
            t = i / steps
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return tuple(out)


@dataclass(frozen=True)
class SampledPoint:
    """A point with its sampled ground elevation.

    Attributes:
        x: Projected x (EPSG:5070 meters).
        y: Projected y (EPSG:5070 meters).
        sample: The elevation sample (value + coverage/nodata diagnostics).
    """

    x: float
    y: float
    sample: ElevationSample


@dataclass(frozen=True)
class SampledLine:
    """A densified, elevation-attributed line plus coverage diagnostics."""

    points: tuple[SampledPoint, ...]

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_covered(self) -> int:
        return sum(1 for p in self.points if p.sample.covered)

    @property
    def n_nodata(self) -> int:
        return sum(1 for p in self.points if p.sample.nodata)

    @property
    def coverage(self) -> float:
        """Fraction of points with in-extent coverage (0.0 for an empty line)."""
        return self.n_covered / self.n_points if self.points else 0.0


class TerrainSampler:
    """Samples ground elevation along densified lines via an injected sampler."""

    def __init__(self, sampler: ElevationSampler) -> None:
        self._sampler = sampler

    def sample_coords(self, coords: Sequence[Coord]) -> SampledLine:
        """Sample each coordinate as-is (no densification)."""
        points = tuple(
            SampledPoint(float(x), float(y), self._sampler.sample(float(x), float(y)))
            for x, y in coords
        )
        return SampledLine(points=points)

    def sample_line(self, coords: Sequence[Coord], spacing: float) -> SampledLine:
        """Densify ``coords`` at ``spacing`` then sample every vertex."""
        return self.sample_coords(densify_line(coords, spacing))


def dem_cell_size(dem: NormalizedDem, level: int = 0) -> float:
    """Nominal cell size (meters) of a DEM pyramid ``level`` (0 = finest)."""
    return dem.pyramid[level].transform.pixel_width


def sampler_for_dem(dem: NormalizedDem, level: int = 0) -> GridSampler:
    """Build a :class:`~src.raster.GridSampler` over a DEM pyramid ``level``.

    Level 0 is the finest (full detail); higher levels are coarser and cheaper,
    for interactive preview.
    """
    return GridSampler(dem.pyramid[level])
