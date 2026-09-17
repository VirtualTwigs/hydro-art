"""Tests for src/raster_io.py (roadmap #31 — concrete 3DEP COG reader).

Fully offline: the concrete ``RasterReader``/``RasterReprojector`` are exercised
through an injected fake ``opener`` (a dataset-like object) and an injected
``warp`` spy, and the affine->grid mapping is pure numpy. No rasterio, no GDAL,
no network — the real ``rasterio`` import only fires on the un-injected default
path, which these tests never take.
"""

from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pytest

from src.elevation import build_provenance
from src.hillshade import hillshade
from src.raster import GridTransform, NormalizedDem, RasterGrid, normalize_dem
from src.raster_io import (
    RasterIOError,
    RasterioRasterReader,
    RasterioReprojector,
    grid_from_arrays,
)


def _provenance(url="https://example/tile.tif"):
    return build_provenance(
        source_product="USGS 3DEP 1/3 arc-second DEM",
        source_url=url,
        acquisition_date="2026-08-17",
        horizontal_crs="EPSG:5070",
        vertical_crs="NAVD88",
        vertical_units="meters",
        resolution_m=10.0,
        checksum="sha256:abc",
    )


class _FakeDataset:
    """A minimal rasterio-dataset stand-in usable as a context manager."""

    def __init__(self, values, transform, crs, nodata):
        self._values = np.asarray(values, dtype=float)
        self.transform = transform
        self.crs = crs
        self.nodata = nodata

    def read(self, band):
        assert band == 1
        return self._values


def _opener_for(dataset):
    @contextmanager
    def _open(path):
        yield dataset

    return _open


class _FakeAsset:
    def __init__(self, path, provenance):
        self.path = path
        self.provenance = provenance


# --- TG1: grid_from_arrays ---------------------------------------------------


def test_north_up_affine_maps_to_grid_transform():
    values = [[1.0, 2.0], [3.0, 4.0]]
    # rasterio affine order (a, b, c, d, e, f): pw=1, origin (10, 20), ph=-1.
    affine = (1.0, 0.0, 10.0, 0.0, -1.0, 20.0)
    prov = _provenance()
    grid = grid_from_arrays(
        values, affine=affine, crs="EPSG:5070", nodata=-9999.0, provenance=prov
    )

    assert isinstance(grid, RasterGrid)
    assert grid.transform == GridTransform(10.0, 20.0, 1.0, 1.0)
    assert grid.crs == "EPSG:5070"
    assert grid.nodata == -9999.0
    assert grid.provenance is prov
    assert grid.bounds == (10.0, 18.0, 12.0, 20.0)
    assert np.array_equal(grid.values, np.asarray(values, dtype=float))


def test_values_cast_to_float():
    grid = grid_from_arrays(
        np.array([[1, 2], [3, 4]], dtype=np.int32),
        affine=(2.0, 0.0, 0.0, 0.0, -2.0, 8.0),
        crs="EPSG:5070",
    )
    assert grid.values.dtype == float
    assert grid.transform.pixel_width == 2.0
    assert grid.transform.pixel_height == 2.0


def test_rotated_affine_raises():
    with pytest.raises(RasterIOError):
        grid_from_arrays(
            [[1.0]], affine=(1.0, 0.5, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070"
        )
    with pytest.raises(RasterIOError):
        grid_from_arrays(
            [[1.0]], affine=(1.0, 0.0, 0.0, 0.5, -1.0, 1.0), crs="EPSG:5070"
        )


def test_non_north_up_affine_raises():
    with pytest.raises(RasterIOError):
        grid_from_arrays(  # non-positive pixel width
            [[1.0]], affine=(-1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070"
        )
    with pytest.raises(RasterIOError):
        grid_from_arrays(  # non-negative pixel height (south-up)
            [[1.0]], affine=(1.0, 0.0, 0.0, 0.0, 1.0, 1.0), crs="EPSG:5070"
        )


def test_non_2d_array_raises():
    with pytest.raises(RasterIOError):
        grid_from_arrays(
            [[[1.0]]], affine=(1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070"
        )


# --- TG2: RasterioRasterReader / RasterioReprojector -------------------------


def test_reader_reads_band_transform_crs_nodata_and_provenance():
    ds = _FakeDataset(
        [[5.0, 6.0], [7.0, 8.0]],
        transform=(1.0, 0.0, 100.0, 0.0, -1.0, 200.0),
        crs="EPSG:5070",
        nodata=-1.0,
    )
    prov = _provenance()
    reader = RasterioRasterReader(opener=_opener_for(ds))
    grid = reader.read(_FakeAsset("/cache/tile.tif", prov))

    assert grid.transform == GridTransform(100.0, 200.0, 1.0, 1.0)
    assert grid.crs == "EPSG:5070"
    assert grid.nodata == -1.0
    assert grid.provenance is prov
    assert np.array_equal(grid.values, np.array([[5.0, 6.0], [7.0, 8.0]]))


def test_reader_accepts_bare_path():
    ds = _FakeDataset(
        [[1.0]], transform=(1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070", nodata=None
    )
    reader = RasterioRasterReader(opener=_opener_for(ds))
    grid = reader.read("/cache/tile.tif")  # a plain path, no .path/.provenance
    assert grid.provenance is None
    assert grid.values.shape == (1, 1)


def test_reprojector_identity_short_circuits():
    grid = grid_from_arrays(
        [[1.0]], affine=(1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070"
    )
    calls = []

    def _warp(g, dst):
        calls.append((g, dst))
        return g

    out = RasterioReprojector(warp=_warp).reproject(grid, "EPSG:5070")
    assert out is grid
    assert calls == []  # warp never invoked when already in the dst CRS


def test_reprojector_delegates_to_injected_warp():
    grid = grid_from_arrays(
        [[1.0]], affine=(1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:4269"
    )
    warped = grid_from_arrays(
        [[2.0]], affine=(1.0, 0.0, 0.0, 0.0, -1.0, 1.0), crs="EPSG:5070"
    )
    calls = []

    def _warp(g, dst):
        calls.append((g, dst))
        return warped

    out = RasterioReprojector(warp=_warp).reproject(grid, "EPSG:5070")
    assert out is warped
    assert calls == [(grid, "EPSG:5070")]


# --- TG3: end-to-end through normalize_dem -----------------------------------


def test_full_chain_reader_normalize_hillshade_offline():
    # Two adjacent 3x3 EPSG:5070 tiles; reader+identity reprojector -> mosaic.
    left = _FakeDataset(
        [[10.0, 11.0, 12.0], [13.0, 14.0, 15.0], [16.0, 17.0, 18.0]],
        transform=(1.0, 0.0, 0.0, 0.0, -1.0, 3.0),
        crs="EPSG:5070",
        nodata=-9999.0,
    )
    right = _FakeDataset(
        [[20.0, 21.0, 22.0], [23.0, 24.0, 25.0], [26.0, 27.0, 28.0]],
        transform=(1.0, 0.0, 3.0, 0.0, -1.0, 3.0),
        crs="EPSG:5070",
        nodata=-9999.0,
    )
    datasets = {"/cache/left.tif": left, "/cache/right.tif": right}

    @contextmanager
    def _open(path):
        yield datasets[str(path)]

    reader = RasterioRasterReader(opener=_open)
    reprojector = RasterioReprojector()  # identity for EPSG:5070

    assets = [
        _FakeAsset("/cache/left.tif", _provenance("https://ex/left.tif")),
        _FakeAsset("/cache/right.tif", _provenance("https://ex/right.tif")),
    ]
    dem = normalize_dem(
        assets=assets,
        boundary=(0.0, 0.0, 6.0, 3.0),
        reader=reader,
        reprojector=reprojector,
    )
    assert isinstance(dem, NormalizedDem)
    assert dem.base.values.shape == (3, 6)  # two 3x3 tiles side by side
    assert dem.base.crs == "EPSG:5070"
    assert len(dem.provenance) == 2

    shaded = hillshade(dem.base)
    assert shaded.values.shape == (3, 6)
    assert shaded.values.min() >= 0
    assert shaded.values.max() <= 255
