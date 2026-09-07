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
    "REGIME_SNOW_MIN",
    "REGIME_RAIN_MAX",
    "SnowRegime",
    "TimingTrend",
    "MeltTimingTrend",
    "AnalogYear",
    "YearRank",
    "RecordBook",
    "DecadeFDC",
    "snow_fraction",
    "classify_regime",
    "snow_regime",
    "melt_timing_trend",
    "center_of_timing_trend",
    "analog_years",
    "rank_years",
    "record_book",
    "decade_flow_duration",
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


# --- #69 snow-vs-rain regime signature -----------------------------------
#
# The disaggregation model (``src.monthly_flow.snow_available_components``) splits
# each reach's monthly available water into a rain bucket and a snowmelt bucket.
# These helpers turn that split into a report story: what share of a watershed's
# water is snowmelt, whether it reads as snowmelt-/rain-dominated, and whether the
# melt pulse is arriving earlier across the decades ("your river is becoming a rain
# river"). Numpy-only; callers pass the rain/melt arrays, so this module never
# imports ``monthly_flow``.

REGIME_SNOW_MIN = 0.4   # snowmelt share >= this → snowmelt-dominated
REGIME_RAIN_MAX = 0.2   # snowmelt share <= this → rain-dominated
_DAYS_PER_MONTH = 30.4368   # mean Gregorian month, for months→days conversion


@dataclass(frozen=True)
class SnowRegime:
    """A watershed's snow-vs-rain verdict for one aggregated year."""

    snow_fraction: float
    label: str
    melt_center_month: float


@dataclass(frozen=True)
class TimingTrend:
    """Decadal drift of a hydrograph's center of timing (roadmap #70).

    ``slope_months_per_year`` is Sen's slope on the per-year center-of-timing;
    ``days_per_decade`` restates it in days (negative = the peak arriving earlier);
    ``trend`` is the Mann-Kendall verdict.
    """

    years: tuple[int, ...]
    center_months: tuple[float, ...]
    slope_months_per_year: float
    days_per_decade: float
    trend: str


@dataclass(frozen=True)
class MeltTimingTrend:
    """Decadal drift of the melt-pulse center of timing (roadmap #69)."""

    years: tuple[int, ...]
    center_months: tuple[float, ...]
    slope_months_per_year: float
    days_per_decade: float
    trend: str


def snow_fraction(rain, melt) -> float | np.ndarray:
    """Annual snowmelt share of available water: ``Σmelt / Σ(rain + melt)``.

    ``[12]`` inputs → float; ``[n,12]`` → ``[n]``. An all-zero year → ``0.0`` (no
    division warning). Inputs must share shape.
    """
    r = _validate_monthly(rain, "rain")
    m = _validate_monthly(melt, "melt")
    if r.shape != m.shape:
        raise FlowMetricsError(f"rain {r.shape} and melt {m.shape} must share shape.")
    axis = r.ndim - 1
    melt_sum = m.sum(axis=axis)
    total = r.sum(axis=axis) + melt_sum
    frac = np.divide(melt_sum, total, out=np.zeros_like(melt_sum), where=total > 0)
    return float(frac) if r.ndim == 1 else frac


def classify_regime(
    fraction, *, snow_min: float = REGIME_SNOW_MIN, rain_max: float = REGIME_RAIN_MAX
) -> str | np.ndarray:
    """Label a snowmelt ``fraction`` snowmelt / transitional / rain.

    ``fraction >= snow_min`` → ``"snowmelt"``; ``<= rain_max`` → ``"rain"``; else
    ``"transitional"``. Scalar → ``str``; array → object ``ndarray`` of labels.
    """
    if not (0.0 <= rain_max < snow_min <= 1.0):
        raise FlowMetricsError(
            f"require 0 <= rain_max ({rain_max}) < snow_min ({snow_min}) <= 1."
        )
    f = np.asarray(fraction, dtype=float)
    labels = np.where(
        f >= snow_min, "snowmelt", np.where(f <= rain_max, "rain", "transitional")
    )
    return str(labels) if f.ndim == 0 else labels.astype(object)


def snow_regime(
    rain, melt, *, snow_min: float = REGIME_SNOW_MIN, rain_max: float = REGIME_RAIN_MAX
) -> SnowRegime:
    """Snow-vs-rain verdict for one aggregated watershed (``[12]`` rain & melt).

    Combines :func:`snow_fraction`, :func:`classify_regime`, and the flow-weighted
    center month of the **melt** pulse (via :func:`center_of_timing`). An all-zero
    melt pulse → ``melt_center_month = nan``.
    """
    r = _validate_monthly(rain, "rain")
    m = _validate_monthly(melt, "melt")
    if r.ndim != 1 or m.ndim != 1:
        raise FlowMetricsError("snow_regime takes single [12] rain and melt vectors.")
    frac = snow_fraction(r, m)
    label = classify_regime(frac, snow_min=snow_min, rain_max=rain_max)
    center = float(center_of_timing(m)) if m.sum() > 0 else float("nan")
    return SnowRegime(snow_fraction=float(frac), label=str(label), melt_center_month=center)


def melt_timing_trend(yearly_melt, years=None) -> MeltTimingTrend:
    """Decadal drift of the melt-pulse center of timing.

    ``yearly_melt`` is a ``{year: [12]}`` mapping (sorted by year) or a ``[years,12]``
    matrix of the melt pulse per calendar year. Computes each year's melt
    center-of-timing, then Sen's slope (months/year) and the Mann-Kendall verdict
    over those centers. ``days_per_decade`` = slope × 10 × mean-days-per-month;
    negative means the pulse is arriving earlier. Needs ≥ 3 years.
    """
    trend = center_of_timing_trend(yearly_melt, years)
    return MeltTimingTrend(**vars(trend))


def _coerce_year_rows(yearly, years, name: str):
    """Coerce a ``{year:[12]}`` mapping or ``[years,12]`` matrix to ``(years, rows)``."""
    if isinstance(yearly, Mapping):
        if years is not None:
            raise FlowMetricsError("pass years only with a matrix, not a mapping.")
        ordered = sorted(int(y) for y in yearly)
        rows = np.vstack([_validate_monthly(yearly[y], f"{name}[{y}]") for y in ordered])
        return tuple(ordered), rows
    rows = _validate_monthly(yearly, name)
    if rows.ndim != 2:
        raise FlowMetricsError(f"matrix {name} must have shape [years,12].")
    year_tuple = tuple(int(y) for y in years) if years is not None else tuple(range(len(rows)))
    if len(year_tuple) != len(rows):
        raise FlowMetricsError("years length must match the number of rows.")
    return year_tuple, rows


def center_of_timing_trend(yearly_flow, years=None) -> TimingTrend:
    """Decadal drift of the whole-hydrograph center of timing (roadmap #70).

    ``yearly_flow`` is a ``{year:[12]}`` mapping (sorted by year) or a ``[years,12]``
    matrix of one aggregated hydrograph per calendar year. Computes each year's
    center-of-timing, then Sen's slope (months/year) and the Mann-Kendall verdict
    over those centers. ``days_per_decade`` = slope × 10 × mean-days-per-month;
    negative means the peak is arriving earlier ("the peak arrives N days earlier
    per decade"). Needs ≥ 3 years.
    """
    year_tuple, rows = _coerce_year_rows(yearly_flow, years, "yearly_flow")
    if len(rows) < 3:
        raise FlowMetricsError("center_of_timing_trend needs at least 3 years.")
    centers = center_of_timing(rows)
    slope = sens_slope(centers)
    verdict = mann_kendall(centers)
    return TimingTrend(
        years=year_tuple,
        center_months=tuple(float(c) for c in centers),
        slope_months_per_year=float(slope),
        days_per_decade=float(slope * 10.0 * _DAYS_PER_MONTH),
        trend=verdict.trend,
    )


# --- #71 analog-year finder ----------------------------------------------
#
# Rank the historical years whose monthly hydrograph most resembles a target
# year's ("2015 looked most like 1934"). Similarity is the Pearson correlation of
# the two 12-month vectors, which removes mean and scale — so a wet year and a dry
# year with the same *seasonal shape* still read as analogs. Reuses ``pearson_r``.


@dataclass(frozen=True)
class AnalogYear:
    """A historical year and its monthly-shape similarity to a target year."""

    year: int
    similarity: float


def _shape_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two 12-month vectors; ``nan`` when undefined."""
    try:
        return pearson_r(a, b)
    except FlowValidationError:
        return float("nan")


def analog_years(series: Mapping[int, object], target: int, *, n: int | None = None) -> list[AnalogYear]:
    """Rank the years in ``series`` by monthly-shape similarity to ``target``.

    ``series`` is a ``{year: [12]}`` mapping of one aggregated hydrograph per year.
    Returns :class:`AnalogYear` records for every year except ``target``, sorted by
    descending Pearson correlation of the 12-month vectors (a constant year yields
    ``nan`` and sorts last); ties break by ascending year for determinism. ``n``
    keeps only the top matches.
    """
    validated: dict[int, np.ndarray] = {}
    for year, vec in series.items():
        a = _validate_monthly(vec, f"series[{year}]")
        if a.ndim != 1:
            raise FlowMetricsError("analog_years takes a {year:[12]} series of single hydrographs.")
        validated[int(year)] = a
    if int(target) not in validated:
        raise FlowMetricsError(f"target year {target} not in series.")
    if n is not None and n < 1:
        raise FlowMetricsError("n must be >= 1.")
    tv = validated[int(target)]
    ranked = [
        AnalogYear(year=y, similarity=_shape_similarity(tv, v))
        for y, v in validated.items()
        if y != int(target)
    ]
    ranked.sort(
        key=lambda a: (
            np.isnan(a.similarity),
            -a.similarity if not np.isnan(a.similarity) else 0.0,
            a.year,
        )
    )
    return ranked[:n] if n is not None else ranked


# --- #72 drought/flood record book ---------------------------------------
#
# Rank years by a scalar metric (summer-low for drought, annual peak for flood)
# and stamp each with its position in the full record ("driest summer in 130
# years," "top-5 wettest"). Reuses ``percentile_rank`` for the position.


@dataclass(frozen=True)
class YearRank:
    """A year, its metric value, 1-based rank, and percentile in the full record."""

    year: int
    value: float
    rank: int
    percentile: float


@dataclass(frozen=True)
class RecordBook:
    """Drought (driest summer-low) and flood (highest peak) leaderboards."""

    driest_summers: list[YearRank]
    wettest_years: list[YearRank]


def rank_years(
    metric_by_year: Mapping[int, float], *, ascending: bool = True, n: int | None = None
) -> list[YearRank]:
    """Rank years by a scalar ``{year: value}`` metric.

    ``ascending`` puts the smallest value at rank 1 (drought leaderboard); set it
    ``False`` for the largest first (flood leaderboard). Each :class:`YearRank`
    carries its :func:`percentile_rank` position in the full record (independent of
    sort direction). Ties break by ascending year for determinism; ``n`` keeps only
    the top entries. Needs ≥ 2 years (``percentile_rank`` requires it).
    """
    if len(metric_by_year) < 2:
        raise FlowMetricsError("rank_years needs at least 2 years.")
    if n is not None and n < 1:
        raise FlowMetricsError("n must be >= 1.")
    values = {int(y): float(v) for y, v in metric_by_year.items()}
    record = np.array(list(values.values()), dtype=float)
    order = sorted(values, key=lambda y: (values[y] if ascending else -values[y], y))
    ranked = [
        YearRank(
            year=y,
            value=values[y],
            rank=i + 1,
            percentile=percentile_rank(values[y], record),
        )
        for i, y in enumerate(order)
    ]
    return ranked[:n] if n is not None else ranked


def record_book(
    series: Mapping[int, object], *, summer_months: Sequence[int] = (6, 7, 8), n: int | None = 5
) -> RecordBook:
    """Drought/flood leaderboards from a ``{year: [12]}`` hydrograph series.

    Reduces each year to a summer-low (min over ``summer_months``) and an annual
    peak (max over 12 months), then ranks the driest summers (ascending low) and the
    wettest years (descending peak) via :func:`rank_years`. ``n`` bounds each list.
    """
    cols = _month_columns(summer_months)
    summer_low: dict[int, float] = {}
    annual_peak: dict[int, float] = {}
    for year, vec in series.items():
        a = _validate_monthly(vec, f"series[{year}]")
        if a.ndim != 1:
            raise FlowMetricsError("record_book takes a {year:[12]} series of single hydrographs.")
        summer_low[int(year)] = float(a[cols].min())
        annual_peak[int(year)] = float(a.max())
    return RecordBook(
        driest_summers=rank_years(summer_low, ascending=True, n=n),
        wettest_years=rank_years(annual_peak, ascending=False, n=n),
    )


# --- #73 flow-duration-curve panel (decade overlays) ---------------------
#
# Group a multi-year series into decades and compute a flow-duration curve for
# each, so the report can overlay them and show how the whole flow *distribution*
# shifts across decades — not just the mean. Reuses ``flow_duration``.


@dataclass(frozen=True)
class DecadeFDC:
    """One decade's flow-duration curve over its pooled monthly flows."""

    decade: int
    quantiles: tuple[float, ...]
    flows: tuple[float, ...]


def decade_flow_duration(
    series: Mapping[int, object], quantiles: Sequence[float], *, decade_size: int = 10
) -> list[DecadeFDC]:
    """Per-decade flow-duration curves from a ``{year: [12]}`` hydrograph series.

    Buckets each year into its decade (``year // decade_size * decade_size``), pools
    all monthly flows in the decade, and computes the exceedance ``quantiles`` via
    :func:`flow_duration`. Returns one :class:`DecadeFDC` per decade, sorted
    ascending, so overlaying them shows the distribution shifting over time.
    """
    if decade_size < 1:
        raise FlowMetricsError("decade_size must be >= 1.")
    buckets: dict[int, list[np.ndarray]] = {}
    for year, vec in series.items():
        a = _validate_monthly(vec, f"series[{year}]")
        if a.ndim != 1:
            raise FlowMetricsError("decade_flow_duration takes a {year:[12]} series.")
        decade = (int(year) // decade_size) * decade_size
        buckets.setdefault(decade, []).append(a)
    q = tuple(float(x) for x in quantiles)
    out: list[DecadeFDC] = []
    for decade in sorted(buckets):
        flows = flow_duration(np.vstack(buckets[decade]), quantiles)
        out.append(DecadeFDC(decade=decade, quantiles=q, flows=tuple(float(f) for f in flows)))
    return out


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
