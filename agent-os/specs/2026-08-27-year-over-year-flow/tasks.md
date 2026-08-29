# Tasks — Year-over-year historical flow (Option C)

Legend: `[x]` done · `[ ]` todo. Offline items ship with tests; `tools/` items are
non-offline (closeout = smoke-render + note).

## Group 1 — Pure historical-flow engine (#44) · offline · **DONE**

- [x] 1.1 Write offline unit tests first (`tests/test_historical_flow.py`, fake
  `ClimateProvider` over a 3-reach chain): `PRISM_FIRST_YEAR`; `normalize_years`
  dedup/sort + rejects pre-1895/after-latest/empty/non-int/bool; `year_span`
  inclusive + reversed-raises; `YearlyClimate` shape validation;
  `yearly_flow_series` parity with `disaggregate_monthly` + once-per-year +
  reach-count mismatch; July-spike peaks in July; `annual_mean_series` /
  `peak_month_series` shapes + mass conservation.
- [x] 1.2 Implement `src/historical_flow.py`: `PRISM_FIRST_YEAR`,
  `HistoricalFlowError`, `YearlyClimate`, `ClimateProvider` (Protocol seam),
  `normalize_years`, `year_span`, `yearly_flow_series`, `annual_mean_series`,
  `peak_month_series`. numpy-only; delegates the model to `src.monthly_flow`.
- [x] 1.3 Run only these tests (17 passing). Full-suite regression check + this
  report deferred to the commit step.

## Group 2 — PRISM climate ingestion (#45) · non-offline · **DONE**

- [x] 2.1 `tools/historical_flow.py`: `PrismClimateProvider` reading 12 monthly
  PRISM `ppt` + `tmean` grids per year, sampling each catchment centroid (EPSG:4269;
  row/col computed once from the shared geotransform, then vectorized) → `YearlyClimate`;
  ocean nodata → precip 0 / temp 10 °C.
- [x] 2.2 NAS-staged PRISM download/stage helper (`tools/prism_fetch.py`, NACSE
  web service, idempotent/resumable; archives under `<root>/prism/<var>/`).
- [x] 2.3 Smoke: staged all of 2014–2023 (240 grids); WA render disaggregated every
  HUC4 with **147,908/147,908 reaches** carrying real PRISM flow (no fallbacks).

## Group 3 — Year-over-year rendering (#46) · non-offline · **DONE**

- [x] 3.1 `tools/render_state_yoy.py` drives frames from
  `src.historical_flow.yearly_flow_series` for a year walk (real per-year
  `disaggregate_monthly` per HUC4, merged by `NHDPlusID`).
- [x] 3.2 Fixed cross-series width span across all rendered years (reuse
  `src.rendering.fixed_flow_span`/`widths_on_span`) so inter-year change shows.
- [x] 3.3 Smoke: WA 2014–2023 GIF — summed peak-month (May) flow ranges from a
  76M cfs drought (2016) to 211M cfs (2023); channel widths visibly differ.

## Group 4 — Utah region (#47) · non-offline

- [ ] 4.1 `tools/derive_state_huc4.py` → Utah HUC4s.
- [ ] 4.2 Wire `SUPPORTED_REGIONS`, `datasets.REGION_HUC4`, `counties.STATE_FIPS`,
  `render_common.STATE_HUC4`; add Utah tests alongside the existing region tests.
- [ ] 4.3 Download UT NHDPlus HR GDBs (NAS-staged); smoke-render a Utah year.

## Group 5 — Close out · offline

- [ ] 5.1 Run the full suite (regression check) + `node
  tests/test_recipe_roundtrip.cjs`.
- [ ] 5.2 `implementation/report.md`; confirm default synthetic-year render
  byte-identical; update `HANDOFF.md` and tick the roadmap items.
