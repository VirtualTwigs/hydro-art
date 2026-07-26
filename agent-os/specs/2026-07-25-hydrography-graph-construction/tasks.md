# Task Breakdown: Hydrography Graph Construction

## Overview
Total Tasks: 3 task groups

## Task List

### Construction Layer

#### Task Group 1: Directed graph construction
**Dependencies:** None (consumes item #4's clipped layers)

- [x] 1.0 Build the directed graph (`src/graph.py`)
  - [x] 1.1 Write 2-8 focused tests (in-memory line networks)
    - Two segments sharing an endpoint produce one shared junction node
    - A segment becomes a directed edge oriented first-vertex -> last-vertex (downstream)
    - MultiLineString is exploded into component-segment edges; empties skipped
    - A zero-length (endpoints snap together) segment is dropped and counted
  - [x] 1.2 Define a `HydroGraph` wrapping `networkx.MultiDiGraph` (preserves braided/parallel channels) and a node-snapping helper
  - [x] 1.3 Implement `build_graph(layers, snap_tolerance=...)`: explode multiparts, snap endpoints, add nodes/edges with geometry+length+segment id
  - [x] 1.4 Skip WBD boundary layers (reuse `is_boundary_layer`); drop-and-count degenerate segments
  - [x] 1.5 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- Tests from 1.1 pass
- Directed graph with junction nodes and segment edges; multiparts exploded
- Coincident endpoints collapse to one node; degenerate segments dropped-and-counted

### Traversal & Statistics Layer

#### Task Group 2: Traversal, basins & network statistics
**Dependencies:** Task Group 1

- [x] 2.0 Add traversal, basins, and stats to `HydroGraph`
  - [x] 2.1 Write 2-8 focused tests (in-memory line networks)
    - `sources`/`outlets` identify headwaters (in-degree 0) and terminals (out-degree 0)
    - `upstream`/`downstream` return ancestors/descendants for a node
    - `basin(outlet)` returns all segment ids draining to the outlet
    - `statistics()` reports correct node/edge/source/outlet counts and total length
  - [x] 2.2 Implement `sources()`/`outlets()`
  - [x] 2.3 Implement `upstream(node)`/`downstream(node)` via graph ancestors/descendants
  - [x] 2.4 Implement `basin(node)` = segment ids among the node and its ancestors
  - [x] 2.5 Define a `NetworkStats` value object and `statistics()`
  - [x] 2.6 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- Tests from 2.1 pass
- Upstream/downstream/basin reflect flow direction; stats are correct
- Empty graph yields zero-valued stats without error

### Integration & Testing

#### Task Group 3: Pipeline integration + test review & report
**Dependencies:** Task Groups 1-2

- [x] 3.0 Wire graph construction into the pipeline and fill test gaps
  - [x] 3.1 Replace the `build_graph` stub: construct from `artifacts["clipped_layers"]`, store `artifacts["hydro_graph"]` + `artifacts["network_stats"]`; log stats via `rich`; keep downstream stages stubs
  - [x] 3.2 Add `networkx` to `requirements.txt`
  - [x] 3.3 Review tests from TG1-2, identify critical gaps for THIS feature only
  - [x] 3.4 Write up to 10 additional strategic tests (e.g., end-to-end clip -> build_graph through the pipeline with a fake loader; stats surfaced in artifacts)
  - [x] 3.5 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path

**Acceptance Criteria:**
- Pipeline `build_graph` constructs the network from clipped layers in tests and production
- `HydroGraph` + statistics land in artifacts; stats logged; no more than 10 additional tests
- Full existing suite still passes (no regressions)

## Execution Order

1. Construction Layer (Task Group 1)
2. Traversal & Statistics Layer (Task Group 2)
3. Integration & Testing (Task Group 3)
