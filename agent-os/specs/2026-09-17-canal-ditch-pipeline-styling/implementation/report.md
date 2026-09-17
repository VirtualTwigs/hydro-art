# Implementation Report: Canal/Ditch/Pipeline Flowline Styling (Item #66)

## Summary

Added opt-in per-segment SVG dash styling for engineered NHDFlowline channels
(CanalDitch, Pipeline, ArtificialPath). When `--flowline-channels` is enabled,
segments are classified by FType and rendered with distinct `stroke-dasharray`
patterns while preserving watershed color, z-order, and flow-scaled width.
Default (disabled) builds are byte-identical.

## Changes

### New files

- **`src/flowline_channels.py`** — Pure classification module (no GIS imports).
  Maps NHD FType codes to normalized channel classes (`stream`, `canal_ditch`,
  `pipeline`, `artificial_path`, `connector`, `coastline`). Provides
  `classify_ftype()` and `build_channel_dashes()` to produce a segment_id →
  SVG dasharray mapping for engineered segments.

- **`tests/test_flowline_channels.py`** — 9 tests covering classification of
  known/missing/unknown FTypes, engineered-class membership, dash mapping with
  default and custom overrides, policy version format, and FType disjointness
  from hydro_structures.

### Modified files

- **`src/loading.py`** — Added `FLOWLINE_ATTRIBUTE_FIELDS = ("FType", "FCode")`
  and `include_attributes: bool = False` parameter to `PyogrioLayerLoader.load_layers()`.
  When `True`, reads FType/FCode from the GDB frame into `Layer.attributes`.

- **`src/graph.py`** — `build_graph()` stores `ftype` on edge data when
  `Layer.attributes` is present. Layers without attributes are unchanged.

- **`src/rendering.py`** — Threaded `channel_dashes: Mapping[int, str] | None`
  through `_path_element`, `_group_lines`, `_halo_lines`, `_render_lines`,
  `render_svg`, and `render_svg_stream`. When a segment_id has an entry,
  `stroke-dasharray` is emitted on the `<path>`.

- **`src/config.py`** — Added `FlowlineChannelSettings` frozen dataclass
  (`enabled`, `dashes`), defaults (`enabled=False`), presets (`screen`,
  `print-state`, `print-county`), and `_coerce_flowline_channels()` validation.

- **`src/cli.py`** — Added `--flowline-channels` and `--flowline-channel-preset`
  CLI flags.

- **`src/pipeline.py`** — `_validate_stage` passes `include_attributes=True` to
  the loader when flowline channels are enabled. `_generate_svg_stage` collects
  edge FTypes, builds channel dashes, and passes them to `render_svg_stream`.
  Fixed: `include_attributes` kwarg only passed when `True` (avoids breaking
  fake loaders in pipeline tests that don't accept the parameter).

### Test files updated

- `tests/test_loading.py` — 2 tests for attribute loading (with/without).
- `tests/test_graph.py` — 2 tests for FType propagation on graph edges.
- `tests/test_rendering_svg.py` — 4 tests for dasharray emission (none/single/mixed/stream).
- `tests/test_config.py` — 5 tests for settings, presets, and CLI flags.
- `tests/test_build.py` — CLI integration test.
- `tests/test_rendering_pipeline.py` — 3 pipeline integration tests
  (disabled default, enabled with dashes, byte-identical when disabled).

## Verification

- Full offline suite: **1133 passed** (0 failed), no regressions.
- Recipe roundtrip: **11/11 passed**.
- Byte-identical default verified in test suite via SHA-256 comparison
  (`test_pipeline_flowline_channels_byte_identical_when_disabled`).
- Real GIS byte-identical verification (task 6.3) deferred — requires
  real data render on NAS-connected machine.

## Design decisions

1. **Per-segment modifier, not a new SVG layer.** Engineered flowlines share
   watershed color/z-order with natural streams — a separate `<g>` group would
   break visual continuity. Instead, `stroke-dasharray` is applied per-`<path>`.

2. **`include_attributes` passed conditionally.** The keyword is only added to
   the `load_layers()` call when `True`, so existing fake loaders (which use
   positional-only signatures) continue to work without modification.

3. **Classification module follows established pattern.** Mirrors
   `hydro_structures.py` — FType policy table, classify function, policy version
   string — and confirms disjoint FType keys via test.
