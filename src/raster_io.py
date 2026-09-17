"""Concrete GDAL/rasterio-backed DEM I/O adapters (roadmap #31, Epoch 8).

``src.raster`` declares the DEM read path as two bare protocols —
:class:`~src.raster.RasterReader` (``read(asset) -> RasterGrid``) and
:class:`~src.raster.RasterReprojector` (``reproject(grid, dst_crs) -> RasterGrid``)
— and :func:`src.raster.normalize_dem` drives them, but nothing in the repo
implemented them, so cached 3DEP COG tiles could never become a ``RasterGrid``.
This module supplies the concrete pair, closing the gap that kept the hillshade
print (roadmap #30) from auto-acquiring accurate relief.

Injectable-seam rule (as everywhere GIS I/O happens): ``rasterio`` is an
**optional** dependency imported **lazily** inside the default I/O path only —
never at module import — so importing this module (and anything above it) needs
no GDAL/rasterio. The offline test suite injects a fake ``opener``/``warp`` and
never triggers the real import; only a live ``tools/`` run does.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.datasets import AcquisitionError
from src.elevation import ElevationProvenance
from src.raster import GridTransform, RasterGrid

__all__ = [
    "RasterIOError",
    "RasterioRasterReader",
    "RasterioReprojector",
    "grid_from_arrays",
]


class RasterIOError(AcquisitionError):
    """Raised when a DEM raster cannot be read or its transform is unsupported.

    Subclasses :class:`~src.datasets.AcquisitionError` so ``build.py`` maps it to
    the acquisition exit code, consistent with DEM I/O being an acquisition
    concern. The message is intended to be shown to the user.
    """


def grid_from_arrays(
    values: Any,
    *,
    affine: Any,
    crs: Any,
    nodata: float | None = None,
    provenance: ElevationProvenance | None = None,
) -> RasterGrid:
    """Map a GDAL/rasterio affine + 2-D array to a north-up :class:`RasterGrid`.

    ``affine`` is any sequence whose first six elements are the rasterio-order
    coefficients ``(a, b, c, d, e, f)`` where ``x = a·col + b·row + c`` and
    ``y = d·col + e·row + f``. Only a north-up raster is accepted: ``b == d == 0``
    (no rotation/skew), pixel width ``a > 0``, and pixel height ``e < 0`` (rows
    increase southward). The corresponding
    :class:`~src.raster.GridTransform` is
    ``origin_x=c, origin_y=f, pixel_width=a, pixel_height=-e``.

    ``values`` is cast to ``float`` (consistent with the rest of the raster
    subsystem) and must be 2-D. ``crs`` is stringified (a rasterio ``CRS`` renders
    as e.g. ``"EPSG:5070"``). ``nodata``/``provenance`` are carried through.

    Raises:
        RasterIOError: If the array is not 2-D or the affine is rotated/skewed or
            not north-up.
    """
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2:
        raise RasterIOError(
            f"DEM raster must be a 2-D array; got shape {arr.shape}."
        )

    coeffs = tuple(float(v) for v in tuple(affine)[:6])
    if len(coeffs) != 6:
        raise RasterIOError(
            f"Affine must have at least 6 coefficients; got {len(coeffs)}."
        )
    a, b, c, d, e, f = coeffs
    if b != 0.0 or d != 0.0:
        raise RasterIOError(
            f"Rotated/skewed affine is not supported (b={b}, d={d}); "
            "north-up rasters only."
        )
    if a <= 0.0 or e >= 0.0:
        raise RasterIOError(
            f"Expected a north-up affine (pixel_width>0, pixel_height<0); "
            f"got pixel_width={a}, e={e}."
        )

    transform = GridTransform(
        origin_x=c, origin_y=f, pixel_width=a, pixel_height=-e
    )
    return RasterGrid(
        values=arr,
        transform=transform,
        crs=str(crs),
        nodata=nodata,
        provenance=provenance,
    )


def _default_opener(path: str) -> AbstractContextManager[Any]:
    """Open a COG via rasterio (lazy import behind the seam)."""
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RasterIOError(
            "rasterio is required to read DEM COG tiles; install the GIS "
            "dependencies from requirements.txt."
        ) from exc
    return rasterio.open(path)


@dataclass
class RasterioRasterReader:
    """Reads a cached 3DEP COG (``asset.path``) into a north-up ``RasterGrid``.

    ``opener`` is an injectable ``Callable[[str], AbstractContextManager]`` yielding a
    dataset that exposes ``read(1) -> 2-D array``, ``.transform`` (a rasterio
    affine), ``.crs``, and ``.nodata`` — defaulting to a lazy ``rasterio.open``
    wrapper. Tests inject a fake dataset so the read path runs fully offline.
    """

    opener: Callable[[str], AbstractContextManager[Any]] | None = None

    def read(self, asset: Any) -> RasterGrid:
        opener = self.opener or _default_opener
        path = getattr(asset, "path", asset)
        provenance = getattr(asset, "provenance", None)
        with opener(str(path)) as dataset:
            values = dataset.read(1)
            affine = dataset.transform
            crs = dataset.crs
            nodata = dataset.nodata
        return grid_from_arrays(
            values,
            affine=affine,
            crs=crs,
            nodata=nodata,
            provenance=provenance,
        )


def _default_warp(grid: RasterGrid, dst_crs: str) -> RasterGrid:  # pragma: no cover
    """Warp a grid to ``dst_crs`` via rasterio (lazy import behind the seam)."""
    try:
        import rasterio.warp as rio_warp
        from rasterio.transform import Affine
    except ImportError as exc:
        raise RasterIOError(
            "rasterio is required to reproject DEM rasters; install the GIS "
            "dependencies from requirements.txt."
        ) from exc

    t = grid.transform
    src_transform = Affine(
        t.pixel_width, 0.0, t.origin_x, 0.0, -t.pixel_height, t.origin_y
    )
    dst_array, dst_transform = rio_warp.reproject(
        source=grid.values,
        src_transform=src_transform,
        src_crs=grid.crs,
        dst_crs=dst_crs,
        src_nodata=grid.nodata,
        dst_nodata=grid.nodata,
        resampling=rio_warp.Resampling.bilinear,
    )
    array = np.asarray(dst_array)
    if array.ndim == 3:
        array = array[0]
    return grid_from_arrays(
        array,
        affine=tuple(dst_transform)[:6],
        crs=dst_crs,
        nodata=grid.nodata,
        provenance=grid.provenance,
    )


@dataclass
class RasterioReprojector:
    """Warps a :class:`RasterGrid` to a destination CRS.

    ``warp`` is an injectable ``Callable[[RasterGrid, str], RasterGrid]``
    defaulting to a lazy ``rasterio.warp.reproject`` wrapper. When the grid is
    already in ``dst_crs`` the call **identity short-circuits** — the grid is
    returned unchanged (deterministic, no warp) — which is the common case for
    CONUS 3DEP tiles already staged in the internal CRS.
    """

    warp: Callable[[RasterGrid, str], RasterGrid] | None = None

    def reproject(self, grid: RasterGrid, dst_crs: str) -> RasterGrid:
        if grid.crs == dst_crs:
            return grid
        warp = self.warp or _default_warp
        return warp(grid, dst_crs)
