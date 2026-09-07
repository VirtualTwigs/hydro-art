# Requirements — Creative report analytics (Epoch 17)

## Source
Roadmap Epoch 17 (`agent-os/product/roadmap.md`), items **#69–#76**. Deepen the Epoch 12
watershed report from seven figures into a richer story, drawing almost entirely on statistics
the engine already computes (`src/flow_metrics.py`, `src/monthly_flow.py`) and data already staged
(`{year:[n,12]}` monthly flow back to 1895, USGS gauges, ONI/PDO indices).

## Discipline (carried from Epoch 12/14)
- Promote **pure, numpy-only** stats into `src/` (offline-testable); heavy external reads stay in
  `tools/` behind provider seams; figures via `tools/report_common.py`; web surface in
  `web/report.html` on the shared `web/shared/*` foundation (no per-page duplication).
- **Nothing enters `PIPELINE_STAGES`.** The 2D pipeline's byte-for-byte default output is untouched.
- `src/flow_metrics.py` and `src/monthly_flow.py` stay numpy-only (no GDAL/network/`tools`/`web`
  imports at module scope). Every new `src` function gets matching `tests/test_*` coverage that runs
  in the offline suite.
- `nan` is skipped, never zero-filled. Identical inputs → identical outputs.
- Climate posture unchanged: default `--climate-source nclimgrid` is public-domain/sellable with
  attribution; PRISM stays A/B-only and non-sellable.

## Scope by item
- **#69** Snow-vs-rain regime signature — surface the snow bucket the disaggregation already models
  as a returned diagnostic (new pure function, no change to existing outputs); classify a watershed
  snowmelt-dominated / transitional / rain-dominated; melt-pulse timing shift across decades.
- **#70** Center-of-timing drift trend panel (Mann-Kendall + Sen's slope on CT).
- **#71** Analog-year finder (rank most-similar historical years via `correlate`/`pearson_r`).
- **#72** Drought/flood record book (rank years by summer-low and peak via `percentile_rank`).
- **#73** Flow-duration-curve panel (log-scale FDC with decade overlays).
- **#74** ENSO/PDO composite hydrographs (mean El Niño vs La Niña year hydrograph).
- **#75** Longitudinal flow-accumulation animation (`longitudinal_profile` walked down the mainstem).
- **#76** Report assembly + web surfacing (`tools/report_common.py`,
  `tools/build_watershed_report.py`, `web/report.html`).

## This session
Implement **#69 only** (first item / Phase 17.1). Remaining items are specified here but left
unchecked; they are implemented one at a time on subsequent "implement item #N" commands.
