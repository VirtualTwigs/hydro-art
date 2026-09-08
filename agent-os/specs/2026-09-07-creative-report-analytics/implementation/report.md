# Implementation report — #69 Snow-vs-rain regime signature

**Date:** 2026-09-07 · **Epoch 17, Phase 17.1, item #69** · one roadmap item, then STOP.

## What shipped
Surfaced the snow bucket the disaggregation model already computes and turned it into a
report-ready regime story — all pure, numpy-only, offline-tested, nothing in `PIPELINE_STAGES`.

### `src/monthly_flow.py`
- New `snow_available_components(precip_mm, temp_c) -> (rain[n,12], melt[n,12])` — the two buckets
  that previously summed inside `snow_available_water`. Same temperature-index physics, same
  3-cycle spin-up (`pack` carried across cycles — the spin-up invariant preserved).
- `snow_available_water` now returns `rain + melt` from the new function. **Byte-identical**: the
  existing `test_snow_bucket_accumulates_cold_and_releases_warm` passes unchanged, and a new test
  asserts `rain + melt == snow_available_water(...)` exactly (`np.array_equal`).
- Exported `snow_available_components` in `__all__`.

### `src/flow_metrics.py` (numpy-only; no `monthly_flow` import — callers pass arrays)
- `snow_fraction(rain, melt)` — annual `Σmelt / Σ(rain+melt)`; `[12]`→float, `[n,12]`→`[n]`;
  all-zero year → `0.0` (guarded divide).
- `REGIME_SNOW_MIN=0.4`, `REGIME_RAIN_MAX=0.2` constants + `classify_regime(fraction, …)` →
  `snowmelt` / `transitional` / `rain`; scalar→`str`, array→object `ndarray`; validates
  `0 <= rain_max < snow_min <= 1`.
- `SnowRegime` dataclass + `snow_regime(rain, melt, …)` — fraction, label, and the melt pulse's
  center-of-timing (reusing `center_of_timing`; all-zero melt → `nan`).
- `MeltTimingTrend` dataclass + `melt_timing_trend(yearly_melt, years=None)` — accepts a
  `{year:[12]}` mapping or `[years,12]` matrix; per-year melt center-of-timing → `sens_slope`
  (months/year) + `mann_kendall` verdict; `days_per_decade = slope × 10 × 30.4368`. Negative =
  melt arriving earlier ("your river is becoming a rain river"). Needs ≥ 3 years.
- All six names exported in `__all__`; added a `# --- #69 …` section header.

## Tests
- `tests/test_monthly_flow.py` (+3): components sum to available water (byte-identical), all-warm →
  ~0 melt, cold→warm spike lands in the melt bucket not rain.
- `tests/test_flow_metrics.py` (+8): `snow_fraction` scalar/vector/all-zero; `classify_regime`
  boundaries, bad thresholds, array labels; `snow_regime` label + melt center; `melt_timing_trend`
  detects an imposed earlier-each-decade shift (negative `days_per_decade`, `trend=="decreasing"`),
  accepts a matrix, and errors on < 3 years.

Targeted run: `tests/test_monthly_flow.py tests/test_flow_metrics.py` → **61 passed**.

## Regression / discipline
- Full offline suite: **861 passed** (no GDAL/network).
- No `PIPELINE_STAGES` edit → 2D default render byte-for-byte identical.
- `flow_metrics`/`monthly_flow` stay numpy-only; no `tools`/`web`/GDAL imports at module scope.

## Not done (by design — later items)
No `tools/report_common.py` figure and no `web/report.html` panel yet — those land with #76
(report assembly & web surfacing). Items #71–#75 remain unchecked in `tasks.md`.

---

# Implementation report — #70 Center-of-timing drift as a hero metric

**Date:** 2026-09-07 · **Epoch 17, Phase 17.1, item #70** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `TimingTrend` dataclass (years, center_months, slope_months_per_year, days_per_decade, trend).
- `center_of_timing_trend(yearly_flow, years=None)` — per-year whole-hydrograph center-of-timing →
  `sens_slope` (months/yr) + `mann_kendall` verdict → `days_per_decade` (negative = peak arriving
  earlier: "the peak arrives N days earlier per decade"). Accepts a `{year:[12]}` mapping or a
  `[years,12]` matrix. Needs ≥ 3 years.
- Extracted `_coerce_year_rows` (mapping/matrix → `(years, rows)`), now shared with #69's
  `melt_timing_trend`, which delegates to `center_of_timing_trend` and repackages into
  `MeltTimingTrend` — **#69's public API and tests unchanged** (a test asserts the two agree on the
  same input). Exported `TimingTrend`/`center_of_timing_trend` in `__all__`.

## Tests (`tests/test_flow_metrics.py`, +4)
Earlier-peak shift → negative `days_per_decade`, `trend=="decreasing"` (6 decades); later-peak shift
→ positive, `"increasing"` (6 years, past Mann-Kendall significance); agreement with
`melt_timing_trend`; `<3` years raises.

Targeted run: `test_flow_metrics.py test_monthly_flow.py` → **65 passed**.

## Regression / discipline
Full offline suite **865 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76. Items #71–#75 remain unchecked.

---

# Implementation report — #71 Analog-year finder

**Date:** 2026-09-07 · **Epoch 17, Phase 17.2, item #71** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `AnalogYear` dataclass (`year`, `similarity`).
- `analog_years(series, target, *, n=None)` — ranks every year in a `{year:[12]}` series by Pearson
  correlation of its 12-month vector to the target year's, via `pearson_r`. Correlation removes
  mean/scale, so a wet year and a dry year with the same seasonal *shape* still read as analogs
  ("2015 looked most like 1934"). A constant year → `nan` similarity and sorts last; ties break by
  ascending year (deterministic); `n` keeps the top matches. Guards: target must be in the series,
  each value must be `[12]`, `n >= 1`. Private `_shape_similarity` maps the degenerate
  `FlowValidationError` to `nan`. Exported both names.

## Tests (`tests/test_flow_metrics.py`, +4)
Shape-not-magnitude ranking (scale-invariant match first, anti-phase last); top-`n` excludes target;
constant year → `nan` sorts last; the three guard errors.

Targeted run: `test_flow_metrics.py` → **60 passed**.

## Regression / discipline
Full offline suite **869 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76. Items #72–#75 remain unchecked.

---

# Implementation report — #72 Drought/flood record book

**Date:** 2026-09-07 · **Epoch 17, Phase 17.2, item #72** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `YearRank` (`year`, `value`, `rank`, `percentile`) and `RecordBook` (`driest_summers`,
  `wettest_years`) dataclasses.
- `rank_years(metric_by_year, *, ascending=True, n=None)` — ranks a `{year: value}` metric; rank 1 =
  smallest (drought) or largest (`ascending=False`, flood); each entry stamped with its
  `percentile_rank` position in the full record (direction-independent). Deterministic year
  tie-break; `n` bounds the list; needs ≥ 2 years.
- `record_book(series, *, summer_months=(6,7,8), n=5)` — reduces a `{year:[12]}` hydrograph series to
  a summer-low (min over summer months) and an annual peak (max over 12), then ranks the driest
  summers (ascending) and wettest years (descending). Exported all four names.

## Tests (`tests/test_flow_metrics.py`, +5)
`rank_years` ascending/descending + percentile + top-`n`; year tie-break; `<2` years and `n<1`
guards; `record_book` selects the driest-summer and highest-peak years with correct values.

Targeted run: `test_flow_metrics.py` → **65 passed**.

## Regression / discipline
Full offline suite **874 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76. Items #73–#75 remain unchecked.

---

# Implementation report — #73 Flow-duration-curve panel (decade overlays)

**Date:** 2026-09-07 · **Epoch 17, Phase 17.2, item #73** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `DecadeFDC` dataclass (`decade`, `quantiles`, `flows`).
- `decade_flow_duration(series, quantiles, *, decade_size=10)` — buckets a `{year:[12]}` series into
  decades (`year // decade_size * decade_size`), pools each decade's monthly flows, and computes the
  exceedance curve via `flow_duration`. Returns one `DecadeFDC` per decade, ascending, so overlaying
  them shows the whole distribution shifting over time (not just the mean). The log-scale plotting is
  the #76 web/tools panel; this is the stats behind it. Exported both names.

## Tests (`tests/test_flow_metrics.py`, +3)
Decade grouping + monotone-non-increasing FDC (q=0 pooled max, q=100 pooled min); a wetter decade
shifts the curve up; `decade_size=20` re-bins; non-`[12]` guard.

Targeted run: `test_flow_metrics.py` → **68 passed**.

## Regression / discipline
Full offline suite **877 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76. Items #74–#75 remain unchecked.

---

# Implementation report — #74 ENSO/PDO composite hydrographs

**Date:** 2026-09-07 · **Epoch 17, Phase 17.3, item #74** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `PhaseComposite` dataclass (per-phase mean hydrograph `warm`/`neutral`/`cool`, each `None` when
  empty, plus the member years).
- `composite_hydrographs(series, index_by_year, *, warm_min=0.5, cool_max=-0.5)` — over the years
  common to the `{year:[12]}` flow series and the climate index, classifies each warm (`>= warm_min`,
  El Niño / positive PDO), cool (`<= cool_max`, La Niña / negative PDO), or neutral, and averages the
  12-month hydrograph within each phase. Defaults are the standard ONI ±0.5 thresholds; reusable for
  PDO by sign. Exported both names.

## Tests (`tests/test_flow_metrics.py`, +3)
Warm/cool/neutral means (warm peaks spring, cool peaks winter); only common years counted (index-only
and series-only years dropped); empty phase → `None`; `cool_max < warm_min` and non-`[12]` guards.

Targeted run: `test_flow_metrics.py` → **71 passed**.

## Regression / discipline
Full offline suite **880 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76. Item #75 remains unchecked.

---

# Implementation report — #75 Longitudinal flow-accumulation animation

**Date:** 2026-09-07 · **Epoch 17, Phase 17.3, item #75** · one roadmap item, then STOP.

## What shipped
`src/flow_metrics.py`:
- `ProfileFrame` dataclass (`step`, `hydroseq`, `accum_flow`, `revealed`, `fraction`).
- `longitudinal_frames(accum_flow, hydroseq, dnhydroseq, path)` — walks the mouth-to-headwater
  `longitudinal_profile` one confluence at a time, emitting one `ProfileFrame` per path position:
  `revealed` is the accumulated-flow polyline from the mouth up to that step (the reveal for a
  progressive draw), and `fraction` is that step's accumulated flow over the mouth total (monotone in
  `[0,1]`, last `1.0`). A zero-mouth network yields all-`0` fractions (guarded divide). Validation from
  `longitudinal_profile` (bad `path`, shape mismatches) propagates unchanged. Exported both names.

## Tests (`tests/test_flow_metrics.py`, +4)
Progressive reveal (`revealed == profile[:step+1]`, `hydroseq`/`accum_flow` match per step); `fraction`
monotone in `[0,1]` with last `1.0`; zero-mouth → all `0` fractions; `longitudinal_profile` validation
errors propagate.

Targeted run: `test_flow_metrics.py` → **75 passed**.

## Regression / discipline
Full offline suite **884 passed**. No `PIPELINE_STAGES` edit → 2D default byte-for-byte identical.
`flow_metrics` stays numpy-only.

## Not done (later items)
`tools`/`web` surfacing lands with #76 — the report-assembly & web panels for all of #69–#75.

---

# Implementation report — #76 Report assembly & web surfacing

**Date:** 2026-09-07 · **Epoch 17, Phase 17.5, item #76** · the assembly item — **Epoch 17 close.**

## What shipped
The seven new statistics (#69–#75) were already pure/offline-tested in `src/flow_metrics.py`; #76 is
the surfacing glue. No `src/` change, nothing in `PIPELINE_STAGES`.

### `tools/report_common.py` (heavy GIS + matplotlib; outside every suite)
Five figures over the outlet `{year:[12]}` series (+ the climate index for composites), each driving
an already-tested `src.flow_metrics` function:
- `fig_timing_drift` — `center_of_timing_trend` (#70): per-year CT + Sen's-slope drift line, days/decade.
- `fig_analog_years` — `analog_years` (#71): horizontal bar of top-6 shape-similarity matches to the latest year.
- `fig_record_book` — `record_book` (#72): monospace driest-summer / wettest-peak leaderboards with percentiles.
- `fig_decade_fdc` — `decade_flow_duration` (#73): log-scale flow-duration curves, one viridis line per decade.
- `fig_composites` — `composite_hydrographs` (#74): warm/neutral/cool mean hydrographs (ONI ±0.5).

Wired into `build_report` behind a `creative=True` flag; `build_watershed_report.py` gains a
`--no-creative` toggle. Both files `py_compile` clean.

### `web/report.html` + `web/shared/hydro-ux.js` (shared foundation, `file://`-safe)
- Two **pure, node-loadable** helpers in `hydro-ux.js`: `classifyRegime(fraction, snowMin, rainMax)`
  (mirrors the Python `REGIME_SNOW_MIN=0.4`/`REGIME_RAIN_MAX=0.2` thresholds, validates
  `0<=rainMax<snowMin<=1`) and `centerOfTimingIndex(v)` (0-based flow-weighted month, `NaN` on empty/
  all-zero). Both exported.
- `sampleReport()` gains deterministic `regime`, `analogs`, `recordBook`, `fdc`/`fdcQuantiles`, and
  `composites` sections, derived from synthetic per-year hydrographs (a private `_pearson` powers the
  analog ranking). Existing `REPORT_SAMPLE` fields are untouched (new `rnd` draws only append), so the
  prior panels render identically.
- `report.html` adds five panels — snow-vs-rain regime badge, analog-year list, drought/flood record
  book, decade flow-duration overlay (stacked sparklines), and ENSO composite hydrographs — reusing
  `buildSparkline` and the existing tile styles.

## Scope note (honest data reality)
The report's flow series is flow-only, so #70–#74 wire directly. **#69** (snow regime) needs precip/temp
and **#75** (longitudinal animation) needs network topology — those remain render-tool territory; the
web report shows the regime as a synthetic **mock badge**, consistent with the page being a deterministic
sample export.

## Tests
- `tests/test_report_web.cjs` (+5, node/stdlib-only): `classifyRegime` boundaries + bad-threshold
  throws; `centerOfTimingIndex` weighting + `NaN` guards; `sampleReport()` carries the new sections with
  sane shapes (analogs descending; record ranks 1-first; FDC non-increasing in q; composites 12-long).
- `tests/test_recipe_roundtrip.cjs` unchanged (11) — still green.
- The `tools/` matplotlib figures are outside every suite (like all `tools/`); verified via `py_compile`.
  The inline `report.html` script was parse-checked and all `doc.*` fields it reads confirmed present.

Node: `test_report_web.cjs` **5** + `test_recipe_roundtrip.cjs` **11** green.

## Regression / discipline
Full offline Python suite **884 passed** (unchanged — no `src/` edit). No `PIPELINE_STAGES` edit → 2D
default byte-for-byte identical. `src/` stays GDAL/network-free; `tools/ → src/` dependency one-way;
`hydro-ux.js` stays Node-loadable (no top-level `document`/`window`).

## Not done
No live browser render check — no Chrome extension was connected this session; the page was verified
statically (script parses, sample-doc fields present) rather than visually.

---

# Epoch 17 close — Creative report analytics (#69–#76)

All eight items shipped one-at-a-time under the offline discipline: seven pure numpy-only
`src/flow_metrics.py` (+ `src/monthly_flow.py`) statistics with offline tests (#69–#75), then the
`tools/`/`web` assembly (#76). Nothing entered `PIPELINE_STAGES`; the 2D default render is byte-for-byte
unchanged throughout. Final: Python suite **884**; node **5+11**.
