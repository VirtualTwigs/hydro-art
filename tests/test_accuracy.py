"""Tests for the accuracy validation suite (Item 20, Epoch 5).

Offline and deterministic. Reuses the synthetic tilted-plane DEM (value ==
x_center + y_center) from the terrain tests so every expected truth is
hand-computable and exact under bilinear sampling. The module under test is
pure and numpy-free; numpy appears here only to build the fixture DEM.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from dataclasses import dataclass

from src.accuracy import (
    AccuracyError,
    AccuracyReport,
    CoverageReport,
    CrsReport,
    ErrorMetrics,
    QARollup,
    build_accuracy_report,
    coverage_report,
    crs_report,
    error_metrics,
    qa_rollup,
    sample_points,
    validate_against_sampler,
)
from src.elevation import ElevationSample, build_provenance
from src.raster import GridSampler, GridTransform, RasterGrid


def _plane_grid(nodata=None):
    # value == x_center + y_center over x[0,4], y[0,4], 1 m pixels.
    values = np.array(
        [[4, 5, 6, 7], [3, 4, 5, 6], [2, 3, 4, 5], [1, 2, 3, 4]], dtype=float
    )
    return RasterGrid(values, GridTransform(0.0, 4.0, 1.0, 1.0), "EPSG:5070", nodata)


def _prov(**over):
    base = dict(
        source_product="USGS 3DEP 1/3 arc-second DEM",
        source_url="https://example.test/dem.tif",
        acquisition_date="2026-07-29",
        horizontal_crs="EPSG:5070",
        vertical_crs="NAVD88",
        vertical_units="meters",
        resolution_m=10.0,
        checksum="sha256:abc",
        processing_parameters={},
    )
    base.update(over)
    return build_provenance(**base)


# ---- error_metrics -----------------------------------------------------------

def test_error_metrics_exact_is_zero() -> None:
    m = error_metrics([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert m.n_compared == 3 and m.n_skipped == 0
    assert m.max_abs_error_m == 0.0
    assert m.mean_abs_error_m == 0.0
    assert m.rmse_m == 0.0
    assert m.residuals == (0.0, 0.0, 0.0)


def test_error_metrics_known_offset() -> None:
    m = error_metrics([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])  # sampled - expected = 1,2,3
    assert m.residuals == (1.0, 2.0, 3.0)
    assert m.max_abs_error_m == 3.0
    assert m.mean_abs_error_m == 2.0
    assert math.isclose(m.rmse_m, math.sqrt(14.0 / 3.0), rel_tol=1e-12)


def test_error_metrics_skips_none_on_either_side() -> None:
    # idx0 compared; idx1 expected None -> skip; idx2 sampled None -> skip.
    m = error_metrics([1.0, None, 3.0], [1.0, 2.0, None])
    assert m.n_compared == 1 and m.n_skipped == 2
    assert m.residuals == (0.0,)


def test_error_metrics_all_skipped_returns_none_metrics() -> None:
    m = error_metrics([None, None], [None, 1.0])
    assert m.n_compared == 0 and m.n_skipped == 2
    assert m.max_abs_error_m is None
    assert m.mean_abs_error_m is None
    assert m.rmse_m is None
    assert m.residuals == ()


def test_error_metrics_length_mismatch_raises() -> None:
    with pytest.raises(AccuracyError):
        error_metrics([1.0, 2.0], [1.0, 2.0, 3.0])


# ---- coverage_report ---------------------------------------------------------

def test_coverage_report_counts_and_fraction() -> None:
    samples = [
        ElevationSample(5.0, True, False),   # covered
        ElevationSample(7.0, True, False),   # covered
        ElevationSample(None, True, True),   # nodata
        ElevationSample(None, False, False), # uncovered
    ]
    c = coverage_report(samples)
    assert isinstance(c, CoverageReport)
    assert c.n_total == 4
    assert c.n_covered == 2
    assert c.n_nodata == 1
    assert c.n_uncovered == 1
    assert c.coverage == 0.5


def test_coverage_report_empty_is_zero() -> None:
    c = coverage_report([])
    assert c.n_total == 0 and c.coverage == 0.0


# ---- crs_report --------------------------------------------------------------

def test_crs_report_passes_provenance_verbatim() -> None:
    r = crs_report(_prov())
    assert isinstance(r, CrsReport)
    assert r.horizontal_crs == "EPSG:5070"
    assert r.vertical_crs == "NAVD88"
    assert r.vertical_units == "meters"
    assert r.resolution_m == 10.0


def test_crs_report_preserves_missing_vertical_fields() -> None:
    r = crs_report(_prov(vertical_crs=None, vertical_units=None))
    assert r.vertical_crs is None
    assert r.vertical_units is None


# ---- qa_rollup ---------------------------------------------------------------

@dataclass(frozen=True)
class _FakeQA:
    # Structural stand-in for src.hydro_z.ProfileQA (keeps this test numpy-light
    # and proves qa_rollup accepts anything with the four fields).
    n_vertices: int
    n_nodata: int
    inversion_indices: tuple[int, ...]
    max_inversion_m: float


def test_qa_rollup_aggregates_counts_and_max() -> None:
    roll = qa_rollup([
        _FakeQA(10, 1, (3,), 0.5),
        _FakeQA(20, 0, (), 0.0),
        _FakeQA(5, 2, (1, 4), 1.25),
    ])
    assert roll.n_lines == 3
    assert roll.n_vertices == 35
    assert roll.n_nodata == 3
    assert roll.n_inversions == 3
    assert roll.max_inversion_m == 1.25


def test_qa_rollup_empty() -> None:
    roll = qa_rollup([])
    assert roll == QARollup(0, 0, 0, 0, 0.0)


# ---- sample_points -----------------------------------------------------------

def test_sample_points_over_grid_sampler() -> None:
    sampler = GridSampler(_plane_grid())
    samples = sample_points(sampler, [(1.0, 1.0), (2.0, 2.0)])
    assert [round(s.value_m, 6) for s in samples] == [2.0, 4.0]
    assert all(s.covered and not s.nodata for s in samples)


# ---- build_accuracy_report ---------------------------------------------------

def test_build_report_compared_skipped_split() -> None:
    samples = [
        ElevationSample(2.0, True, False),    # compared
        ElevationSample(None, True, True),    # nodata -> skipped
        ElevationSample(None, False, False),  # uncovered -> skipped
    ]
    rep = build_accuracy_report(
        samples=samples, expected=[2.0, 5.0, 9.0], provenance=_prov(), tolerance_m=0.0
    )
    assert isinstance(rep, AccuracyReport)
    assert rep.metrics.n_compared == 1 and rep.metrics.n_skipped == 2
    assert rep.coverage.n_covered == 1 and rep.coverage.n_nodata == 1
    assert rep.coverage.n_uncovered == 1
    assert rep.within_tolerance is True


def test_build_report_length_mismatch_and_negative_tolerance() -> None:
    with pytest.raises(AccuracyError):
        build_accuracy_report(
            samples=[ElevationSample(1.0, True, False)],
            expected=[1.0, 2.0], provenance=_prov(), tolerance_m=0.0
        )
    with pytest.raises(AccuracyError):
        build_accuracy_report(
            samples=[ElevationSample(1.0, True, False)],
            expected=[1.0], provenance=_prov(), tolerance_m=-0.5
        )


# ---- validate_against_sampler (end-to-end) -----------------------------------

def test_validate_exact_truth_within_tolerance() -> None:
    sampler = GridSampler(_plane_grid())
    points = [(1.0, 1.0), (2.0, 2.0), (1.5, 2.5)]
    expected = [2.0, 4.0, 4.0]  # value == x + y
    rep = validate_against_sampler(
        sampler=sampler, points=points, expected=expected,
        provenance=_prov(), tolerance_m=0.0
    )
    assert rep.metrics.n_compared == 3
    assert rep.metrics.max_abs_error_m == 0.0
    assert rep.coverage.n_uncovered == 0
    assert rep.within_tolerance is True
    assert rep.crs.horizontal_crs == "EPSG:5070"


def test_validate_off_by_more_than_tolerance_fails() -> None:
    sampler = GridSampler(_plane_grid())
    points = [(1.0, 1.0), (2.0, 2.0)]
    expected = [2.0, 5.0]  # second is off by 1.0
    rep0 = validate_against_sampler(
        sampler=sampler, points=points, expected=expected,
        provenance=_prov(), tolerance_m=0.0
    )
    assert rep0.metrics.max_abs_error_m == 1.0
    assert rep0.within_tolerance is False
    rep1 = validate_against_sampler(
        sampler=sampler, points=points, expected=expected,
        provenance=_prov(), tolerance_m=1.0
    )
    assert rep1.within_tolerance is True


def test_validate_out_of_extent_point_is_skipped_and_uncovered() -> None:
    sampler = GridSampler(_plane_grid())
    points = [(1.0, 1.0), (100.0, 100.0)]
    rep = validate_against_sampler(
        sampler=sampler, points=points, expected=[2.0, 999.0],
        provenance=_prov(), tolerance_m=0.0
    )
    assert rep.coverage.n_uncovered == 1
    assert rep.metrics.n_compared == 1 and rep.metrics.n_skipped == 1
    assert rep.within_tolerance is True


def test_within_tolerance_false_when_all_skipped() -> None:
    sampler = GridSampler(_plane_grid())
    points = [(100.0, 100.0), (200.0, 200.0)]
    rep = validate_against_sampler(
        sampler=sampler, points=points, expected=[1.0, 2.0],
        provenance=_prov(), tolerance_m=100.0
    )
    assert rep.metrics.n_compared == 0
    assert rep.within_tolerance is False


def test_validate_is_deterministic() -> None:
    sampler = GridSampler(_plane_grid())
    args = dict(
        sampler=sampler, points=[(1.0, 1.0), (2.5, 1.5)], expected=[2.0, 4.0],
        provenance=_prov(), tolerance_m=0.0,
    )
    assert validate_against_sampler(**args) == validate_against_sampler(**args)
