# Requirements — Color & line-width art-direction options (roadmap #23)

## Source

Roadmap Epoch 6, item #23:

> Color & line-width art-direction options — Promote the "proposed" style controls into
> `src/config.py`/`src/cli.py`/`src/rendering.py` as validated options: `color_by`
> (`watershed`|`single`|`elevation`, the last mirroring `tools/render_state_mono.py`'s
> hypsometric tint) and `width_by` (`flow`|`uniform`) with min/max/gamma. Deterministic;
> defaults keep existing builds byte-identical. `M`

The web control surface (`web/shared/hydro-ux.js`) already emits these as **(proposed)**
flags: `--color-by elevation`, `--single-color`, `--width-by flow --width-min --width-max`,
and the YAML keys `color_by`, `single_color`, `width_by`, `line_width_min`, `line_width_max`,
`flow_gamma`. This item makes them real, validated, first-class options so the control surface
can drop the `(proposed)` marker for #23.

## Functional requirements

1. **`color_by`** ∈ {`watershed`, `single`, `elevation`}, default `watershed`.
   - `watershed` — current behavior: deterministic high-contrast palette per HUC group.
   - `single` — paint every flowline one color (`single_color`).
   - `elevation` — hypsometric tint (deep-blue sea → white summit), mirroring
     `tools/render_state_mono.py`.
2. **`single_color`** — hex color used by `color_by=single`, default `#00ffff` (neon cyan).
3. **`width_by`** ∈ {`uniform`, `flow`}, default `uniform`.
   - `uniform` — every stroke is the base `line_width` (current behavior).
   - `flow` — stroke widens with a channel's flow, mapped `[width_min, width_max]` shaped by
     `width_gamma`.
4. **`width_min` / `width_max` / `width_gamma`** — floats. Defaults `0.35` (== `line_width`
   default), `2.0`, `1.0`. Validation: `width_min > 0`, `width_max > 0`,
   `width_max >= width_min`, `width_gamma > 0`.
5. All six options are settable via **YAML and CLI** with the established
   `defaults < YAML < CLI` precedence; unset CLI flags never clobber YAML.
6. **Defaults keep existing builds byte-identical.** With `color_by=watershed` and
   `width_by=uniform` the emitted SVG is unchanged from before this item.
7. **Deterministic** — identical inputs yield identical output; no randomness.

## Non-functional / boundary constraints

- Validation lives in `build_settings` (`src/config.py`) against allowlists — the single
  source of truth, raising `ConfigError` with user-facing messages.
- The elevation ramp and the flow→width mapping are **pure functions in `src/rendering.py`**,
  unit-testable with hand-built inputs (no GDAL, no real data), and reusable by the `tools/`
  renderers so the recipe stays single-sourced.

## Data-availability decisions (RESOLVED 2026-08-12)

The core 2D pipeline graph carries only `segment_id`/`geometry`/`length`/`huc4` (see
`src/graph.py`); it does **not** load per-segment discharge (`QAMA`) or smoothed elevation
(`MinElevSmo`/`MaxElevSmo`) — those are read directly from the GDB only by the `tools/`
renderers. That constrains what each pipeline mode can do today:

1. **`color_by=single`** — fully wired into the pipeline (no new data needed).
2. **`width_by=flow`** — wired using the pipeline's available flow proxy: the computed
   `stream_orders` / `max_stream_order` (PRD §17 width scaling). True EROM-discharge scaling
   remains a `tools/` capability; the pipeline documents that `flow` scales by stream order.
3. **`color_by=elevation`** — has **no** per-segment metric in the 2D pipeline and no proxy, so
   selecting it raises a clear, actionable error from the `assign_colors` stage pointing at the
   DEM subsystem / `tools/render_state_mono.py`. The rendering primitive
   (`hypsometric_colors`) is still delivered and tested so the tool shares one recipe and a
   future data-plumbing item lights up the pipeline path.

Rationale: options are validated first-class (so web/YAML/CLI are real), the byte-identical
default holds, and we neither silently mislead (elevation → wrong colors) nor over-reach into
loader/graph data plumbing that belongs to a later item.
