# Tasks: Canal/Ditch/Pipeline Flowline Styling (Item #66)

## Task Group 1 — Classification module (`src/flowline_channels.py`)

Pure classification: no geometry, no GIS imports, no rendering.

- [ ] 1.1 Create `src/flowline_channels.py` with `FLOWLINE_CHANNEL_POLICY_VERSION`,
  `FLOWLINE_CHANNEL_CLASSES` tuple, `FLOWLINE_CHANNEL_FTYPE_CLASS` dict (FType→class),
  `FLOWLINE_CHANNEL_FTYPE_LABELS` dict (FType→human label), `ENGINEERED_CLASSES` frozenset,
  `DEFAULT_CHANNEL_DASHES` dict (class→SVG dasharray).
- [ ] 1.2 Implement `classify_ftype(ftype)` → channel class string. Missing/unknown → `"stream"`.
- [ ] 1.3 Implement `build_channel_dashes(edge_ftypes, dashes=None)` → `dict[int, str]`.
  Maps segment_id → dasharray for every segment whose FType classifies as engineered.
  Optional `dashes` overrides `DEFAULT_CHANNEL_DASHES`.
- [ ] 1.4 Create `tests/test_flowline_channels.py`:
  - `test_classify_known_ftypes` — each of the 6 known FTypes maps to the expected class.
  - `test_classify_missing_ftype` — `None`, empty string, non-integer → `"stream"`.
  - `test_classify_unknown_ftype` — unrecognized integer → `"stream"`.
  - `test_engineered_classes_subset` — `ENGINEERED_CLASSES ⊂ FLOWLINE_CHANNEL_CLASSES`.
  - `test_build_channel_dashes_basic` — 3 segments (stream/canal/pipeline) → only 2 get dashes.
  - `test_build_channel_dashes_custom_override` — custom dashes dict replaces defaults.
  - `test_build_channel_dashes_empty` — no engineered segments → empty dict.
  - `test_policy_version_format` — version matches `YYYY-MM-DD.N` pattern.
  - `test_ftype_class_disjoint_from_structures` — confirm no FType code overlap with
    `hydro_structures.HYDRO_STRUCTURE_FTYPE_CLASS` keys.

**Run:** `.venv/bin/python -m pytest tests/test_flowline_channels.py -q`

## Task Group 2 — Attribute loading and graph propagation

Thread FType attributes from GDB → Layer → graph edge.

- [ ] 2.1 Add `FLOWLINE_ATTRIBUTE_FIELDS = ("FType", "FCode")` to `src/loading.py`.
- [ ] 2.2 Add `include_attributes: bool = False` parameter to `PyogrioLayerLoader.load_layers()`.
  When `True`, read `FLOWLINE_ATTRIBUTE_FIELDS` from the GDB frame and populate
  `Layer.attributes` as a parallel tuple of dicts (same pattern as `load_waterbody_layers`).
  Default `False` → existing behavior unchanged.
- [ ] 2.3 Modify `build_graph()` in `src/graph.py`: when a `Layer` has `attributes`, store
  the `FType` value on the edge data dict (`ftype=attrs.get("FType")`). Layers without
  attributes → no `ftype` key (preserves existing edge data shape).
- [ ] 2.4 Tests in `tests/test_loading.py` and `tests/test_graph.py`:
  - `test_load_layers_without_attributes` — default call produces `Layer.attributes=None`.
  - `test_load_layers_with_attributes` — `include_attributes=True` populates parallel attrs.
  - `test_build_graph_preserves_ftype` — edge data includes `ftype` when layer has attributes.
  - `test_build_graph_no_ftype_without_attributes` — `ftype` absent from edge data when
    layer has no attributes.

**Run:** `.venv/bin/python -m pytest tests/test_loading.py tests/test_graph.py -q`

## Task Group 3 — Rendering: per-segment dash patterns

Thread `channel_dashes` through the rendering pipeline.

- [ ] 3.1 Add `channel_dashes: Mapping[int, str] | None = None` parameter to `_path_element`
  in `src/rendering.py`. When present and segment_id is in the mapping, emit
  `stroke-dasharray="<value>"` on the `<path>`.
- [ ] 3.2 Thread `channel_dashes` through `_group_lines`, `_halo_lines` → `_path_element`.
- [ ] 3.3 Thread `channel_dashes` through `_render_lines`, `render_svg`, `render_svg_stream`.
- [ ] 3.4 Tests in `tests/test_rendering_svg.py`:
  - `test_render_svg_no_dashes_default` — no `channel_dashes` → no `stroke-dasharray` in output.
  - `test_render_svg_with_channel_dashes` — segment with dash entry gets `stroke-dasharray`.
  - `test_render_svg_mixed_dashes` — only engineered segments get dashes, natural segments don't.
  - `test_render_svg_stream_with_dashes` — streaming path produces identical output.

**Run:** `.venv/bin/python -m pytest tests/test_rendering_svg.py -q`

## Task Group 4 — Config, CLI, and presets

Settings, validation, CLI flags, presets.

- [ ] 4.1 Add `FlowlineChannelSettings` frozen dataclass to `src/config.py`:
  `enabled: bool`, `dashes: dict[str, str]`.
- [ ] 4.2 Add `DEFAULTS["flowline_channels"]` and `FLOWLINE_CHANNEL_PRESETS` dict
  (`screen`, `print-state`, `print-county`).
- [ ] 4.3 Add `_coerce_flowline_channels()` validation function following the existing
  `_coerce_hydro_structures` pattern. Wire into `build_settings`.
- [ ] 4.4 Add `--flowline-channels` (enable flag) and `--flowline-channel-preset` to
  `src/cli.py`.
- [ ] 4.5 Tests in `tests/test_config.py` and `tests/test_build.py`:
  - `test_flowline_channels_default_disabled` — default settings have `enabled=False`.
  - `test_flowline_channels_enable` — `{"flowline_channels": {"enabled": true}}` produces
    `FlowlineChannelSettings(enabled=True, ...)`.
  - `test_flowline_channels_preset_screen` — preset applies default dashes.
  - `test_flowline_channels_cli_flag` — `--flowline-channels` sets `enabled=True`.
  - `test_flowline_channels_cli_preset` — `--flowline-channel-preset screen` applies preset.

**Run:** `.venv/bin/python -m pytest tests/test_config.py tests/test_build.py -q`

## Task Group 5 — Pipeline integration

Wire classification + dash mapping into the pipeline stages.

- [ ] 5.1 In `_validate_stage` (`src/pipeline.py`): when `settings.flowline_channels.enabled`,
  pass `include_attributes=True` to the loader.
- [ ] 5.2 In `_generate_svg_stage`: when `settings.flowline_channels.enabled`, iterate graph
  edges to collect `edge_ftypes: dict[int, int | None]`, call
  `build_channel_dashes(edge_ftypes, settings.flowline_channels.dashes)`, pass as
  `channel_dashes` to `render_svg_stream`.
- [ ] 5.3 Tests in `tests/test_pipeline.py` and `tests/test_rendering_pipeline.py`:
  - `test_pipeline_default_no_channel_dashes` — disabled setting → no dasharray in SVG output.
  - `test_pipeline_with_flowline_channels` — enabled + fake layers with FType attrs →
    engineered segments get dasharray in SVG output.
  - `test_pipeline_flowline_channels_byte_identical_when_disabled` — disabled output matches
    baseline (byte-identical check via sha256).

**Run:** `.venv/bin/python -m pytest tests/test_pipeline.py tests/test_rendering_pipeline.py -q`

## Task Group 6 — Full suite regression + smoke

- [ ] 6.1 Run full suite: `.venv/bin/python -m pytest -q` — all green, no regressions.
- [ ] 6.2 Run recipe roundtrip: `node tests/test_recipe_roundtrip.cjs` — green.
- [ ] 6.3 Verify byte-identical default: compare SVG sha256 of a default build (no
  `--flowline-channels` flag) against previous output — must match exactly.
- [ ] 6.4 Write `implementation/report.md`.
