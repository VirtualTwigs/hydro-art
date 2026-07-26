# Task Breakdown: Deterministic Basin Coloring

## Overview
Total Tasks: 3 task groups

## Task List

### Palette Layer

#### Task Group 1: Neon palette + palette config validation
**Dependencies:** None

- [x] 1.0 Add `src/coloring.py` palette data + `palette` config validation
  - [x] 1.1 Write 2-8 focused tests
    - `PALETTES["neon"]` has 12 entries, all valid `#rrggbb` hex
    - `get_palette("neon")` returns the tuple; unknown name raises `ColoringError`
    - `palette` validates (allowlist) in `build_settings`; unknown palette raises `ConfigError`
    - unset `--palette` flag doesn't clobber YAML palette
  - [x] 1.2 Implement `PALETTES`, `get_palette`, and `ColoringError` in `src/coloring.py`
  - [x] 1.3 Add `SUPPORTED_PALETTES` to `src/config.py`, export it, and validate `palette` in `build_settings`
  - [x] 1.4 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- Neon palette present with 12 valid hex colors; `get_palette` works + raises on unknown
- `palette` validated at the boundary; unset flag never clobbers YAML

### Coloring Layer

#### Task Group 2: Adjacency + deterministic graph coloring
**Dependencies:** Task Group 1 (uses `PALETTES`/`get_palette`)

- [x] 2.0 Implement adjacency + coloring in `src/coloring.py`
  - [x] 2.1 Write 2-8 focused tests (in-memory graphs + watershed dicts)
    - Two watersheds sharing a junction node are adjacent; non-touching are not; every code is a key
    - `greedy_color` gives adjacent watersheds different class indices; deterministic (equal on repeat)
    - `assign_colors` maps codes to neon hex; adjacent codes get different colors when classes ≤ palette size
    - Single watershed → one color; empty watersheds → empty result
  - [x] 2.2 Implement `build_adjacency(graph, watersheds)` over shared graph nodes
  - [x] 2.3 Implement `greedy_color(adjacency)` (Welsh–Powell, deterministic ordering + tie-break)
  - [x] 2.4 Implement `assign_colors(graph, watersheds, palette="neon")` composing adjacency → coloring → palette
  - [x] 2.5 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- Adjacency from shared junctions; proper coloring where chromatic number ≤ palette size
- Fully deterministic (identical inputs → identical colors); no randomness

### Integration & Testing

#### Task Group 3: assign_colors pipeline stage + test review & report
**Dependencies:** Task Groups 1-2

- [x] 3.0 Wire the `assign_colors` stage and fill test gaps
  - [x] 3.1 Replace the `assign_colors` stub: compute `watershed_colors` from `artifacts["hydro_graph"]` + `artifacts["watersheds"]` with `settings.palette`; expand to `segment_colors`; store both + palette name; log via `rich`; keep downstream stages stubs
  - [x] 3.2 Review tests from TG1-2, identify critical gaps for THIS feature only
  - [x] 3.3 Write up to 10 additional strategic tests (e.g., end-to-end build_graph → compute_watersheds → assign_colors through the pipeline; colors + determinism in artifacts)
  - [x] 3.4 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path

**Acceptance Criteria:**
- Pipeline `assign_colors` computes watershed + segment colors in tests and production
- `watershed_colors`, `segment_colors`, palette name land in artifacts; stats logged; no more than 10 additional tests
- Full existing suite still passes (no regressions)

## Execution Order

1. Palette Layer (Task Group 1)
2. Coloring Layer (Task Group 2)
3. Integration & Testing (Task Group 3)
