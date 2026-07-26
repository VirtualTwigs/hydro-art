# Requirements: Layered SVG Rendering

## Raw Idea (from roadmap item #8)

Render every river as a round-capped, round-joined vector path grouped by watershed into a layered SVG on a black background, with default styling and optional stream-order/drainage/discharge width scaling.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** the `Generate SVG` stage sits between `Assign colors` and `Optimize SVG`.
- **§9 Projection:** SVG coordinates should be projected into a cartesian coordinate system (internal EPSG:5070).
- **§17 Rendering:** every river is a vector path with round caps, round joins, uniform width by default. Optional width scaling: stream order, drainage area, discharge.
- **§18 SVG Architecture:** `<svg><defs/><g id="background"/><g id="watershed_XXX"/>…</svg>`. Group rivers by watershed.
- **§19 Styling:** default background `#000000`, stroke width `0.35px`, line cap round, join round, opacity 100%, no fills.
- **§27 Logging:** rich terminal output; report statistics.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests, pure/offline-testable.

## Design Notes / Decisions

- **Stdlib SVG writer, no new dependency.** tech-stack.md lists `svgwrite`, but it is uninstalled and the project prizes determinism (needed for item #10's byte-identical goal) and fully offline tests. Item #8 hand-rolls a small, deterministic SVG serializer over the stdlib — full control over coordinate precision and element ordering, no install, no network. `svgwrite` can be swapped in later behind the same `render_svg` seam if desired. (Confirmed with the user 2026-07-26.)
- **Input seams (from items #5–#7):** `artifacts["hydro_graph"]` (each edge carries `segment_id` + `geometry` LineString in EPSG:5070), `artifacts["segment_colors"]` (segment_id → hex), and `artifacts["watersheds"]` (HUC code → set of segment ids, for grouping `<g>` layers). Optional width scaling can key off `artifacts["stream_orders"]` + `artifacts["max_stream_order"]` (item #6).
- **Cartesian Y-flip.** Projected northing increases upward; SVG's y-axis increases downward. Transform each coordinate to `(x − min_x, max_y − y)` so north renders up, and set `viewBox="0 0 (max_x−min_x) (max_y−min_y)"`. No simplification of geometry (§11).
- **Deterministic serialization.** Watershed groups emitted in sorted HUC-code order; segments within a group and any unassigned segments emitted in sorted `segment_id` order; coordinates rounded to a fixed precision (default 3) with `-0` normalized to `0` and trailing zeros stripped; stable attribute order. Identical inputs → identical bytes.
- **Style via SVG inheritance.** Shared presentation (`fill="none"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, base `stroke-width`) is set once on the root `<svg>` and inherited. Because item #7 gives every segment in a watershed the same color, `stroke` is set once per watershed `<g>`; paths are bare `<path d=…/>`. This is compact and correct; SVGO (item #9) will further dedupe.
- **Background.** `<g id="background">` holds a `<rect>` covering the viewBox filled with `settings.background` (explicit fill overrides the root `fill="none"`).
- **generate_svg produces a document, not a file.** The stage builds the SVG string into `artifacts["svg"]` and logs stats. Writing files to disk is deferred to the `export` stage (item #10); `optimize_svg` (item #9) will transform the in-memory string. This keeps the stage pure, needs no `RunContext`/filesystem change, and avoids stray files in tests.
- **Optional width scaling is a capability, not yet a config knob.** `render_svg` accepts an optional per-segment `stroke_widths` map, and a `stream_order_widths` helper derives widths from `stream_orders`/`max_stream_order`. No new config flag is added this item (none exists); the pipeline renders uniform width by default. Wiring a `--width-scale` toggle is deferred so this item stays focused on rendering.
- **Pure & testable.** All rendering is a pure computation over shapely geometries + plain dicts; no GDAL, no real data, no network. Tests build tiny in-memory line networks.

## Open Questions (resolve during implementation)

- Group id form: use `watershed_<HUC code>` (deterministic, meaningful) rather than the PRD example's sequential `watershed_001`. Acceptable, documented deviation.
- Segments present in the graph but absent from every watershed group → emitted last in a `<g id="rivers_unassigned">` (only if non-empty), colored from `segment_colors` or a documented fallback. Edge case; kept simple.
- Empty network (no geometries) → a valid minimal SVG with a `0×0` viewBox and empty background; must not crash.
