# Spec — Monthly-flow rendering option (roadmap #25)

## Overview

Promote the monthly-flow disaggregation and the fixed year-max width scale into
tested `src/` code, add a validated `--months` option, and refactor the tools to
consume the shared `src/` implementation. Default (`annual`) keeps builds
byte-identical. Follows the #23 precedent: promote pure algorithms + option
surface; defer the discharge/climatology loader plumbing and multi-frame export.

## `src/monthly_flow.py` (new, numpy-only, offline)

Copied verbatim from `tools/monthly_flow.py` (same numeric behavior), minus the
pyogrio reads:

```python
MONTHS = range(1, 13)
MONTH_ABBR = ["Jan", ..., "Dec"]
T_ALL_SNOW, T_ALL_RAIN, T_MELT, T_MELT_FULL = -1.0, 3.0, 0.0, 6.0
SPINUP_CYCLES = 3

def snow_available_water(precip_mm, temp_c): ...      # [n,12]
def normalize_shape(available): ...                   # mean-1 per reach
def accumulate_downstream(incr_monthly, hydroseq, dnhydroseq): ...  # [n,12]

def disaggregate_monthly(precip_mm, temp_c, q_incr, hydroseq, dnhydroseq):
    """shape = normalize_shape(snow_available_water(precip_mm, temp_c));
    incr_monthly = shape * clip(q_incr,0,None)[:,None];
    return accumulate_downstream(incr_monthly, hydroseq, dnhydroseq).
    Conserves each reach's annual mean."""
```

`__all__` exports the four functions + constants.

## `src/rendering.py` (add fixed-span width helpers, pure/stdlib)

```python
def fixed_flow_span(values, *, floor=1e-2) -> tuple[float, float]:
    """(lo, hi) = (log(min positive or floor), log(max positive or floor)) over
    ALL values — the fixed year-max log scale. Empty/degenerate → (l, l)."""

def widths_on_span(flows, lo, hi, *, width_min, width_max, floor=1e-2) -> dict[int,float]:
    """Map each flow onto [width_min,width_max] via
    t=clip((log(max(q,floor))-lo)/max(hi-lo,1e-9),0,1); fixed scale (clamped)."""

def monthly_width_frames(monthly, *, width_min, width_max, floor=1e-2) -> list[dict[int,float]]:
    """monthly: seg_id -> length-12 flows. Compute one span across all months,
    return 12 width dicts on it (seasonal change visible)."""
```

Added to `__all__`. These mirror `tools/render_monthly.fixed_widths` exactly
(`base_units`→`width_min`, `top_units`→`width_max`).

## Config (`src/config.py`)

- New `Settings.months: tuple[int, ...]` (empty = annual mean) + `DEFAULTS["months"] = "annual"`.
- `parse_months(value) -> tuple[int, ...]` (pure; no numpy):
  - `None`/`""`/`annual`/`all`/`mean` → `()`.
  - single `"7"` / `"jul"` / `"july"` → `(7,)`.
  - range `"5-9"` / `"may-sep"` → `(5,6,7,8,9)`; wrapping `"nov-feb"` → `(11,12,1,2)`.
  - Month names via a local lowercase abbr/full map (kept in `config.py` to avoid
    importing numpy). Out-of-range/garbage → `ConfigError`.
- `build_settings` calls `parse_months`; stores the tuple.

## CLI (`src/cli.py`)

- New `--months` flag (default `None`) mapped to the flat `months` override key.

## Pipeline (`src/pipeline.py`)

- At the top of `_generate_svg_stage`, if `ctx.settings.months` is non-empty:
  `raise ConfigError("months=<abbrs> needs per-reach monthly discharge/"
  "climatology, which the 2D pipeline does not load. Use "
  "tools/render_monthly.py for month-by-month frames, or leave --months annual.")`
- `months == ()` (annual, default) → stage unchanged → byte-identical SVG.

## Tool refactor (`tools/`)

- `tools/monthly_flow.py`: import constants + math from `src.monthly_flow`
  (re-export `MONTHS`, `MONTH_ABBR`, `snow_available_water`, `normalize_shape`,
  `accumulate_downstream`); keep `_value_column`/`_load_monthly` (GDB reads);
  `build_monthly_flow` now reads arrays and returns
  `disaggregate_monthly(precip, temp, q_incr, hydroseq, dnhydroseq)` (+ ids, qama).
- `tools/render_monthly.py`: `fixed_widths(month_flow, base_units, top_units, lo, hi)`
  delegates to `src.rendering.widths_on_span(month_flow, lo, hi,
  width_min=base_units, width_max=top_units, floor=FLOOR)`. Keep `FLOOR`.

## Determinism & byte-identical default

- `months` default `annual` → `()` → `_generate_svg_stage` unchanged.
- All new `src/` functions are pure functions of their inputs.

## Testing (offline)

- `test_monthly_flow.py`: snow bucket (cold accumulates, warm melts, spin-up
  periodic), normalize_shape (mean 1 / degenerate uniform), accumulate_downstream
  (downstream = sum of upstream by HydroSeq), disaggregate_monthly (mass
  conservation; snowmelt headwater shifts a downstream peak).
- `test_rendering.py` (add): fixed_flow_span endpoints + floor + degenerate;
  widths_on_span endpoints/clamp/fixed-scale; monthly_width_frames wet>dry per seg.
- `test_config.py` (add): months default `()`; single/name/range/wrap; invalid raises.
- `test_cli.py` (add): `--months` override; unset keeps YAML.
- `test_monthly_pipeline.py` (new): non-annual months → `ConfigError`; annual
  default builds an SVG unchanged.

## Out of scope (deferred)

- Discharge/climatology loader→graph plumbing + multi-frame export (live
  `build.py --months`, part of #27).
- Interpolation/activation/GIF (tool-only).
- Web control-surface `--months` (#26).
