"""Unit tests for the monthly-flow disaggregation core (Item #25, Task Group 1).

Pure numpy disaggregation promoted from ``tools/monthly_flow.py``: the
temperature-index snow bucket, per-reach shape normalization, downstream
HydroSeq accumulation, and the orchestrator that conserves each reach's annual
mean. Hand-built arrays only -- no pyogrio, no GDAL, no real datasets.
"""

import numpy as np

from src.monthly_flow import (
    MONTH_ABBR,
    MONTHS,
    accumulate_downstream,
    disaggregate_monthly,
    normalize_shape,
    snow_available_water,
)


def test_constants():
    assert list(MONTHS) == list(range(1, 13))
    assert MONTH_ABBR[0] == "Jan"
    assert MONTH_ABBR[-1] == "Dec"
    assert len(MONTH_ABBR) == 12


def test_snow_bucket_accumulates_cold_and_releases_warm():
    # One reach: cold Jan-Mar (snow piles up, no melt), warm Apr-Jun (melt),
    # mild rest. Precip constant so the difference is purely snow physics.
    precip = np.full((1, 12), 50.0)
    temp = np.array([[-5, -5, -5, 8, 8, 8, 10, 10, 10, 10, 10, 10]], dtype=float)
    avail = snow_available_water(precip, temp)
    # Cold months: all precip is snow, none melts -> ~0 available water.
    assert avail[0, 0] < 1.0
    assert avail[0, 1] < 1.0
    # First warm month releases the accumulated pack -> a melt spike far above
    # the 50 mm of rain that month.
    assert avail[0, 3] > 100.0
    # Spin-up makes the series periodic: rerunning on a rolled year keeps the
    # warm-month melt spike (pack carried across the year boundary).
    assert avail[0, 3] > avail[0, 6]


def test_normalize_shape_mean_one_and_degenerate():
    avail = np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
            [0.0] * 12,  # degenerate -> uniform 1.0
        ]
    )
    shape = normalize_shape(avail)
    assert np.isclose(shape[0].mean(), 1.0)
    assert np.allclose(shape[1], 1.0)


def test_accumulate_downstream_sums_upstream_by_hydroseq():
    # Two headwaters (HydroSeq 3, 2) both drain into a mouth (HydroSeq 1).
    # Mouth's DnHydroSeq is 0 (terminal). Increments are flat monthly vectors.
    incr = np.array(
        [
            [1.0] * 12,  # HydroSeq 3 headwater
            [2.0] * 12,  # HydroSeq 2 headwater
            [4.0] * 12,  # HydroSeq 1 mouth (its own local increment)
        ]
    )
    hydroseq = np.array([3.0, 2.0, 1.0])
    dnhydroseq = np.array([1.0, 1.0, 0.0])
    acc = accumulate_downstream(incr, hydroseq, dnhydroseq)
    # Headwaters unchanged; mouth = its own 4 + 1 + 2 = 7.
    assert np.allclose(acc[0], 1.0)
    assert np.allclose(acc[1], 2.0)
    assert np.allclose(acc[2], 7.0)


def test_disaggregate_conserves_annual_mean():
    rng = np.random.default_rng(0)
    n = 5
    precip = rng.uniform(10, 80, size=(n, 12))
    temp = rng.uniform(-5, 15, size=(n, 12))
    q_incr = np.array([3.0, 1.5, 0.0, 5.0, 2.0])
    hydroseq = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    dnhydroseq = np.array([1.0, 1.0, 1.0, 1.0, 0.0])
    flow = disaggregate_monthly(precip, temp, q_incr, hydroseq, dnhydroseq)
    assert flow.shape == (n, 12)
    # Accumulated monthly mean equals accumulated incremental QAMA.
    acc_incr = accumulate_downstream(
        np.repeat(np.clip(q_incr, 0, None)[:, None], 12, axis=1),
        hydroseq,
        dnhydroseq,
    )
    assert np.allclose(flow.mean(axis=1), acc_incr.mean(axis=1))


def test_snowmelt_headwater_shifts_downstream_peak():
    # Snowy headwater (cold winter, warm spring melt) drains into a rain-driven
    # mouth. The mouth's own catchment peaks in winter, but after accumulation
    # its peak should move toward spring because the headwater dominates volume.
    cold_spring = np.array([-8, -8, -8, 10, 10, 6, 4, 4, 4, 2, -4, -8], dtype=float)
    rainy = np.array([80, 70, 40, 20, 10, 5, 5, 10, 20, 40, 70, 80], dtype=float)
    precip = np.array([[60.0] * 12, rainy])
    temp = np.array([cold_spring, [12.0] * 12])
    q_incr = np.array([50.0, 1.0])  # headwater dominates volume
    hydroseq = np.array([2.0, 1.0])
    dnhydroseq = np.array([1.0, 0.0])
    flow = disaggregate_monthly(precip, temp, q_incr, hydroseq, dnhydroseq)
    mouth_peak = int(flow[1].argmax())
    # Rain-only, the mouth would peak in Dec/Jan (month 11/0). Snowmelt pulls the
    # accumulated peak into spring/summer.
    assert 3 <= mouth_peak <= 7
