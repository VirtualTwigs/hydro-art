# Requirements — Monthly-flow rendering option (roadmap #25)

## Goal

Promote the `tools/monthly_flow.py` disaggregation and the `tools/render_monthly.py`
fixed year-max width scale into first-class, tested `src/` capabilities, and add a
validated `--months` build option (single month, month range, or annual mean).
Mirrors the #23 pattern: the *pure algorithms* become shared, deterministic,
offline `src/` code (the single source of truth the tools and future web/live
runner consume); the heavy GDB reads stay behind the existing tool seams.

## Functional requirements

1. **`src/monthly_flow.py`** — pure, deterministic, numpy-only disaggregation
   promoted from `tools/monthly_flow.py`:
   - `snow_available_water(precip_mm, temp_c)` — temperature-index snow bucket
     with spin-up → monthly available water `[n, 12]`.
   - `normalize_shape(available)` — per-reach 12-month vector normalized to mean 1.
   - `accumulate_downstream(incr_monthly, hydroseq, dnhydroseq)` — route
     incremental monthly volumes downstream by HydroSeq.
   - `disaggregate_monthly(precip_mm, temp_c, q_incr, hydroseq, dnhydroseq)` —
     orchestrator returning accumulated monthly flow `[n, 12]` (cfs) that
     conserves each reach's annual mean (`mean_m Q ≈ accumulated QIncrAMA`).
   - Constants `MONTHS`, `MONTH_ABBR`, and the snow thresholds live here.
   No pyogrio/GDAL — operates on caller-supplied arrays, so it's offline-testable.

2. **`src/rendering.py`** — the fixed year-max width scale, promoted from
   `tools/render_monthly.fixed_widths`:
   - `fixed_flow_span(values, *, floor)` — one `(lo, hi)` log-span across *all*
     months' flows (the "compute once, hold fixed" trick).
   - `widths_on_span(flows, lo, hi, *, width_min, width_max, floor)` — map one
     frame's flows onto `[width_min, width_max]` on that fixed span (clamped).
   - `monthly_width_frames(monthly, *, width_min, width_max, floor)` — 12 width
     dicts on one shared span so seasonal swell/retreat is visible.

3. **`--months` option** (config + CLI): `annual` (default; annual mean =
   unchanged behavior), a single month (`7`/`jul`/`july`), or a range
   (`5-9`/`may-sep`, wrapping like `nov-feb`). Stored on `Settings` as a canonical
   `tuple[int, ...]` (empty = annual). Invalid months fail fast with `ConfigError`.

4. **Pipeline**: default (`annual`) is byte-identical. A non-annual `--months`
   fails fast in the pipeline with a clear `ConfigError` — per-reach monthly
   discharge/climatology isn't loaded by the 2D pipeline (same limitation as
   `color_by=elevation`); the message points to `tools/render_monthly.py` /
   the future live runner.

5. **Tool refactor**: `tools/monthly_flow.build_monthly_flow` reads the GDB then
   delegates the math to `src.monthly_flow.disaggregate_monthly`;
   `tools/render_monthly.fixed_widths` delegates to `src.rendering.widths_on_span`.
   Existing importable names (`build_monthly_flow`, `MONTH_ABBR`, `_value_column`,
   `FLOOR`, `fixed_widths`) stay so `render_infographic*.py` keep working.

## Non-functional / invariants

- `src/` stays offline/GDAL-free: `src/monthly_flow.py` imports only numpy (already
  a suite dependency via `clipping.py`); no pyogrio.
- Determinism: identical arrays → identical monthly flow and widths.
- Config precedence unchanged; `--months` defaults to `None` so it never clobbers
  YAML. Byte-identical default output.
- `src/` must not import `tools/`; the promotion moves logic the other way.

## Out of scope (deferred)

- Loading per-reach discharge/climatology into the core pipeline (loader/graph
  plumbing) and multi-frame SVG/PNG export — the follow-on that would light up a
  live `build.py --months` end-to-end run (part of #27 live integration).
- Frame interpolation / activation / GIF assembly (stay in `tools/render_monthly.py`).
- Web control-surface `--months` wiring (#26).
