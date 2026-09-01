"""Tests for the combined flow-metrics engine (roadmap #48/#49/#53 + #50/#51).

Offline, numpy-only: hand-built ``{year: [n,12]}`` series and ``[12]`` monthly
rows with known answers, plus model/obs arrays for the validation half. Missing
values (``nan``) are skipped, never zero-filled (the ``src.accuracy`` discipline).
No GDAL/network; the heavy GDB reads and NWIS/ONI providers live in tools/.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.flow_metrics import (
    FlowMetricsError,
    FlowValidationError,
    align_index,
    anomaly,
    bias,
    center_of_timing,
    correlate,
    flashiness,
    flow_duration,
    longitudinal_profile,
    low_flow,
    mann_kendall,
    nash_sutcliffe,
    outlet_index,
    peak_flow,
    pearson_r,
    percentile_rank,
    rmse,
    rolling_normals,
    seasonal_ratio,
    seasonal_skill,
    sens_slope,
    subset_series,
    validate,
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


# --- #50 model vs observed -----------------------------------------------

def test_identical_arrays_are_perfect() -> None:
    a = np.arange(1.0, 13.0)
    assert bias(a, a) == pytest.approx(0.0)
    assert pearson_r(a, a) == pytest.approx(1.0)
    assert nash_sutcliffe(a, a) == pytest.approx(1.0)
    assert rmse(a, a) == pytest.approx(0.0)


def test_constant_offset_is_exact_bias() -> None:
    obs = np.arange(1.0, 6.0)
    assert bias(obs + 3.0, obs) == pytest.approx(3.0)  # bias = mean(model - obs)


def test_anti_correlated_pair_is_minus_one() -> None:
    obs = np.arange(1.0, 6.0)
    assert pearson_r(obs[::-1], obs) == pytest.approx(-1.0)


def test_predicting_obs_mean_gives_zero_nse() -> None:
    obs = np.arange(1.0, 6.0)
    model = np.full(5, obs.mean())
    assert nash_sutcliffe(model, obs) == pytest.approx(0.0)


def test_seasonal_skill_length_12_and_nan_month_skipped() -> None:
    model = np.arange(1.0, 13.0)
    obs = model * 1.1
    obs[4] = np.nan  # May is missing in the observed record
    skill = seasonal_skill(model, obs)
    assert skill.shape == (12,)
    assert np.isnan(skill[4])  # nan month skipped, not zero-filled
    # every other month is unaffected by the missing May
    full = seasonal_skill(model, model * 1.1)
    keep = [i for i in range(12) if i != 4]
    np.testing.assert_allclose(skill[keep], full[keep])


def test_validate_verdict_crosses_thresholds() -> None:
    obs = np.arange(1.0, 6.0)
    assert validate(obs * 1.05, obs).verdict == "good"      # nse .986, r 1.0
    assert validate(obs * 1.30, obs).verdict == "moderate"  # nse .505, r 1.0
    assert validate(obs[::-1], obs).verdict == "weak"       # nse -3, r -1


def test_validate_report_carries_the_rolled_up_metrics() -> None:
    obs = np.arange(1.0, 6.0)
    rep = validate(obs + 3.0, obs)
    assert rep.bias == pytest.approx(3.0)
    assert rep.pearson_r == pytest.approx(1.0)
    assert rep.seasonal_skill.shape == (5,)


def test_errors_on_length_mismatch_and_all_nan_overlap() -> None:
    with pytest.raises(FlowValidationError):
        bias(np.arange(5.0), np.arange(4.0))
    with pytest.raises(FlowValidationError):
        pearson_r(np.array([np.nan, np.nan]), np.array([1.0, 2.0]))


# --- #51 climate-index teleconnection ------------------------------------

def test_align_index_keeps_common_years_in_order() -> None:
    metric = {y: float(y) for y in range(2014, 2024)}       # 2014..2023
    index = {y: -float(y) for y in range(2016, 2026)}       # 2016..2025
    m, i = align_index(metric, index)
    assert m.shape == i.shape == (8,)                        # 2016..2023
    np.testing.assert_allclose(m, np.arange(2016.0, 2024.0))
    np.testing.assert_allclose(i, -np.arange(2016.0, 2024.0))


def test_align_index_empty_overlap_raises() -> None:
    with pytest.raises(FlowValidationError):
        align_index({2000: 1.0}, {2010: 2.0})


def test_correlate_perfect_tracking_and_lag() -> None:
    metric = {y: float(y) for y in range(2010, 2016)}
    index = {y: 2.0 * y + 1.0 for y in range(2010, 2016)}
    assert correlate(metric, index) == pytest.approx(1.0)
    # lag=1 joins metric[year] with index[year-1]; still perfectly linear → 1.0
    assert correlate(metric, index, lag=1) == pytest.approx(1.0)


def test_correlate_lag_shifts_the_join() -> None:
    # metric tracks the index only after a one-year lag: metric[y] = index[y-1].
    index = {2010: 1.0, 2011: 5.0, 2012: 2.0, 2013: 9.0, 2014: 3.0}
    metric = {2011: 1.0, 2012: 5.0, 2013: 2.0, 2014: 9.0}
    assert correlate(metric, index, lag=1) == pytest.approx(1.0)
