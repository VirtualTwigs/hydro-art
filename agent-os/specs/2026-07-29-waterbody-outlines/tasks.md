# Task Breakdown: Waterbody Outlines

## Status

Decisions resolved (see `planning/requirements.md`): on-by-default, single water color, inland
threshold 0, conservative coast policy. **Task Groups 1–3 (W1–W3) implemented** (W1/W2 on
2026-07-29, W3 on 2026-07-30); Group 4 (W4, geographic QA & presets) remains.

## Task Group 1: Source layers and classification contract — done

- [x] Expand the allowlist/discovery contract for relevant NHD polygon layers without loading
  unrelated data. (`WATERBODY_LAYER_ALLOWLIST` + `discover_waterbody_layers` in `src/loading.py`,
  kept separate from `HYDRO_LAYER_ALLOWLIST`.)
- [x] Preserve per-feature attributes in `Layer` and define `WaterbodyFeature`/policy objects.
  (`PyogrioLayerLoader.load_waterbody_layers` populates `Layer.attributes`; `src/waterbodies.py`
  adds `WaterbodyFeature`, the versioned `FTYPE_CLASS` policy, and `classify_*`.)
- [x] Add fixture tests for layer discovery and source-type/code classification.
  (`tests/test_waterbodies.py`, plus waterbody-discovery tests in `tests/test_loading.py`.)

## Task Group 2: Polygon normalization and selection — done

- [x] Implement polygon repair/reprojection/area measurement/clip path, preserving holes and
  multipart geometry. (`process_waterbodies` in `src/waterbody_selection.py` reuses
  `repair_geometry`/`clip_geometry`; area in EPSG:5070 = m²; `area_m2` added to
  `WaterbodyFeature`.)
- [x] Implement deterministic threshold and conservative coastal policies with selection report.
  (`WaterbodySelectionPolicy` inland/coastal thresholds + `coastal_mode="conservative"` excludes
  clipped coastal fragments; `WaterbodySelection` report accounts for every candidate, plus
  duplicate-geometry dedup and shared-edge counting.)
- [x] Add tests for invalid polygons, clipped fragments, area boundaries, holes, and duplicates.
  (`tests/test_waterbody_selection.py`, 8 offline fixture tests.)

## Task Group 3: Rendering and configuration — done

- [x] Add validated waterbody settings plus YAML/CLI precedence. (`WaterbodySettings` +
  `DEFAULTS["waterbodies"]` + `_coerce_waterbodies` in `src/config.py`; `--waterbodies/
  --no-waterbodies`, `--waterbody-color`, `--waterbody-stroke-width` flags with per-sub-key
  deep-merge in `src/cli.py`; `tests/test_waterbody_config.py`, 8 tests.)
- [x] Render dedicated layered SVG groups with stable IDs and no fill. (`polygon_path_d` +
  `_waterbody_lines` in `src/rendering.py` emit `<g id="waterbodies" fill="none">` with per-feature
  `<g id="waterbody_{id}">`/`<path id="waterbody_{id}_outline">`; holes/multipart preserved via
  per-ring closed subpaths; `tests/test_waterbody_rendering.py`, 5 tests.)
- [x] Add style/z-order behavior and tests verifying existing flowline output is unchanged when
  waterbody outlines are disabled. (`waterbody_order` below/above + configured color/width;
  pipeline wiring loads/classifies/selects only when enabled AND the loader supports it —
  `tests/test_waterbody_pipeline.py`, 4 tests, including a byte-identical disabled build.)

## Task Group 4: Geographic QA and performance

- [ ] Validate real Clark County, Oregon, and Washington samples against source feature IDs.
- [ ] Establish approved state/county/print thresholds and coastal examples.
- [ ] Measure SVG size/rasterization impact and establish a documented detail policy.

## Verification gates

1. All policy and geometry transforms have offline fixture tests.
2. A waterbody selection report accounts for every candidate feature as selected or excluded.
3. SVG parses in vector tools and preserves holes/multipart features.
4. The normal existing test suite and disabled-default SVG output remain byte-identical.
