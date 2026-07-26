# Specification: Layered SVG Rendering

## Goal
Turn the colored river network into a single, editable, layered SVG document: every segment a round-capped/round-joined vector path, grouped by watershed into `<g>` layers on a solid background, with deterministic (byte-identical) output from identical inputs. Store the SVG string on the run context so item #9 can optimize it and item #10 can export it.

## User Stories
- As a user, I want a clean layered SVG of my region's rivers on a black background so I can print it or refine it in Illustrator/Affinity/Figma/Inkscape.
- As a user, I want re-running the build to produce byte-identical SVG so output is reproducible.
- As a developer, I want rendering as pure functions over geometries + color/watershed dicts so it is fully testable without GDAL, a browser, or real data.

## Specific Requirements

**SVG geometry core (`src/rendering.py`)**
- `bounds(geometries) -> tuple[float, float, float, float]`: `(min_x, min_y, max_x, max_y)` over all LineString coordinates; a well-defined sentinel (`(0, 0, 0, 0)`) when empty.
- `format_number(value, precision) -> str`: fixed-precision decimal, trailing zeros and trailing dot stripped, `-0` normalized to `0`. Deterministic.
- `transform_coords(coords, min_x, max_y, precision) -> list[tuple[str, str]]`: translate to origin and flip Y (`x−min_x`, `max_y−y`), formatted via `format_number`.
- `path_d(geometry, min_x, max_y, precision) -> str`: an SVG path `d` string (`M x,y L x,y …`), handling multi-part line geometries as multiple sub-paths.

**Document assembly (`src/rendering.py`)**
- `render_svg(geometries, segment_colors, watersheds, *, background="#000000", line_width=0.35, precision=3, stroke_widths=None, fallback_color="#ffffff") -> str`:
  - Root `<svg xmlns=… viewBox="0 0 W H" width="Wpx" height="Hpx" fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="<line_width>">` where `W=max_x−min_x`, `H=max_y−min_y`.
  - First child `<defs/>`, then `<g id="background"><rect x="0" y="0" width="W" height="H" fill="<background>"/></g>`.
  - One `<g id="watershed_<code>" stroke="<color>">` per watershed in sorted code order, containing that watershed's segments (present in `geometries`) as bare `<path d=…/>` in sorted `segment_id` order. Group stroke is the watershed's color (from `segment_colors`, else `fallback_color`).
  - Segments in `geometries` not covered by any watershed → a trailing `<g id="rivers_unassigned">` (only if non-empty) with per-path `stroke` from `segment_colors`/`fallback_color`.
  - When `stroke_widths` is given, emit per-`<path>` `stroke-width` (overriding the inherited base); otherwise paths inherit the uniform width.
  - Deterministic: sorted groups/segments, fixed coordinate precision, stable attribute order → identical inputs yield identical strings.
- `stream_order_widths(stream_orders, max_order, base_width, max_scale=3.0) -> dict[int, float]`: map each segment's order to a stroke width scaled linearly from `base_width` (order 1) up to `base_width*max_scale` (order `max_order`). Deterministic; supports the "optional width scaling" requirement without a new config field.

**Pipeline integration (`src/pipeline.py`)**
- Replace the `generate_svg` stub stage: build `geometries = {segment_id: geometry}` from `artifacts["hydro_graph"]` edges; call `render_svg` with `settings.background`/`settings.line_width` and `artifacts["segment_colors"]`/`artifacts["watersheds"]`; store the string in `artifacts["svg"]`; log a `rich` summary (paths rendered, watershed groups, viewBox `W×H`). `optimize_svg` and `export` remain stubs. No file is written (deferred to item #10).

## Existing Code to Leverage
- **`src/graph.py` — `HydroGraph`:** iterate `digraph.edges(data=True)` for each edge's `segment_id` + `geometry` (a shapely LineString in EPSG:5070). No graph API change.
- **`src/coloring.py` (item #7) outputs:** `artifacts["segment_colors"]` (segment_id → hex) and `artifacts["watersheds"]` (HUC code → segment ids) drive per-path color and `<g>` grouping.
- **`src/ordering.py` (item #6) outputs:** `artifacts["stream_orders"]` + `artifacts["max_stream_order"]` feed the optional `stream_order_widths` helper.
- **`src/pipeline.py` — stages/`RunContext`:** replace the `generate_svg` stub `Stage`; read from `artifacts`; no new injected dependency (pure computation).

## Out of Scope
- Glow (vector or Gaussian blur) and its radius — item #9.
- SVGO optimization (duplicate paths, unused defs, precision passes) — item #9.
- Writing SVG/PDF/PNG files to disk and multi-format export — item #10.
- A config/CLI flag to toggle width scaling — capability is provided and tested at the module level; wiring a flag is deferred.
- Interactive/zoomable/animated output (PRD §32 future work).
- Loading real datasets in tests — rendering is tested with hand-built geometries + dicts.
