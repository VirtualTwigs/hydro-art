# Implementation report — Watershed report analytics (#48–#55)

_Spec: `agent-os/specs/2026-08-30-watershed-report-analytics/`. Closed 2026-08-31._

## Summary

Turned the one-off `notebooks/salmon_creek_yoy.ipynb` into a reusable, credible
watershed report. Two pure, numpy-only, offline `src/` modules hold all the
statistics; the heavy external reads (USGS NWIS, PRISM back-catalog, ENSO/PDO)
live in `tools/` behind injectable provider seams; a parametrized report builder
and a web report view sit on top. The 2D pipeline and its byte-identical default
output are untouched — nothing entered `PIPELINE_STAGES`.

## What shipped, by group

- **Group 1 — #48** `src/flow_metrics.py`: `peak_flow`/`low_flow`, `center_of_timing`,
  `flashiness` (Richards-Baker), `seasonal_ratio`, `flow_duration`. `tests/test_flow_metrics.py`.
- **Group 2 — #49** extends `src/flow_metrics.py`: `mann_kendall`, `sens_slope`,
  `percentile_rank`, `anomaly`, `rolling_normals`.
- **Group 3 — #50** in the combined `src/flow_metrics.py`: `bias`/`pearson_r`/`nash_sutcliffe`/`rmse`,
  `seasonal_skill` (nan months skipped, never zero-filled), `validate`→`ValidationReport`.
  Non-offline `tools/nwis_gauge.py` `GaugeProvider` (NWIS monthly means + site
  location, snapshotted). Tests in `tests/test_flow_metrics.py`.
- **Group 4 — #51** `align_index`/`correlate` (+ lag) in `src/flow_metrics.py`;
  non-offline `tools/climate_index.py` `ClimateIndexProvider` (ONI/PDO, snapshotted).
- **Group 5 — #52** `tools/prism_fetch.py --start/--end` span (idempotent, resumable,
  mount-aware); gauge-era 1944–1989 span staged for HUC4 1708.
- **Group 6 — #53** `subset_series`/`outlet_index`/`longitudinal_profile` in
  `src/flow_metrics.py`.
- **Group 7 — #54** `tools/report_common.py` (shared load + reach selection + 7-panel
  recipe) + `tools/build_watershed_report.py` CLI; `notebooks/salmon_creek_yoy.ipynb`
  refactored to consume `report_common`.
- **Group 8 — #55** `web/shared/ux.css` report components + `web/shared/hydro-ux.js`
  helpers (Node-loadable) + `web/report.html`; `tests/test_report_helpers.cjs`.

## Reach-matching fix (the credibility finding, #50)

The first model-vs-gauge run scored the **basin outlet** against gauge 14212000 →
r=0.80 but NSE=−9.86, bias=+166.9 cfs. The outlet is the basin mouth ~23 km
downstream (Lake-River confluence), a ~3.7× larger drainage than the mid-watershed
Battle Ground gauge. Snapping the comparison to the model reach *at the gauge*
(`report_common.gauge_reach_index`, using the NWIS site lat/lon → idx 597, 10.3 m
away) gives **r=0.78, NSE=+0.50, bias=+18.6 cfs, RMSE=44.9** — bias down 9×. Verdict
stays "weak" only because NSE=0.4993 misses the 0.50 "moderate" cutoff by 0.0007.
Honest framing: the model reproduces gauge timing and magnitude at the gauge site.

## Verification

- **Offline suite: 630 passed** (`.venv/bin/python -m pytest -q`), no regressions.
- **Node harnesses:** `tests/test_recipe_roundtrip.cjs` (11) + `tests/test_report_helpers.cjs` (8) green.
- **2D default output byte-identical:** Epoch 12 added only the pure combined
  `src/flow_metrics.py`, not in `PIPELINE_STAGES`; no pipeline stage touched.
- **Real-data smokes** (non-offline, on the GIS/NAS host): recorded in the spec
  `tasks.md` (3.5 validation, 4.4 ENSO, 5.2 PRISM staging, 7.4 full report build).
- **Notebook (#54 task 7.3):** `notebooks/salmon_creek_yoy.ipynb` refactored to a thin
  `report_common` driver and re-executed end-to-end with `jupyter nbconvert --execute`
  on the GIS/NAS host — all cells run, seven report panels render inline, no errors.
  Gotcha fixed: the setup cell `os.chdir(REPO)` so `report_common`'s repo-root-relative
  caches resolve under nbconvert (which runs with CWD = the notebook's directory).

## Non-goals held

- Nothing enters `PIPELINE_STAGES`; the combined `src/flow_metrics.py`
  imports numpy only; the offline suite stays GDAL/network-free.
- **Rights gate:** no PRISM-derived report or animation ships commercially until the
  PRISM Climate Group arrangement is documented (roadmap Notes).
