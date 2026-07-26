# Specification: Hydrography Graph Construction

## Goal
Build a directed river-network graph from the clipped flowline geometries — nodes are river junctions, edges are river segments oriented downstream — and expose upstream/downstream traversal, basin extraction, and network statistics behind a thin `HydroGraph` wrapper, so later stages (watersheds, stream ordering, coloring) can reason about network topology without touching NetworkX or raw geometry.

## User Stories
- As a later pipeline stage, I want the river network as a directed graph so that I can traverse it and extract basins.
- As a user, I want network statistics reported so that I can sanity-check the constructed network.
- As a developer, I want graph construction as pure functions over geometry + NetworkX so that it is fully testable without GDAL or real data.

## Specific Requirements

**Graph construction**
- Provide `build_graph(layers, snap_tolerance=...) -> HydroGraph` consuming flowline layers (LineString/MultiLineString in the internal CRS).
- Explode MultiLineString into component segments; skip empty geometries.
- Each segment endpoint becomes a node, snapped to `snap_tolerance` so coincident endpoints collapse into one shared junction.
- Each segment becomes a directed edge from its first vertex (upstream) to its last vertex (downstream), storing the segment geometry, its length, and a stable segment id.
- Drop-and-count degenerate segments whose endpoints snap to the same node (zero-length).

**HydroGraph wrapper (over `networkx.DiGraph`)**
- `.digraph` exposes the underlying graph for advanced use.
- `.sources()` = headwater nodes (in-degree 0); `.outlets()` = terminal nodes (out-degree 0).
- `.upstream(node)` = all nodes that flow to `node` (ancestors); `.downstream(node)` = descendants.
- `.basin(node)` = the set of segment ids draining to `node` (edges among `node` + its ancestors).
- `.statistics()` = a `NetworkStats` value object.

**Network statistics**
- `NetworkStats`: num_nodes, num_edges, num_sources, num_outlets, total_length; rendered via `rich`.

**Error recovery**
- Empty input (no flowline geometries) yields an empty graph with zero stats, not an error.
- Degenerate/self-loop segments are dropped-and-counted, not fatal (PRD §28).

**Pipeline integration**
- Replace the `build_graph` stub: construct the graph from `artifacts["clipped_layers"]`, store `artifacts["hydro_graph"]` and `artifacts["network_stats"]`, and log the statistics via `rich`.
- Downstream stages remain stubs.

**Dependencies**
- Add `networkx` to `requirements.txt`.

## Existing Code to Leverage

**`src/pipeline.py` — `RunContext` / stages**
- Input seam is `artifacts["clipped_layers"]` (item #4); replace the `build_graph` stub `Stage`. No new injected dependency (construction is deterministic).

**`src/clipping.py` — boundary-layer distinction**
- Only flowline (non-boundary) layers form the network; reuse `is_boundary_layer` to skip WBD polygon layers.

**`src/loading.py` — `Layer`**
- Consume `Layer.geometries`; `Layer.attributes` remains unused (flow-direction refinement is a later concern).

## Out of Scope
- Stream ordering (Strahler/Shreve/Hack) and HUC grouping (roadmap item #6).
- Watershed/basin *coloring* (item #7) and everything downstream (items #8–#10).
- Refining edge orientation from NHD flow-direction attributes (FromNode/ToNode) — geometry vertex order is the orientation source for this item.
- Performance tuning for millions of segments (spatial-index snapping, vectorized build) — correctness first.
- Loading real datasets in tests — tests build in-memory line networks.
