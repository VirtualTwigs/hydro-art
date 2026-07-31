"""Prototype: disaggregate NHDPlus HR mean-annual flow into 12 monthly flows.

NHDPlus HR ships only *mean-annual* EROM discharge (``QAMA``, cfs) per reach --
there is no monthly streamflow table. But the same GDB *does* carry real
per-catchment **monthly climate**: incremental precipitation
(``NHDPlusIncrPrecipMM01..12``) and temperature (``NHDPlusIncrTempMM01..12``),
both in hundredths (0.01 mm, 0.01 degC). This script turns that monthly
climatology into a 12-month flow series that conserves each reach's annual mean,
so it can feed straight into :func:`src.rendering.flow_widths` for a
year-in-motion render.

Model (deterministic, offline, physically motivated -- not a calibrated forecast):

1. **Local snow-aware available water.** For each reach's own catchment, split
   monthly precip into rain vs. snow by temperature, accumulate a snowpack, and
   release it as melt on warm months (temperature-index bucket). Available water
   ``= rain + melt``. A 3-cycle spin-up gives the snowpack a periodic steady
   state so spring melt appears regardless of which month we start on.
2. **Incremental monthly volume.** Scale each reach's normalized monthly shape by
   its *incremental* annual flow ``QIncrAMA`` so the monthly mean equals the
   local contribution.
3. **Network accumulation.** Route incremental monthly volumes downstream via
   ``HydroSeq``/``DnHydroSeq`` (process upstream reaches first). A mainstem then
   integrates many catchments, so a snowmelt headwater shifts the big river's
   peak into spring even though the mouth's local catchment is rain-driven.
   Result conserves mass: ``mean_m Q[reach][m] ~= QAMA[reach]``.

Divergences use only the main ``DnHydroSeq`` path (minor divergence fractions are
ignored -- fine for an art prototype). Run directly:

    .venv/bin/python tools/monthly_flow.py datasets/nhdplus_hr/1709/NHDPLUS_H_1709_HU4_GDB.gdb
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pyogrio

MONTHS = range(1, 13)
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Snow / melt thresholds, in degC (temperature-index bucket).
T_ALL_SNOW = -1.0   # at/below this, all precip falls as snow
T_ALL_RAIN = 3.0    # at/above this, all precip falls as rain
T_MELT = 0.0        # melt begins above this
T_MELT_FULL = 6.0   # snowpack melts at full monthly rate at/above this
SPINUP_CYCLES = 3   # repeat the 12-month cycle to reach periodic snowpack


def _value_column(gdb: str, layer: str, prefix: str) -> str:
    """Return the first field starting with ``prefix`` (handles USGS quirks like
    ``TempVMM08``)."""
    fields = pyogrio.read_info(gdb, layer=layer)["fields"]
    for f in fields:
        if f.startswith(prefix) and not f.startswith("Miss"):
            return f
    raise KeyError(f"no {prefix!r} column in {layer}")


def _load_monthly(gdb: str, kind: str, prefix: str, ids_index: dict[int, int],
                  n: int) -> np.ndarray:
    """Load a 12-month stack [n, 12] for precip or temp, aligned to ids_index."""
    out = np.full((n, 12), np.nan, dtype=np.float64)
    for m in MONTHS:
        layer = f"NHDPlusIncr{kind}MM{m:02d}"
        col = _value_column(gdb, layer, prefix)
        df = pyogrio.read_dataframe(
            gdb, layer=layer, columns=["NHDPlusID", col], read_geometry=False
        )
        idx = df["NHDPlusID"].map(ids_index)
        keep = idx.notna()
        out[idx[keep].astype(int).to_numpy(), m - 1] = df[col][keep].to_numpy()
    return out


def snow_available_water(precip_mm: np.ndarray, temp_c: np.ndarray) -> np.ndarray:
    """Monthly available water (rain + snowmelt) per reach, shape [n, 12].

    Vectorized temperature-index snow bucket with spin-up. Inputs already in
    physical units (mm, degC).
    """
    n = precip_mm.shape[0]
    snow_frac = np.clip((T_ALL_RAIN - temp_c) / (T_ALL_RAIN - T_ALL_SNOW), 0.0, 1.0)
    melt_frac = np.clip((temp_c - T_MELT) / (T_MELT_FULL - T_MELT), 0.0, 1.0)
    snowfall = precip_mm * snow_frac
    rainfall = precip_mm - snowfall

    pack = np.zeros(n)
    available = np.zeros((n, 12))
    for _ in range(SPINUP_CYCLES):
        available = np.zeros((n, 12))
        for m in range(12):
            pack = pack + snowfall[:, m]
            melt = pack * melt_frac[:, m]
            pack = pack - melt
            available[:, m] = rainfall[:, m] + melt
    return available


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
    we push into its downstream reach. Returns accumulated monthly flow [n, 12].
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


def build_monthly_flow(gdb: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (nhdplus_ids [n], monthly_flow [n,12] cfs, qama [n] cfs)."""
    erom = pyogrio.read_dataframe(
        gdb, layer="NHDPlusEROMMA",
        columns=["NHDPlusID", "QAMA", "QIncrAMA"], read_geometry=False,
    )
    vaa = pyogrio.read_dataframe(
        gdb, layer="NHDPlusFlowlineVAA",
        columns=["NHDPlusID", "HydroSeq", "DnHydroSeq"], read_geometry=False,
    )
    df = erom.merge(vaa, on="NHDPlusID", how="inner").dropna(
        subset=["HydroSeq", "DnHydroSeq"]
    )
    df = df[df["HydroSeq"] > 0].reset_index(drop=True)

    ids = df["NHDPlusID"].to_numpy()
    ids_index = {int(v): i for i, v in enumerate(ids)}
    n = len(ids)

    precip = _load_monthly(gdb, "Precip", "Precip", ids_index, n) / 100.0  # -> mm
    temp = _load_monthly(gdb, "Temp", "Temp", ids_index, n) / 100.0        # -> degC
    precip = np.nan_to_num(precip, nan=0.0)
    temp = np.nan_to_num(temp, nan=10.0)  # missing climate -> mild, no snow

    shape = normalize_shape(snow_available_water(precip, temp))
    incr = np.clip(df["QIncrAMA"].to_numpy(dtype=np.float64), 0.0, None)
    incr_monthly = shape * incr[:, None]  # mean_m == incr per reach

    flow = accumulate_downstream(
        incr_monthly, df["HydroSeq"].to_numpy(), df["DnHydroSeq"].to_numpy()
    )
    return ids, flow, df["QAMA"].to_numpy(dtype=np.float64)


def _print_diagnostics(ids, flow, qama) -> None:
    mean_flow = flow.mean(axis=1)
    # Mass conservation: accumulated monthly mean vs. QAMA (both cfs).
    valid = qama > 1.0
    ratio = mean_flow[valid] / qama[valid]
    print(f"reaches: {len(ids):,}")
    print(f"mass check  mean_m(Q)/QAMA : median={np.median(ratio):.3f} "
          f"p10={np.percentile(ratio, 10):.3f} p90={np.percentile(ratio, 90):.3f}")

    peak_month = flow.argmax(axis=1)
    print("\npeak-month distribution (all reaches):")
    counts = np.bincount(peak_month, minlength=12)
    for m in range(12):
        bar = "#" * int(40 * counts[m] / max(counts.max(), 1))
        print(f"  {MONTH_ABBR[m]} {counts[m]:>7,} {bar}")

    # Show a big mainstem and a small headwater hydrograph.
    big = int(np.argmax(qama))
    small_candidates = np.where((qama > 0.5) & (qama < 3))[0]
    small = int(small_candidates[0]) if len(small_candidates) else int(np.argmin(qama))
    for label, i in [("MAINSTEM", big), ("HEADWATER", small)]:
        series = flow[i]
        norm = series / series.mean() if series.mean() > 0 else series
        print(f"\n{label}  reach={int(ids[i])}  QAMA={qama[i]:.1f} cfs  "
              f"peak={MONTH_ABBR[peak_month[i]]}")
        for m in range(12):
            bar = "#" * int(30 * norm[m] / max(norm.max(), 1e-9))
            print(f"  {MONTH_ABBR[m]} {series[m]:>10.1f}  {bar}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gdb", help="path to a NHDPLUS_H_XXXX_HU4_GDB.gdb")
    ap.add_argument("--out", help="write monthly flow map as JSON (id -> [12 cfs])")
    args = ap.parse_args(argv)

    ids, flow, qama = build_monthly_flow(args.gdb)
    _print_diagnostics(ids, flow, qama)

    if args.out:
        payload = {str(int(i)): [round(float(x), 4) for x in row]
                   for i, row in zip(ids, flow)}
        Path(args.out).write_text(json.dumps(payload))
        print(f"\nwrote {len(payload):,} reaches -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
