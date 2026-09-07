# Specification: Creative report analytics (Epoch 17)

## Goal
Extend the watershed report with more engaging, source-honest panels built from statistics the
engine already computes and data already staged — no new data source, no rights gate, nothing in
`PIPELINE_STAGES`, 2D default output byte-for-byte identical.

## User Stories
- As a watershed-report buyer, I want to know whether my river is snowmelt- or rain-driven and
  whether that is shifting, so the report tells a personal climate story, not just a hydrograph.
- As a builder, I want each new statistic as a pure numpy-only `src/` function with offline tests,
  feeding `tools/report_common.py` figures, so the report deepens without touching the pipeline.

---

## Item #69 — Snow-vs-rain regime signature (this session)

The disaggregation model (`src/monthly_flow.snow_available_water`) already splits monthly precip
into rain vs. snow and releases a snowpack as melt, but it only returns the *combined* available
water (`rain + melt`). #69 exposes the snow bucket as a returned diagnostic, then classifies a
watershed's regime and measures how the melt pulse drifts across decades.

### `src/monthly_flow.py`
- Add `snow_available_components(precip_mm, temp_c) -> tuple[np.ndarray, np.ndarray]` returning
  `(rain[n,12], melt[n,12])` — the two buckets that currently sum inside `snow_available_water`.
  Same temperature-index physics, same 3-cycle spin-up.
- Refactor `snow_available_water` to `return sum(snow_available_components(...))` so it stays
  **byte-identical** (existing test `test_snow_bucket_accumulates_cold_and_releases_warm` still
  passes unchanged). Add `snow_available_components` to `__all__`.

### `src/flow_metrics.py` (report analytics; numpy-only, no `monthly_flow` import)
Accepts caller-supplied rain/melt arrays (the module's existing design), so it stays decoupled.

- `snow_fraction(rain, melt) -> float | np.ndarray` — annual snowmelt share of available water:
  `sum(melt) / sum(rain + melt)` over the 12 months. `[12]` → float; `[n,12]` → `[n]`.
  Degenerate all-zero year → `0.0` (no division warning).
- `REGIME_SNOW_MIN = 0.4`, `REGIME_RAIN_MAX = 0.2` module constants (art-direction thresholds).
- `classify_regime(fraction, *, snow_min=REGIME_SNOW_MIN, rain_max=REGIME_RAIN_MAX)
  -> str | np.ndarray` — `"snowmelt"` when `fraction >= snow_min`, `"rain"` when
  `fraction <= rain_max`, else `"transitional"`. Scalar → `str`; array → object `ndarray` of labels.
  Validate `0 <= rain_max < snow_min <= 1` else `FlowMetricsError`.
- `@dataclass(frozen=True) SnowRegime`: `snow_fraction: float`, `label: str`,
  `melt_center_month: float`. `snow_regime(rain, melt, *, snow_min, rain_max) -> SnowRegime`
  for a single aggregated watershed (`[12]` rain & melt): computes the fraction, the label, and the
  flow-weighted center month of the **melt** pulse (reusing `center_of_timing` on the melt vector;
  all-zero melt → `melt_center_month = float("nan")`).
- `@dataclass(frozen=True) MeltTimingTrend`: `years: tuple[int,...]`,
  `center_months: tuple[float,...]`, `slope_months_per_year: float`, `days_per_decade: float`,
  `trend: str`. `melt_timing_trend(yearly_melt, years=None) -> MeltTimingTrend` — `yearly_melt` is
  a `{year:[12]}` mapping or a `[years,12]` matrix of the melt pulse per calendar year. Computes
  each year's melt center-of-timing, then `sens_slope` over those centers (months/year) and the
  `mann_kendall` verdict; `days_per_decade = slope_months_per_year * 10 * 30.4368` (mean days per
  month). Negative `days_per_decade` = the melt pulse arriving earlier ("your river is becoming a
  rain river"). Needs ≥ 3 years (reuses the `mann_kendall` guard) — fewer raises `FlowMetricsError`.
  Years default to `range(len)` when a matrix is passed; a mapping is sorted by year.

Export all new names in `__all__`. Add a `# --- #69 snow-vs-rain regime ---` section header.

### Tests
- `tests/test_monthly_flow.py`: `snow_available_components` sums to `snow_available_water`
  (byte-identical); an all-warm climate yields ~0 melt (all rain); the cold→warm case puts the
  spike in the melt bucket, not the rain bucket.
- `tests/test_flow_metrics.py`: `snow_fraction` on a hand snow-heavy vs rain-heavy year; `[n,12]`
  vectorization; all-zero → 0. `classify_regime` boundaries + bad-threshold error + array labels.
  `snow_regime` returns correct label + melt center month on a spring-melt vector. `melt_timing_trend`
  detects an imposed earlier-each-decade shift (negative `days_per_decade`, `trend == "decreasing"`)
  and errors on < 3 years.

### Non-goals (#69)
No web/report changes, no `tools/` figure yet (those land with #76). No change to
`snow_available_water`'s numeric output. No `PIPELINE_STAGES` edit.

---

## Items #70–#76
Specified in `planning/requirements.md`; implemented one at a time on later commands. Each follows
the same template: pure numpy `src/flow_metrics.py` (or a sibling) function + offline tests, then a
`tools/report_common.py` figure and a `web/report.html` panel at assembly (#76).
