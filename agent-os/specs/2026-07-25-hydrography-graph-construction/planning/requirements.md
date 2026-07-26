# Requirements: Hydrography Graph Construction

## Raw Idea (from roadmap item #5)

Build a directed river network graph (nodes = junctions, edges = segments) supporting upstream/downstream traversal, basin extraction, and network statistics.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** `Build hydrography graph` sits between `Clip to region` and `Compute watersheds`.
- **§14 Graph Construction:** construct a **directed** graph — each node is a river junction, each edge a river segment. Support upstream traversal, downstream traversal, basin extraction, stream ordering, network statistics.
- **§27 Logging:** rich terminal output; report network statistics.
- **§29 Tech Stack:** NetworkX.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests.

## Design Notes / Decisions

- **Input seam:** `context.artifacts["clipped_layers"]` — flowline layers of shapely LineString/MultiLineString in the internal CRS (EPSG:5070), already valid and trimmed to region.
- **Nodes = snapped endpoints:** a junction is a segment endpoint; endpoints are snapped to a tolerance so coincident endpoints from different segments collapse to one shared junction node. Real NHD endpoints are typically bit-identical, but a snap tolerance keeps construction robust.
- **Edges = segments, oriented downstream:** NHDFlowline geometry is digitized in the direction of flow, so each segment's edge runs from its first vertex (upstream) to its last vertex (downstream). This gives a directed graph without needing NHD flow-direction attributes yet (attributes are still unused; a later item can refine orientation using FromNode/ToNode if needed).
- **NetworkX DiGraph under a thin wrapper:** a `HydroGraph` wraps `networkx.DiGraph` and exposes the domain operations (upstream/downstream/basin/sources/outlets/statistics) so downstream stages don't depend on NetworkX internals.
- **Traversal semantics:** upstream(node) = graph ancestors (everything that flows *to* the node); downstream(node) = descendants. A basin draining to a node = the node plus all its ancestors (and the segments among them).
- **Statistics:** node/edge counts, source (headwater) count, outlet (terminal) count, total segment length — logged via `rich`, mirroring earlier stats objects.
- **Pure & testable:** construction/traversal operate on shapely geometries + NetworkX; fully unit-tested with hand-built line networks (no GDAL, no real data).

## Open Questions (resolve during implementation)

- Snap tolerance default: start at exact-match on rounded coordinates (sub-metric precision in EPSG:5070); expose a tolerance parameter for later tuning.
- Handling of MultiLineString flowlines: explode into component segments, each an edge.
- Disconnected / self-loop segments (zero-length after snap): drop-and-count rather than fail.
