# Specification: Optional Glow & SVG Optimization

## Goal
Add an optional neon glow to the rendered SVG (pure-vector or Gaussian-blur, configurable radius) and run the result through SVGO to shrink/clean it — wired into the `optimize_svg` pipeline stage behind an injectable seam so tests stay offline. Glow-off output stays byte-identical to item #8.

## User Stories
- As a user, I want an optional neon glow around my rivers so the art looks like glowing neon cartography, in either a filter-based or pure-vector style.
- As a user, I want the final SVG automatically optimized (smaller, de-duplicated) so it's easy to ship and print.
- As a developer, I want glow as a pure render option and SVGO behind an injected seam so both are fully testable without Node, a browser, or real data.

## Specific Requirements

**Glow config (`src/config.py`, `src/cli.py`)**
- Add `SUPPORTED_GLOW_MODES = ("vector", "blur")` (exported); `glow_mode` default `"blur"`, validated in `build_settings` (raise `ConfigError` listing valid modes).
- Add `glow_radius` default `2.0`; validated as a number `> 0` in `build_settings` (raise `ConfigError`).
- Extend `Settings` with `glow_mode: str` and `glow_radius: float`.
- Add `--glow-mode` and `--glow-radius` CLI flags (default `None`); map through `cli_overrides`. Show both in `build.py`'s resolved-settings table.

**Glow rendering (`src/rendering.py`)**
- Extend `render_svg(..., glow=False, glow_mode="blur", glow_radius=2.0)`:
  - `glow=False` → output identical to item #8 (no defs content, no halos).
  - **Blur:** populate `<defs>` with `<filter id="hydro-glow" …><feGaussianBlur stdDeviation="<radius>" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`; add `filter="url(#hydro-glow)"` to each river `<g>`.
  - **Vector:** for each river group, emit a preceding halo `<g id="<id>_glow" stroke="<color>" stroke-width="<line_width + 2*glow_radius>" stroke-opacity="0.4">` with the same `<path>`s, then the sharp group on top. No filter.
  - Deterministic; formatted via the existing `format_number`.

**SVGO optimization seam (`src/optimize.py`, new)**
- `SvgOptimizer` protocol: `optimize(svg: str) -> str`.
- `SvgoOptimizer` (real): shells out to the `svgo` CLI (stdin→stdout) via `subprocess`; on `FileNotFoundError`/non-zero exit, return the input unchanged and emit a warning (never crash). Injectable, no import-time subprocess.
- `OptimizeError` (subclasses `AcquisitionError`) for unexpected failures if needed.

**Pipeline integration (`src/pipeline.py`)**
- Add an `optimizer: SvgOptimizer` field to `RunContext` and a `Pipeline.__init__` param (default `SvgoOptimizer()`), mirroring `downloader`/`loader`.
- `generate_svg` passes `glow=settings.glow`, `glow_mode=settings.glow_mode`, `glow_radius=settings.glow_radius` into `render_svg`.
- Replace the `optimize_svg` stub: read `artifacts["svg"]`, run `ctx.optimizer.optimize(...)`, store `artifacts["optimized_svg"]`, log before→after byte sizes. `export` remains a stub.

## Existing Code to Leverage
- **`src/rendering.py`:** `render_svg` structure + `format_number`; the bare `<defs/>` placeholder becomes populated when glow is on.
- **`src/config.py` / `src/cli.py`:** `SUPPORTED_*` allowlist + `build_settings` validation pattern, `ConfigError`, `cli_overrides` (the `glow` bool + `--glow` flag already exist).
- **`src/pipeline.py`:** `RunContext`/`Pipeline` DI pattern (`downloader`, `loader`) extended with `optimizer`; `generate_svg` already produces `artifacts["svg"]`.
- **`src/datasets.py`:** `AcquisitionError` base for a new `OptimizeError`.

## Out of Scope
- Multi-format export (PDF/PNG/TIFF/EPS) and writing files to disk — item #10.
- Installing/bundling SVGO or Node; byte-identical guarantees *through* SVGO (host-tool dependent) — reproducibility hardening is item #10.
- Multi-layer/animated glow, per-watershed glow tuning, configurable halo opacity — a single halo layer / single filter is sufficient.
- New palettes, width-scaling config flags, or geometry changes.
- Loading real datasets or running real SVGO/Node in tests — glow is tested on hand-built SVGs; the optimizer is tested via an injected fake.
