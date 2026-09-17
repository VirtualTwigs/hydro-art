# Requirements: Canal/Ditch/Pipeline Flowline Styling (Epoch 16, Item #66)

## Background

NHDFlowline segments carry an `FType` attribute distinguishing natural streams from engineered
channels. Today all flowlines render identically — a canal through irrigated farmland looks the
same as a mountain creek. Item #66 makes engineered channels visually distinct by applying
per-class dash patterns and optional color overrides while keeping natural streams unchanged.

This was descoped from Epoch 16 (hydro-structure taxonomy) because it targets **NHDFlowline**
FTypes (the same segments already in the graph/watershed/coloring pipeline), not the separate
NHDLine/NHDPoint/NHDArea structure geometries that #65/#67/#68 handle.

## NHDFlowline FType codes (from the NHD spec)

| FType | Name | Class for #66 |
|-------|------|---------------|
| 460 | StreamRiver | `stream` (natural, default styling) |
| 336 | CanalDitch | `canal_ditch` (engineered) |
| 428 | Pipeline | `pipeline` (engineered) |
| 558 | ArtificialPath | `artificial_path` (engineered — e.g., through a reservoir) |
| 334 | Connector | `connector` (network topology, render as natural) |
| 566 | Coastline | `coastline` (render as natural) |

Only `canal_ditch`, `pipeline`, and `artificial_path` get distinct styling. `stream`, `connector`,
and `coastline` all render with the existing default style (no visual change).

## Functional requirements

1. **Preserve FType on NHDFlowline load.** `load_layers()` must read `FType` (and optionally
   `FCode`) from the GDB and store them as per-geometry attributes on the `Layer` object.

2. **Store FType on graph edges.** `build_graph()` must propagate the `FType` attribute from
   the loaded layer onto each edge's data dict so downstream stages can access it.

3. **Classify flowline channel types.** A new pure module `src/flowline_channels.py` maps
   FType → normalized channel class (`stream`, `canal_ditch`, `pipeline`, `artificial_path`,
   `connector`, `coastline`). Missing/unknown FType → `stream` (conservative default).

4. **Render engineered channels distinctly.** In `render_svg` / `render_svg_stream`, segments
   classified as engineered channels get a distinct SVG `stroke-dasharray` pattern. Each
   engineered class has its own default dash pattern (e.g., canals = long-dash, pipelines =
   dotted, artificial paths = dash-dot). The color stays the same (watershed-assigned) — only
   the dash pattern changes. The channel styling renders in the SAME `<g>` groups as natural
   streams (not a separate layer) so z-order is unchanged.

5. **Settings + presets + CLI.** New `FlowlineChannelSettings` dataclass on `Settings`:
   `enabled: bool` (default `False`), per-class style overrides (dash, opacity). CLI flag
   `--flowline-channels` / `--flowline-channel-preset`. Presets: `screen`, `print-state`,
   `print-county`.

6. **Pipeline integration.** Wire into `_generate_svg_stage`: when `flowline_channels.enabled`,
   build a `channel_classes: dict[int, str]` mapping from graph edge FTypes, pass to the
   renderer. No new pipeline stage — this is a rendering option, not a data stage.

7. **Default (disabled) build byte-identical.** When `flowline_channels.enabled=False` (the
   default), no attributes are read, no classification runs, no dash patterns are applied.
   The output is bit-for-bit identical to the current default.

## Non-functional requirements

- No top-level GDAL imports in `src/` or `tests/`.
- `src/flowline_channels.py` is a classification module — no geometry, no GIS imports, runs
  without even shapely.
- Complementary with the hydro-structure taxonomy: FType 336 appears in BOTH NHDFlowline and
  NHDArea/NHDLine; the flowline-channel classifier handles the flowline occurrence, the
  structure classifier handles the area/line occurrence. No overlap — they classify different
  source layers.
- All tests offline with hand-built inputs.

## Out of scope

- New pipeline stage or change to `PIPELINE_STAGES` order.
- Changing the graph structure (huc4 grouping, watershed coloring, stream ordering).
- Color overrides per channel type (only dash pattern; color stays watershed-assigned).
- Width overrides per channel type.
- Any web/, fulfillment, or elevation/3D interaction.
