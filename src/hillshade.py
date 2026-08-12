"""Terrain-aware 2D hillshade (roadmap #22, print-mode slice).

Turns a bare-earth elevation :class:`~src.raster.RasterGrid` into a Lambertian
shaded-relief grid (0-255) so the flat river art can be composited over a sense of
the underlying topography — without leaving 2D. Uses Horn's 3x3 gradient method
and the standard ESRI/GDAL hillshade illumination model with a configurable sun
(azimuth + altitude) and a shading-only vertical ``z_factor``.

Pure, deterministic, and offline: numpy over the existing ``RasterGrid`` — no
GDAL, no network. Part of the parallel elevation/terrain subsystem; **not** wired
into ``PIPELINE_STAGES``. Nodata is never invented: a cell that is nodata, or
whose 3x3 neighborhood touches nodata, is emitted as the output sentinel.
"""

from __future__ import annotations

import math

import numpy as np

from src.elevation import ElevationError
from src.raster import RasterGrid

__all__ = ["HillshadeError", "hillshade"]


class HillshadeError(ElevationError):
    """Raised for invalid hillshade parameters (azimuth/altitude/z_factor).

    The message is intended to be shown directly to the user.
    """


def hillshade(
    grid: RasterGrid,
    *,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
    z_factor: float = 1.0,
    nodata: float = -1.0,
) -> RasterGrid:
    """Compute a Lambertian shaded-relief ``RasterGrid`` (0-255) from a DEM.

    Args:
        grid: North-up elevation raster (row 0 at the north edge).
        azimuth_deg: Compass bearing of the light source, ``[0, 360)``
            (``315`` = NW, the cartographic convention).
        altitude_deg: Sun angle above the horizon, ``(0, 90]``.
        z_factor: Vertical exaggeration applied to slope for shading only; must
            be ``> 0``. Does not alter the source elevations.
        nodata: Output sentinel for cells whose shade is undefined.

    Returns:
        A same-shape/transform/CRS ``RasterGrid`` of relief in ``[0, 255]`` with
        ``nodata`` set; ``provenance`` is carried through from ``grid``.

    Raises:
        HillshadeError: If ``azimuth_deg``/``altitude_deg``/``z_factor`` are out
            of range.
    """
    if not 0.0 <= azimuth_deg < 360.0:
        raise HillshadeError(
            f"azimuth_deg must be in [0, 360), got {azimuth_deg}."
        )
    if not 0.0 < altitude_deg <= 90.0:
        raise HillshadeError(
            f"altitude_deg must be in (0, 90], got {altitude_deg}."
        )
    if z_factor <= 0.0:
        raise HillshadeError(f"z_factor must be > 0, got {z_factor}.")

    values = np.asarray(grid.values, dtype=float)
    cw = grid.transform.pixel_width
    ch = grid.transform.pixel_height

    # Edge-replicate so every cell has a full 3x3 neighborhood (GDAL
    # -compute_edges), keeping the output the same shape as the input.
    padded = np.pad(values, 1, mode="edge")
    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, f = padded[1:-1, :-2], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]

    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * cw)
    dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * ch)

    slope = np.arctan(z_factor * np.hypot(dz_dx, dz_dy))
    aspect = np.arctan2(dz_dy, -dz_dx)
    aspect = np.where(aspect < 0.0, 2.0 * math.pi + aspect, aspect)

    zenith = math.radians(90.0 - altitude_deg)
    az = math.radians((360.0 - azimuth_deg + 90.0) % 360.0)

    shade = 255.0 * (
        math.cos(zenith) * np.cos(slope)
        + math.sin(zenith) * np.sin(slope) * np.cos(az - aspect)
    )
    shade = np.clip(shade, 0.0, 255.0)

    if grid.nodata is not None:
        invalid = values == grid.nodata
        if invalid.any():
            # A cell is undefined if it or any 8-neighbor is nodata (its gradient
            # would be corrupted). 3x3 OR-dilation, padded with False so real
            # border cells are not spuriously invalidated.
            pad_inv = np.pad(invalid, 1, mode="constant", constant_values=False)
            neighbor_invalid = (
                pad_inv[:-2, :-2] | pad_inv[:-2, 1:-1] | pad_inv[:-2, 2:]
                | pad_inv[1:-1, :-2] | pad_inv[1:-1, 1:-1] | pad_inv[1:-1, 2:]
                | pad_inv[2:, :-2] | pad_inv[2:, 1:-1] | pad_inv[2:, 2:]
            )
            shade = np.where(neighbor_invalid, float(nodata), shade)

    return RasterGrid(
        values=shade,
        transform=grid.transform,
        crs=grid.crs,
        nodata=float(nodata),
        provenance=grid.provenance,
    )
