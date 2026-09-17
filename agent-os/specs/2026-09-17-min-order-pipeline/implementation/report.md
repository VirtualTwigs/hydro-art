# Implementation Report: `--min-order` pipeline filter (Item #107)

## Summary

Promoted the Strahler-order filtering from `tools/render_common.clip_flowlines`
into the main pipeline as `--min-order N` (default `1` = no filter). This is the
single most impactful CONUS prerequisite — at `min_order=3`, ~80–90% of NHDPlus HR
flowlines are dropped before graph construction, shrinking both the NetworkX graph
and the SVG to workstation-feasible sizes.

## Changes

| File | Change |
|------|--------|
| `src/config.py` | Added `"min_order": 1` to `DEFAULTS`; `min_order: int` field on `Settings`; validation in `build_settings` (positive int, `ConfigError` on ≤0) |
| `src/cli.py` | Added `--min-order` argument (type=int, default=None); wired into overrides |
| `src/pipeline.py` | `_compute_watersheds_stage` filters `stream_orders` and `watersheds` dicts after `assign_stream_order` when `min_order > 1`; empty watersheds pruned |
| `tests/test_min_order.py` | Removed `xfail` marker |

## Design decisions

- **Filter point:** after `assign_stream_order` in `_compute_watersheds_stage`,
  not in `validate` or `build_graph`. This keeps the graph complete for ordering
  computation, then prunes for coloring/rendering. The alternative (filtering in
  `validate` before graph construction) would save more memory but requires
  ordering information not yet computed at that stage.
- **Downstream propagation:** filtering `stream_orders` and `watersheds` is
  sufficient — `assign_colors` and `generate_svg` iterate those dicts, so
  dropped segments naturally disappear from the SVG without touching the graph.
- **Byte-identical default:** `min_order=1` keeps every segment; the filtering
  code path (`if min_order > 1`) never fires.

## Test results

- `tests/test_min_order.py`: **8/8 passed** (config validation ×4, pipeline ×4)
- Full suite: **1091 passed**, 0 failures
- Recipe roundtrip: **11 passed**
