"""Tests for the terrain-aware 2D hillshade (roadmap #22, print-mode slice).

Offline and deterministic. Builds tiny synthetic DEMs as numpy grids so every
illumination case is hand-reasoned. The module under test is pure numpy over the
existing ``RasterGrid`` — no GDAL, no real DEM assets.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.hillshade import HillshadeError, hillshade
from src.raster import GridTransform, RasterGrid


def _grid(values, nodata=None, pixel=1.0):
    arr = np.asarray(values, dtype=float)
    # origin at top-left corner; north-up.
    transform = GridTransform(0.0, float(arr.shape[0]) * pixel, pixel, pixel)
    return RasterGrid(arr, transform, "EPSG:5070", nodata)


def _plane(nrows, ncols, dz_dcol=1.0, dz_drow=0.0):
    """Tilted plane: elevation increases by dz per column (east) / row (south)."""
    rows = np.arange(nrows)[:, None]
    cols = np.arange(ncols)[None, :]
    return (cols * dz_dcol + rows * dz_drow).astype(float)


# ---- TG-H1: core -------------------------------------------------------------

def test_flat_dem_is_uniform_sun_altitude_shade():
    grid = _grid(np.full((5, 5), 100.0))
    hs = hillshade(grid, altitude_deg=45.0)
    expected = 255.0 * math.sin(math.radians(45.0))
    assert np.allclose(hs.values, expected)


def test_slope_brighter_when_lit_from_upslope():
    # Plane rising toward the east (+x / +col): its face points downhill, to the
    # west (aspect = west). A west light (azimuth 270) hits the slope face-on ->
    # brighter than an east light (azimuth 90) which rakes the shadowed far side.
    grid = _grid(_plane(6, 6, dz_dcol=2.0))
    lit = hillshade(grid, azimuth_deg=270.0, altitude_deg=45.0)
    away = hillshade(grid, azimuth_deg=90.0, altitude_deg=45.0)
    # Compare an interior cell (borders use edge replication).
    assert lit.values[2, 2] > away.values[2, 2]


def test_output_preserves_grid_and_range():
    grid = _grid(_plane(7, 5, dz_dcol=1.5, dz_drow=0.5))
    hs = hillshade(grid)
    assert hs.values.shape == grid.values.shape
    assert hs.crs == grid.crs
    assert hs.transform == grid.transform
    assert hs.values.min() >= 0.0 and hs.values.max() <= 255.0


def test_hillshade_is_deterministic():
    grid = _grid(_plane(6, 6, dz_dcol=1.0, dz_drow=0.7))
    assert np.array_equal(
        hillshade(grid, azimuth_deg=300.0).values,
        hillshade(grid, azimuth_deg=300.0).values,
    )


def test_larger_z_factor_deepens_shadow():
    grid = _grid(_plane(6, 6, dz_dcol=1.0))
    soft = hillshade(grid, z_factor=1.0)
    hard = hillshade(grid, z_factor=5.0)
    # Exaggerating relief pushes the darkest interior cell darker (more contrast).
    assert hard.values[1:-1, 1:-1].min() < soft.values[1:-1, 1:-1].min()


# ---- TG-H2: nodata + validation ----------------------------------------------

def test_nodata_cell_and_neighbors_propagate():
    values = _plane(7, 7, dz_dcol=1.0)
    values[3, 3] = -9999.0  # a single interior hole
    grid = _grid(values, nodata=-9999.0)
    hs = hillshade(grid)
    # The hole and its 8 neighbors are undefined -> output sentinel.
    for r in (2, 3, 4):
        for col in (2, 3, 4):
            assert hs.values[r, col] == hs.nodata
    # A cell two rows away keeps a real shade.
    assert hs.values[0, 0] != hs.nodata
    assert 0.0 <= hs.values[0, 0] <= 255.0


def test_no_nodata_source_yields_no_sentinel():
    grid = _grid(_plane(5, 5, dz_dcol=1.0))  # nodata=None
    hs = hillshade(grid, nodata=-1.0)
    assert not np.any(hs.values == -1.0)
    assert hs.values.min() >= 0.0


def test_invalid_parameters_raise():
    grid = _grid(_plane(4, 4, dz_dcol=1.0))
    with pytest.raises(HillshadeError, match="altitude"):
        hillshade(grid, altitude_deg=0.0)
    with pytest.raises(HillshadeError, match="altitude"):
        hillshade(grid, altitude_deg=91.0)
    with pytest.raises(HillshadeError, match="azimuth"):
        hillshade(grid, azimuth_deg=360.0)
    with pytest.raises(HillshadeError, match="z_factor"):
        hillshade(grid, z_factor=0.0)
