# Task Breakdown — Monthly-flow rendering option (roadmap #25)

TDD: write 2–8 tests first per group, run only those, then implement until green.

## Task Group 1: `src/monthly_flow.py` (disaggregation, numpy-only)

- [x] Tests (`tests/test_monthly_flow.py`): snow bucket (cold months accumulate,
  warm months release melt, spin-up makes the series periodic); `normalize_shape`
  (mean 1 per reach; degenerate all-zero → uniform); `accumulate_downstream`
  (downstream reach = sum of upstream increments by HydroSeq);
  `disaggregate_monthly` (annual-mean mass conservation; a snowmelt headwater
  shifts a downstream monthly peak).
- [x] Implement `MONTHS`, `MONTH_ABBR`, thresholds, `snow_available_water`,
  `normalize_shape`, `accumulate_downstream`, `disaggregate_monthly`; `__all__`
  exports the four functions + constants. Numpy only, no pyogrio.

## Task Group 2: `src/rendering.py` fixed-span width helpers

- [x] Tests (`tests/test_rendering.py`, add): `fixed_flow_span` endpoints +
  floor + degenerate (empty/all-zero → `(l, l)`); `widths_on_span`
  endpoints/clamp/fixed-scale; `monthly_width_frames` wet month > dry month
  per segment on one shared span.
- [x] Implement `fixed_flow_span`, `widths_on_span`, `monthly_width_frames`;
  add to `__all__`.

## Task Group 3: Config `--months` parsing (`src/config.py`)

- [x] Tests (`tests/test_config.py`, add): default `months == ()`; single
  `"7"`/`"jul"`/`"july"` → `(7,)`; range `"5-9"`/`"may-sep"` → `(5..9)`; wrap
  `"nov-feb"` → `(11,12,1,2)`; `annual`/`all`/`mean`/`""` → `()`; garbage/
  out-of-range raises `ConfigError`.
- [x] Add `parse_months`, `Settings.months`, `DEFAULTS["months"] = "annual"`;
  `build_settings` calls `parse_months` and stores the tuple.

## Task Group 4: `--months` CLI flag (`src/cli.py`)

- [x] Tests (`tests/test_cli.py`, add): `--months jul` parses into the `months`
  override; unset produces no `months` key (YAML survives).
- [x] Add `--months` to `build_parser` (default `None`) and map it in
  `cli_overrides`.

## Task Group 5: Pipeline fail-fast (`src/pipeline.py`)

- [x] Tests (`tests/test_monthly_pipeline.py`, new): a non-annual `months`
  settings raises `ConfigError` at `_generate_svg_stage`; an annual (default)
  run builds an SVG unchanged.
- [x] At the top of `_generate_svg_stage`, raise `ConfigError` when
  `ctx.settings.months` is non-empty; annual (`()`) leaves the stage unchanged.

## Task Group 6: Tool refactor (`tools/`)

- [x] `tools/monthly_flow.py`: import constants + math from `src.monthly_flow`
  (re-export `MONTHS`, `MONTH_ABBR`, `snow_available_water`, `normalize_shape`,
  `accumulate_downstream`); keep `_value_column`/`_load_monthly`;
  `build_monthly_flow` delegates to `disaggregate_monthly`.
- [x] `tools/render_monthly.py`: `fixed_widths` delegates to
  `src.rendering.widths_on_span`; keep `FLOOR`.

## Task Group 7: Verification & docs

- [x] Write `implementation/report.md`.
- [x] Tick these checkboxes; mark roadmap #25 `[x]`; update `HANDOFF.md`.
- [x] Run the full suite for regressions.
- [x] Smoke-test: `disaggregate_monthly` conserves an annual mean on hand-built
  arrays; `build_settings({"months": "may-sep"})` stores `(5,6,7,8,9)`.
- [x] Report and STOP (commit is a separate explicit step).

## Verification gates

1. Default (`annual`) build SVG + filename byte-identical to pre-change.
2. Non-annual `--months` raises `ConfigError` in the pipeline; garbage months
   raise `ConfigError` at config time.
3. All new `src/` functions are pure/deterministic and numpy/stdlib only.
4. Tool importer names (`build_monthly_flow`, `MONTH_ABBR`, `_value_column`,
   `FLOOR`, `fixed_widths`) still import after the refactor.
5. Full suite green; `src/` stays GDAL-free and offline.
