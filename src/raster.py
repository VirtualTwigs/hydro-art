"""DEM raster normalization, pyramids, and bilinear sampling (Item 13).

This module turns the DEM tiles discovered/cached in item 12 into a single,
normalized, queryable elevation surface. It provides:

- :class:`RasterGrid` / :class:`GridTransform` — an immutable, north-up raster
  value object (a numpy array plus an affine origin/pixel-size transform, CRS,
  and nodata value). ``numpy`` is imported directly here, consistent with the
  other analysis modules (``clipping``/``graph``); the heavy *GDAL-backed* work
  (reading COG tiles, warping between CRSs) stays behind the injected
  :class:`RasterReader` / :class:`RasterReprojector` seams so this module and its
  tests run fully offline on tiny synthetic grids.
- Pure transforms: :func:`mosaic` (merge aligned tiles), :func:`clip_grid`
  (window to a boundary bbox), and :func:`build_pyramid` (deterministic 2x
  block-mean downsampling for interactive/statewide/county detail).
- :func:`sample_bilinear` + :class:`GridSampler` — deterministic bilinear
  interpolation returning an :class:`~src.elevation.ElevationSample` with
  coverage/nodata diagnostics (never a silent synthetic substitution).
- :func:`normalize_dem` — the orchestrator: read → reproject to EPSG:5070 →
  mosaic → clip → pyramid, preserving each tile's vertical datum/units verbatim
  (horizontal reprojection only; the resolved NAVD88 decision is identity for
  CONUS 3DEP, so no vertical transform happens here).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, Sequence

import numpy as np

from src.elevation import ElevationProvenance, ElevationSample

__all__ = [
    "GridTransform",
    "RasterGrid",
    "NormalizedDem",
    "RasterReader",
    "RasterReprojector",
    "GridSampler",
    "sample_bilinear",
    "mosaic",
    "clip_grid",
    "build_pyramid",
    "normalize_dem",
]

#: The project's internal horizontal CRS (per PRD / config).
INTERNAL_CRS = "EPSG:5070"


@dataclass(frozen=True)
class GridTransform:
    """North-up affine transform for a raster.

    Attributes:
        origin_x: World x of the raster's top-left *corner* (west edge).
        origin_y: World y of the raster's top-left *corner* (north edge).
        pixel_width: Cell size along +x in world units; must be > 0.
        pixel_height: Cell size along -y in world units; must be > 0.
    """

    origin_x: float
    origin_y: float
    pixel_width: float
    pixel_height: float


@dataclass(frozen=True)
class RasterGrid:
    """An immutable, north-up elevation raster.

    ``values`` is a 2D array in row-major order with row 0 at the north edge.
    """

    values: np.ndarray
    transform: GridTransform
    crs: str
    nodata: float | None = None
    provenance: ElevationProvenance | None = None

    @property
    def height(self) -> int:
        return int(self.values.shape[0])

    @property
    def width(self) -> int:
        return int(self.values.shape[1])

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) covered by the raster's outer edges."""
        t = self.transform
        min_x = t.origin_x
        max_y = t.origin_y
        max_x = t.origin_x + self.width * t.pixel_width
        min_y = t.origin_y - self.height * t.pixel_height
        return (min_x, min_y, max_x, max_y)


@dataclass(frozen=True)
class NormalizedDem:
    """The normalized elevation surface for a region.

    Attributes:
        base: The full-resolution mosaicked, clipped, reprojected grid.
        pyramid: Multi-resolution levels, finest (``base``) first.
        provenance: Per-source lineage, preserved verbatim from acquisition.
    """

    base: RasterGrid
    pyramid: tuple[RasterGrid, ...]
    provenance: tuple[ElevationProvenance, ...] = field(default_factory=tuple)


class RasterReader(Protocol):
    """Seam that reads a DEM asset into a :class:`RasterGrid` (GDAL-backed)."""

    def read(self, asset: Any) -> RasterGrid:
        ...


class RasterReprojector(Protocol):
    """Seam that warps a :class:`RasterGrid` to a destination CRS (GDAL-backed)."""

    def reproject(self, grid: RasterGrid, dst_crs: str) -> RasterGrid:
        ...


def sample_bilinear(grid: RasterGrid, x: float, y: float) -> ElevationSample:
    """Bilinearly sample ``grid`` at world point ``(x, y)``.

    Returns an :class:`~src.elevation.ElevationSample`:

    - Outside the raster's extent -> ``covered=False``, ``value_m=None``.
    - Inside but any of the four interpolation neighbors is the nodata value ->
      ``covered=True``, ``nodata=True``, ``value_m=None`` (never substituted).
    - Otherwise -> the interpolated elevation with ``covered=True``.

    Edge neighbor indices are clamped into range so points within the extent
    but past the outermost pixel centers still interpolate against real cells.
    """
    t = grid.transform
    min_x, min_y, max_x, max_y = grid.bounds
    if not (min_x <= x <= max_x and min_y <= y <= max_y):
        return ElevationSample(value_m=None, covered=False, nodata=False)

    # Fractional coordinates in pixel-center space.
    fc = (x - t.origin_x) / t.pixel_width - 0.5
    fr = (t.origin_y - y) / t.pixel_height - 0.5

    c0 = int(math.floor(fc))
    r0 = int(math.floor(fr))
    c1, r1 = c0 + 1, r0 + 1
    tx = fc - c0
    ty = fr - r0

    def _clamp(idx: int, size: int) -> int:
        return max(0, min(size - 1, idx))

    cc0, cc1 = _clamp(c0, grid.width), _clamp(c1, grid.width)
    rr0, rr1 = _clamp(r0, grid.height), _clamp(r1, grid.height)

    v00 = grid.values[rr0, cc0]
    v01 = grid.values[rr0, cc1]
    v10 = grid.values[rr1, cc0]
    v11 = grid.values[rr1, cc1]

    if grid.nodata is not None and grid.nodata in (v00, v01, v10, v11):
        return ElevationSample(value_m=None, covered=True, nodata=True)

    top = v00 * (1 - tx) + v01 * tx
    bottom = v10 * (1 - tx) + v11 * tx
    value = top * (1 - ty) + bottom * ty
    return ElevationSample(value_m=float(value), covered=True, nodata=False)


class GridSampler:
    """An :class:`~src.elevation.ElevationSampler` backed by a :class:`RasterGrid`."""

    def __init__(self, grid: RasterGrid) -> None:
        self._grid = grid

    def sample(self, x: float, y: float) -> ElevationSample:
        return sample_bilinear(self._grid, x, y)


def _require_aligned(grids: Sequence[RasterGrid]) -> tuple[float, float, str]:
    """Validate grids share pixel size and CRS; return (pw, ph, crs)."""
    first = grids[0]
    pw = first.transform.pixel_width
    ph = first.transform.pixel_height
    crs = first.crs
    for g in grids[1:]:
        if g.transform.pixel_width != pw or g.transform.pixel_height != ph:
            raise ValueError(
                "Cannot mosaic grids with mismatched pixel sizes: "
                f"{(pw, ph)} vs "
                f"{(g.transform.pixel_width, g.transform.pixel_height)}."
            )
        if g.crs != crs:
            raise ValueError(
                f"Cannot mosaic grids in different CRSs: {crs} vs {g.crs}."
            )
    return pw, ph, crs


def mosaic(grids: Sequence[RasterGrid]) -> RasterGrid:
    """Merge aligned, same-CRS grids into one; gaps are filled with nodata.

    All inputs must share pixel size and CRS and be aligned to a common pixel
    grid. Overlaps take the last writer. The result's nodata value is taken from
    the first grid (or a sentinel when none is set).

    Raises:
        ValueError: If ``grids`` is empty or the grids are not alignable.
    """
    if not grids:
        raise ValueError("mosaic requires at least one grid.")
    pw, ph, crs = _require_aligned(grids)

    min_x = min(g.bounds[0] for g in grids)
    min_y = min(g.bounds[1] for g in grids)
    max_x = max(g.bounds[2] for g in grids)
    max_y = max(g.bounds[3] for g in grids)

    width = int(round((max_x - min_x) / pw))
    height = int(round((max_y - min_y) / ph))
    nodata = grids[0].nodata if grids[0].nodata is not None else float("nan")

    out = np.full((height, width), nodata, dtype=float)
    for g in grids:
        col = int(round((g.bounds[0] - min_x) / pw))
        row = int(round((max_y - g.bounds[3]) / ph))
        out[row : row + g.height, col : col + g.width] = g.values

    return RasterGrid(
        values=out,
        transform=GridTransform(min_x, max_y, pw, ph),
        crs=crs,
        nodata=grids[0].nodata,
        provenance=grids[0].provenance,
    )


def clip_grid(
    grid: RasterGrid, bounds: tuple[float, float, float, float]
) -> RasterGrid:
    """Return the sub-grid whose pixels cover ``bounds`` (min_x, min_y, max_x, max_y).

    The window snaps outward to whole pixels, so the clipped raster fully covers
    the requested bounds (never partially truncating a needed cell).

    Raises:
        ValueError: If ``bounds`` does not intersect the grid.
    """
    t = grid.transform
    min_x, min_y, max_x, max_y = bounds

    c_start = int(math.floor((min_x - t.origin_x) / t.pixel_width))
    c_end = int(math.ceil((max_x - t.origin_x) / t.pixel_width))
    r_start = int(math.floor((t.origin_y - max_y) / t.pixel_height))
    r_end = int(math.ceil((t.origin_y - min_y) / t.pixel_height))

    c_start = max(0, c_start)
    r_start = max(0, r_start)
    c_end = min(grid.width, c_end)
    r_end = min(grid.height, r_end)
    if c_start >= c_end or r_start >= r_end:
        raise ValueError("Clip bounds do not intersect the raster grid.")

    sub = grid.values[r_start:r_end, c_start:c_end]
    new_origin_x = t.origin_x + c_start * t.pixel_width
    new_origin_y = t.origin_y - r_start * t.pixel_height
    return RasterGrid(
        values=sub.copy(),
        transform=GridTransform(new_origin_x, new_origin_y, t.pixel_width, t.pixel_height),
        crs=grid.crs,
        nodata=grid.nodata,
        provenance=grid.provenance,
    )


def _downsample_2x(grid: RasterGrid) -> RasterGrid:
    """Halve resolution via 2x2 block mean, ignoring nodata within a block."""
    t = grid.transform
    # Trim to an even shape so blocks are full 2x2 (deterministic).
    h = grid.height - (grid.height % 2)
    w = grid.width - (grid.width % 2)
    vals = grid.values[:h, :w].astype(float)

    blocks = vals.reshape(h // 2, 2, w // 2, 2)
    if grid.nodata is not None:
        mask = blocks != grid.nodata
        counts = mask.sum(axis=(1, 3))
        sums = np.where(mask, blocks, 0.0).sum(axis=(1, 3))
        with np.errstate(invalid="ignore"):
            out = np.where(counts > 0, sums / np.maximum(counts, 1), grid.nodata)
    else:
        out = blocks.mean(axis=(1, 3))

    return RasterGrid(
        values=out,
        transform=GridTransform(
            t.origin_x, t.origin_y, t.pixel_width * 2, t.pixel_height * 2
        ),
        crs=grid.crs,
        nodata=grid.nodata,
        provenance=grid.provenance,
    )


def build_pyramid(grid: RasterGrid, max_levels: int = 4) -> tuple[RasterGrid, ...]:
    """Build a deterministic multi-resolution pyramid, finest (``grid``) first.

    Each level halves resolution by 2x2 block-mean. Downsampling stops early
    once a level would be smaller than 2x2 or ``max_levels`` is reached.
    """
    if max_levels < 1:
        raise ValueError("max_levels must be >= 1.")
    levels = [grid]
    current = grid
    while len(levels) < max_levels and current.height >= 2 and current.width >= 2:
        current = _downsample_2x(current)
        levels.append(current)
    return tuple(levels)


def normalize_dem(
    *,
    assets: Sequence[Any],
    boundary: tuple[float, float, float, float],
    reader: RasterReader,
    reprojector: RasterReprojector,
    target_crs: str = INTERNAL_CRS,
    pyramid_levels: int = 4,
) -> NormalizedDem:
    """Read, reproject, mosaic, clip, and pyramid DEM ``assets`` for a region.

    Each asset is read into its source-CRS grid, warped to ``target_crs``
    (horizontal only — vertical datum/units are preserved verbatim in each
    asset's provenance), then all grids are mosaicked, clipped to ``boundary``,
    and reduced into a deterministic pyramid.

    Raises:
        ValueError: If ``assets`` is empty.
    """
    assets = list(assets)
    if not assets:
        raise ValueError("normalize_dem requires at least one DEM asset.")

    reprojected = [
        reprojector.reproject(reader.read(asset), target_crs) for asset in assets
    ]
    merged = mosaic(reprojected)
    clipped = clip_grid(merged, boundary)
    pyramid = build_pyramid(clipped, max_levels=pyramid_levels)
    provenance = tuple(
        asset.provenance for asset in assets if getattr(asset, "provenance", None)
    )
    return NormalizedDem(base=clipped, pyramid=pyramid, provenance=provenance)
