# Implementation Report: Deterministic Basin Coloring

**Date:** 2026-07-26
**Status:** Complete — all 3 task groups done, 106/106 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/coloring.py` | New module. `PALETTES` (neon, the 12 §16 colors as hex) + `get_palette`; `build_adjacency(graph, watersheds)` (watersheds adjacent when they share a river junction); `greedy_color(adjacency)` (deterministic Welsh–Powell); `assign_colors(graph, watersheds, palette)` (adjacency → coloring → palette lookup); `ColoringError`. Pure, deterministic, no randomness. |
| `src/config.py` | `SUPPORTED_PALETTES = ("neon",)` allowlist (exported) + `palette` validation in `build_settings` (raises `ConfigError`). Default `neon` unchanged. |
| `src/pipeline.py` | Real `assign_colors` stage: computes `watershed_colors` from `artifacts["hydro_graph"]` + `artifacts["watersheds"]` with `settings.palette`, expands to `segment_colors`, stores both + `palette`, logs a `rich` summary. Downstream stages remain stubs. |
| `tests/test_coloring_palette.py`, `test_coloring.py`, `test_coloring_pipeline.py` | 6 + 7 + 2 = 15 new tests (106 total suite). |

## Key decisions

- **Adjacency from shared junctions, not polygons.** Two watersheds are adjacent when some graph node has incident edges in both. This falls straight out of the hydro graph + item #6 grouping (rivers connect at confluence nodes across HUC borders) — no WBD polygon geometry or spatial join needed, and it stays pure/testable.
- **Deterministic greedy coloring (Welsh–Powell).** Vertices ordered by descending adjacency degree, ties broken by HUC code; each takes the lowest color index unused by colored neighbors. Proper coloring in ≤ maxdegree+1 classes; identical inputs → identical class assignments. No RNG anywhere (satisfies §15 "do NOT assign random colors").
- **Palette assignment by class index.** `palette[class_index % len(palette)]`. When chromatic number ≤ palette size (the common case for the 12-color neon palette), adjacent watersheds always get distinct colors → maximum contrast; larger cases wrap deterministically.
- **Two artifacts for the renderer.** `watershed_colors` (HUC code → hex) plus `segment_colors` (segment_id → hex, expanded from watershed membership) so item #8 can paint paths directly by segment id.
- **Palette as validated config data.** Colors live in `src/coloring.py`; the config allowlist gates the `palette` value at the boundary, consistent with the existing `SUPPORTED_*` pattern. Adding palettes later needs no API change.
- **No new injected dependency.** Like `compute_watersheds`, the stage is a deterministic computation over the graph; tests use hand-built graphs + watershed dicts (no GDAL, no real data).

## Acceptance criteria met

- Neon palette present with 12 valid, distinct hex colors; `get_palette` raises on unknown; `palette` validated at the boundary; unset flag never clobbers YAML.
- Adjacency derived from shared junctions; adjacent watersheds get distinct classes/colors where chromatic number ≤ palette size; fully deterministic.
- Pipeline `assign_colors` computes watershed + segment colors in tests and production; `watershed_colors`, `segment_colors`, `palette` land in artifacts; stats logged; downstream stages remain stubs.
- Full suite passes with no regressions (106 passed, 4 pre-existing warnings); 15 new tests (TG1 6, TG2 7, TG3 2).

## Smoke test

`Pipeline.run` on the offline fake-downloader/loader network produces
`watershed_colors={'1707': '#00ffff'}`, `segment_colors={0..2: '#00ffff'}`,
`palette='neon'`, with the stage logged and `generate_svg`/`optimize_svg`/`export`
still stubs.

## Notes for next feature (roadmap #8: layered SVG rendering)

- Input seams now on the context: `artifacts["segment_colors"]` (segment_id → hex), `artifacts["watershed_colors"]` (HUC code → hex), `artifacts["watersheds"]` (HUC code → segment ids, for grouping SVG layers), and each edge's `geometry`/`length` in `artifacts["hydro_graph"]`.
- Render each segment as a round-capped/round-joined path colored by `segment_colors[segment_id]`, grouped into `<g>` layers per watershed; background `settings.background`; base stroke `settings.line_width`.
- Optional stream-order/width scaling can key off `artifacts["stream_orders"]` + `artifacts["max_stream_order"]` (already present from item #6).
