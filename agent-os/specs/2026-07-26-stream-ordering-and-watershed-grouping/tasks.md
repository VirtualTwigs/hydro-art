# Task Breakdown: Stream Ordering & Watershed Grouping

## Overview
Total Tasks: 3 task groups

## Task List

### Ordering Layer

#### Task Group 1: Stream ordering methods + selectable config
**Dependencies:** None (consumes item #5's hydro graph)

- [x] 1.0 Implement stream ordering (`src/ordering.py`) and `stream_method` config
  - [x] 1.1 Write 2-8 focused tests (in-memory graphs)
    - Strahler: two order-1 streams merge to order 2; an order-1 joining order-2 stays 2
    - Shreve: confluence sums incoming magnitudes
    - Hack: main stem = 1, tributary = 2
    - `assign_stream_order` dispatches by method; unknown method / cyclic graph raises
    - `stream_method` validates (allowlist) and unset flag doesn't clobber YAML
  - [x] 1.2 Add `stream_method` to `Settings`/`DEFAULTS`/allowlist + `build_settings` validation
  - [x] 1.3 Add a `--stream-method` CLI flag (default `None`) + `cli_overrides` entry
  - [x] 1.4 Implement `strahler_order`, `shreve_order`, `hack_order`, `custom_order`, `assign_stream_order`; add `OrderingError`
  - [x] 1.5 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- Tests from 1.1 pass
- All four methods computed correctly; dispatcher + validation work
- Cyclic graph raises a clear error

### Grouping Layer

#### Task Group 2: Watershed HUC grouping + selectable config
**Dependencies:** None (pure graph; can proceed with TG1)

- [x] 2.0 Implement HUC grouping (`src/watersheds.py`) and `huc_level` config
  - [x] 2.1 Write 2-8 focused tests (in-memory graphs with per-edge huc4)
    - Segments group by HUC4 code; HUC2 truncates to the 2-digit prefix
    - A level finer than available digits degrades to HUC4 and warns
    - `WatershedStats` reports watershed/segment counts
    - `huc_level` validates (allowlist) and unset flag doesn't clobber YAML
  - [x] 2.2 Add `huc_level` to `Settings`/`DEFAULTS`/allowlist + `build_settings` validation
  - [x] 2.3 Add a `--huc-level` CLI flag (default `None`) + `cli_overrides` entry
  - [x] 2.4 Record `huc4` on each edge in `build_graph`
  - [x] 2.5 Implement `HUC_LEVEL_DIGITS`, `group_segments_by_huc`, `WatershedStats`
  - [x] 2.6 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- Tests from 2.1 pass
- Grouping by HUC prefix at the selected level; finer-than-available degrades + warns
- Config/CLI selection validated

### Integration & Testing

#### Task Group 3: compute_watersheds stage + test review & report
**Dependencies:** Task Groups 1-2

- [x] 3.0 Wire compute_watersheds and fill test gaps
  - [x] 3.1 Replace the `compute_watersheds` stub: compute stream orders (`settings.stream_method`) and HUC groups (`settings.huc_level`) from `artifacts["hydro_graph"]`; store `stream_orders`, `watersheds`, `max_stream_order`; log via `rich`; keep downstream stages stubs
  - [x] 3.2 Update `build.py` settings table to show `stream_method` + `huc_level`
  - [x] 3.3 Review tests from TG1-2, identify critical gaps for THIS feature only
  - [x] 3.4 Write up to 10 additional strategic tests (e.g., end-to-end build_graph -> compute_watersheds through the pipeline; orders + groups in artifacts)
  - [x] 3.5 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path

**Acceptance Criteria:**
- Pipeline `compute_watersheds` computes orders + groups in tests and production
- Orders, watersheds, and max order land in artifacts; stats logged; no more than 10 additional tests
- Full existing suite still passes (no regressions)

## Execution Order

1. Ordering Layer (Task Group 1)
2. Grouping Layer (Task Group 2)
3. Integration & Testing (Task Group 3)
