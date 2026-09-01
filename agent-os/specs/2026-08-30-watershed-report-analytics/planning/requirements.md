# Requirements — Watershed report analytics (roadmap #48–#55)

## Problem

`notebooks/salmon_creek_yoy.ipynb` reconstructs real PRISM year-over-year monthly
flow for the Salmon Creek watershed (two HUC12s in Clark County, WA) and is a
genuinely nice artifact. But as a *report* it has two structural weaknesses:

1. **Ten data points.** It spans only 2014–2023 (the currently-staged PRISM
   years), so its headline "peak-flow trend + 5-year projection" (an OLS fit on 10
   noisy points) is essentially fitting interannual noise — no significance, no
   climatological signal. PRISM's monthly record actually reaches back to **1895**.
2. **Uncalibrated and unvalidated.** The notebook honestly disclaims "model, not
   gauge" — but Salmon Creek has a real USGS gauge, so that disclaimer could be
   *evidence* (a validation plot) rather than a caveat.

It also answers only one question (seasonal-peak shift), from one point (the
outlet), with no attribution of *why* wet/dry years occur.

## Goal

Turn the notebook into a **reusable, credible watershed report** for any watershed
in the supported cohort, by adding analytical depth and — first — credibility:

- a **deeper temporal record** (toward 1895) so trends mean something;
- an **honest model-vs-gauge validation** (USGS NWIS) that bounds every claim;
- **climate-driver attribution** (ENSO/PDO teleconnection);
- **spatial decomposition** (sub-watershed hydrographs, longitudinal profile);
- a **parametrized builder** (any HUC12 group) + a **web report view**.

## Chosen approach

Reuse the existing engine and this repo's proven architecture. The
`{year: [n,12]}` flow series `src.historical_flow.yearly_flow_series` already
produces is the single input to a new **offline, numpy-only statistics layer**
(the single combined `src/flow_metrics.py`). All external observations
(PRISM back-catalog, USGS NWIS gauge, ENSO/PDO index) are read by **`tools/`
executors behind injectable provider seams** — the `ClimateProvider` precedent
(#44/#45) — and **snapshotted** so a report is reproducible offline. The notebook
and a new `tools/build_watershed_report.py` are thin consumers of a shared
`tools/report_common.py` recipe (mirroring `render_common.py`).

## Functional requirements

1. **Intrinsic hydrograph metrics** over `{year:[n,12]}`: per-year peak and
   summer-low-flow series, center-of-timing (month of 50% cumulative flow),
   Richards-Baker flashiness, wet/dry seasonal ratio, monthly flow-duration
   percentiles. (#48)
2. **Trend & distribution statistics**: Mann-Kendall trend + Sen's slope (robust
   to non-normal, autocorrelated flow), percentile rank of a year vs. the record,
   anomaly-vs-normal, sliding 30-year normals. (#49)
3. **Model-vs-gauge validation**: bias, Pearson r, Nash-Sutcliffe efficiency,
   RMSE, per-month seasonal skill between modeled and observed monthly means;
   missing months skipped, **never zero-filled** (mirrors `src/accuracy.py`). A
   USGS NWIS `GaugeProvider`. (#50)
4. **Climate-index correlation**: join a per-year flow metric to a per-year
   climate index (ENSO ONI / PDO) on common years; Pearson + optional lag. (#51)
5. **Deep record**: stage PRISM back toward 1895 (span-parametrized fetch); every
   temporal metric then runs on the full record. (#52)
6. **Spatial decomposition**: per-membership sub-series (per-HUC12 hydrographs),
   outlet-reach selection, longitudinal flow-accumulation profile. (#53)
7. **Report builder**: any HUC12 group → the full figure set, via a shared
   loading+plotting recipe; refactor the Salmon Creek notebook to consume it. (#54)
8. **Web report view** (proposed UX): metric tiles, a validation badge, a
   long-record sparkline, an ENSO overlay — on the shared `ux.css`/`hydro-ux.js`
   foundation. (#55)

## Non-functional / invariants

- **Offline discipline preserved.** the combined `src/flow_metrics.py` is
  **numpy-only**, imports no GDAL/rasterio/geopandas,
  and are not wired into `PIPELINE_STAGES`. All heavy/external reads live in
  `tools/` behind injectable seams; the offline suite injects fakes + hand-built
  arrays with known answers.
- **Reproducibility of external data.** NWIS/PRISM/ENSO are queryable, moving
  sources. Fetched observations are **staged and snapshotted** (mirroring
  `src/manifest.py`) so a given report is reproducible from local snapshots, not a
  live network call. Purity: identical staged inputs → identical metrics.
- **Default byte-identical.** No `src/` change touches the 2D pipeline; the
  synthetic-year and default renders are unchanged.
- **Statistical honesty.** Report *bands*, not point estimates, on short/
  autocorrelated series; if model-vs-gauge skill is low, the report reframes from
  "validated" to "climatology-consistent" and surfaces the metrics.
- **Large data on the NAS.** PRISM back-catalog stages on the NAS Pro drive
  (mount-aware), never bulking up local disk.

## Out of scope (deferred)

- Live `build.py` report generation in the 2D pipeline (these are `tools/`/
  notebook analytics, like the DEM/monthly subsystems).
- NWM-retrospective observed flow (Option A) and any NHDPlus-V2↔HR crosswalk.
- Gauge-calibration of the disaggregation model itself (we *validate* against the
  gauge; we do not tune the model to it).
- Multi-watershed comparison dashboards beyond the single-watershed report
  (a natural follow-on once the single report is solid).
