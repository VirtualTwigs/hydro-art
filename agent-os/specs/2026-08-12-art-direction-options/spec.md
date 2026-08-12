# Spec — Color & line-width art-direction options (roadmap #23)

## Overview

Add six validated art-direction options across `src/config.py`, `src/cli.py`, and
`src/rendering.py`, and wire them into the pipeline where the core data model supports them.
Defaults (`color_by=watershed`, `width_by=uniform`) keep existing builds byte-identical.

## Config (`src/config.py`)

New allowlists:

```python
SUPPORTED_COLOR_MODES: tuple[str, ...] = ("watershed", "single", "elevation")
SUPPORTED_WIDTH_MODES: tuple[str, ...] = ("uniform", "flow")
```

New `Settings` fields (with `DEFAULTS`):

| field         | type  | default    | validation                              |
|---------------|-------|------------|-----------------------------------------|
| `color_by`    | str   | `watershed`| in `SUPPORTED_COLOR_MODES`              |
| `single_color`| str   | `#00ffff`  | hex (`_HEX_COLOR`)                      |
| `width_by`    | str   | `uniform`  | in `SUPPORTED_WIDTH_MODES`              |
| `width_min`   | float | `0.35`     | `> 0`                                   |
| `width_max`   | float | `2.0`      | `> 0` and `>= width_min`                |
| `width_gamma` | float | `1.0`      | `> 0`                                   |

`build_settings` validates each at the boundary, raising `ConfigError` with a clear message.
`color_by`/`width_by` are lowercased before lookup (like `stream_method`).

## CLI (`src/cli.py`)

New flags (all default `None` so unset never clobbers YAML), mapped in `cli_overrides`:

- `--color-by` → `color_by`
- `--single-color` → `single_color`
- `--width-by` → `width_by`
- `--width-min` (`type=float`) → `width_min`
- `--width-max` (`type=float`) → `width_max`
- `--width-gamma` (`type=float`) → `width_gamma`

These are flat top-level keys (not nested), so the existing shallow `merge_values` suffices —
no deep-merge block needed.

## Rendering primitives (`src/rendering.py`)

Two new pure, deterministic functions (added to `__all__`):

```python
def hypsometric_colors(
    elevations: Mapping[int, float],
    *,
    gamma: float = 0.75,
    anchor: float | None = None,
    low: tuple[int, int, int] = (26, 72, 156),   # deep blue (sea level)
    high: tuple[int, int, int] = (255, 255, 255), # white (summit)
) -> dict[int, str]:
    """Map per-segment elevation (m) → deep-blue..white hex, anchored at the max.

    t = clip(elev / anchor, 0, 1) ** gamma; sea level → low, anchor → high.
    anchor defaults to max(elevations). Degenerate (anchor<=0) → all low.
    Promoted from tools/render_state_mono.elevation_colors so the tool and the
    pipeline share one tested ramp.
    """

def scaled_widths(
    metric: Mapping[int, float],
    *,
    width_min: float,
    width_max: float,
    gamma: float = 1.0,
    log: bool = False,
) -> dict[int, float]:
    """Normalize a per-segment metric to [0,1] (optionally on log), shape by
    gamma, and map to [width_min, width_max]. Degenerate (single value / empty
    span) → uniform width_min. Deterministic."""
```

`scaled_widths` is the general width resolver: the pipeline calls it with `stream_orders`
(`log=False`); the tools can call it with discharge (`log=True`). Existing `flow_widths` /
`stream_order_widths` are left untouched (still used by the tools and their tests).

## Pipeline wiring (`src/pipeline.py`)

**`_assign_colors_stage`** branches on `ctx.settings.color_by`:

- `watershed` (default): unchanged — `assign_colors(graph, watersheds, palette)`.
- `single`: `segment_colors = {sid: single_color for every segment}`; `watershed_colors`
  becomes `{code: single_color}`. Deterministic, no new data.
- `elevation`: raise `ConfigError` — per-segment elevation is not available in the 2D
  pipeline; message points to the DEM subsystem / `tools/render_state_mono.py`.

**`_generate_svg_stage`** branches on `ctx.settings.width_by`:

- `uniform` (default): `stroke_widths=None` → base `line_width` (byte-identical).
- `flow`: `stroke_widths = scaled_widths(stream_orders, width_min, width_max, width_gamma)`
  using `ctx.artifacts["stream_orders"]` (the flow proxy). Passed to `render_svg`.

No change to `render_svg`'s signature or output for the default path, guaranteeing the
byte-identical guarantee holds trivially.

## Determinism & byte-identical default

- Default `color_by=watershed` + `width_by=uniform` → `assign_colors` and `generate_svg` take
  exactly their current code paths; SVG bytes unchanged.
- All new helpers are pure functions of their inputs with fixed formatting.

## Out of scope (deferred)

- Loading per-segment `QAMA`/elevation into the core pipeline (loader/graph plumbing) — a
  follow-on to light up `color_by=elevation` and true-discharge `width_by=flow` in `build.py`.
- The `--county` (#24) and `--months` (#25) options.
- Updating the web control surface to drop the `(proposed)` marker (belongs with #26 polish).
