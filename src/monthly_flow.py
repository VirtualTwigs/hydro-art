"""Monthly-flow disaggregation: turn a mean-annual flow into a 12-month series.

NHDPlus HR ships only *mean-annual* EROM discharge (``QAMA``/``QIncrAMA``, cfs)
per reach -- there is no monthly streamflow table. But the same GDB carries real
per-catchment monthly climate (incremental precipitation and temperature). This
module holds the pure, deterministic, numpy-only algorithm that turns that
monthly climatology into a 12-month flow series conserving each reach's annual
mean, so it can feed :func:`src.rendering.flow_widths` for a year-in-motion
render.

The heavy pyogrio/GDB reads live in ``tools/monthly_flow.py``; this module
operates purely on caller-supplied arrays so it is fully offline-testable (numpy
only, no pyogrio/GDAL).

Model (deterministic, offline, physically motivated -- not a calibrated forecast):

1. **Local snow-aware available water.** For each reach's own catchment, split
   monthly precip into rain vs. snow by temperature, accumulate a snowpack, and
   release it as melt on warm months (temperature-index bucket). A 3-cycle
   spin-up gives the snowpack a periodic steady state.
2. **Incremental monthly volume.** Scale each reach's normalized monthly shape by
   its incremental annual flow ``QIncrAMA`` so the monthly mean equals the local
   contribution.
3. **Network accumulation.** Route incremental monthly volumes downstream via
   ``HydroSeq``/``DnHydroSeq`` (upstream reaches first). Result conserves mass:
   ``mean_m Q[reach][m] ~= accumulated QIncrAMA[reach]``.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "MONTHS",
    "MONTH_ABBR",
    "T_ALL_SNOW",
    "T_ALL_RAIN",
    "T_MELT",
    "T_MELT_FULL",
    "SPINUP_CYCLES",
    "snow_available_components",
    "snow_available_water",
    "normalize_shape",
    "accumulate_downstream",
    "disaggregate_monthly",
]

MONTHS = range(1, 13)
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Snow / melt thresholds, in degC (temperature-index bucket).
T_ALL_SNOW = -1.0   # at/below this, all precip falls as snow
T_ALL_RAIN = 3.0    # at/above this, all precip falls as rain
T_MELT = 0.0        # melt begins above this
T_MELT_FULL = 6.0   # snowpack melts at full monthly rate at/above this
SPINUP_CYCLES = 3   # repeat the 12-month cycle to reach periodic snowpack


def snow_available_components(
    precip_mm: np.ndarray, temp_c: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Split monthly available water into ``(rain, melt)`` buckets, each ``[n, 12]``.

    Vectorized temperature-index snow bucket with spin-up (identical physics to
    :func:`snow_available_water`, which returns ``rain + melt``). Exposing the two
    buckets separately lets the watershed report characterize a reach's snow-vs-rain
    regime (roadmap #69). Inputs already in physical units (mm, degC).
    """
    n = precip_mm.shape[0]
    snow_frac = np.clip((T_ALL_RAIN - temp_c) / (T_ALL_RAIN - T_ALL_SNOW), 0.0, 1.0)
    melt_frac = np.clip((temp_c - T_MELT) / (T_MELT_FULL - T_MELT), 0.0, 1.0)
    snowfall = precip_mm * snow_frac
    rainfall = precip_mm - snowfall

    pack = np.zeros(n)
    melt_out = np.zeros((n, 12))
    for _ in range(SPINUP_CYCLES):
        melt_out = np.zeros((n, 12))
        for m in range(12):
            pack = pack + snowfall[:, m]
            melt = pack * melt_frac[:, m]
            pack = pack - melt
            melt_out[:, m] = melt
    return rainfall, melt_out


def snow_available_water(precip_mm: np.ndarray, temp_c: np.ndarray) -> np.ndarray:
    """Monthly available water (rain + snowmelt) per reach, shape ``[n, 12]``.

    Vectorized temperature-index snow bucket with spin-up. Inputs already in
    physical units (mm, degC).
    """
    rain, melt = snow_available_components(precip_mm, temp_c)
    return rain + melt


def normalize_shape(available: np.ndarray) -> np.ndarray:
    """Normalize each reach's 12-month vector to mean 1.0 (uniform if degenerate)."""
    mean = available.mean(axis=1, keepdims=True)
    shape = np.divide(available, mean, out=np.ones_like(available), where=mean > 0)
    return shape


def accumulate_downstream(incr_monthly: np.ndarray, hydroseq: np.ndarray,
                          dnhydroseq: np.ndarray) -> np.ndarray:
    """Route incremental monthly volumes downstream via HydroSeq connectivity.

    Downstream reaches have smaller HydroSeq, so processing in *descending*
    HydroSeq order guarantees a reach's upstream contributions are summed before
    we push into its downstream reach. Returns accumulated monthly flow
    ``[n, 12]``.
    """
    seq_to_idx = {int(s): i for i, s in enumerate(hydroseq)}
    acc = incr_monthly.copy()
    order = np.argsort(-hydroseq)  # descending: upstream first
    for i in order:
        dn = int(dnhydroseq[i])
        if dn == 0:
            continue
        j = seq_to_idx.get(dn)
        if j is not None:
            acc[j] += acc[i]
    return acc


def disaggregate_monthly(precip_mm: np.ndarray, temp_c: np.ndarray,
                         q_incr: np.ndarray, hydroseq: np.ndarray,
                         dnhydroseq: np.ndarray) -> np.ndarray:
    """Disaggregate mean-annual increments into accumulated monthly flow ``[n, 12]``.

    Builds the snow-aware monthly shape, scales it by each reach's incremental
    annual flow ``q_incr`` (clipped non-negative) so the per-reach monthly mean
    equals that increment, then accumulates downstream by HydroSeq. Conserves
    each reach's annual mean (``mean_m Q ~= accumulated QIncrAMA``).
    """
    shape = normalize_shape(snow_available_water(precip_mm, temp_c))
    incr = np.clip(q_incr.astype(np.float64), 0.0, None)
    incr_monthly = shape * incr[:, None]  # mean_m == incr per reach
    return accumulate_downstream(incr_monthly, hydroseq, dnhydroseq)
