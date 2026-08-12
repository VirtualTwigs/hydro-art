# Implementation Report — Color & line-width art-direction options (roadmap #23)

_Implemented 2026-08-12._

## Summary

Promoted the web control surface's `(proposed)` style controls into first-class, validated,
deterministic options across `src/config.py`, `src/cli.py`, and `src/rendering.py`, and wired
them into the pipeline where the core 2D data model supports them. Defaults keep existing
builds byte-identical.

## What shipped

**Config (`src/config.py`)** — new allowlists `SUPPORTED_COLOR_MODES`
(`watershed`|`single`|`elevation`) and `SUPPORTED_WIDTH_MODES` (`uniform`|`flow`); six new
`Settings` fields with `DEFAULTS` and boundary validation in `build_settings`:
`color_by` (default `watershed`), `single_color` (`#00ffff`), `width_by` (`uniform`),
`width_min` (`0.35`), `width_max` (`2.0`), `width_gamma` (`1.0`). Invalid values raise
`ConfigError` (bad mode, bad hex, `width_min<=0`, `width_max<width_min`, `width_gamma<=0`).

**CLI (`src/cli.py`)** — six flags (`--color-by`, `--single-color`, `--width-by`,
`--width-min`, `--width-max`, `--width-gamma`), all defaulting to `None` and mapped in
`cli_overrides` as flat keys, so the `defaults < YAML < CLI` precedence holds and unset flags
never clobber YAML.

**Rendering (`src/rendering.py`)** — two pure, deterministic primitives added to `__all__`:
- `hypsometric_colors(elevations, *, gamma, anchor, low, high)` — deep-blue→white elevation
  ramp, promoted from `tools/render_state_mono.elevation_colors` so tool and pipeline share
  one tested recipe.
- `scaled_widths(metric, *, width_min, width_max, gamma, log)` — general width resolver
  (linear or log normalization, gamma shaping, degenerate→uniform). Existing `flow_widths` /
  `stream_order_widths` left untouched.

**Pipeline (`src/pipeline.py`)**:
- `_assign_colors_stage` branches on `color_by`: `watershed` unchanged; `single` paints every
  segment `single_color`; `elevation` raises a clear `ConfigError` (no per-segment elevation
  in the 2D pipeline — points at the tools / DEM subsystem).
- `_generate_svg_stage` branches on `width_by` via the new `_resolve_stroke_widths` helper:
  `uniform` → `None` (base `line_width`, byte-identical); `flow` → `scaled_widths` over the
  computed `stream_orders` (the pipeline's flow proxy).

## Design decisions (see planning/requirements.md)

The core pipeline graph carries no per-segment discharge or elevation (only
`segment_id`/`geometry`/`length`/`huc4`). So: `single` is fully wired; `flow` scales by stream
order as the available proxy (true QAMA remains a `tools/` capability); `elevation` fails fast
rather than silently miscoloring. All three modes' rendering primitives are delivered and
tested, so future loader/graph data-plumbing lights up the pipeline paths without further
rendering work.

## Tests

- `tests/test_config.py` (+8): defaults byte-identical baseline, normalization, and each
  invalid-value `ConfigError`.
- `tests/test_cli.py` (+2): all six flags parse; unset flags keep YAML.
- `tests/test_rendering_svg.py` (+4): `hypsometric_colors` anchors/gamma/degenerate;
  `scaled_widths` endpoints/gamma/log/degenerate.
- `tests/test_rendering_pipeline.py` (+4): default has no per-path widths; `single` one color;
  `elevation` raises; `flow` scales stroke widths (mainstem widest).

Full suite: **294 passed** (was 276), no regressions. Offline (no GDAL/network). Smoke test:
defaults unchanged; `single`+`flow` settings and both primitives run clean.

Note: `ruff` is not installed in this offline `.venv`, so the lint step wasn't run here.

## Out of scope / follow-ups

- Loading real `QAMA`/elevation into the core pipeline (loader/graph) to fully light up
  `color_by=elevation` and true-discharge `width_by=flow` in `build.py`.
- Dropping the web control surface's `(proposed)` marker for these flags (#26 polish).
- `--county` (#24) and `--months` (#25).
