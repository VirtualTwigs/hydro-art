"""Tests for DEM raster normalization, pyramids, and sampling (Item 13).

Offline and deterministic: uses tiny synthetic numpy grids with hand-computed
bilinear results and nodata cases. The GDAL-backed tile reader and raster
reprojector are injected seams, exercised here with fakes; no rasterio/GDAL.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from src.dem import DemAsset
from src.elevation import ElevationSample, TileRef, build_provenance
from src.raster import (
    GridTransform,
    NormalizedDem,
    RasterGrid,
    GridSampler,
    build_pyramid,
    clip_grid,
    grid_checksum,
    mosaic,
    normalize_dem,
    sample_bilinear,
)


def _grid(values, origin_x=0.0, origin_y=2.0, px=1.0, py=1.0, crs="EPSG:5070", nodata=None):
    return RasterGrid(
        values=np.array(values, dtype=float),
        transform=GridTransform(origin_x, origin_y, px, py),
        crs=crs,
        nodata=nodata,
    )


def test_grid_bounds_from_transform() -> None:
    grid = _grid([[10, 20], [30, 40]])  # 2x2, 1m pixels, north at y=2
    assert grid.bounds == (0.0, 0.0, 2.0, 2.0)
    assert grid.height == 2 and grid.width == 2


def test_bilinear_at_pixel_center_returns_that_value() -> None:
    grid = _grid([[10, 20], [30, 40]])
    s = sample_bilinear(grid, 0.5, 1.5)  # center of top-left pixel
    assert s.covered and not s.nodata
    assert s.value_m == pytest.approx(10.0)


def test_bilinear_midpoint_is_average_of_four() -> None:
    grid = _grid([[10, 20], [30, 40]])
    s = sample_bilinear(grid, 1.0, 1.0)  # equidistant to all four centers
    assert s.value_m == pytest.approx(25.0)


def test_bilinear_outside_bounds_is_uncovered() -> None:
    grid = _grid([[10, 20], [30, 40]])
    s = sample_bilinear(grid, 5.0, 5.0)
    assert s.covered is False
    assert s.value_m is None
    assert s.nodata is False


def test_bilinear_nodata_neighbor_flags_nodata() -> None:
    grid = _grid([[10, -9999], [30, 40]], nodata=-9999)
    s = sample_bilinear(grid, 1.0, 1.0)  # touches the nodata neighbor
    assert s.covered is True
    assert s.nodata is True
    assert s.value_m is None


def test_grid_sampler_conforms_to_elevation_sampler() -> None:
    grid = _grid([[10, 20], [30, 40]])
    sampler = GridSampler(grid)
    result = sampler.sample(0.5, 1.5)
    assert isinstance(result, ElevationSample)
    assert result.value_m == pytest.approx(10.0)


def test_mosaic_of_two_aligned_tiles() -> None:
    left = _grid([[10, 20], [30, 40]], origin_x=0.0)
    right = _grid([[50, 60], [70, 80]], origin_x=2.0)
    merged = mosaic([left, right])
    assert merged.values.tolist() == [[10, 20, 50, 60], [30, 40, 70, 80]]
    assert merged.transform == GridTransform(0.0, 2.0, 1.0, 1.0)
    assert merged.bounds == (0.0, 0.0, 4.0, 2.0)


def test_mosaic_rejects_mismatched_resolution() -> None:
    a = _grid([[1, 2], [3, 4]])
    b = _grid([[1, 2], [3, 4]], px=2.0)
    with pytest.raises(ValueError):
        mosaic([a, b])


def test_mosaic_tolerates_float_noise_pixel_sizes() -> None:
    # Warping adjacent 3DEP tiles to EPSG:5070 independently yields pixel sizes
    # that differ in the last float digits (~1e-13); they are the same
    # resolution and must still mosaic (regression: real WA statewide run).
    eps = 2e-13
    left = _grid([[10, 20], [30, 40]], origin_x=0.0, px=1.0, py=1.0)
    right = _grid([[50, 60], [70, 80]], origin_x=2.0, px=1.0 + eps, py=1.0 + eps)
    merged = mosaic([left, right])
    assert merged.values.tolist() == [[10, 20, 50, 60], [30, 40, 70, 80]]


def test_clip_selects_the_covering_window() -> None:
    merged = _grid([[10, 20, 50, 60], [30, 40, 70, 80]])  # 2x4, x[0,4] y[0,2]
    clipped = clip_grid(merged, (1.0, 0.0, 3.0, 2.0))
    assert clipped.values.tolist() == [[20, 50], [40, 70]]
    assert clipped.transform.origin_x == 1.0
    assert clipped.bounds == (1.0, 0.0, 3.0, 2.0)


def test_build_pyramid_downsamples_by_two_deterministically() -> None:
    base = _grid(np.arange(16).reshape(4, 4), origin_y=4.0)
    levels = build_pyramid(base, max_levels=2)
    assert len(levels) == 2
    assert levels[0] is base  # finest first
    coarse = levels[1]
    assert coarse.values.tolist() == [[2.5, 4.5], [10.5, 12.5]]
    assert coarse.transform.pixel_width == 2.0
    assert coarse.transform.pixel_height == 2.0
    # Deterministic: identical inputs -> identical values.
    assert build_pyramid(base, max_levels=2)[1].values.tolist() == coarse.values.tolist()


def _asset(tile_id: str, url: str) -> DemAsset:
    prov = build_provenance(
        source_product="USGS 3DEP 1 arc-second DEM",
        source_url=url,
        acquisition_date="2026-07-30",
        horizontal_crs="EPSG:4269",
        vertical_crs="NAVD88",
        vertical_units="meters",
        resolution_m=30.0,
        checksum="sha256:abc",
    )
    return DemAsset(tile=TileRef(tile_id, url, 30.0), path=Path("x"), provenance=prov)


class _FakeReader:
    """Maps a DemAsset to a predefined source-CRS grid (EPSG:4269)."""

    def __init__(self, grids: dict[str, RasterGrid]) -> None:
        self._grids = grids

    def read(self, asset: DemAsset) -> RasterGrid:
        return self._grids[asset.tile.tile_id]


class _FakeReprojector:
    """Identity reprojection that only relabels the horizontal CRS."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def reproject(self, grid: RasterGrid, dst_crs: str) -> RasterGrid:
        self.calls.append(dst_crs)
        return replace(grid, crs=dst_crs)


def test_normalize_dem_reprojects_mosaics_clips_and_pyramids() -> None:
    grids = {
        "a": _grid([[10, 20], [30, 40]], origin_x=0.0, crs="EPSG:4269"),
        "b": _grid([[50, 60], [70, 80]], origin_x=2.0, crs="EPSG:4269"),
    }
    assets = [_asset("a", "http://x/a.tif"), _asset("b", "http://x/b.tif")]
    reprojector = _FakeReprojector()

    result = normalize_dem(
        assets=assets,
        boundary=(1.0, 0.0, 3.0, 2.0),
        reader=_FakeReader(grids),
        reprojector=reprojector,
        pyramid_levels=2,
    )

    assert isinstance(result, NormalizedDem)
    # The tiles are mosaicked in their shared source CRS, then the single
    # mosaic is warped once (not one warp per tile).
    assert reprojector.calls == ["EPSG:5070"]
    assert result.base.crs == "EPSG:5070"
    # mosaic(0..4) clipped to x[1,3] -> cols 1,2
    assert result.base.values.tolist() == [[20, 50], [40, 70]]
    assert len(result.pyramid) == 2
    # Vertical reference preserved verbatim through normalization.
    assert result.provenance[0].vertical_crs == "NAVD88"
    assert result.provenance[0].vertical_units == "meters"


# --- grid_checksum (roadmap #40: DEM mosaic fingerprint) ---------------------


def test_grid_checksum_is_stable_and_hex() -> None:
    g = _grid([[10, 20], [30, 40]])
    a = grid_checksum(g)
    b = grid_checksum(_grid([[10, 20], [30, 40]]))
    assert a == b  # identical grids -> identical hash
    assert len(a) == 64 and all(c in "0123456789abcdef" for c in a)


def test_grid_checksum_changes_with_values() -> None:
    base = grid_checksum(_grid([[10, 20], [30, 40]]))
    assert grid_checksum(_grid([[10, 20], [30, 41]])) != base


def test_grid_checksum_changes_with_transform_crs_and_nodata() -> None:
    base = grid_checksum(_grid([[10, 20], [30, 40]]))
    assert grid_checksum(_grid([[10, 20], [30, 40]], origin_x=1.0)) != base
    assert grid_checksum(_grid([[10, 20], [30, 40]], px=2.0)) != base
    assert grid_checksum(_grid([[10, 20], [30, 40]], crs="EPSG:4269")) != base
    assert grid_checksum(_grid([[10, 20], [30, 40]], nodata=-9999.0)) != base


def test_grid_checksum_nan_is_canonical() -> None:
    # Two grids with NaN in the same cell must hash equal (nan != nan must not
    # make an otherwise-identical grid hash differently); a NaN in a different
    # cell must differ.
    g1 = _grid([[np.nan, 20], [30, 40]])
    g2 = _grid([[np.nan, 20], [30, 40]])
    assert grid_checksum(g1) == grid_checksum(g2)
    g3 = _grid([[10, np.nan], [30, 40]])
    assert grid_checksum(g3) != grid_checksum(g1)


def test_grid_checksum_is_endianness_and_contiguity_stable() -> None:
    values = np.array([[10.0, 20.0], [30.0, 40.0]])
    canonical = grid_checksum(_grid(values))
    # Big-endian view of the same data.
    be = RasterGrid(
        values=values.astype(">f8"),
        transform=GridTransform(0.0, 2.0, 1.0, 1.0),
        crs="EPSG:5070",
    )
    assert grid_checksum(be) == canonical
    # Non-contiguous view (a transposed-back slice) of the same logical array.
    non_contig = np.asfortranarray(values)
    nc = RasterGrid(
        values=non_contig,
        transform=GridTransform(0.0, 2.0, 1.0, 1.0),
        crs="EPSG:5070",
    )
    assert grid_checksum(nc) == canonical
