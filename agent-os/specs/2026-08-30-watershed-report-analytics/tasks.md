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
- [ ] 3.5 (non-offline smoke) Validate the Salmon Creek model series against the
  real gauge; **record bias/r/NSE/seasonal skill** and the chosen framing verdict.

## Group 4 — Climate-index teleconnection (#51) · offline metrics + non-offline fetch

- [x] 4.1 Extend `tests/test_flow_validation.py`:
  - `align_index`: metric years {2014..2023} ∩ index years {2016..2025} → the 8
    common years, both arrays aligned; empty overlap → `FlowValidationError`.
  - `correlate`: a perfectly index-tracking metric → `1.0`; `lag=1` shifts the join
    by one year (hand-checked).
- [x] 4.2 Implement `align_index`/`correlate` in `src/flow_validation.py`.
- [x] 4.3 Run only these tests.
- [ ] 4.4 (non-offline) `tools/climate_index.py`: fetch + snapshot ENSO ONI / PDO;
  expose `index_by_year`. Smoke-correlate against Salmon Creek peak-flow; record r.

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

- [ ] 7.1 `tools/report_common.py`: shared load (reuse `_yoy_net_<huc4>.pkl` +
  clip caches) + watershed-reach selection + the matplotlib figure recipe.
- [ ] 7.2 `tools/build_watershed_report.py` CLI (`--huc4/--huc12/--name/--start/
  --end/[--gauge]`) → full figure set to `notebooks/figures/`.
- [ ] 7.3 Refactor `notebooks/salmon_creek_yoy.ipynb` to consume `report_common`;
  add long-record, validation, low-flow/salmon, and ENSO sections.
- [ ] 7.4 Smoke: build the Salmon Creek report end-to-end; eyeball each figure.

## Group 8 — Web report view (#55) · view-layer (proposed UX)

- [x] 8.1 Add shared components to `web/shared/ux.css` (`.metric-tile`,
  `.report-grid`, `.validation-badge`, `.chart-card`, `.sparkline`).
- [x] 8.2 Add report data/formatting helpers to `web/shared/hydro-ux.js`
  (Node-loadable — no top-level `document`/`window`); extend the headless
  `tests/test_recipe_roundtrip.cjs`-style harness for any new pure helper
  (`tests/test_report_helpers.cjs`).
- [x] 8.3 Build the report page over the shared foundation (`web/report.html`).

## Group 9 — Close out · offline

- [ ] 9.1 Run the full suite (regression check) + `node
  tests/test_recipe_roundtrip.cjs`; confirm the 2D default output byte-identical.
- [ ] 9.2 `implementation/report.md`; update `HANDOFF.md`; tick roadmap #48–#55.
- [ ] 9.3 Write the Epoch 12 retrospective (see `planning/pre-analysis.md` for the
  watch-list to close against).
