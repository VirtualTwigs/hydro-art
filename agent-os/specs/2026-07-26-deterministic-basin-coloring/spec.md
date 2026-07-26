# Specification: Deterministic Basin Coloring

## Goal
Assign every watershed a color so that adjacent watersheds maximize contrast, using graph coloring followed by neon-palette assignment, and store watershed→color (and segment→color) on the run context so item #8 rendering can paint river paths. Identical inputs must always produce identical colors — no randomness.

## User Stories
- As a user, I want adjacent watersheds to have strongly contrasting neon colors so the art reads clearly and looks like neon cartography.
- As a user, I want reproducible output so re-running the build yields byte-identical colors.
- As a developer, I want coloring as pure functions over the graph + watershed groups so it is fully testable without GDAL or real data.

## Specific Requirements

**Neon palette (`src/coloring.py`)**
- Define `PALETTES: dict[str, tuple[str, ...]]` with a `neon` entry containing the twelve §16 colors as hex (cyan, electric blue, indigo, purple, violet, magenta, orange, gold, lime, teal, turquoise, green). All valid `#rrggbb`, none muted.
- `get_palette(name) -> tuple[str, ...]` returns the palette or raises `ColoringError` for an unknown name.

**Palette selectability (config)**
- Add `SUPPORTED_PALETTES = ("neon",)` to `src/config.py` and validate `palette` in `build_settings` (raise `ConfigError` listing valid palettes). Default stays `neon`; the existing `--palette` flag and `cli_overrides` entry are unchanged.

**Adjacency (`src/coloring.py`)**
- `build_adjacency(graph, watersheds) -> dict[str, set[str]]`: two watershed codes are adjacent when some graph node has incident edges (in or out) in both watersheds. Every watershed code appears as a key (isolated watersheds map to an empty set). Deterministic; ignores self-adjacency.

**Deterministic graph coloring (`src/coloring.py`)**
- `greedy_color(adjacency) -> dict[str, int]`: Welsh–Powell — order codes by descending degree, ties broken by code; assign each the lowest color index not used by already-colored neighbors. No randomness; stable across runs.
- `assign_colors(graph, watersheds, palette="neon") -> dict[str, str]`: compose adjacency → coloring → palette; return HUC code → hex via `palette[class_index % len(palette)]`.

**Pipeline integration (`src/pipeline.py`)**
- Replace the `assign_colors` stub stage: read `artifacts["hydro_graph"]` and `artifacts["watersheds"]`, compute `watershed_colors` (code → hex) with `settings.palette`; expand to `segment_colors` (segment_id → hex) from watershed membership; store both plus the palette name; log a summary via `rich` (watersheds colored, distinct colors used, palette). Downstream stages (`generate_svg`, `optimize_svg`, `export`) remain stubs.

## Existing Code to Leverage

**`src/config.py` / `src/cli.py`**
- Extend the `SUPPORTED_*` allowlist pattern and `build_settings` validation; reuse `ConfigError`. `--palette` flag already present.

**`src/graph.py` — `HydroGraph`**
- Reuse `digraph` and per-edge `segment_id`/`huc4`; iterate nodes and incident edges for adjacency. No graph API change needed.

**`src/watersheds.py`**
- Consume its `group_segments_by_huc` output shape (`dict[str, set[int]]`) directly as the `watersheds` input.

**`src/pipeline.py` — `RunContext` / stages**
- Input seams `artifacts["hydro_graph"]` and `artifacts["watersheds"]`; replace the `assign_colors` stub `Stage`. No new injected dependency (computation is deterministic).

## Out of Scope
- Layered SVG rendering, stroke styling, widths (roadmap item #8) — this item only assigns colors.
- Glow, SVG optimization, and multi-format export (items #9–#10).
- Per-*segment* stream-order coloring/opacity — colors key off watershed, not stream order (that styling is item #8).
- Perceptual-distance palette ordering or additional palettes beyond `neon` (the allowlist/data structure allows adding more later without an API change).
- Spatial polygon adjacency — adjacency is derived from shared graph junctions, not WBD polygon borders.
- Loading real datasets in tests — tests build in-memory graphs + watershed dicts.
