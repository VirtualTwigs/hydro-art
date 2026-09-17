"""Offline unit tests for the pure gridded-climate sampling helpers (numpy only).

These pin the highest-risk correctness surface of the nClimGrid provider — the
monthly-time-axis band index (off-by-one on the 1895 epoch and 0-/1-based bands),
the lon/lat -> (row, col) cell math, and the honest nodata fallback — without any
GDAL/rasterio (the concrete NetCDF read lives in ``tools/nclimgrid_flow.py``).
"""

from __future__ import annotations

import numpy as np
import pytest

from src.climate_grid import (
    GRIDDED_FIRST_YEAR,
    ClimateGridError,
    band_for_month,
    cells_from_lonlat,
    fill_nodata,
)

# --- band_for_month: the epoch/off-by-one guard (watch-list risk #2) --------


def test_band_for_month_epoch_boundaries_one_based() -> None:
    assert GRIDDED_FIRST_YEAR == 1895
    assert band_for_month(1895, 1) == 1       # first month of the record
    assert band_for_month(1895, 12) == 12     # first year, December
    assert band_for_month(1896, 1) == 13      # rolls into year two
    assert band_for_month(2023, 12) == (2023 - 1895) * 12 + 12  # == 1548


def test_band_for_month_zero_based_shifts_by_one() -> None:
    for year, month in [(1895, 1), (1896, 1), (2020, 7)]:
        assert (
            band_for_month(year, month, one_based=False)
            == band_for_month(year, month) - 1
        )


def test_band_for_month_guards() -> None:
    with pytest.raises(ClimateGridError):
        band_for_month(1894, 1)          # before the record start
    with pytest.raises(ClimateGridError):
        band_for_month(2000, 0)          # month too low
    with pytest.raises(ClimateGridError):
        band_for_month(2000, 13)         # month too high
    with pytest.raises(ClimateGridError):
        band_for_month(True, 1)          # bool is not a valid int year
    with pytest.raises(ClimateGridError):
        band_for_month(2000.0, 1)        # non-int year


# --- cells_from_lonlat: vectorized (row, col) from an inverse affine ---------


def test_cells_from_lonlat_maps_and_clips() -> None:
    # A 10x10 grid, 1-degree cells, origin (lon0, lat0) = (0, 10) north-up.
    # Forward transform: x = 0 + 1*col, y = 10 - 1*row.
    # Inverse (a,b,c,d,e,f): col = x ; row = 10 - y  ->  (1,0,0, 0,-1,10).
    inv = (1.0, 0.0, 0.0, 0.0, -1.0, 10.0)
    lon = np.array([0.0, 4.5, 9.9])
    lat = np.array([10.0, 5.5, 0.1])
    rows, cols = cells_from_lonlat(lon, lat, inv, width=10, height=10)
    assert cols.tolist() == [0, 4, 9]
    assert rows.tolist() == [0, 4, 9]


def test_cells_from_lonlat_clips_out_of_bounds() -> None:
    inv = (1.0, 0.0, 0.0, 0.0, -1.0, 10.0)
    lon = np.array([-5.0, 99.0])
    lat = np.array([99.0, -99.0])
    rows, cols = cells_from_lonlat(lon, lat, inv, width=10, height=10)
    assert cols.tolist() == [0, 9]   # clipped to [0, width-1]
    assert rows.tolist() == [0, 9]   # clipped to [0, height-1]


def test_cells_from_lonlat_shape_guard() -> None:
    inv = (1.0, 0.0, 0.0, 0.0, -1.0, 10.0)
    with pytest.raises(ClimateGridError):
        cells_from_lonlat(np.zeros(3), np.zeros(2), inv, width=5, height=5)
    with pytest.raises(ClimateGridError):
        cells_from_lonlat(np.zeros((2, 2)), np.zeros((2, 2)), inv, width=5, height=5)


# --- fill_nodata: honest ocean/nodata handling, pure --------------------------


def test_fill_nodata_replaces_sentinel_and_nan() -> None:
    vals = np.array([1.5, -9999.0, np.nan, 3.0])
    out = fill_nodata(vals, nodata=-9999.0, fill=0.0)
    assert out.tolist() == [1.5, 0.0, 0.0, 3.0]


def test_fill_nodata_is_pure() -> None:
    vals = np.array([1.0, -9999.0])
    before = vals.copy()
    fill_nodata(vals, nodata=-9999.0, fill=10.0)
    assert vals.tolist() == before.tolist()  # input untouched


def test_fill_nodata_none_nodata_only_scrubs_nonfinite() -> None:
    vals = np.array([1.0, np.inf, 2.0])
    out = fill_nodata(vals, nodata=None, fill=0.0)
    assert out.tolist() == [1.0, 0.0, 2.0]
