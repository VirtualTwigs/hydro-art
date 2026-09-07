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
    AnalogYear,
    DecadeFDC,
    MeltTimingTrend,
    RecordBook,
    SnowRegime,
    TimingTrend,
    YearRank,
    align_index,
    analog_years,
    decade_flow_duration,
    anomaly,
    bias,
    center_of_timing,
    center_of_timing_trend,
    classify_regime,
    correlate,
    rank_years,
    record_book,
    flashiness,
    flow_duration,
    longitudinal_profile,
    low_flow,
    mann_kendall,
    melt_timing_trend,
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
    snow_fraction,
    snow_regime,
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


def test_center_of_timing_vectorized_over_reaches() -> None:
    a = np.zeros((2, 12))
    a[0, 4] = 3.0          # reach 0: all flow in May (month 5)
    a[1, :] = 1.0          # reach 1: flat year → 6.5
    cot = center_of_timing(a)
    assert cot.shape == (2,)
    np.testing.assert_allclose(cot, [5.0, 6.5])


def test_flashiness_vectorized_over_reaches() -> None:
    a = np.vstack([np.full(12, 4.0), np.array([1.0, 0.0] * 6)])
    flash = flashiness(a)
    assert flash.shape == (2,)
    np.testing.assert_allclose(flash, [0.0, 11.0 / 6.0])


def test_seasonal_ratio_vectorized_over_reaches() -> None:
    wet = [10, 11, 0, 1, 2, 3]   # Nov,Dec,Jan,Feb,Mar,Apr
    dry = [4, 5, 6, 7, 8, 9]     # May..Oct
    a = np.zeros((2, 12))
    a[0, wet] = 8.0; a[0, dry] = 2.0   # ratio 4.0
    a[1, wet] = 6.0; a[1, dry] = 3.0   # ratio 2.0
    ratio = seasonal_ratio(a)
    assert ratio.shape == (2,)
    np.testing.assert_allclose(ratio, [4.0, 2.0])


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


def test_boolean_mask_membership_selects_flagged_reaches() -> None:
    a = np.arange(60.0).reshape(5, 12)
    mask = np.array([True, False, True, False, True])  # reaches 0, 2, 4
    sub = subset_series({2020: a}, mask)
    assert sub[2020].shape == (3, 12)
    np.testing.assert_array_equal(sub[2020], a[[0, 2, 4]])
    # outlet_index over the same boolean membership returns a *global* index
    accum = np.array([10.0, 50, 30, 5, 40])
    assert outlet_index(accum, np.array([True, False, True, True, False])) == 2


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


def test_pearson_r_constant_series_is_nan() -> None:
    # a zero-variance series has no correlation defined → nan (documented)
    assert np.isnan(pearson_r(np.array([3.0, 3.0, 3.0]), np.array([1.0, 2.0, 3.0])))


def test_nash_sutcliffe_zero_variance_obs_is_nan() -> None:
    # obs with no spread → the NSE denominator is 0 → nan, never a divide error
    assert np.isnan(nash_sutcliffe(np.array([1.0, 2.0, 3.0]), np.array([5.0, 5.0, 5.0])))


# --- boundary-error guards (fail fast, never silently) -------------------

def test_series_and_monthly_shape_guards() -> None:
    with pytest.raises(FlowMetricsError):
        peak_flow({2020: [[1.0, 2.0, 3.0], [4.0, 5.0]]})   # ragged inner rows
    with pytest.raises(FlowMetricsError):
        center_of_timing(np.ones(11))                      # not 12 months


def test_month_window_guards() -> None:
    y = np.ones((1, 12))
    with pytest.raises(FlowMetricsError):
        low_flow({2020: y}, months=(13,))                  # month out of range
    with pytest.raises(FlowMetricsError):
        low_flow({2020: y}, months=())                     # empty window
    with pytest.raises(FlowMetricsError):
        seasonal_ratio(np.ones(12), wet=tuple(range(1, 13)))  # leaves no dry months


def test_flow_duration_quantile_guards() -> None:
    with pytest.raises(FlowMetricsError):
        flow_duration(np.ones(12), [])                     # empty quantiles
    with pytest.raises(FlowMetricsError):
        flow_duration(np.ones(12), [150])                  # outside [0, 100]


def test_series_1d_length_guards() -> None:
    with pytest.raises(FlowMetricsError):
        mann_kendall(np.ones((2, 3)))                      # not 1-D
    with pytest.raises(FlowMetricsError):
        mann_kendall([1, 2])                               # < 3 points
    with pytest.raises(FlowMetricsError):
        sens_slope([5.0])                                  # < 2 points
    with pytest.raises(FlowMetricsError):
        percentile_rank(5.0, [3.0])                        # record < 2
    with pytest.raises(FlowMetricsError):
        rolling_normals(np.arange(5.0), window=0)          # window < 1


def test_membership_guards() -> None:
    series = {2020: np.ones((3, 12))}
    with pytest.raises(FlowMetricsError):
        subset_series(series, np.array([True, False]))     # bool mask wrong length
    with pytest.raises(FlowMetricsError):
        subset_series(series, [])                          # empty idx
    with pytest.raises(FlowMetricsError):
        subset_series(series, [5])                         # idx out of range


def test_longitudinal_profile_guards() -> None:
    with pytest.raises(FlowMetricsError):
        longitudinal_profile([1.0, 2.0, 3.0], [10.0, 20.0], [0.0, 10.0], [10])  # length mismatch
    with pytest.raises(FlowMetricsError):
        longitudinal_profile([1.0], [10.0], [0.0], [])     # empty path
    with pytest.raises(FlowMetricsError):
        longitudinal_profile([1.0], [10.0], [0.0], [99])   # unknown HydroSeq


def test_seasonal_skill_shape_guard() -> None:
    with pytest.raises(FlowValidationError):
        seasonal_skill(np.ones(12), np.ones(11))           # model/obs shape mismatch


# --- #69 snow-vs-rain regime -------------------------------------------------

def test_snow_fraction_scalar_and_vector() -> None:
    # Snow-heavy: most available water is melt. Rain-heavy: almost none.
    snow_rain = np.array([1.0] * 6 + [9.0] * 6)   # melt bucket, sum 60
    snow_melt = np.array([9.0] * 6 + [1.0] * 6)   # rain bucket, sum 60 -> frac 0.5
    assert snow_fraction(snow_melt, snow_rain) == pytest.approx(0.5)
    # Vectorized [n,12]: reach 0 all-melt (frac 1), reach 1 all-rain (frac 0).
    rain = np.array([[0.0] * 12, [5.0] * 12])
    melt = np.array([[5.0] * 12, [0.0] * 12])
    np.testing.assert_allclose(snow_fraction(rain, melt), [1.0, 0.0])


def test_snow_fraction_all_zero_is_zero() -> None:
    assert snow_fraction(np.zeros(12), np.zeros(12)) == 0.0


def test_classify_regime_boundaries_and_labels() -> None:
    assert classify_regime(0.5) == "snowmelt"
    assert classify_regime(0.4) == "snowmelt"      # >= snow_min
    assert classify_regime(0.3) == "transitional"
    assert classify_regime(0.2) == "rain"          # <= rain_max
    assert classify_regime(0.05) == "rain"
    labels = classify_regime(np.array([0.9, 0.3, 0.1]))
    assert list(labels) == ["snowmelt", "transitional", "rain"]


def test_classify_regime_bad_thresholds() -> None:
    with pytest.raises(FlowMetricsError):
        classify_regime(0.5, snow_min=0.2, rain_max=0.4)   # rain_max >= snow_min
    with pytest.raises(FlowMetricsError):
        classify_regime(0.5, rain_max=-0.1)                # out of [0,1]


def test_snow_regime_label_and_melt_center() -> None:
    # Spring-melt watershed: melt concentrated in Apr-Jun (months 4-6), rain small.
    rain = np.array([2.0] * 12)
    melt = np.zeros(12)
    melt[3:6] = 30.0   # Apr,May,Jun
    reg = snow_regime(rain, melt)
    assert isinstance(reg, SnowRegime)
    assert reg.label == "snowmelt"
    assert reg.snow_fraction == pytest.approx(90.0 / (90.0 + 24.0))
    # Center of timing of the melt pulse sits in May (month 5).
    assert reg.melt_center_month == pytest.approx(5.0)


def test_snow_regime_no_melt_center_is_nan() -> None:
    reg = snow_regime(np.array([5.0] * 12), np.zeros(12))
    assert reg.label == "rain"
    assert np.isnan(reg.melt_center_month)


def test_melt_timing_trend_detects_earlier_shift() -> None:
    # Build 6 decades where the melt pulse moves one month earlier each step:
    # center of timing drifts from ~June down to ~January.
    yearly = {}
    for k, year in enumerate(range(1960, 2020, 10)):
        melt = np.zeros(12)
        peak_month = 6 - k              # 6,5,4,3,2,1 (1-based)
        melt[peak_month - 1] = 100.0
        yearly[year] = melt
    trend = melt_timing_trend(yearly)
    assert isinstance(trend, MeltTimingTrend)
    assert trend.years == tuple(range(1960, 2020, 10))
    assert trend.slope_months_per_year < 0
    assert trend.days_per_decade < 0      # pulse arrives earlier
    assert trend.trend == "decreasing"
    assert trend.center_months[0] == pytest.approx(6.0)


def test_melt_timing_trend_accepts_matrix_and_needs_three_years() -> None:
    mat = np.zeros((3, 12))
    for i in range(3):
        mat[i, 4 - i] = 10.0
    trend = melt_timing_trend(mat)
    assert trend.years == (0, 1, 2)
    with pytest.raises(FlowMetricsError):
        melt_timing_trend(mat[:2])   # < 3 years


# --- #70 center-of-timing drift trend ----------------------------------------

def test_center_of_timing_trend_detects_earlier_peak() -> None:
    # 6 decades where the hydrograph peak moves one month earlier each step.
    yearly = {}
    for k, year in enumerate(range(1960, 2020, 10)):
        flow = np.full(12, 5.0)          # baseline flow all year
        peak_month = 7 - k               # 7,6,5,4,3,2 (1-based)
        flow[peak_month - 1] += 100.0    # dominant peak
        yearly[year] = flow
    trend = center_of_timing_trend(yearly)
    assert isinstance(trend, TimingTrend)
    assert trend.years == tuple(range(1960, 2020, 10))
    assert trend.slope_months_per_year < 0
    assert trend.days_per_decade < 0     # peak arrives earlier
    assert trend.trend == "decreasing"


def test_center_of_timing_trend_detects_later_peak() -> None:
    mat = np.full((6, 12), 2.0)
    for i in range(6):
        mat[i, 2 + i] += 50.0            # peak drifts Mar→Aug (later)
    trend = center_of_timing_trend(mat)
    assert trend.years == (0, 1, 2, 3, 4, 5)
    assert trend.slope_months_per_year > 0
    assert trend.days_per_decade > 0
    assert trend.trend == "increasing"


def test_center_of_timing_trend_matches_melt_on_same_input() -> None:
    # center_of_timing_trend is the general primitive; melt_timing_trend is the
    # same computation on the melt bucket. Same input → same numbers.
    mat = np.zeros((5, 12))
    for i in range(5):
        mat[i, 5 - i] = 10.0
    general = center_of_timing_trend(mat)
    melt = melt_timing_trend(mat)
    assert general.center_months == melt.center_months
    assert general.slope_months_per_year == melt.slope_months_per_year
    assert general.days_per_decade == melt.days_per_decade
    assert general.trend == melt.trend


def test_center_of_timing_trend_needs_three_years() -> None:
    with pytest.raises(FlowMetricsError):
        center_of_timing_trend(np.ones((2, 12)))


# --- #71 analog-year finder --------------------------------------------------

def _spring(scale: float = 1.0) -> np.ndarray:
    v = np.array([1, 1, 2, 6, 9, 7, 4, 2, 1, 1, 1, 1], dtype=float)
    return v * scale


def _winter() -> np.ndarray:
    return np.array([9, 8, 6, 3, 1, 1, 1, 1, 2, 4, 7, 9], dtype=float)


def test_analog_years_ranks_by_shape_not_magnitude() -> None:
    series = {
        2000: _spring(1.0),        # target
        1934: _spring(3.0),        # same shape, 3x magnitude → most similar (r≈1)
        1988: _spring(1.0) + np.array([0, 0, 0, 1, -1, 1, -1, 0, 0, 0, 0, 0.0]),  # near
        1977: _winter(),           # anti-phase → least similar
    }
    ranked = analog_years(series, 2000)
    assert [a.year for a in ranked] == [1934, 1988, 1977]
    assert isinstance(ranked[0], AnalogYear)
    assert ranked[0].similarity == pytest.approx(1.0)   # scale-invariant match
    assert ranked[-1].similarity < ranked[0].similarity


def test_analog_years_top_n_and_target_excluded() -> None:
    series = {y: _spring(1.0 + 0.1 * y) for y in range(5)}
    ranked = analog_years(series, 0, n=2)
    assert len(ranked) == 2
    assert all(a.year != 0 for a in ranked)


def test_analog_years_constant_year_sorts_last_as_nan() -> None:
    series = {
        2000: _spring(1.0),
        1950: _spring(2.0),
        1960: np.full(12, 5.0),   # constant → pearson nan
    }
    ranked = analog_years(series, 2000)
    assert ranked[0].year == 1950
    assert ranked[-1].year == 1960
    assert np.isnan(ranked[-1].similarity)


def test_analog_years_guards() -> None:
    with pytest.raises(FlowMetricsError):
        analog_years({2000: _spring()}, 1999)          # target not in series
    with pytest.raises(FlowMetricsError):
        analog_years({2000: np.ones((2, 12))}, 2000)   # not single [12] hydrographs
    with pytest.raises(FlowMetricsError):
        analog_years({2000: _spring(), 2001: _spring()}, 2000, n=0)  # n < 1


# --- #72 drought/flood record book -------------------------------------------

def test_rank_years_ascending_and_percentile() -> None:
    metric = {2000: 5.0, 2001: 1.0, 2002: 9.0, 2003: 3.0}
    driest = rank_years(metric, ascending=True)
    assert [r.year for r in driest] == [2001, 2003, 2000, 2002]
    assert driest[0].rank == 1 and driest[0].value == 1.0
    assert driest[0].percentile == pytest.approx(0.0)     # lowest in record
    assert isinstance(driest[0], YearRank)


def test_rank_years_descending_and_top_n() -> None:
    metric = {2000: 5.0, 2001: 1.0, 2002: 9.0, 2003: 3.0}
    wettest = rank_years(metric, ascending=False, n=2)
    assert [r.year for r in wettest] == [2002, 2000]
    assert wettest[0].rank == 1 and wettest[0].value == 9.0
    assert wettest[0].percentile == pytest.approx(1.0)    # highest in record


def test_rank_years_tie_break_by_year() -> None:
    metric = {2001: 4.0, 2000: 4.0, 2002: 1.0}
    ranked = rank_years(metric, ascending=True)
    # 2002 lowest; the 4.0 tie breaks to earlier year first.
    assert [r.year for r in ranked] == [2002, 2000, 2001]


def test_rank_years_needs_two_years() -> None:
    with pytest.raises(FlowMetricsError):
        rank_years({2000: 1.0})
    with pytest.raises(FlowMetricsError):
        rank_years({2000: 1.0, 2001: 2.0}, n=0)


def test_record_book_driest_summer_and_wettest_peak() -> None:
    base = np.array([8, 7, 5, 4, 3, 2, 2, 2, 3, 5, 7, 8], dtype=float)
    series = {
        1990: base,
        1991: base + np.array([0, 0, 0, 0, 0, -1.5, -1.5, -1.5, 0, 0, 0, 0.0]),  # driest summer
        1992: base + np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 40.0]),          # highest peak
    }
    book = record_book(series, n=2)
    assert isinstance(book, RecordBook)
    assert book.driest_summers[0].year == 1991
    assert book.wettest_years[0].year == 1992
    assert len(book.driest_summers) == 2 and len(book.wettest_years) == 2
    # summer-low uses Jun/Jul/Aug min; 1991 min is 0.5.
    assert book.driest_summers[0].value == pytest.approx(0.5)
    # peak is the annual max; 1992 Dec = 48.
    assert book.wettest_years[0].value == pytest.approx(48.0)


# --- #73 flow-duration-curve panel (decade overlays) -------------------------

def test_decade_flow_duration_groups_and_is_monotone() -> None:
    rng = np.arange(1.0, 13.0)
    series = {1990: rng, 1991: rng + 1, 1992: rng + 2, 2000: rng + 10, 2001: rng + 11}
    curves = decade_flow_duration(series, [0, 25, 50, 75, 100])
    assert [c.decade for c in curves] == [1990, 2000]
    assert isinstance(curves[0], DecadeFDC)
    assert curves[0].quantiles == (0.0, 25.0, 50.0, 75.0, 100.0)
    # Exceedance q=0 is the pooled max, q=100 the pooled min; curve non-increasing.
    flows = np.array(curves[0].flows)
    assert np.all(np.diff(flows) <= 1e-9)
    assert flows[0] == pytest.approx(14.0)   # 1992 = rng+2 → max 14
    assert flows[-1] == pytest.approx(1.0)   # 1990 = rng → min 1


def test_decade_flow_duration_shows_upward_shift() -> None:
    rng = np.arange(1.0, 13.0)
    series = {1990: rng, 1991: rng, 2000: rng + 10, 2001: rng + 10}
    early, late = decade_flow_duration(series, [50])
    assert late.decade == 2000
    assert late.flows[0] > early.flows[0]    # whole distribution shifted up


def test_decade_flow_duration_decade_size_and_guard() -> None:
    rng = np.arange(1.0, 13.0)
    series = {1990: rng, 2005: rng, 2011: rng}
    curves = decade_flow_duration(series, [50], decade_size=20)
    assert [c.decade for c in curves] == [1980, 2000]  # 20-yr bins: 1980-99, 2000-19
    with pytest.raises(FlowMetricsError):
        decade_flow_duration({1990: np.ones((2, 12))}, [50])  # not single [12]
