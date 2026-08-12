# Implementation Report — Monthly-flow rendering option (roadmap #25)

Scope: "Promote algorithms + option" (mirrors #23). The pure disaggregation and
the fixed year-max width scale become tested `src/` code; a validated `--months`
option is added; the tools refactor to consume `src/`; the 2D pipeline fails fast
on non-annual months. Loader/graph discharge plumbing and multi-frame export stay
deferred (part of #27).

## What landed

### `src/monthly_flow.py` (new, numpy-only, offline)
Promoted verbatim (numeric behavior identical) from `tools/monthly_flow.py`,
minus the pyogrio reads:
- Constants: `MONTHS`, `MONTH_ABBR`, `T_ALL_SNOW/RAIN`, `T_MELT/_FULL`,
  `SPINUP_CYCLES`.
- `snow_available_water(precip_mm, temp_c)` — temperature-index snow bucket with
  3-cycle spin-up → `[n, 12]` available water.
- `normalize_shape(available)` — per-reach 12-month vector normalized to mean 1
  (uniform if degenerate).
- `accumulate_downstream(incr_monthly, hydroseq, dnhydroseq)` — descending-
  HydroSeq downstream routing.
- `disaggregate_monthly(precip_mm, temp_c, q_incr, hydroseq, dnhydroseq)` —
  orchestrator; conserves each reach's annual mean.
- `__all__` exports the four functions + constants. Imports only numpy.

### `src/rendering.py` (fixed-span width helpers)
- `fixed_flow_span(values, *, floor=1e-2)` — one `(lo, hi)` log-span over ALL
  values (empty/degenerate → `(log(floor), log(floor))`).
- `widths_on_span(flows, lo, hi, *, width_min, width_max, floor=1e-2)` — clamped
  fixed-scale flow→width mapping (mirrors `tools/render_monthly.fixed_widths`).
- `monthly_width_frames(monthly, *, width_min, width_max, floor=1e-2)` — 12 width
  dicts on one shared span so seasonal swell/retreat is visible.
- All three added to `__all__`.

### Config / CLI
- `DEFAULTS["months"] = "annual"`; `Settings.months: tuple[int, ...]` (empty =
  annual mean).
- `parse_months(value)` (pure, no numpy) — `annual/all/mean/""/None` → `()`;
  single `7`/`jul`/`july`; range `5-9`/`may-sep`; wrapping `nov-feb`; invalid →
  `ConfigError`. Month tokens live in `config.py` (`_MONTH_TOKENS`) to keep it
  numpy-free.
- `build_settings` calls `parse_months` and stores the tuple.
- `--months` CLI flag (default `None`) mapped to the `months` override key.

### Pipeline
- `_generate_svg_stage` raises `ConfigError` when `settings.months` is non-empty
  (same fail-fast pattern as `color_by=elevation`), pointing to
  `tools/render_monthly.py`. Annual (`()`, default) leaves the stage unchanged →
  byte-identical SVG.

### Tool refactor
- `tools/monthly_flow.py` imports + re-exports the promoted names from
  `src.monthly_flow`; keeps `_value_column`/`_load_monthly`; `build_monthly_flow`
  now delegates to `disaggregate_monthly`.
- `tools/render_monthly.py` `fixed_widths` delegates to
  `src.rendering.widths_on_span`; `FLOOR` kept.

## Tests
- `tests/test_monthly_flow.py` (new, 6): constants, snow bucket accum/release,
  normalize_shape mean-1/degenerate, downstream sum, mass conservation, snowmelt
  peak shift.
- `tests/test_rendering.py` (+5): span endpoints/floor/degenerate, widths clamp,
  fixed-not-renormalized, monthly frames wet>dry.
- `tests/test_config.py` (+3 incl. parametrized): default `()`, all parse forms,
  invalid raises, stored on settings.
- `tests/test_cli.py` (+2): `--months` override; unset keeps YAML.
- `tests/test_monthly_pipeline.py` (new, 2): non-annual → `ConfigError`; annual
  builds SVG.

## Verification
- Full suite: **345 passed** (was 310 at #24 commit).
- Smoke test: `build_settings({"months":"may-sep"}).months == (5,6,7,8,9)`;
  `disaggregate_monthly` conserves the annual mean on hand-built arrays; annual
  default `months == ()`.
- `src/` stays GDAL/pyogrio-free (numpy only in `monthly_flow.py`); tools compile
  and keep their importable names (`build_monthly_flow`, `MONTH_ABBR`,
  `_value_column`, `FLOOR`, `fixed_widths`).
- Byte-identical default: annual (`()`) does not touch `_generate_svg_stage`.

## Notes
- `ruff` is not installed in this environment (`No module named ruff`), so the
  lint step was skipped; code follows the existing style (line-length 88,
  `from __future__ import annotations`, typed public functions).
- Out of scope (deferred to #27): discharge/climatology loader→graph plumbing and
  multi-frame SVG/PNG export for a live `build.py --months` end-to-end run;
  interpolation/GIF (tool-only); web `--months` wiring (#26).
