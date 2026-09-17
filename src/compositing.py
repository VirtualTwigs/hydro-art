"""Hillshade print compositing (roadmap #30, Epoch 8).

Pure, deterministic, offline infrastructure for placing the flat river art over a
sense of the underlying terrain in a *rendered image* — without leaving 2D. It
turns the shaded-relief :class:`~src.raster.RasterGrid` produced by
:func:`src.hillshade.hillshade` into a tinted RGBA background raster and
alpha-composites the rasterized river-art layers over it, generalising the
flat-black canvas that ``tools/rasterize_layered.py`` composites over today into a
*supplied* background.

numpy-only over uint8 RGBA arrays — no GDAL, no resvg, no network — so it is fully
offline-testable with hand-built grids and small arrays. Part of the parallel
elevation/terrain subsystem; **not** wired into ``PIPELINE_STAGES`` and never
changes the vector pipeline's rendered bytes. Resampling the DEM grid to the print
canvas is a caller (tool) concern; these functions composite equal-shape arrays.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.raster import RasterGrid

__all__ = [
    "CompositingError",
    "alpha_over",
    "composite_over_background",
    "shade_to_background",
    "solid_canvas",
]


class CompositingError(Exception):
    """Raised for invalid compositing inputs (opacity/tint/shape/dtype).

    The message is intended to be shown directly to the user.
    """


def _validate_rgba(name: str, arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise CompositingError(
            f"{name} must be an (H, W, 4) RGBA array, got shape {arr.shape}."
        )
    if arr.dtype != np.uint8:
        raise CompositingError(
            f"{name} must be uint8, got {arr.dtype}."
        )


def shade_to_background(
    grid: RasterGrid,
    *,
    tint: tuple[int, int, int] | None = None,
    opacity: float = 1.0,
) -> np.ndarray:
    """Turn a hillshade ``RasterGrid`` into an ``(H, W, 4)`` uint8 RGBA background.

    The relief is grayscale (``r == g == b == shade``) unless ``tint`` (an RGB
    colour, each channel ``0-255``) is supplied, in which case
    ``rgb = round(shade / 255 * tint)`` — a single-colour wash over the relief.
    Valid cells get alpha ``round(255 * opacity)``; cells equal to ``grid.nodata``
    get alpha ``0`` (transparent), so the relief never invents terrain where the
    DEM had none.

    Args:
        grid: Shaded-relief raster of values in ``[0, 255]`` (from
            :func:`src.hillshade.hillshade`), optionally carrying a ``nodata``
            sentinel.
        tint: Optional ``(r, g, b)`` colour multiplied by the normalised shade;
            ``None`` keeps grayscale.
        opacity: Alpha of valid cells, ``[0, 1]`` (lets the relief sit subtly
            behind the art).

    Raises:
        CompositingError: If ``opacity`` is outside ``[0, 1]`` or ``tint`` is
            malformed.
    """
    if not 0.0 <= opacity <= 1.0:
        raise CompositingError(f"opacity must be in [0, 1], got {opacity}.")
    if tint is not None:
        channels = tuple(tint)
        if len(channels) != 3 or not all(0 <= int(c) <= 255 for c in channels):
            raise CompositingError(
                f"tint must be three ints in [0, 255], got {tint!r}."
            )

    values = np.asarray(grid.values, dtype=float)
    shade = np.clip(values, 0.0, 255.0)

    if tint is None:
        rgb = np.repeat(np.rint(shade)[..., None], 3, axis=2)
    else:
        tint_arr = np.asarray(tint, dtype=float)
        rgb = np.rint((shade[..., None] / 255.0) * tint_arr)

    alpha = np.full(shade.shape, float(np.rint(255.0 * opacity)))
    if grid.nodata is not None:
        alpha = np.where(values == grid.nodata, 0.0, alpha)

    out = np.concatenate([rgb, alpha[..., None]], axis=2)
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def solid_canvas(
    height: int, width: int, color: tuple[int, int, int] = (0, 0, 0)
) -> np.ndarray:
    """Return an opaque ``(height, width, 4)`` uint8 RGBA canvas of one colour."""
    if height <= 0 or width <= 0:
        raise CompositingError(
            f"canvas size must be positive, got {height}x{width}."
        )
    if len(tuple(color)) != 3 or not all(0 <= int(c) <= 255 for c in color):
        raise CompositingError(
            f"color must be three ints in [0, 255], got {color!r}."
        )
    canvas = np.empty((height, width, 4), dtype=np.uint8)
    canvas[..., 0], canvas[..., 1], canvas[..., 2] = color
    canvas[..., 3] = 255
    return canvas


def alpha_over(base: np.ndarray, over: np.ndarray) -> np.ndarray:
    """Porter-Duff "over" of two equal-shape ``(H, W, 4)`` uint8 RGBA arrays.

    Straight (unpremultiplied) alpha, computed in float then rounded back to
    uint8. Where the composited alpha is zero the RGB is zero. Returns a new
    ``(H, W, 4)`` uint8 array.

    Raises:
        CompositingError: If the arrays are not both uint8 ``(H, W, 4)`` of the
            same shape.
    """
    _validate_rgba("base", base)
    _validate_rgba("over", over)
    if base.shape != over.shape:
        raise CompositingError(
            f"base {base.shape} and over {over.shape} must match."
        )

    ab = base[..., 3:4].astype(float) / 255.0
    ao = over[..., 3:4].astype(float) / 255.0
    base_rgb = base[..., :3].astype(float)
    over_rgb = over[..., :3].astype(float)

    out_a = ao + ab * (1.0 - ao)
    with np.errstate(invalid="ignore", divide="ignore"):
        out_rgb = np.where(
            out_a > 0.0,
            (over_rgb * ao + base_rgb * ab * (1.0 - ao)) / out_a,
            0.0,
        )

    out = np.concatenate([out_rgb, out_a * 255.0], axis=2)
    return np.clip(np.rint(out), 0.0, 255.0).astype(np.uint8)


def composite_over_background(
    background: np.ndarray, layers: Sequence[np.ndarray]
) -> np.ndarray:
    """Fold ``layers`` over ``background`` in order via :func:`alpha_over`.

    Each layer (and the background) must be a uint8 ``(H, W, 4)`` array of the
    same shape. An empty ``layers`` returns a copy of ``background``.
    """
    _validate_rgba("background", background)
    result = background.copy()
    for layer in layers:
        result = alpha_over(result, layer)
    return result
