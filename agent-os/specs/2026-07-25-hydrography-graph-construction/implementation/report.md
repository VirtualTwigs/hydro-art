# Implementation Report: Hydrography Graph Construction

**Date:** 2026-07-25
**Status:** Complete — all 3 task groups done, 75/75 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/graph.py` | `build_graph(layers, snap_tolerance)` and `HydroGraph` (over `networkx.MultiDiGraph`): node snapping, segment edges, upstream/downstream traversal, basin extraction, sources/outlets, and a `NetworkStats` value object. |
| `src/pipeline.py` | Real `build_graph` stage constructing the network from `artifacts["clipped_layers"]`, storing `hydro_graph` + `network_stats` and logging the summary via `rich`. |
| `requirements.txt` | Added `networkx`. |
| `tests/test_graph.py`, `test_graph_traversal.py`, `test_graph_pipeline.py` | 6 + 5 + 2 = 13 new tests (75 total suite). |

## Key decisions

- **`MultiDiGraph`, not `DiGraph`:** PRD §11 requires preserving braided channels, so parallel segments between the same two junctions must survive. A plain `DiGraph` would silently collapse them; `MultiDiGraph` keeps every segment as its own edge.
- **Edge orientation from geometry vertex order:** NHDFlowline is digitized downstream, so each segment's edge runs first-vertex → last-vertex. This yields a directed graph without needing NHD flow-direction attributes yet (a later item can refine orientation via FromNode/ToNode; `Layer.attributes` stays unused).
- **Nodes are snapped endpoints:** endpoints are rounded to sub-metric precision (or a supplied grid tolerance) so coincident endpoints from different segments collapse into one shared junction. Segments whose endpoints snap together are dropped-and-counted (`HydroGraph.dropped_degenerate`), never fatal.
- **Thin domain wrapper:** `HydroGraph` exposes upstream/downstream/basin/sources/outlets/statistics so downstream stages depend on river-network semantics, not NetworkX internals. Traversal uses `nx.ancestors`/`nx.descendants`; a basin is the segment ids among a node and its ancestors.
- **Deterministic, pure, testable:** construction is a pure function over shapely geometries + NetworkX; boundary (WBD) layers are skipped via `is_boundary_layer`. Tests build in-memory line networks (no GDAL, no real data).

## Acceptance criteria met

- Directed graph with junction nodes and segment edges; MultiLineStrings exploded; empties skipped; coincident endpoints collapse; degenerate segments dropped-and-counted.
- `sources`/`outlets`/`upstream`/`downstream`/`basin` reflect flow direction; `statistics()` reports correct node/edge/source/outlet counts and total length; an empty graph yields zero-valued stats without error.
- Pipeline `build_graph` constructs the network from clipped layers in tests and production; `HydroGraph` + `NetworkStats` land in artifacts and are logged.
- Full suite passes with no regressions (75 passed); 13 new tests (TG1 6, TG2 5, TG3 2).

## Notes for next feature (roadmap #6: stream ordering & watershed grouping)

- `context.artifacts["hydro_graph"]` is the input seam: a directed `MultiDiGraph` with per-edge `segment_id`, `geometry`, and `length`.
- Strahler/Shreve/Hack ordering is a traversal from `sources()` toward `outlets()` — the topology and `basin()`/`upstream()` helpers are already in place.
- HUC grouping (HUC2–HUC12) will need HUC codes per segment; the WBD polygon layers (currently only used for the clip boundary) or NHD reach codes are the likely source — plumb attributes through the loader when item #6 lands.
- Edge orientation currently trusts geometry direction; if real NHD data has mis-digitized segments, item #6 may need a flow-direction correction pass.
