"""Tests for the intrinsic hydrograph metrics engine (roadmap #48/#49/#53).

Offline, numpy-only: hand-built ``{year: [n,12]}`` series and ``[12]`` monthly
rows with known answers. No GDAL/network; the heavy GDB reads live in tools/.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.flow_metrics import (
    FlowMetricsError,
    anomaly,
    center_of_timing,
    flashiness,
    flow_duration,
    longitudinal_profile,
    low_flow,
    mann_kendall,
    outlet_index,
    peak_flow,
    percentile_rank,
    rolling_normals,
    seasonal_ratio,
    sens_slope,
    subset_series,
)


# --- #48 intrinsic hydrograph shape --------------------------------------

def test_peak_flow_per_year_max_over_months() -> None:
    y = np.zeros((2, 12))
    y[0, 3] = 5.0  # reach 0 peaks in April
    y[1, 7] = 9.0  # reach 1 peaks in August
    out = peak_flow({2020: y})
    assert set(out) == {2020}
    np.testing.assert_allclose(out[2020], [5.0, 9.0])


def test_low_flow_summer_minimum_picks_july() -> None:
    y = np.full((1, 12), 10.0)
    y[0, 6] = 2.0  # July (index 6) is the summer minimum
    out = low_flow({2021: y})  # default months=(6,7,8)
    np.testing.assert_allclose(out[2021], [2.0])


def test_low_flow_custom_months_window_honored() -> None:
    y = np.full((1, 12), 10.0)
    y[0, 0] = 1.0  # January
    y[0, 6] = 2.0  # July
    out = low_flow({2021: y}, months=(1, 2, 3))  # winter window → picks January
    np.testing.assert_allclose(out[2021], [1.0])


def test_center_of_timing_single_month_and_flat() -> None:
    single = np.zeros(12)
    single[4] = 3.0  # all flow in May (month 5)
    assert center_of_timing(single) == pytest.approx(5.0)
    assert center_of_timing(np.ones(12)) == pytest.approx(6.5)


def test_flashiness_constant_zero_and_alternating_upper() -> None:
    assert flashiness(np.full(12, 4.0)) == pytest.approx(0.0)
    # [1,0,1,0,...] → 11 unit steps over sum 6 → the RB upper value for n=12.
    assert flashiness(np.array([1.0, 0.0] * 6)) == pytest.approx(11.0 / 6.0)


def test_seasonal_ratio_wet_over_dry_mean() -> None:
    m = np.zeros(12)
    for i in (10, 11, 0, 1, 2, 3):  # wet: Nov,Dec,Jan,Feb,Mar,Apr
        m[i] = 8.0
    for i in (4, 5, 6, 7, 8, 9):  # dry: May..Oct
        m[i] = 2.0
    assert seasonal_ratio(m) == pytest.approx(4.0)


def test_flow_duration_monotone_non_increasing_with_endpoints() -> None:
    m = np.arange(1.0, 13.0)  # 1..12
    fd = flow_duration(m, [0, 50, 100])
    assert fd[0] == pytest.approx(12.0)   # 0% exceedance → max
    assert fd[-1] == pytest.approx(1.0)   # 100% exceedance → min
    assert np.all(np.diff(fd) <= 0)


def test_purity_inputs_not_mutated() -> None:
    y = np.ones((2, 12))
    series = {2020: y}
    before = y.copy()
    peak_flow(series)
    low_flow(series)
    np.testing.assert_array_equal(series[2020], before)


def test_errors_on_empty_and_ragged_series() -> None:
    with pytest.raises(FlowMetricsError):
        peak_flow({})
    with pytest.raises(FlowMetricsError):
        peak_flow({2020: np.ones((2, 11))})  # 11 months, not 12


# --- #49 trend / distribution --------------------------------------------

def test_mann_kendall_monotone_and_flat_trends() -> None:
    inc = mann_kendall(np.arange(1, 11))
    assert inc.trend == "increasing" and inc.S > 0 and inc.tau == pytest.approx(1.0)
    dec = mann_kendall(np.arange(10, 0, -1))
    assert dec.trend == "decreasing" and dec.S < 0
    flat = mann_kendall(np.ones(10))
    assert flat.trend == "none" and flat.S == 0


def test_mann_kendall_textbook_tau() -> None:
    mk = mann_kendall([1, 2, 4, 3])  # one inversion → S=4, tau=4/6
    assert mk.S == 4
    assert mk.tau == pytest.approx(2.0 / 3.0)


def test_sens_slope_is_robust_to_one_outlier() -> None:
    # y = 2x + 3, with index 4 corrupted to 100.
    values = [3, 5, 7, 9, 100, 13]
    assert sens_slope(values) == pytest.approx(2.0)


def test_percentile_rank_median_and_max() -> None:
    record = np.arange(1, 12)  # 1..11, median 6
    assert percentile_rank(6, record) == pytest.approx(0.5)
    assert percentile_rank(11, record) == pytest.approx(1.0)


def test_anomaly_is_value_minus_normal() -> None:
    assert anomaly(5.0, 3.0) == pytest.approx(2.0)


def test_rolling_normals_windows_and_bounds() -> None:
    normals = rolling_normals(np.arange(40.0), window=30)
    assert len(normals) == 11  # 40 - 30 + 1
    assert normals[0].mean == pytest.approx(14.5)   # mean(0..29)
    assert normals[-1].mean == pytest.approx(24.5)  # mean(10..39)
    with pytest.raises(FlowMetricsError):
        rolling_normals(np.arange(10.0), window=30)  # window > record


# --- #53 spatial decomposition -------------------------------------------

def test_subset_series_partitions_disjoint_and_complete() -> None:
    a = np.arange(60.0).reshape(5, 12)
    series = {2020: a}
    left = subset_series(series, [0, 1])
    right = subset_series(series, [2, 3, 4])
    assert left[2020].shape == (2, 12)
    assert right[2020].shape == (3, 12)
    np.testing.assert_array_equal(left[2020], a[[0, 1]])
    np.testing.assert_array_equal(np.vstack([left[2020], right[2020]]), a)


def test_outlet_index_picks_max_accumulated_within_membership() -> None:
    accum = np.array([10.0, 50, 30, 5, 40])
    assert outlet_index(accum, [0, 2, 3]) == 2  # max of (10,30,5) is 30 at idx 2
    assert outlet_index(accum, [0, 3, 4]) == 4  # max of (10,5,40) is 40 at idx 4


def test_longitudinal_profile_non_decreasing_downstream() -> None:
    accum = np.array([5.0, 12, 20])
    hydroseq = np.array([30.0, 20, 10])       # decreases downstream (NHDPlus)
    dnhydroseq = np.array([20.0, 10, 0])      # each reach's downstream HydroSeq
    prof = longitudinal_profile(accum, hydroseq, dnhydroseq, [30, 20, 10])
    np.testing.assert_array_equal(prof, [5, 12, 20])
    assert np.all(np.diff(prof) >= 0)


def test_longitudinal_profile_rejects_broken_chain() -> None:
    accum = np.array([5.0, 12, 20])
    hydroseq = np.array([30.0, 20, 10])
    dnhydroseq = np.array([20.0, 10, 0])
    with pytest.raises(FlowMetricsError):
        longitudinal_profile(accum, hydroseq, dnhydroseq, [30, 10])  # 30→20, not 10
