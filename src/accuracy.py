"""Accuracy validation suite for DEM-backed elevation (Item 20, Epoch 5).

Quantifies how accurately the elevation subsystem samples known ground truth,
and rolls up the CRS/units/nodata-coverage/QA facts into an auditable report.
It compares terrain/river vertices sampled from a DEM fixture against expected
("truth") elevations and reports:

- **error metrics** — max/mean absolute error and RMSE over the points that had
  both a truth and a usable (covered, non-nodata) sample;
- **coverage** — how many samples were covered / nodata / uncovered;
- **CRS & units** — surfaced verbatim from the fixture's
  :class:`~src.elevation.ElevationProvenance`;
- **downstream QA** — a rollup of the river-profile inversion QA
  (:class:`src.hydro_z.ProfileQA`).

Design constraints:

- **Pure, deterministic, offline, numpy-free.** This module imports only stdlib
  plus :mod:`src.elevation` (itself numpy-free). DEM sampling is reached through
  the injected :class:`~src.elevation.ElevationSampler` seam (a duck-typed
  ``.sample(x, y) -> ElevationSample``), so the suite never imports ``raster``
  (numpy) or GDAL and the test suite stays GDAL-free.
- **Nodata is never invented.** A sample that is uncovered or nodata contributes
  no value and is *skipped* — never counted as zero error, never substituted
  with a synthetic height (elevation policy).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.elevation import ElevationError, ElevationProvenance, ElevationSample

__all__ = [
    "AccuracyError",
    "AccuracyReport",
    "CoverageReport",
    "CrsReport",
    "ErrorMetrics",
    "QARollup",
    "SamplerLike",
    "build_accuracy_report",
    "coverage_report",
    "crs_report",
    "error_metrics",
    "qa_rollup",
    "sample_points",
    "validate_against_sampler",
]


class AccuracyError(ElevationError):
    """Raised when accuracy-validation inputs are malformed.

    Subclasses :class:`~src.elevation.ElevationError` so it maps to the
    acquisition exit code, consistent with the elevation subsystem. The message
    is intended to be shown to the user.
    """


class SamplerLike(Protocol):
    """The :class:`~src.elevation.ElevationSampler` seam used for validation."""

    def sample(self, x: float, y: float) -> ElevationSample:
        ...


@dataclass(frozen=True)
class ErrorMetrics:
    """Vertical-error summary over the compared points.

    Attributes:
        n_compared: Points with both a truth and a covered, non-nodata sample.
        n_skipped: Points excluded (nodata / uncovered sample, or no truth).
        max_abs_error_m: Largest ``|sampled - expected|``; ``None`` if none.
        mean_abs_error_m: Mean absolute error; ``None`` if none.
        rmse_m: Root-mean-square error; ``None`` if none.
        residuals: ``sampled - expected`` for each compared point, in order.
    """

    n_compared: int
    n_skipped: int
    max_abs_error_m: float | None
    mean_abs_error_m: float | None
    rmse_m: float | None
    residuals: tuple[float, ...]


@dataclass(frozen=True)
class CoverageReport:
    """Nodata / coverage tally over a set of samples."""

    n_total: int
    n_covered: int
    n_nodata: int
    n_uncovered: int

    @property
    def coverage(self) -> float:
        """Fraction of samples that are covered and non-nodata (0.0 if empty)."""
        return self.n_covered / self.n_total if self.n_total else 0.0


@dataclass(frozen=True)
class CrsReport:
    """Source CRS / units / resolution, surfaced verbatim from provenance."""

    horizontal_crs: str
    vertical_crs: str | None
    vertical_units: str | None
    resolution_m: float | None


@dataclass(frozen=True)
class QARollup:
    """Aggregate of river-profile QA across one or more lines."""

    n_lines: int
    n_vertices: int
    n_nodata: int
    n_inversions: int
    max_inversion_m: float


@dataclass(frozen=True)
class AccuracyReport:
    """Bundled accuracy verdict: metrics + coverage + CRS + QA."""

    metrics: ErrorMetrics
    coverage: CoverageReport
    crs: CrsReport
    qa: QARollup
    tolerance_m: float

    @property
    def within_tolerance(self) -> bool:
        """True iff at least one point was compared and its worst error is within
        ``tolerance_m``. River-profile inversions are reported in :attr:`qa` but do
        not gate this vertical-accuracy verdict."""
        if self.metrics.n_compared == 0 or self.metrics.max_abs_error_m is None:
            return False
        return self.metrics.max_abs_error_m <= self.tolerance_m


def _sample_value(sample: ElevationSample) -> float | None:
    """Usable elevation for comparison, or ``None`` when nodata/uncovered."""
    if sample.covered and not sample.nodata:
        return sample.value_m
    return None


def error_metrics(
    expected: Sequence[float | None],
    sampled: Sequence[float | None],
) -> ErrorMetrics:
    """Compute vertical error metrics for aligned expected/sampled sequences.

    A point is *compared* only when both ``expected[i]`` and ``sampled[i]`` are
    non-``None``; otherwise it is *skipped*. Callers pass ``None`` for nodata or
    uncovered samples (see :func:`_sample_value`) and for missing truths.

    Raises:
        AccuracyError: If the two sequences differ in length.
    """
    if len(expected) != len(sampled):
        raise AccuracyError(
            "expected and sampled must be the same length "
            f"({len(expected)} != {len(sampled)})."
        )
    residuals: list[float] = []
    skipped = 0
    for exp, got in zip(expected, sampled):
        if exp is None or got is None:
            skipped += 1
            continue
        residuals.append(float(got) - float(exp))
    if not residuals:
        return ErrorMetrics(0, skipped, None, None, None, ())
    abs_err = [abs(r) for r in residuals]
    rmse = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    return ErrorMetrics(
        n_compared=len(residuals),
        n_skipped=skipped,
        max_abs_error_m=max(abs_err),
        mean_abs_error_m=sum(abs_err) / len(abs_err),
        rmse_m=rmse,
        residuals=tuple(residuals),
    )


def coverage_report(samples: Sequence[ElevationSample]) -> CoverageReport:
    """Tally covered / nodata / uncovered across ``samples``."""
    covered = nodata = uncovered = 0
    for s in samples:
        if not s.covered:
            uncovered += 1
        elif s.nodata:
            nodata += 1
        else:
            covered += 1
    return CoverageReport(len(samples), covered, nodata, uncovered)


def crs_report(provenance: ElevationProvenance) -> CrsReport:
    """Surface CRS / units / resolution from provenance, verbatim."""
    return CrsReport(
        horizontal_crs=provenance.horizontal_crs,
        vertical_crs=provenance.vertical_crs,
        vertical_units=provenance.vertical_units,
        resolution_m=provenance.resolution_m,
    )


def qa_rollup(profiles: Sequence[Any]) -> QARollup:
    """Aggregate river-profile QA results.

    ``profiles`` are structural: each must expose ``n_vertices``, ``n_nodata``,
    ``inversion_indices`` and ``max_inversion_m`` (e.g. :class:`src.hydro_z.ProfileQA`).
    Accepting them structurally keeps this module free of the numpy-backed
    ``hydro_z`` import chain.
    """
    n_vertices = n_nodata = n_inversions = 0
    max_inversion = 0.0
    for p in profiles:
        n_vertices += int(p.n_vertices)
        n_nodata += int(p.n_nodata)
        n_inversions += len(p.inversion_indices)
        max_inversion = max(max_inversion, float(p.max_inversion_m))
    return QARollup(
        n_lines=len(profiles),
        n_vertices=n_vertices,
        n_nodata=n_nodata,
        n_inversions=n_inversions,
        max_inversion_m=max_inversion,
    )


def sample_points(
    sampler: SamplerLike,
    points: Sequence[tuple[float, float]],
) -> tuple[ElevationSample, ...]:
    """Sample ``sampler`` at each ``(x, y)`` point through the elevation seam."""
    return tuple(sampler.sample(float(x), float(y)) for x, y in points)


def build_accuracy_report(
    *,
    samples: Sequence[ElevationSample],
    expected: Sequence[float | None],
    provenance: ElevationProvenance,
    tolerance_m: float,
    profiles: Sequence[Any] = (),
) -> AccuracyReport:
    """Assemble an :class:`AccuracyReport` from already-obtained samples.

    The compared/skipped split is derived from ``samples``: a sample contributes
    a value only when ``covered and not nodata``; otherwise it is skipped.

    Raises:
        AccuracyError: If ``samples`` and ``expected`` differ in length, or
            ``tolerance_m`` is negative.
    """
    if len(samples) != len(expected):
        raise AccuracyError(
            "samples and expected must be the same length "
            f"({len(samples)} != {len(expected)})."
        )
    if tolerance_m < 0:
        raise AccuracyError(f"tolerance_m must be >= 0, got {tolerance_m}.")
    sampled_values = [_sample_value(s) for s in samples]
    return AccuracyReport(
        metrics=error_metrics(expected, sampled_values),
        coverage=coverage_report(samples),
        crs=crs_report(provenance),
        qa=qa_rollup(profiles),
        tolerance_m=float(tolerance_m),
    )


def validate_against_sampler(
    *,
    sampler: SamplerLike,
    points: Sequence[tuple[float, float]],
    expected: Sequence[float | None],
    provenance: ElevationProvenance,
    tolerance_m: float,
    profiles: Sequence[Any] = (),
) -> AccuracyReport:
    """Sample a DEM at ``points`` and assemble the full accuracy report.

    Convenience over :func:`sample_points` + :func:`build_accuracy_report`.

    Raises:
        AccuracyError: If ``points`` and ``expected`` differ in length, or
            ``tolerance_m`` is negative.
    """
    if len(points) != len(expected):
        raise AccuracyError(
            "points and expected must be the same length "
            f"({len(points)} != {len(expected)})."
        )
    samples = sample_points(sampler, points)
    return build_accuracy_report(
        samples=samples,
        expected=expected,
        provenance=provenance,
        tolerance_m=tolerance_m,
        profiles=profiles,
    )
