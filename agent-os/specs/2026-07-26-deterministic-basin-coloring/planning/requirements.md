# Requirements: Deterministic Basin Coloring

## Raw Idea (from roadmap item #7)

Assign colors so adjacent watersheds maximize contrast via graph coloring followed by neon-palette assignment, guaranteeing identical colors from identical inputs (no randomness).

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** the `Assign colors` stage sits between `Compute watersheds` and `Generate SVG`.
- **§15 Basin Coloring:** Do NOT assign random colors. Generate deterministic colors. Adjacent watersheds should maximize color contrast. Preferred algorithm: **graph coloring followed by palette assignment**.
- **§16 Palette:** neon-inspired; include cyan, electric blue, indigo, purple, violet, magenta, orange, gold, lime, teal, turquoise, green. No muted colors. Black background.
- **§27 Logging:** rich terminal output; report statistics.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests.

## Design Notes / Decisions

- **Input seams (from item #6):** `context.artifacts["hydro_graph"]` (the directed `MultiDiGraph`, each edge carrying `segment_id`/`huc4`) and `context.artifacts["watersheds"]` (HUC code → set of segment ids). Item #7 colors *watersheds*, not individual segments.
- **Adjacency = shared junction:** two watersheds are adjacent when some graph node has incident edges belonging to both. This is a pure, deterministic derivation from the graph + watershed grouping — no geometry/polygon intersection needed, and it matches how rivers actually connect across HUC boundaries (confluences at shared nodes).
- **Graph coloring (deterministic, no randomness):** greedy Welsh–Powell — order watershed vertices by descending adjacency degree, ties broken by HUC code (stable), then assign each the lowest color index not used by already-colored neighbors. Proper coloring uses ≤ maxdegree+1 classes; identical inputs always yield identical class assignments.
- **Palette assignment for max contrast:** map color class index → `palette[index % len(palette)]`. When the number of classes ≤ palette size (the common case with the 12-color neon palette), adjacent watersheds always receive distinct neon colors, satisfying "maximize contrast". If classes exceed palette size the mapping wraps deterministically (adjacency conflicts only possible when chromatic number > palette size — acceptable and still deterministic).
- **Palette as data + config allowlist:** define `PALETTES` in `src/coloring.py` (start with `neon`, the 12 §16 colors as hex). Add a `SUPPORTED_PALETTES` allowlist to config and validate `palette` in `build_settings` (consistent with the existing `SUPPORTED_*` boundary-validation pattern; default `neon` unchanged). `--palette` flag already exists.
- **Outputs on the context:** store `artifacts["watershed_colors"]` (HUC code → hex) and `artifacts["segment_colors"]` (segment_id → hex, expanded from watershed membership) so item #8 rendering can color paths directly. Also record the resolved `palette` name for logging.
- **Pure & testable:** all computation is over the in-memory graph + watershed dict; no GDAL, no real data. No new injected dependency (deterministic computation, like `compute_watersheds`).

## Open Questions (resolve during implementation)

- Watersheds with no adjacency (isolated) still get a color (class 0 or their greedy assignment) — fine.
- Segments whose watershed was dropped (no `huc4`) are simply absent from `segment_colors`; the renderer will fall back to a default in item #8. Out of scope here.
- Palette color *ordering* for contrast: keep the §16 listing order; do not attempt perceptual-distance optimization this item (deterministic wrap is sufficient).
