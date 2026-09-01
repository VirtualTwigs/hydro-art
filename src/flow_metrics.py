"""Hydrograph metrics, trend/spatial helpers, and model-vs-observed validation
(roadmap #48/#49/#53 + #50/#51).

Pure, numpy-only statistics over the ``{year: [n,12]}`` monthly-flow series that
:func:`src.historical_flow.yearly_flow_series` produces (n reaches × 12 months per
year), or over a single reach's ``[12]`` / ``[years,12]`` matrix. No mutation of
inputs; identical inputs → identical outputs. Imports only numpy, so the whole
surface runs in the offline suite — the heavy GDB reads live in ``tools/``.

This is the single combined analysis module for the watershed report: intrinsic
hydrograph shape + trend/distribution + spatial decomposition (#48/#49/#53), plus
model-vs-observed validation and climate-index teleconnection (#50/#51). The
validation half compares caller-supplied arrays; ``nan`` values are **skipped,
never zero-filled** (the ``src.accuracy`` discipline). The real USGS NWIS gauge and
ENSO/PDO index reads live in ``tools/`` behind provider seams — this module never
touches the network.

Nothing here enters ``PIPELINE_STAGES``; this is a parallel analysis layer feeding
the watershed report (Epoch 12).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

__all__ = [
    "FlowMetricsError",
    "MannKendall",
    "Normal",
    "peak_flow",
    "low_flow",
    "center_of_timing",
    "flashiness",
    "seasonal_ratio",
    "flow_duration",
    "mann_kendall",
    "sens_slope",
    "percentile_rank",
    "anomaly",
    "rolling_normals",
    "subset_series",
    "outlet_index",
    "longitudinal_profile",
    "FlowValidationError",
    "ValidationReport",
    "bias",
    "pearson_r",
    "nash_sutcliffe",
    "rmse",
    "seasonal_skill",
    "validate",
    "align_index",
    "correlate",
]

_MONTHS = np.arange(1, 13)


class FlowMetricsError(ValueError):
    """Raised for invalid metric inputs (empty series, ragged shape, bad window)."""


def _to_float_array(arr, name: str) -> np.ndarray:
    try:
        return np.asarray(arr, dtype=float)
    except (ValueError, TypeError) as exc:
        raise FlowMetricsError(f"{name} is ragged or non-numeric.") from exc


def _validate_series(series: Mapping[int, object]) -> dict[int, np.ndarray]:
    """Coerce + validate a ``{year: [n,12]}`` series (never mutates the input)."""
    if not series:
        raise FlowMetricsError("series is empty.")
    out: dict[int, np.ndarray] = {}
    for year, arr in series.items():
        a = _to_float_array(arr, f"series[{year}]")
        if a.ndim != 2 or a.shape[1] != 12:
            raise FlowMetricsError(
                f"series[{year}] must have shape [n,12], got {a.shape}."
            )
        out[int(year)] = a
    return out


def _validate_monthly(monthly, name: str = "monthly") -> np.ndarray:
    """Coerce + validate a ``[12]`` or ``[n,12]`` monthly array."""
    a = _to_float_array(monthly, name)
    if a.ndim not in (1, 2) or a.shape[-1] != 12:
        raise FlowMetricsError(f"{name} must have 12 months, got shape {a.shape}.")
    return a


def _month_columns(months: Sequence[int]) -> list[int]:
    cols = []
    for m in months:
        if not 1 <= int(m) <= 12:
            raise FlowMetricsError(f"month {m} out of range 1..12.")
        cols.append(int(m) - 1)
    if not cols:
        raise FlowMetricsError("months window is empty.")
    return cols


# --- #48 intrinsic hydrograph shape --------------------------------------

def peak_flow(series: Mapping[int, object]) -> dict[int, np.ndarray]:
    """Per-year, per-reach maximum flow across the 12 months."""
    return {year: a.max(axis=1) for year, a in _validate_series(series).items()}


def low_flow(
    series: Mapping[int, object], *, months: Sequence[int] = (6, 7, 8)
) -> dict[int, np.ndarray]:
    """Per-year, per-reach minimum flow within a month window (default summer)."""
    cols = _month_columns(months)
    return {year: a[:, cols].min(axis=1) for year, a in _validate_series(series).items()}


def center_of_timing(monthly) -> float | np.ndarray:
    """Flow-weighted mean month (1..12) — the timing of the hydrograph's mass.

    All flow in one month → that month; a flat year → 6.5.
    """
    a = _validate_monthly(monthly)
    if a.ndim == 1:
        return float((_MONTHS * a).sum() / a.sum())
    return (a * _MONTHS).sum(axis=1) / a.sum(axis=1)


def flashiness(monthly) -> float | np.ndarray:
    """Richards-Baker flashiness: Σ|Δmonthly| / Σmonthly (0 for a constant year)."""
    a = _validate_monthly(monthly)
    if a.ndim == 1:
        return float(np.abs(np.diff(a)).sum() / a.sum())
    return np.abs(np.diff(a, axis=1)).sum(axis=1) / a.sum(axis=1)


def seasonal_ratio(monthly, *, wet: Sequence[int] = (11, 12, 1, 2, 3, 4)) -> float | np.ndarray:
    """Ratio of wet-season mean flow to dry-season (the complement) mean flow."""
    a = _validate_monthly(monthly)
    wet_cols = _month_columns(wet)
    dry_cols = [m - 1 for m in range(1, 13) if m not in {int(x) for x in wet}]
    if not dry_cols:
        raise FlowMetricsError("wet window leaves no dry months.")
    if a.ndim == 1:
        return float(a[wet_cols].mean() / a[dry_cols].mean())
    return a[:, wet_cols].mean(axis=1) / a[:, dry_cols].mean(axis=1)


def flow_duration(monthly, quantiles: Sequence[float]) -> np.ndarray:
    """Flow-duration curve: flow value exceeded ``q``% of the time, per ``q``.

    Exceedance ``q`` maps to the ``(100-q)``-th value percentile, so the result is
    monotone non-increasing in ``q``; ``q=0`` is the max, ``q=100`` the min.
    """
    a = _validate_monthly(monthly).ravel()
    exc = _to_float_array(quantiles, "quantiles")
    if exc.size == 0:
        raise FlowMetricsError("quantiles is empty.")
    if np.any((exc < 0) | (exc > 100)):
        raise FlowMetricsError("exceedance quantiles must be within [0, 100].")
    return np.percentile(a, 100.0 - exc)


# --- #49 trend / distribution --------------------------------------------

@dataclass(frozen=True)
class MannKendall:
    """Mann-Kendall trend test result over an ordered series."""

    S: int
    tau: float
    p: float
    trend: str  # "increasing" | "decreasing" | "none"


@dataclass(frozen=True)
class Normal:
    """A rolling-window mean over ``values[start:end+1]`` (inclusive indices)."""

    start: int
    end: int
    mean: float


def _series_1d(values, name: str = "values") -> np.ndarray:
    a = _to_float_array(values, name)
    if a.ndim != 1 or a.size == 0:
        raise FlowMetricsError(f"{name} must be a non-empty 1-D sequence.")
    return a


def mann_kendall(values, *, alpha: float = 0.05) -> MannKendall:
    """Non-parametric monotonic-trend test (S, Kendall tau, two-sided p, verdict).

    ``trend`` is ``"increasing"``/``"decreasing"`` when ``p < alpha`` and ``S`` is
    positive/negative, else ``"none"``. Variance uses the no-tie formula with a
    continuity correction (adequate for the report's short annual series).
    """
    x = _series_1d(values)
    n = x.size
    if n < 3:
        raise FlowMetricsError("mann_kendall needs at least 3 points.")
    diff = x[np.newaxis, :] - x[:, np.newaxis]
    s = int(np.sign(diff[np.triu_indices(n, k=1)]).sum())
    denom = n * (n - 1) / 2.0
    tau = s / denom
    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = math.erfc(abs(z) / math.sqrt(2.0))
    if p < alpha and s > 0:
        trend = "increasing"
    elif p < alpha and s < 0:
        trend = "decreasing"
    else:
        trend = "none"
    return MannKendall(S=s, tau=float(tau), p=float(p), trend=trend)


def sens_slope(values) -> float:
    """Sen's slope: the median of all pairwise slopes over the series index.

    Robust to outliers (a single corrupted point barely moves the median).
    """
    x = _series_1d(values)
    n = x.size
    if n < 2:
        raise FlowMetricsError("sens_slope needs at least 2 points.")
    i, j = np.triu_indices(n, k=1)
    slopes = (x[j] - x[i]) / (j - i)
    return float(np.median(slopes))


def percentile_rank(value: float, record) -> float:
    """Position of ``value`` within ``record``, scaled so median→0.5, max→1.0.

    Uses ``count(record < value) / (n - 1)`` clamped to ``[0, 1]``.
    """
    r = _series_1d(record, "record")
    if r.size < 2:
        raise FlowMetricsError("percentile_rank needs a record of length >= 2.")
    frac = np.count_nonzero(r < value) / (r.size - 1)
    return float(min(1.0, max(0.0, frac)))


def anomaly(value: float, normal: float) -> float:
    """Departure of ``value`` from a reference ``normal`` (value - normal)."""
    return float(value) - float(normal)


def rolling_normals(values, *, window: int = 30) -> list[Normal]:
    """Sliding-window means over ``values`` (each a :class:`Normal`).

    Raises:
        FlowMetricsError: If ``window`` exceeds the record length or is < 1.
    """
    x = _series_1d(values)
    if window < 1:
        raise FlowMetricsError("window must be >= 1.")
    if window > x.size:
        raise FlowMetricsError(f"window {window} exceeds record length {x.size}.")
    out: list[Normal] = []
    for start in range(x.size - window + 1):
        end = start + window - 1
        out.append(Normal(start=start, end=end, mean=float(x[start : end + 1].mean())))
    return out


# --- #53 spatial decomposition -------------------------------------------

def _membership(idx, n: int) -> np.ndarray:
    """Coerce ``idx`` to an int index array and bounds-check it against ``n``."""
    a = np.asarray(idx)
    if a.dtype == bool:
        if a.shape != (n,):
            raise FlowMetricsError(f"boolean idx must have length {n}, got {a.shape}.")
        return np.flatnonzero(a)
    a = a.astype(int)
    if a.ndim != 1 or a.size == 0:
        raise FlowMetricsError("idx must be a non-empty 1-D index.")
    if a.min() < 0 or a.max() >= n:
        raise FlowMetricsError(f"idx out of range for {n} reaches.")
    return a


def subset_series(series: Mapping[int, object], idx) -> dict[int, np.ndarray]:
    """Restrict every year's ``[n,12]`` matrix to the reaches in ``idx``."""
    validated = _validate_series(series)
    n = next(iter(validated.values())).shape[0]
    members = _membership(idx, n)
    return {year: a[members] for year, a in validated.items()}


def outlet_index(mean_flow_per_reach, idx) -> int:
    """Global index of the max-accumulated-flow reach within membership ``idx``.

    The outlet of a sub-basin is its most-accumulated reach; this returns that
    reach's index into the *full* per-reach array (not the position within ``idx``).
    """
    accum = _series_1d(mean_flow_per_reach, "mean_flow_per_reach")
    members = _membership(idx, accum.size)
    return int(members[int(np.argmax(accum[members]))])


def longitudinal_profile(accum_flow, hydroseq, dnhydroseq, path) -> np.ndarray:
    """Accumulated flow sampled along an upstream→downstream ``path`` of HydroSeqs.

    ``path`` is a sequence of HydroSeq ids ordered upstream→downstream; consecutive
    entries must be topologically linked (each reach's ``DnHydroSeq`` equals the next
    reach's ``HydroSeq``). Accumulated flow grows downstream, so the returned profile
    is monotone non-decreasing.

    Raises:
        FlowMetricsError: On shape mismatch, an unknown HydroSeq, or a break in the
            downstream chain.
    """
    accum = _series_1d(accum_flow, "accum_flow")
    hs = _series_1d(hydroseq, "hydroseq")
    dhs = _series_1d(dnhydroseq, "dnhydroseq")
    if not (accum.shape == hs.shape == dhs.shape):
        raise FlowMetricsError("accum_flow/hydroseq/dnhydroseq must share length.")
    path = [float(h) for h in path]
    if not path:
        raise FlowMetricsError("path is empty.")

    index_of: dict[float, int] = {}
    for k, h in enumerate(hs):
        index_of[float(h)] = k
    for h in path:
        if h not in index_of:
            raise FlowMetricsError(f"path HydroSeq {h} not found in the network.")
    for up, down in zip(path[:-1], path[1:]):
        if dhs[index_of[up]] != down:
            raise FlowMetricsError(
                f"path is not a downstream chain: {up} → {down} not linked."
            )
    rows = [index_of[h] for h in path]
    return accum[rows]


# --- #50/#51 model-vs-observed validation + climate-index teleconnection ---
#
# Pure comparison and correlation metrics over caller-supplied arrays, plus a
# rolled-up :class:`ValidationReport` that picks an honest ``good/moderate/weak``
# framing from documented skill thresholds. Missing values (``nan``) are
# **skipped, never zero-filled** — the ``src.accuracy`` discipline. The real USGS
# NWIS gauge and ENSO/PDO index reads live in ``tools/`` behind provider seams;
# this module never touches the network.

# verdict thresholds (documented, so the report framing is honest)
GOOD_MIN_NSE = 0.75
GOOD_MIN_R = 0.9
MODERATE_MIN_NSE = 0.5
MODERATE_MIN_R = 0.7


class FlowValidationError(ValueError):
    """Raised on length mismatch or an empty (all-``nan``) overlap."""


@dataclass(frozen=True)
class ValidationReport:
    """Rolled-up model-vs-gauge skill with an honest framing verdict."""

    bias: float
    pearson_r: float
    nash_sutcliffe: float
    rmse: float
    seasonal_skill: np.ndarray
    verdict: str  # one of {"good", "moderate", "weak"}


def _paired(model, obs) -> tuple[np.ndarray, np.ndarray]:
    """Validate equal length and return the finite (non-``nan``) pairs only."""
    m = np.asarray(model, dtype=float)
    o = np.asarray(obs, dtype=float)
    if m.shape != o.shape:
        raise FlowValidationError(
            f"model/obs shape mismatch: {m.shape} vs {o.shape}"
        )
    mask = np.isfinite(m) & np.isfinite(o)
    if not mask.any():
        raise FlowValidationError("no overlapping non-nan model/obs pairs")
    return m[mask], o[mask]


def bias(model, obs) -> float:
    """Mean signed error ``mean(model - obs)`` over valid pairs."""
    m, o = _paired(model, obs)
    return float(np.mean(m - o))


def pearson_r(model, obs) -> float:
    """Pearson correlation over valid pairs (``nan`` if a series is constant)."""
    m, o = _paired(model, obs)
    if m.size < 2 or np.std(m) == 0 or np.std(o) == 0:
        return float("nan")
    return float(np.corrcoef(m, o)[0, 1])


def nash_sutcliffe(model, obs) -> float:
    """Nash-Sutcliffe efficiency; ``1.0`` is perfect, ``0`` == obs-mean, can be < 0."""
    m, o = _paired(model, obs)
    denom = float(np.sum((o - o.mean()) ** 2))
    if denom == 0:
        return float("nan")
    return float(1.0 - np.sum((o - m) ** 2) / denom)


def rmse(model, obs) -> float:
    """Root-mean-square error over valid pairs."""
    m, o = _paired(model, obs)
    return float(np.sqrt(np.mean((m - o) ** 2)))


def seasonal_skill(model_12, obs_12) -> np.ndarray:
    """Per-month symmetric agreement in ``[0, 1]`` (``nan`` where a month is missing).

    ``1 - |model - obs| / (|model| + |obs|)`` — 1.0 == identical, 0.0 == maximal
    disagreement. Element-wise: a missing (``nan``) month stays ``nan`` and never
    contaminates the others.
    """
    m = np.asarray(model_12, dtype=float)
    o = np.asarray(obs_12, dtype=float)
    if m.shape != o.shape:
        raise FlowValidationError(
            f"model/obs shape mismatch: {m.shape} vs {o.shape}"
        )
    denom = np.abs(m) + np.abs(o)
    with np.errstate(divide="ignore", invalid="ignore"):
        skill = 1.0 - np.abs(m - o) / denom
    skill[denom == 0] = np.nan
    return skill


def _verdict(r: float, nse: float) -> str:
    if np.isfinite(r) and np.isfinite(nse):
        if nse >= GOOD_MIN_NSE and r >= GOOD_MIN_R:
            return "good"
        if nse >= MODERATE_MIN_NSE and r >= MODERATE_MIN_R:
            return "moderate"
    return "weak"


def validate(model_12, obs_12) -> ValidationReport:
    """Roll the #50 metrics up into a report with a documented framing verdict."""
    r = pearson_r(model_12, obs_12)
    nse = nash_sutcliffe(model_12, obs_12)
    return ValidationReport(
        bias=bias(model_12, obs_12),
        pearson_r=r,
        nash_sutcliffe=nse,
        rmse=rmse(model_12, obs_12),
        seasonal_skill=seasonal_skill(model_12, obs_12),
        verdict=_verdict(r, nse),
    )


def align_index(
    metric_by_year: Mapping[int, float],
    index_by_year: Mapping[int, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Inner-join two ``{year: value}`` maps on the common years, sorted ascending."""
    years = sorted(set(metric_by_year) & set(index_by_year))
    if not years:
        raise FlowValidationError("no overlapping years between metric and index")
    metric = np.array([float(metric_by_year[y]) for y in years], dtype=float)
    index = np.array([float(index_by_year[y]) for y in years], dtype=float)
    return metric, index


def correlate(
    metric_by_year: Mapping[int, float],
    index_by_year: Mapping[int, float],
    *,
    lag: int = 0,
) -> float:
    """Pearson correlation of ``metric[y]`` against ``index[y - lag]``."""
    shifted = {y + lag: v for y, v in index_by_year.items()}
    metric, index = align_index(metric_by_year, shifted)
    return pearson_r(metric, index)
