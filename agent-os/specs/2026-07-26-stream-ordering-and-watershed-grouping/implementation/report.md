# Implementation Report: Stream Ordering & Watershed Grouping

**Date:** 2026-07-26
**Status:** Complete — all 3 task groups done, 91/91 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/ordering.py` | `assign_stream_order(graph, method)` dispatcher plus `strahler_order`, `shreve_order`, `hack_order`, `custom_order(graph, weight)`, and `OrderingError`. Pure graph computation in topological order; cycles raise. |
| `src/watersheds.py` | `group_segments_by_huc(graph, level)`, `HUC_LEVEL_DIGITS`, `WatershedStats` + `watershed_stats()`. Groups segment ids by HUC prefix; finer-than-available levels degrade to HUC4 with one warning. |
| `src/config.py` | `stream_method` (allowlist strahler/shreve/hack/custom, default strahler) and `huc_level` (allowlist HUC2–HUC12, default HUC4) fields, defaults, allowlists, and `build_settings` validation. |
| `src/cli.py` | `--stream-method` / `--huc-level` flags (default `None`) + `cli_overrides` entries so unset flags never clobber YAML. |
| `src/graph.py` | `build_graph` now records `huc4=layer.huc4` on each segment edge. |
| `src/pipeline.py` | Real `compute_watersheds` stage: computes orders + HUC groups from `artifacts["hydro_graph"]`, stores `stream_orders`/`watersheds`/`max_stream_order`, logs summary via `rich`. |
| `build.py` | Settings table now shows `stream_method` and `huc_level`. |
| `tests/test_ordering.py`, `test_watersheds.py`, `test_watersheds_pipeline.py` | 8 + 6 + 2 = 16 new tests (91 total suite). |

## Key decisions

- **Strahler vs. Shreve confluence rule:** Strahler increments only when the two highest incoming orders tie (otherwise inherits the single highest); Shreve simply sums incoming magnitudes. Both start sources at 1.
- **Hack via cumulative upstream length:** the main channel at each junction is the incoming segment with the greatest cumulative upstream length (computed forward in topo order); order is assigned in reverse topo order so parents are known before their tributaries. Ties break on `segment_id` for determinism.
- **Custom is the §12 extensibility seam:** `custom_order(graph, weight)` takes a `weight(edge_data)` hook; the dispatcher's default weight is cumulative upstream length.
- **Cycle safety:** all methods derive a topological order first; a cyclic graph raises `OrderingError` with a clear message.
- **HUC grouping by prefix, honest about data:** HUC codes are hierarchical prefixes, so HUC2/HUC4 come straight from the loaded `huc4`. HUC6–HUC12 need sub-HUC boundary polygons we do not yet load, so they degrade to HUC4 grouping with a single warning — the signature is stable for when finer WBD layers arrive.
- **`huc4` carried on edges:** grouping reads the code directly from edge data (added in `build_graph`), avoiding fragile re-derivation.
- **Pure and deterministic:** no new injected dependency; the stage is a deterministic computation over the graph. Tests use hand-built in-memory graphs (no GDAL, no real data).

## Acceptance criteria met

- All four ordering methods computed correctly; dispatcher + config/CLI validation work; cyclic graph raises.
- Grouping by HUC prefix at the selected level; finer-than-available degrades + warns; `WatershedStats` reports counts.
- Pipeline `compute_watersheds` computes orders + groups in tests and production; `stream_orders`, `watersheds`, `max_stream_order` land in artifacts and are logged; downstream stages remain stubs.
- Full suite passes with no regressions (91 passed, 4 pre-existing warnings); 16 new tests (TG1 8, TG2 6, TG3 2).

## Notes for next feature (roadmap #7: basin coloring)

- Input seams now on the context: `artifacts["stream_orders"]` (segment_id → order), `artifacts["watersheds"]` (HUC code → segment ids), `artifacts["max_stream_order"]` for normalization.
- Coloring can key line weight/opacity off stream order and hue off watershed group; both are already deterministic and testable without real data.
- HUC6–HUC12 still degrade to HUC4; once sub-HUC WBD polygons are loaded, `group_segments_by_huc` picks up finer levels without an API change.
