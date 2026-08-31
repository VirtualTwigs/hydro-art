"""Tests for the offline model-vs-observed validation layer (roadmap #50/#51).

Offline, numpy-only: hand-built model/obs arrays with known answers. Missing
values (``nan``) are skipped, never zero-filled (the ``src.accuracy`` discipline).
No network/GDAL; the real NWIS/ONI providers live in ``tools/``.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.flow_validation import (
    FlowValidationError,
    align_index,
    bias,
    correlate,
    nash_sutcliffe,
    pearson_r,
    rmse,
    seasonal_skill,
    validate,
)


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
