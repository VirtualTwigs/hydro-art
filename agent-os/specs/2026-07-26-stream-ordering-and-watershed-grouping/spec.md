# Specification: Stream Ordering & Watershed Grouping

## Goal
Compute a selectable stream-hierarchy order (Strahler/Shreve/Hack/custom) for every river segment and group segments into a selectable HUC level (HUC2–HUC12), storing both on the run context so downstream coloring (item #7) and layered rendering (item #8) can style and group rivers by importance and watershed.

## User Stories
- As a user, I want to pick a stream-ordering method so that the art emphasizes river hierarchy the way I want.
- As a user, I want to pick a watershed (HUC) level so that segments group at the resolution I care about.
- As a developer, I want ordering and grouping as pure functions over the graph so that they are fully testable without GDAL or real data.

## Specific Requirements

**Selectability (config + CLI)**
- Add `stream_method` to `Settings` (allowlist `strahler`/`shreve`/`hack`/`custom`, default `strahler`) with a `--stream-method` CLI flag.
- Add `huc_level` to `Settings` (allowlist `HUC2`/`HUC4`/`HUC6`/`HUC8`/`HUC10`/`HUC12`, default `HUC4`) with a `--huc-level` CLI flag.
- Validate both at the boundary in `build_settings`, with `ConfigError` listing valid options; flags default to `None` so they never clobber YAML.

**Stream ordering (`src/ordering.py`)**
- `assign_stream_order(graph, method="strahler") -> dict[int, int|float]` mapping `segment_id` → order.
- Implement `strahler_order`, `shreve_order`, `hack_order`, and `custom_order(graph, weight)`:
  - Strahler: sources = 1; confluence increments only when the two highest incoming orders tie.
  - Shreve: sources = 1; confluence = sum of incoming.
  - Hack: main stem = 1 (chosen by greatest cumulative upstream length), tributaries increment outward.
  - Custom: per-segment weight from a supplied `weight(edge_data)` (dispatcher default = cumulative upstream length).
- Process the DAG in topological order; a cycle raises `OrderingError`.

**Watershed grouping (`src/watersheds.py`)**
- `group_segments_by_huc(graph, level) -> dict[str, set[int]]` mapping HUC code → segment ids, from each edge's `huc4` truncated to the level's digit count.
- `HUC_LEVEL_DIGITS` maps HUC2..HUC12 → 2..12. Levels finer than the available HUC digits degrade to the full `huc4` with a single warning.
- Provide `WatershedStats` (num_watersheds, num_segments) for logging.

**Graph edge attribute**
- Extend `build_graph` to record `huc4=layer.huc4` on each segment edge (used by grouping). Existing edge attributes (`segment_id`, `geometry`, `length`) are unchanged.

**Pipeline integration**
- Replace the `compute_watersheds` stub: compute stream orders (`settings.stream_method`) and HUC groups (`settings.huc_level`) from `artifacts["hydro_graph"]`; store `artifacts["stream_orders"]`, `artifacts["watersheds"]`, `artifacts["max_stream_order"]`; log a summary via `rich`.
- Downstream stages remain stubs.

## Existing Code to Leverage

**`src/config.py` / `src/cli.py`**
- Extend the allowlist pattern (`SUPPORTED_*`) and `build_settings` validation; add two argparse flags and their `cli_overrides` entries. Reuse `ConfigError`.

**`src/graph.py` — `HydroGraph`**
- Reuse `sources()`/`outlets()`/traversal and the `MultiDiGraph` edges; add `huc4` to edge data at construction.

**`src/pipeline.py` — `RunContext` / stages**
- Input seam `artifacts["hydro_graph"]`; replace the `compute_watersheds` stub `Stage`. No new injected dependency (computation is deterministic).

## Out of Scope
- Basin *coloring* / adjacency and contrast (roadmap item #7) and everything downstream (items #8–#10).
- Rendering-time stream-order *filtering* (the existing `stream_order: all` config) — that is item #8.
- Spatially joining segments to sub-HUC (HUC6–HUC12) boundary polygons — deferred until those WBD layers are loaded; finer levels degrade to HUC4 with a warning.
- Refining edge orientation from NHD flow-direction attributes.
- Performance tuning (vectorized ordering for millions of segments).
- Loading real datasets in tests — tests build in-memory graphs.
