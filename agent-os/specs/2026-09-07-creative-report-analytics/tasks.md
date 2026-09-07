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

## Task Group 2 — #70 Center-of-timing drift panel · not started
## Task Group 3 — #71 Analog-year finder · not started
## Task Group 4 — #72 Drought/flood record book · not started
## Task Group 5 — #73 Flow-duration-curve panel · not started
## Task Group 6 — #74 ENSO/PDO composite hydrographs · not started
## Task Group 7 — #75 Longitudinal flow-accumulation animation · not started
## Task Group 8 — #76 Report assembly & web surfacing · not started
