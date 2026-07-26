# Implementation Report: Optional Glow & SVG Optimization

**Date:** 2026-07-26
**Status:** Complete — all 3 task groups done, 134/134 tests passing (14 new)

## What was built

| File | Purpose |
|------|---------|
| `src/config.py` | Added `SUPPORTED_GLOW_MODES = ("vector", "blur")`; `glow_mode` (default `"blur"`) + `glow_radius` (default `2.0`) to `DEFAULTS` and the `Settings` dataclass; boundary validation in `build_settings` (mode allowlist + positive-number radius) raising `ConfigError`. |
| `src/cli.py` | `--glow-mode` / `--glow-radius` flags (default `None` so unset never clobbers YAML); added to `cli_overrides`. |
| `build.py` | `glow_mode` / `glow_radius` rows in the settings table. |
| `src/rendering.py` | Optional glow in `render_svg`: blur mode emits a `feGaussianBlur` `<defs>` filter and `filter="url(#hydro-glow)"` on river `<g>`; vector mode emits a wider translucent `*_glow` halo group before each river group. `glow=False` is byte-identical to item #8. |
| `src/optimize.py` | `SvgOptimizer` `Protocol` seam + `SvgoOptimizer` subprocess wrapper (`svgo -i - -o -`); degrades gracefully (returns input + warns) on `FileNotFoundError` / `CalledProcessError`. |
| `src/pipeline.py` | `optimizer` field on `RunContext` + `Pipeline`; threaded glow settings into `generate_svg`; real `optimize_svg` stage (`ctx.optimizer.optimize`, stores `artifacts["optimized_svg"]`, logs sizes). `export` still a stub. |
| `tests/test_glow_config.py`, `test_glow_rendering.py`, `test_optimize.py`, `test_optimize_pipeline.py` | 4 + 4 + 2 + 4 = 14 new tests. |

## Key decisions

- **Glow at render time, not string-munging in optimize_svg.** Both modes are produced inside `render_svg` and threaded via `generate_svg`, keeping `optimize_svg` a pure optimizer pass. `glow=False` yields output byte-identical to item #8 (backward compatible).
- **Injectable `SvgOptimizer` seam** mirroring the `Downloader`/`LayerLoader` pattern: production injects `SvgoOptimizer`, tests inject a fake. The suite stays fully offline — no Node/SVGO required.
- **Graceful degradation** in the real optimizer: a host without `svgo` gets the unoptimized SVG (and a warning) instead of a crash — verified end-to-end (`optimize_svg 872 -> 872 bytes` in the smoke test).
- **Blur vs vector** distinguished by `glow_mode`: blur uses a single shared filter def; vector emits per-group halos with `stroke-width = line_width + 2*glow_radius` and reduced opacity, no filter.

## Acceptance criteria met

- Both glow modes render deterministically per PRD §20; glow-off unchanged from item #8.
- `optimize_svg` runs the SVG through the injected optimizer into `artifacts["optimized_svg"]`; the real optimizer degrades gracefully without Node/SVGO.
- Both new settings validated at the boundary; defaults `blur` / `2.0`; unset flags never clobber YAML.
- `export` remains a stub; 14 added tests (≤10 additional strategic tests in TG3); full existing suite passes with no regressions.

## Regression fixed

- `tests/test_rendering_pipeline.py::test_downstream_stages_remain_stubs` (item #8) asserted `optimized_svg` was absent. Now that `optimize_svg` is implemented, the assertion was narrowed to `export` being the only remaining stub.

## Notes for next feature (roadmap #10: export)

- `context.artifacts["optimized_svg"]` is the SVG string the `export` stage should write to disk (and rasterize/convert to PDF/PNG per requested `settings.outputs`).
- No file writing happens yet — `generate_svg` / `optimize_svg` keep everything in memory; `export` owns the filesystem.
