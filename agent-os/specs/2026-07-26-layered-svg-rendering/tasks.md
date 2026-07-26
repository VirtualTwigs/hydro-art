# Task Breakdown: Layered SVG Rendering

## Overview
Total Tasks: 3 task groups

## Task List

### Geometry Layer

#### Task Group 1: SVG geometry core
**Dependencies:** None

- [x] 1.0 Add `src/rendering.py` low-level geometry → SVG helpers
  - [x] 1.1 Write 2-8 focused tests
    - `bounds` over several LineStrings returns correct min/max; empty → `(0,0,0,0)`
    - `format_number` strips trailing zeros/dot, normalizes `-0` to `0`, honors precision
    - `transform_coords` translates to origin and flips Y (`x−min_x`, `max_y−y`)
    - `path_d` yields `M x,y L x,y …` for a LineString and multi sub-paths for a MultiLineString
  - [x] 1.2 Implement `bounds`, `format_number`, `transform_coords`, `path_d`
  - [x] 1.3 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- Coordinates flip Y and translate to a `0,0`-origin viewBox; formatting is deterministic
- Path strings are correct for single- and multi-part line geometries

### Document Layer

#### Task Group 2: render_svg document assembly + width scaling
**Dependencies:** Task Group 1

- [x] 2.0 Implement `render_svg` and `stream_order_widths` in `src/rendering.py`
  - [x] 2.1 Write 2-8 focused tests (hand-built geometries + color/watershed dicts)
    - Root carries `viewBox="0 0 W H"` + round cap/join + `fill="none"` + base `stroke-width`; `<defs/>` and `<g id="background">` rect filled with the background color present
    - One `<g id="watershed_<code>">` per watershed in sorted order, each with its color as `stroke`, containing its segments' `<path>` in sorted `segment_id` order
    - Segments outside any watershed land in `<g id="rivers_unassigned">`; group absent when empty
    - Deterministic: identical inputs → identical string; empty geometries → valid `0×0` SVG, no crash
    - `stroke_widths` produces per-path `stroke-width`; `stream_order_widths` scales base→base*max_scale by order
  - [x] 2.2 Implement `render_svg` (root/defs/background/watershed groups/unassigned, inheritance-based styling)
  - [x] 2.3 Implement `stream_order_widths` helper
  - [x] 2.4 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- SVG matches PRD §18 structure; §19 default styling; grouped by watershed; deterministic bytes
- Optional per-segment width scaling supported and tested at the module level

### Integration & Testing

#### Task Group 3: generate_svg pipeline stage + test review & report
**Dependencies:** Task Groups 1-2

- [x] 3.0 Wire the `generate_svg` stage and fill test gaps
  - [x] 3.1 Replace the `generate_svg` stub: build `geometries` from `artifacts["hydro_graph"]`, call `render_svg` with `settings.background`/`line_width` + `segment_colors`/`watersheds`, store `artifacts["svg"]`, log a `rich` summary; keep `optimize_svg`/`export` stubs; write no file
    - [x] 3.2 Review tests from TG1-2, identify critical gaps for THIS feature only
  - [x] 3.3 Write up to 10 additional strategic tests (e.g., end-to-end build_graph → … → generate_svg through the offline pipeline; `artifacts["svg"]` is a valid layered SVG containing the watershed group + colored paths; determinism; downstream stages remain stubs)
  - [x] 3.4 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path via a smoke test

**Acceptance Criteria:**
- Pipeline `generate_svg` produces `artifacts["svg"]` (layered, colored, on background) in tests and production; stats logged; downstream stages remain stubs
- No more than 10 additional tests; full existing suite still passes (no regressions)

## Execution Order

1. Geometry Layer (Task Group 1)
2. Document Layer (Task Group 2)
3. Integration & Testing (Task Group 3)
