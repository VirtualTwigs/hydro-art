"""Tests for the terrain sampling service (Item 14).

Offline and deterministic. Uses a synthetic tilted-plane DEM (value == x + y)
so bilinear interpolation is exact and every densified vertex has a
hand-checkable elevation.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.elevation import ElevationSample
from src.raster import (
    GridSampler,
    GridTransform,
    NormalizedDem,
    RasterGrid,
    build_pyramid,
)
from src.terrain import (
    SampledLine,
    SampledPoint,
    TerrainSampler,
    densify_line,
    dem_cell_size,
    sampler_for_dem,
)


def _plane_grid(nodata=None):
    # value == x_center + y_center over x[0,4], y[0,4], 1 m pixels.
    values = np.array(
        [[4, 5, 6, 7], [3, 4, 5, 6], [2, 3, 4, 5], [1, 2, 3, 4]], dtype=float
    )
    return RasterGrid(values, GridTransform(0.0, 4.0, 1.0, 1.0), "EPSG:5070", nodata)


def test_densify_line_subdivides_and_preserves_originals() -> None:
    out = densify_line([(0.0, 0.0), (10.0, 0.0)], spacing=2.0)
    assert out == (
        (0.0, 0.0),
        (2.0, 0.0),
        (4.0, 0.0),
        (6.0, 0.0),
        (8.0, 0.0),
        (10.0, 0.0),
    )


def test_densify_line_keeps_interior_vertices() -> None:
    out = densify_line([(0.0, 0.0), (3.0, 0.0), (3.0, 3.0)], spacing=1.0)
    assert (3.0, 0.0) in out  # original interior vertex preserved
    assert out[0] == (0.0, 0.0) and out[-1] == (3.0, 3.0)
    # No consecutive gap exceeds the spacing.
    for (x0, y0), (x1, y1) in zip(out, out[1:]):
        assert ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 <= 1.0 + 1e-9


def test_densify_line_rejects_nonpositive_spacing() -> None:
    with pytest.raises(ValueError):
        densify_line([(0.0, 0.0), (1.0, 0.0)], spacing=0.0)


def test_densify_line_passthrough_for_degenerate_input() -> None:
    assert densify_line([(1.0, 1.0)], spacing=1.0) == ((1.0, 1.0),)


def test_terrain_sampler_attributes_plane_elevation() -> None:
    sampler = TerrainSampler(GridSampler(_plane_grid()))
    line = sampler.sample_line([(0.5, 3.5), (3.5, 3.5)], spacing=1.0)
    assert isinstance(line, SampledLine)
    assert isinstance(line.points[0], SampledPoint)
    xs = [round(p.x, 3) for p in line.points]
    zs = [round(p.sample.value_m, 3) for p in line.points]
    assert xs == [0.5, 1.5, 2.5, 3.5]
    assert zs == [4.0, 5.0, 6.0, 7.0]  # z == x + y (y == 3.5)
    assert line.n_covered == 4 and line.n_nodata == 0
    assert line.coverage == pytest.approx(1.0)


def test_terrain_sampler_reports_uncovered_points() -> None:
    sampler = TerrainSampler(GridSampler(_plane_grid()))
    line = sampler.sample_line([(2.0, 2.0), (20.0, 2.0)], spacing=2.0)
    assert line.n_points > line.n_covered  # some densified points fall off-grid
    assert any(not p.sample.covered for p in line.points)
    assert 0.0 < line.coverage < 1.0


def test_terrain_sampler_flags_nodata() -> None:
    grid = _plane_grid(nodata=5.0)  # the value 5 becomes a nodata hole
    sampler = TerrainSampler(GridSampler(grid))
    line = sampler.sample_line([(0.5, 3.5), (3.5, 3.5)], spacing=1.0)
    assert line.n_nodata >= 1
    assert any(p.sample.nodata for p in line.points)


def test_dem_cell_size_and_sampler_for_dem_use_pyramid_level() -> None:
    base = _plane_grid()
    dem = NormalizedDem(base=base, pyramid=build_pyramid(base, max_levels=2))
    assert dem_cell_size(dem) == 1.0
    assert dem_cell_size(dem, level=1) == 2.0
    sampler = sampler_for_dem(dem, level=0)
    s = sampler.sample(2.0, 2.0)
    assert isinstance(s, ElevationSample)
    assert s.value_m == pytest.approx(4.0)
