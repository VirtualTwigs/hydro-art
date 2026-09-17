# Specification: Canal/Ditch/Pipeline Flowline Styling (Item #66)

## Goal

Style NHDFlowline engineered channels (CanalDitch, Pipeline, ArtificialPath) distinctly from
natural streams by applying per-segment SVG dash patterns while keeping their watershed color
and z-order unchanged. Default (disabled) build byte-identical.

## User Stories

- As a viewer, I want to see at a glance which rivers are natural streams and which are
  engineered canals, pipelines, or artificial paths, so the map reads as an honest depiction
  of the hydrographic network rather than treating all water the same.
- As a builder, I want an opt-in `--flowline-channels` flag that classifies and styles
  engineered flowlines so I can toggle the feature without changing my build command.

## NHDFlowline FType Classification

NHDFlowline segments carry an `FType` attribute. The classifier maps each to a normalized
channel class:

| FType | NHD Name | Channel Class | Styled? |
|-------|----------|---------------|---------|
| 460 | StreamRiver | `stream` | No (default) |
| 336 | CanalDitch | `canal_ditch` | Yes — long dash `"8,4"` |
| 428 | Pipeline | `pipeline` | Yes — dotted `"2,4"` |
| 558 | ArtificialPath | `artificial_path` | Yes — dash-dot `"6,3,2,3"` |
| 334 | Connector | `connector` | No (default) |
| 566 | Coastline | `coastline` | No (default) |
| (missing/unknown) | — | `stream` | No (conservative default) |

**Relationship to `src/hydro_structures.py`:** FType 336 (CanalDitch) appears in BOTH
NHDFlowline and NHDArea/NHDLine. This module classifies the *flowline* occurrence; the
existing structure taxonomy classifies the *area/line* occurrence. They operate on different
source layers — no overlap.

## Architecture

### Approach: per-segment dash modifier (not a new SVG layer)

Engineered flowlines are part of the river network — they carry watershed colors, stream
orders, and flow-scaled widths like any other segment. Creating a separate layer would break
coloring continuity and z-order. Instead:

1. **Classify segments** by FType → channel class
2. **Build a dash mapping** `channel_dashes: dict[int, str]` (segment_id → SVG dasharray)
3. **Pass into rendering** — `_path_element` emits `stroke-dasharray` when a segment has an
   entry in the mapping

This is the minimal change: one new optional parameter threaded through the rendering path,
no new `<g>` groups, no restructuring of the watershed groups. Segments without a dash entry
(natural streams) are completely unaffected.

### Changes by module

**New module: `src/flowline_channels.py`** (classification only — no geometry, no GIS imports)
- `FLOWLINE_CHANNEL_POLICY_VERSION = "2026-09-17.1"`
- `FLOWLINE_CHANNEL_CLASSES`: `("stream", "canal_ditch", "pipeline", "artificial_path",
  "connector", "coastline")`
- `FLOWLINE_CHANNEL_FTYPE_CLASS: dict[int, str]` — the FType→class table
- `ENGINEERED_CLASSES: frozenset[str]` — `{"canal_ditch", "pipeline", "artificial_path"}`
- `DEFAULT_CHANNEL_DASHES: dict[str, str]` — default SVG dasharray per engineered class
- `classify_ftype(ftype: int | str | None) -> str` — returns channel class
- `build_channel_dashes(edge_ftypes: Mapping[int, int | str | None], dashes: Mapping[str, str] | None = None) -> dict[int, str]` — maps segment_id → dasharray for all engineered segments

**Modify: `src/loading.py`** (lines 181-222)
- Add `FLOWLINE_ATTRIBUTE_FIELDS: tuple[str, ...]` = `("FType", "FCode")`
- When flowline-channel classification is requested, `load_layers()` preserves attributes
  alongside geometries (same pattern as `load_waterbody_layers` but with fewer fields)
- **Approach:** add an optional `include_attributes: bool = False` parameter to `load_layers()`.
  When `True`, read `FLOWLINE_ATTRIBUTE_FIELDS` and populate `Layer.attributes`. Default
  `False` → no behavior change.

**Modify: `src/graph.py`** (lines 139-146)
- When a `Layer` carries `attributes`, store the parallel attribute dict (or just `ftype`)
  on the edge data. Layers without attributes → no change (byte-identical path).
- Add `ftype` key to edge data when available: `ftype=attrs.get("FType")` if `layer.attributes`.

**Modify: `src/rendering.py`** (lines 649-665, 682-710, 920-945)
- Add `channel_dashes: Mapping[int, str] | None = None` parameter to `_path_element`,
  `_group_lines`, `_halo_lines`, `_render_lines`, `render_svg`, and `render_svg_stream`.
- In `_path_element`: if `channel_dashes` has an entry for `segment_id`, emit
  `stroke-dasharray="<value>"`.
- Threading only — no structural change to how groups are built.

**Modify: `src/config.py`**
- New `FlowlineChannelSettings` frozen dataclass: `enabled: bool`, `dashes: dict[str, str]`
  (per-class dash overrides).
- Defaults: `enabled=False`, `dashes={}` (uses module defaults).
- Presets: `screen` (default dashes), `print-state` (wider dashes for legibility at scale),
  `print-county` (default dashes).
- CLI: `--flowline-channels` (enable), `--flowline-channel-preset`.
- Validation: `_coerce_flowline_channels()` following the established pattern.

**Modify: `src/pipeline.py`**
- In `_generate_svg_stage`: when `settings.flowline_channels.enabled`, iterate graph edges
  to build `edge_ftypes: dict[int, int]`, call `build_channel_dashes(edge_ftypes, settings.flowline_channels.dashes)`, pass result as `channel_dashes` to `render_svg_stream`.
- In `_validate_stage`: when `settings.flowline_channels.enabled`, pass
  `include_attributes=True` to the loader so FType attributes are preserved.

## Byte-identical guarantee

When `flowline_channels.enabled=False` (default):
- `load_layers()` called without `include_attributes` → `Layer.attributes` stays `None`
- `build_graph()` sees no attributes → edge data unchanged
- `render_svg` / `render_svg_stream` receive `channel_dashes=None` → no dasharray emitted
- Output identical to current

## Out of Scope

- Color overrides per channel class (color stays watershed-assigned).
- Width overrides per channel class (width stays flow/order-scaled).
- New pipeline stage or `PIPELINE_STAGES` order change.
- Any web/, fulfillment, elevation/3D, or monthly-flow interaction.
- Rendering engineered channels in a separate SVG `<g>` layer.
