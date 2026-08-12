# Task Breakdown — Color & line-width art-direction options (roadmap #23)

TDD: write 2–8 tests first per group, run only those, then implement until green.

## Task Group 1: Config options (`src/config.py`)

- [x] Tests (`tests/test_config.py`): defaults for the six new fields; byte-identical defaults
  (`color_by=watershed`, `width_by=uniform`); valid overrides accepted; each invalid value
  raises `ConfigError` (bad `color_by`, bad `width_by`, bad `single_color` hex,
  `width_min<=0`, `width_max<width_min`, `width_gamma<=0`).
- [x] Add `SUPPORTED_COLOR_MODES` / `SUPPORTED_WIDTH_MODES`, `DEFAULTS` entries, `Settings`
  fields, and `build_settings` validation. Extend `__all__`.

## Task Group 2: CLI flags (`src/cli.py`)

- [x] Tests (`tests/test_cli.py`): each new flag parses into the right override key; unset
  flags produce no override key (YAML survives); precedence `defaults < YAML < CLI` holds for
  at least one of the new options.
- [x] Add the six flags to `build_parser` and map them in `cli_overrides`.

## Task Group 3: Rendering primitives (`src/rendering.py`)

- [x] Tests (`tests/test_rendering.py`): `hypsometric_colors` — sea level → low, anchor →
  high, gamma monotonic, degenerate all-zero → all low; `scaled_widths` — endpoints map to
  width_min/width_max, gamma monotonic, degenerate single value → uniform width_min, `log`
  path orders by magnitude.
- [x] Implement `hypsometric_colors` and `scaled_widths`; add to `__all__`.

## Task Group 4: Pipeline wiring (`src/pipeline.py`)

- [x] Tests (`tests/test_render_pipeline.py` or the pipeline integration test): `color_by=single`
  paints all segments `single_color`; `color_by=elevation` raises `ConfigError`;
  `width_by=flow` produces per-segment `stroke_widths` (mainstem wider than headwater);
  default (`watershed`/`uniform`) SVG is byte-identical to pre-change output.
- [x] Wire `_assign_colors_stage` (color_by) and `_generate_svg_stage` (width_by).

## Task Group 5: Verification & docs

- [x] Write `implementation/report.md`.
- [x] Tick these checkboxes; run the full suite for regressions.
- [x] Smoke-test: `build_settings({})` defaults unchanged; a `color_by=single` +
  `width_by=flow` settings object renders without error on a hand-built graph.
- [x] Report and STOP (commit is a separate explicit step).

## Verification gates

1. Default build SVG is byte-identical to pre-change output.
2. Every invalid option value raises `ConfigError` at the boundary.
3. New rendering primitives are pure/deterministic and covered by unit tests.
4. `color_by=single` and `width_by=flow` visibly change the render; `color_by=elevation`
   fails fast with a clear message.
5. Full suite green; `src/` stays GDAL-free and offline.
