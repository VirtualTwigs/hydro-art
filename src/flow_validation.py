"""Offline model-vs-observed validation + climate-index teleconnection (#50/#51).

Pure comparison and correlation metrics over caller-supplied arrays, plus a
rolled-up :class:`ValidationReport` that picks an honest ``good/moderate/weak``
framing from documented skill thresholds. Missing values (``nan``) are **skipped,
never zero-filled** — the ``src.accuracy`` discipline.

numpy-only and fully offline: the real USGS NWIS gauge and ENSO/PDO index reads
live in ``tools/`` behind provider seams; this module never touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

__all__ = [
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

# --- verdict thresholds (documented, so the report framing is honest) ------
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


# --- #50 model vs observed -----------------------------------------------

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


# --- #51 climate-index teleconnection ------------------------------------

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
