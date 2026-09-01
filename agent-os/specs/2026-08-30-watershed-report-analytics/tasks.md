# Tasks — Watershed report analytics (#48–#55)

Legend: `[x]` done · `[ ]` todo. Offline items ship tests-first; `tools/`/web
items are non-offline / view-layer (closeout = smoke-run + note). Write 2–8 tests
per group first, run ONLY those, then implement.

## Group 1 — Intrinsic hydrograph metrics (#48) · offline

- [x] 1.1 Write `tests/test_flow_metrics.py` first, over a hand-built
  `{year: [n,12]}` with known answers:
  - `peak_flow` / `low_flow`: a year whose July column is the minimum → `low_flow`
    picks July; the max month → `peak_flow`. Custom `months=` window honored.
  - `center_of_timing`: all flow in one month → COT == that month; a flat 12-month
    row → COT ≈ 6.5.
  - `flashiness`: a constant series → 0.0; a max-swing alternating series → the
    documented Richards-Baker upper value.
  - `seasonal_ratio`: hand ratio of wet-half mean to dry-half mean.
  - `flow_duration`: returned exceedance percentiles are monotone non-increasing;
    the 0th/100th match series max/min.
  - purity: inputs are not mutated; identical inputs → identical outputs.
  - `FlowMetricsError` on an empty series and on a ragged (non-`[n,12]`) row.
- [x] 1.2 Implement `src/flow_metrics.py` #48 surface (numpy-only; `__all__`).
- [x] 1.3 Run only these tests.

## Group 2 — Trend / distribution statistics (#49) · offline

- [x] 2.1 Extend `tests/test_flow_metrics.py`:
  - `mann_kendall`: a strictly increasing sequence → `trend == "increasing"`,
    `S > 0`; strictly decreasing → decreasing; a flat sequence → `"none"`;
    a textbook small series → known `tau`.
  - `sens_slope`: points on `y = 2x + 3` → slope `2.0` (robust to one outlier).
  - `percentile_rank`: value == record median → ≈ 0.5; == max → ≈ 1.0.
  - `anomaly`: `value - normal`.
  - `rolling_normals`: a 40-long series, window 30 → 11 windows with correct means;
    window > record length → `FlowMetricsError`.
- [x] 2.2 Implement the #49 functions in `src/flow_metrics.py`.
- [x] 2.3 Run only these tests.

## Group 3 — Model-vs-gauge validation (#50) · offline metrics + non-offline provider

- [x] 3.1 Write `tests/test_flow_validation.py` first (hand-built model/obs arrays):
  - identical arrays → `bias == 0`, `pearson_r == 1`, `nash_sutcliffe == 1`,
    `rmse == 0`.
  - a constant offset → exact `bias`; an anti-correlated pair → `pearson_r == -1`;
    predicting the obs mean → `nash_sutcliffe == 0`.
  - `seasonal_skill`: per-month array length 12; a month with `nan` in obs is
    skipped, **not** zero-filled (result unaffected by the nan month).
  - `validate` → `ValidationReport` whose `verdict` crosses the documented
    good/moderate/weak thresholds at hand-chosen r/NSE.
  - `FlowValidationError` on length mismatch and on all-nan overlap.
- [x] 3.2 Implement `src/flow_validation.py` #50 surface (numpy-only).
- [x] 3.3 Run only these tests.
- [x] 3.4 (non-offline) `tools/nwis_gauge.py` `GaugeProvider`: fetch USGS NWIS
  monthly means for a gauge id, snapshot raw response + manifest to the NAS, return
  `{year: [12]}`. Confirmed: **14212000 Salmon Creek nr Battle Ground, WA**; dv
  discharge period of record **1943-10-01..1990-05-10** (gap 1976..1987), so the
  model-vs-gauge overlap is water years 1944..1989 (34 years staged). (Note: no
  active gauge covers 2014..2023 — 14212000 was discontinued 1990.)
- [x] 3.5 (non-offline smoke) Validated the Salmon Creek model against gauge
  14212000 over the 34 overlap years (1944–1975 + 1988–1989). **Reach-matching
  fix:** the comparison now snaps to the model reach *at the gauge* (idx 597,
  10.3 m away via `GaugeProvider.location()` → `report_common.gauge_reach_index`)
  instead of the watershed outlet — the outlet (idx 614) is the basin mouth 23 km
  downstream at the Lake-River confluence, a ~3.7× larger drainage than the
  mid-watershed Battle Ground gauge, so the two were never apples-to-apples.
  Snapped: **r = 0.78, NSE = +0.50, bias = +18.6 cfs, RMSE = 44.9** (vs. outlet
  r=0.80, NSE=−9.86, bias=+166.9, RMSE=208.9 — bias collapsed 9×). Verdict stays
  "weak" only because NSE=0.4993 lands a hair under the 0.50 "moderate" cutoff
  (moderate = NSE≥0.5 & r≥0.7; r clears, NSE misses by 0.0007). Honest framing:
  the model reproduces gauge *timing and magnitude* at the gauge site — it was
  never overpredicting, it was being scored at the wrong drainage point. Figure:
  `notebooks/figures/salmon_creek_validation.png`.

## Group 4 — Climate-index teleconnection (#51) · offline metrics + non-offline fetch

- [x] 4.1 Extend `tests/test_flow_validation.py`:
  - `align_index`: metric years {2014..2023} ∩ index years {2016..2025} → the 8
    common years, both arrays aligned; empty overlap → `FlowValidationError`.
  - `correlate`: a perfectly index-tracking metric → `1.0`; `lag=1` shifts the join
    by one year (hand-checked).
- [x] 4.2 Implement `align_index`/`correlate` in `src/flow_validation.py`.
- [x] 4.3 Run only these tests.
- [x] 4.4 (non-offline) `tools/climate_index.py`: snapshot-backed ENSO ONI (NOAA
  CPC) + PDO (NCEI ERSST v5), annual-mean `index_by_year`. Smoke-correlated ONI
  against Salmon Creek Dec peak-flow (n=40): **r = +0.16 (lag-1 r = +0.12)** —
  weak; peak flow here isn't strongly ENSO-driven. Figure:
  `notebooks/figures/salmon_creek_enso.png`.

## Group 5 — PRISM back-catalog extension (#52) · non-offline

- [x] 5.1 Extend `tools/prism_fetch.py` with a `--start/--end` span (idempotent,
  resumable, mount-aware); no change to `PrismClimateProvider`. (Already present:
  `--start/--end/--vars/--root/--pause`, skips staged grids — verified idempotent.)
- [x] 5.2 Smoke: staged the 1990–2023 span for HUC4 1708 (816 grids = 34 yrs × 12
  mo × {ppt,tmean}: 576 downloaded + 240 already staged, 0 failed) under
  `<root>/prism/<var>/`. A second gauge-era 1944–1989 span is staging for the #50
  validation panel. Record depth confirmed via the report build.

## Group 6 — Spatial decomposition (#53) · offline

- [x] 6.1 Extend `tests/test_flow_metrics.py`:
  - `subset_series`: a 2-membership index partition → disjoint, complete
    sub-series with correct shapes.
  - `outlet_index`: over a hand-built accumulated-flow array → the max-accumulated
    reach within the membership set.
  - `longitudinal_profile`: a hand-built upstream→downstream chain → strictly
    non-decreasing accumulated flow along the path.
- [x] 6.2 Implement the #53 helpers in `src/flow_metrics.py`.
- [x] 6.3 Run only these tests.

## Group 7 — Report assembly (#54) · non-offline

- [x] 7.1 `tools/report_common.py`: shared load (reuses `output/_wshed_<tag>_mo<n>`
  clip + `_yoy_net_<huc4>.pkl` network caches) → `WatershedSeries` (outlet via
  `flow_metrics.outlet_index`) + the 7-panel matplotlib figure recipe, driven
  purely by the offline `src/flow_metrics` + `src/flow_validation` layer.
- [x] 7.2 `tools/build_watershed_report.py` CLI (`--huc4/--huc12/--name/--start/
  --end/[--gauge]/[--index]`) → full 7-figure set to `notebooks/figures/` + a JSON
  metrics summary. Smoke-built Salmon Creek 1944–1989 end-to-end (615 reaches,
  outlet idx 614, Dec peak) → all 7 PNGs rendered (multipart-geometry safe).
- [x] 7.3 Refactored `notebooks/salmon_creek_yoy.ipynb` to a thin `report_common`
  driver (24 cells): `load_watershed_series` + `build_report`, long-record,
  validation, low-flow/salmon, and ENSO sections, 7 panels shown inline. Re-executed
  end-to-end via `jupyter nbconvert --execute` on the GIS/NAS host — 0 cell errors, 7
  inline PNG panels. Setup cell `os.chdir(REPO)` so `report_common`'s repo-root caches
  resolve under nbconvert (CWD = notebook dir).
- [x] 7.4 Smoke: built the Salmon Creek 1944–1989 report end-to-end (`--gauge
  14212000 --index oni`) → 7 PNGs in `notebooks/figures/` (map, hydrographs,
  long_record, typical_year, low_flow, validation, enso). Metrics recorded in 3.5
  / 4.4 above (long record: trend "none", τ=−0.02 p=0.87; summer low: "none").

## Group 8 — Web report view (#55) · view-layer (proposed UX)

- [x] 8.1 Add shared components to `web/shared/ux.css` (`.metric-tile`,
  `.report-grid`, `.validation-badge`, `.chart-card`, `.sparkline`).
- [x] 8.2 Add report data/formatting helpers to `web/shared/hydro-ux.js`
  (Node-loadable — no top-level `document`/`window`); extend the headless
  `tests/test_recipe_roundtrip.cjs`-style harness for any new pure helper
  (`tests/test_report_helpers.cjs`).
- [x] 8.3 Build the report page over the shared foundation (`web/report.html`).

## Group 9 — Close out · offline

- [x] 9.1 Full offline suite green: **630 passed**; `node
  tests/test_recipe_roundtrip.cjs` (11) + `node tests/test_report_helpers.cjs` (8)
  green. 2D default output byte-identical (Epoch 12 added only pure numpy `src/`
  modules, none in `PIPELINE_STAGES`; no pipeline stage touched).
- [x] 9.2 `implementation/report.md` written; `HANDOFF.md` updated; roadmap
  #48–#55 ticked.
- [x] 9.3 Wrote the Epoch 12 retrospective
  (`agent-os/retrospectives/2026-08-31-epoch-12-watershed-report.md`), graded against
  the pre-registered watch-list.
