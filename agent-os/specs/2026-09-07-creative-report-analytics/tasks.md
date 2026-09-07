# Tasks — Creative report analytics (Epoch 17)

One roadmap item at a time. Only Task Group 1 (#69) is implemented this session.

## Task Group 1 — #69 Snow-vs-rain regime signature

- [x] 1.0 Tests first (run only these):
  - [x] 1.1 `tests/test_monthly_flow.py` — `snow_available_components` sums to
    `snow_available_water` (byte-identical); all-warm → ~0 melt; cold→warm spike lands in melt bucket.
  - [x] 1.2 `tests/test_flow_metrics.py` — `snow_fraction` (snow-heavy vs rain-heavy, `[n,12]`
    vectorization, all-zero→0), `classify_regime` (boundaries, bad thresholds, array labels),
    `snow_regime` (label + melt center month), `melt_timing_trend` (earlier-each-decade shift → neg
    `days_per_decade`, `trend=="decreasing"`; <3 years errors).
- [x] 1.2 `src/monthly_flow.py` — add `snow_available_components`; refactor `snow_available_water`
  to reuse it (byte-identical); export in `__all__`.
- [x] 1.3 `src/flow_metrics.py` — add `snow_fraction`, `REGIME_SNOW_MIN`/`REGIME_RAIN_MAX`,
  `classify_regime`, `SnowRegime` + `snow_regime`, `MeltTimingTrend` + `melt_timing_trend`; export all.
- [x] 1.4 Run the two test modules only; green.
- [x] 1.5 Tick roadmap #69; write `implementation/report.md`.
- [x] 1.6 Full offline suite for regressions; confirm no `PIPELINE_STAGES` touched (2D byte-identical).

## Task Group 2 — #70 Center-of-timing drift panel

- [x] 2.1 Tests (`tests/test_flow_metrics.py`) — `center_of_timing_trend` detects an earlier-peak
  shift (neg `days_per_decade`, `trend=="decreasing"`) and a later-peak shift (pos, `"increasing"`);
  agrees with `melt_timing_trend` on the same input; `<3` years errors.
- [x] 2.2 `src/flow_metrics.py` — add `TimingTrend` + `center_of_timing_trend`; extract shared
  `_coerce_year_rows`; refactor `melt_timing_trend` to delegate (keep `MeltTimingTrend` API). Export.
- [x] 2.3 Full offline suite green (865); roadmap #70 ticked; report updated. No `PIPELINE_STAGES`.
## Task Group 3 — #71 Analog-year finder

- [x] 3.1 Tests (`tests/test_flow_metrics.py`) — `analog_years` ranks by monthly *shape* not
  magnitude (scale-invariant match r≈1 first, anti-phase last); top-`n` truncation excludes target;
  constant year → `nan` sorts last; target-not-in-series / non-`[12]` / `n<1` guards.
- [x] 3.2 `src/flow_metrics.py` — add `AnalogYear` + `analog_years(series, target, n=None)` over
  `pearson_r`, deterministic nan-last sort. Export.
- [x] 3.3 Full offline suite green (869); roadmap #71 ticked; report updated. No `PIPELINE_STAGES`.
## Task Group 4 — #72 Drought/flood record book

- [x] 4.1 Tests (`tests/test_flow_metrics.py`) — `rank_years` ascending/descending, 1-based rank +
  percentile attach, year tie-break, top-`n`, `<2` years / `n<1` guards; `record_book` picks the
  driest summer and the wettest-peak year from a `{year:[12]}` series.
- [x] 4.2 `src/flow_metrics.py` — add `YearRank`/`RecordBook` + `rank_years` + `record_book` over
  `percentile_rank`. Export.
- [x] 4.3 Full offline suite green (874); roadmap #72 ticked; report updated. No `PIPELINE_STAGES`.
## Task Group 5 — #73 Flow-duration-curve panel

- [x] 5.1 Tests (`tests/test_flow_metrics.py`) — `decade_flow_duration` groups by decade, per-decade
  FDC non-increasing in q (q=0 pooled max, q=100 pooled min), a wetter decade shifts the curve up,
  `decade_size` re-bins, non-`[12]` guard.
- [x] 5.2 `src/flow_metrics.py` — add `DecadeFDC` + `decade_flow_duration` delegating to
  `flow_duration` over pooled decade months. Export.
- [x] 5.3 Full offline suite green (877); roadmap #73 ticked; report updated. No `PIPELINE_STAGES`.
## Task Group 6 — #74 ENSO/PDO composite hydrographs · not started
## Task Group 7 — #75 Longitudinal flow-accumulation animation · not started
## Task Group 8 — #76 Report assembly & web surfacing · not started
