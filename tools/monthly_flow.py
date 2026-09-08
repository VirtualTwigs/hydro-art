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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyogrio

# The pure, offline disaggregation math lives in ``src/monthly_flow.py`` (the
# single source of truth); this tool adds only the pyogrio/GDB reads. Re-export
# the promoted names so existing importers (render_monthly.py etc.) keep working.
from src.monthly_flow import (  # noqa: F401  (re-exported for tool importers)
    MONTH_ABBR,
    MONTHS,
    SPINUP_CYCLES,
    T_ALL_RAIN,
    T_ALL_SNOW,
    T_MELT,
    T_MELT_FULL,
    accumulate_downstream,
    disaggregate_monthly,
    normalize_shape,
    snow_available_water,
)


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


def build_monthly_flow(gdb: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (nhdplus_ids [n], monthly_flow [n,12] cfs, qama [n] cfs).

    Reads the GDB (EROM discharge, VAA connectivity, monthly precip/temp
    climatology), then delegates the disaggregation math to
    :func:`src.monthly_flow.disaggregate_monthly` (the shared source of truth).
    """
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

    flow = disaggregate_monthly(
        precip,
        temp,
        df["QIncrAMA"].to_numpy(dtype=np.float64),
        df["HydroSeq"].to_numpy(),
        df["DnHydroSeq"].to_numpy(),
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
