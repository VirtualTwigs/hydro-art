# Spec: Promote `--min-order` to the pipeline (Item #107)

## Overview

Wire Strahler-order filtering into the main pipeline as a `--min-order N` CLI
flag (default `1` = no filter). Today this filtering exists only in
`tools/render_common.clip_flowlines` — it drops flowlines below a Strahler
threshold *before* the expensive spatial clip. Promoting it to the pipeline
means large-state and CONUS renders can shed ~80–90% of features before graph
construction, keeping memory feasible.

## Scope

1. **`src/config.py`** — add `min_order` to `DEFAULTS` (default `1`), validate
   in `build_settings` (positive int, `ConfigError` on ≤0), add field to
   `Settings`.
2. **`src/cli.py`** — add `--min-order` argument (type `int`, default `None`).
3. **`src/pipeline.py`** — in `_compute_watersheds_stage`, after
   `assign_stream_order`, filter the graph's edges and the `stream_orders` dict
   to drop segments below `settings.min_order`. The remaining stages
   (`assign_colors`, `generate_svg`) consume the filtered artifacts.
4. **Byte-identical default.** `min_order=1` keeps every segment — no filtering
   code path fires, output is identical to a build without the field.

## Non-goals

- Streaming SVG writer (#108) — separate item.
- CONUS region alias (#109) — separate item.
- Changes to `tools/render_common.clip_flowlines` — it keeps its own
  `min_order` param for the non-pipeline render scripts.

## Integration point

The filter runs in `_compute_watersheds_stage` *after* `assign_stream_order`
returns, so every segment already has its Strahler/Shreve/Hack order computed.
Segments below the threshold are removed from:
- `stream_orders` dict
- `hydro_graph.digraph` edges (or: rebuild geometries/segment_colors maps
  downstream to exclude them)

The simplest correct approach: after computing `stream_orders`, build a
`kept` set of segment IDs where `order >= min_order`, then filter the
`stream_orders` dict. Downstream stages (`assign_colors`, `generate_svg`)
naturally skip filtered segments because they iterate `stream_orders` /
`segment_colors` / `watersheds` which no longer contain the dropped IDs.

## Tests

Pre-written in `tests/test_min_order.py` (currently xfail). The implementation
must make all 7 tests pass and remove the `xfail` marker.
