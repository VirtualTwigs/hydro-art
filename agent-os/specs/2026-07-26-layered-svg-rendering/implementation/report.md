# Implementation Report: Layered SVG Rendering

**Date:** 2026-07-26
**Status:** Complete — all 3 task groups done, 120/120 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/rendering.py` | New module. Geometry core (`bounds`, `format_number`, `transform_coords`, `path_d`) + `render_svg(...)` (full layered SVG document) + `stream_order_widths(...)` (optional width scaling). Pure, deterministic, stdlib-only serialization. |
| `src/pipeline.py` | Real `generate_svg` stage: builds `{segment_id: geometry}` from `artifacts["hydro_graph"]`, renders via `render_svg` with `settings.background`/`line_width` + `artifacts["segment_colors"]`/`artifacts["watersheds"]`, stores `artifacts["svg"]`, logs a `rich` summary. `optimize_svg`/`export` remain stubs. |
| `tests/test_rendering.py`, `test_rendering_svg.py`, `test_rendering_pipeline.py` | 5 + 6 + 3 = 14 new tests (120 total suite). |

## Key decisions

- **Stdlib SVG serializer, no `svgwrite` dependency.** Confirmed with the user: the project prizes determinism (item #10 wants byte-identical output) and offline tests, so the SVG is built by hand over the stdlib. Full control of coordinate precision + element ordering; no install, no network. `render_svg` is a clean seam if `svgwrite` is ever swapped in. This deviates from `tech-stack.md`'s `svgwrite` note (documented here + in requirements.md).
- **generate_svg produces a document, not a file.** The stage stores the SVG string in `artifacts["svg"]`; `optimize_svg` (item #9) transforms it and `export` (item #10) writes files. Keeps the stage pure, needs no `RunContext`/filesystem change, and avoids stray files during tests.
- **Cartesian Y-flip.** Coordinates map to `(x − min_x, max_y − y)` so projected northing renders upward; `viewBox="0 0 (max_x−min_x) (max_y−min_y)"`. Verified in the smoke test (three EPSG:5070 segments render into a ~156k×236k viewBox).
- **Styling by SVG inheritance.** Root `<svg>` carries `fill="none"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, base `stroke-width` (PRD §19); each watershed `<g>` sets `stroke` once (item #7 gives a watershed's segments one shared color); paths are bare `<path d=…/>`. Compact and correct; SVGO (item #9) will dedupe further.
- **Deterministic serialization.** Watershed groups in sorted HUC-code order; segments in sorted `segment_id` order; coordinates at fixed precision (default 3) with `-0`→`0` and trailing zeros stripped; stable attribute order. Two runs produce byte-identical strings (tested at module + pipeline level).
- **Group id = `watershed_<HUC code>`.** Deterministic and meaningful; a documented deviation from PRD §18's sequential `watershed_001`.
- **Unassigned segments** (present in the graph, in no watershed group) go into a trailing `<g id="rivers_unassigned">` with per-path stroke, emitted only when non-empty.
- **Optional width scaling as capability, not config.** `render_svg(..., stroke_widths=...)` + `stream_order_widths(stream_orders, max_order, base_width, max_scale)` implement PRD §17's optional scaling and are unit-tested, but no `--width-scale` flag is wired (none exists); the pipeline renders uniform width. Deferred to avoid scope creep.
- **No new injected dependency.** Like the other compute stages, rendering is a deterministic computation over in-memory geometries + dicts; tests use hand-built lines (no GDAL, no browser, no real data).

## Acceptance criteria met

- SVG matches PRD §18 structure (`<defs/>`, `<g id="background">`, per-watershed `<g>`) and §19 default styling (black bg, 0.35 stroke, round cap/join, `fill="none"`); rivers grouped by watershed; output deterministic.
- Every segment is a round-capped/round-joined vector path colored via item #7's `segment_colors`; optional stream-order width scaling supported + tested.
- Pipeline `generate_svg` produces `artifacts["svg"]` (layered, colored, on background) in tests and production; stats logged; `optimize_svg`/`export` remain stubs.
- Full suite passes with no regressions (120 passed, 4 pre-existing warnings); 14 new tests (TG1 5, TG2 6, TG3 3).

## Smoke test

`Pipeline.run` on the offline fake-downloader/loader network renders the 3-segment
Oregon network into a well-formed SVG: `viewBox="0 0 156597.516 236020.307"`, a
`#000000` background rect, one `<g id="watershed_1707" stroke="#00ffff">` holding
three `<path>` elements, `optimize_svg`/`export` still logged as stubs.

## Notes for next feature (roadmap #9: optional glow & SVG optimization)

- Input seam: `artifacts["svg"]` (the SVG document string). Glow adds a `<defs>` filter (Gaussian-blur mode) or duplicated blurred paths (pure-vector mode), keyed off `settings.glow` (config field already exists) with a configurable radius (no config field yet — add one).
- The renderer currently emits a bare `<defs/>`; glow/optimization can populate it. `render_svg` accepts a `precision` arg for the coordinate-precision optimization pass.
- SVGO is a Node tool (subprocess) — keep it behind an injectable seam so tests stay offline, mirroring the Downloader/LayerLoader pattern.
