"""Tests for src/compositing.py (roadmap #30 — hillshade print compositing).

Pure/offline: the compositing seam is numpy-only over hand-built ``RasterGrid``s
and small uint8 RGBA arrays — no GDAL, no resvg, no network. Safe in the offline
suite.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.compositing import (
    CompositingError,
    alpha_over,
    composite_over_background,
    shade_to_background,
    solid_canvas,
)
from src.raster import GridTransform, RasterGrid


def _grid(values, nodata=None):
    arr = np.asarray(values, dtype=float)
    transform = GridTransform(0.0, float(arr.shape[0]), 1.0, 1.0)
    return RasterGrid(arr, transform, "EPSG:5070", nodata)


# --- TG1: shade_to_background ------------------------------------------------


def test_grayscale_maps_shade_to_equal_rgb_opaque():
    grid = _grid([[0.0, 128.0], [200.0, 255.0]])
    bg = shade_to_background(grid)

    assert bg.shape == (2, 2, 4)
    assert bg.dtype == np.uint8
    # r == g == b == shade for every cell.
    assert np.array_equal(bg[..., 0], bg[..., 1])
    assert np.array_equal(bg[..., 1], bg[..., 2])
    assert list(bg[..., 0].ravel()) == [0, 128, 200, 255]
    # Fully opaque with no nodata and default opacity.
    assert np.all(bg[..., 3] == 255)


def test_tint_multiplies_normalized_shade():
    grid = _grid([[255.0, 0.0]])
    bg = shade_to_background(grid, tint=(200, 100, 50))

    # shade 255 -> full tint; shade 0 -> black.
    assert list(bg[0, 0, :3]) == [200, 100, 50]
    assert list(bg[0, 1, :3]) == [0, 0, 0]


def test_nodata_cells_are_transparent():
    grid = _grid([[100.0, -1.0]], nodata=-1.0)
    bg = shade_to_background(grid)

    assert bg[0, 0, 3] == 255  # valid cell opaque
    assert bg[0, 1, 3] == 0  # nodata cell transparent


def test_opacity_scales_valid_alpha_only():
    grid = _grid([[100.0, -1.0]], nodata=-1.0)
    bg = shade_to_background(grid, opacity=0.5)

    assert bg[0, 0, 3] == round(255 * 0.5)  # valid cell alpha scaled to ~128
    assert bg[0, 1, 3] == 0  # nodata still fully transparent


def test_bad_opacity_and_tint_raise():
    grid = _grid([[100.0]])
    with pytest.raises(CompositingError):
        shade_to_background(grid, opacity=1.5)
    with pytest.raises(CompositingError):
        shade_to_background(grid, opacity=-0.1)
    with pytest.raises(CompositingError):
        shade_to_background(grid, tint=(300, 0, 0))
    with pytest.raises(CompositingError):
        shade_to_background(grid, tint=(0, 0))  # wrong length


# --- TG2: solid_canvas / alpha_over / composite_over_background ---------------


def test_solid_canvas_is_opaque_single_color():
    c = solid_canvas(2, 3, (10, 20, 30))
    assert c.shape == (2, 3, 4)
    assert c.dtype == np.uint8
    assert list(c[0, 0]) == [10, 20, 30, 255]
    assert np.all(c[..., 3] == 255)


def test_alpha_over_opaque_replaces_base():
    base = solid_canvas(1, 1, (0, 0, 0))
    over = np.array([[[255, 0, 0, 255]]], dtype=np.uint8)
    out = alpha_over(base, over)
    assert list(out[0, 0]) == [255, 0, 0, 255]


def test_alpha_over_transparent_is_identity():
    base = solid_canvas(1, 1, (12, 34, 56))
    over = np.zeros((1, 1, 4), dtype=np.uint8)  # fully transparent
    out = alpha_over(base, over)
    assert list(out[0, 0]) == [12, 34, 56, 255]


def test_alpha_over_half_alpha_blends_halfway():
    base = solid_canvas(1, 1, (0, 0, 0))
    over = np.array([[[255, 255, 255, 128]]], dtype=np.uint8)
    out = alpha_over(base, over)
    # 128/255 ~= 0.502 over black -> ~128 grey, opaque result.
    assert out[0, 0, 3] == 255
    assert abs(int(out[0, 0, 0]) - 128) <= 1


def test_alpha_over_zero_out_alpha_gives_black():
    base = np.zeros((1, 1, 4), dtype=np.uint8)
    over = np.zeros((1, 1, 4), dtype=np.uint8)
    out = alpha_over(base, over)
    assert list(out[0, 0]) == [0, 0, 0, 0]


def test_alpha_over_shape_mismatch_raises():
    base = solid_canvas(1, 1)
    over = solid_canvas(2, 2)
    with pytest.raises(CompositingError):
        alpha_over(base, over)


def test_composite_folds_layers_in_order():
    base = solid_canvas(1, 1, (0, 0, 0))
    red = np.array([[[255, 0, 0, 255]]], dtype=np.uint8)
    half_blue = np.array([[[0, 0, 255, 128]]], dtype=np.uint8)
    out = composite_over_background(base, [red, half_blue])
    # Blue at ~50% over opaque red: red drops ~half, blue ~half.
    assert out[0, 0, 2] > out[0, 0, 0]  # more blue than red now
    assert out[0, 0, 3] == 255


def test_composite_empty_layers_returns_background_copy():
    base = solid_canvas(1, 2, (7, 8, 9))
    out = composite_over_background(base, [])
    assert np.array_equal(out, base)
    assert out is not base  # a copy, not the same array
