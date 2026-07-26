# Task Breakdown: Optional Glow & SVG Optimization

## Overview
Total Tasks: 3 task groups

## Task List

### Config Layer

#### Task Group 1: glow_mode + glow_radius config surface
**Dependencies:** None

- [x] 1.0 Add glow mode/radius to config + CLI
  - [x] 1.1 Write 2-8 focused tests
    - `glow_mode` defaults to `"blur"`, validates against `SUPPORTED_GLOW_MODES`; unknown mode raises `ConfigError`
    - `glow_radius` defaults to `2.0`, accepts positive numbers; `<= 0`/non-number raises `ConfigError`
    - `--glow-mode`/`--glow-radius` override YAML; unset flags never clobber YAML
  - [x] 1.2 Add `SUPPORTED_GLOW_MODES`, `glow_mode`/`glow_radius` to `DEFAULTS` + `Settings`, validate in `build_settings`
  - [x] 1.3 Add `--glow-mode`/`--glow-radius` to the parser + `cli_overrides`; add rows to `build.py`'s table
  - [x] 1.4 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- Both settings validated at the boundary; defaults `blur`/`2.0`; unset flags never clobber YAML

### Rendering Layer

#### Task Group 2: glow in render_svg + generate_svg wiring
**Dependencies:** Task Group 1

- [x] 2.0 Implement optional glow in `src/rendering.py` and thread it through the stage
  - [x] 2.1 Write 2-8 focused tests (hand-built geometries + dicts)
    - `glow=False` → byte-identical to no-glow output (backward compatible)
    - Blur → `<defs>` has a `feGaussianBlur` with the radius; river `<g>` carry `filter="url(#hydro-glow)"`
    - Vector → a `*_glow` halo group precedes each river group with wider `stroke-width` + `stroke-opacity`; no filter
    - Deterministic (identical inputs → identical string) for each mode
  - [x] 2.2 Implement glow (blur filter + vector halos) in `render_svg`
  - [x] 2.3 Thread `settings.glow`/`glow_mode`/`glow_radius` into the `generate_svg` stage
  - [x] 2.4 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- Both glow modes render deterministically per PRD §20; glow-off unchanged from item #8

### Optimization & Integration

#### Task Group 3: SVGO seam + optimize_svg stage + report
**Dependencies:** Task Groups 1-2

- [x] 3.0 Add the optimizer seam, wire the stage, fill test gaps
  - [x] 3.1 Implement `src/optimize.py`: `SvgOptimizer` protocol + `SvgoOptimizer` (subprocess `svgo`, graceful fallback + warning when absent/failed)
  - [x] 3.2 Add `optimizer` to `RunContext` + `Pipeline`; replace the `optimize_svg` stub (run `ctx.optimizer.optimize`, store `artifacts["optimized_svg"]`, log sizes); keep `export` a stub
  - [x] 3.3 Review tests from TG1-2, identify critical gaps for THIS feature only
  - [x] 3.4 Write up to 10 additional strategic tests (injected fake optimizer wiring; `SvgoOptimizer` returns input unchanged when `svgo` missing; end-to-end pipeline with glow on → `optimized_svg` present; `export` still stub)
  - [x] 3.5 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path via a smoke test

**Acceptance Criteria:**
- `optimize_svg` runs the SVG through the injected optimizer into `artifacts["optimized_svg"]`; real optimizer degrades gracefully without Node/SVGO
- `export` remains a stub; ≤10 additional tests; full existing suite passes (no regressions)

## Execution Order

1. Config Layer (Task Group 1)
2. Rendering Layer (Task Group 2)
3. Optimization & Integration (Task Group 3)
