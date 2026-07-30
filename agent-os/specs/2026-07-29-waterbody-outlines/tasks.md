# Task Breakdown: Waterbody Outlines

## Status

Decisions resolved (see `planning/requirements.md`): on-by-default, single water color, inland
threshold 0, conservative coast policy. **Task Group 1 (W1) implemented** on 2026-07-29; Groups
2–4 (W2–W4) remain.

## Task Group 1: Source layers and classification contract — done

- [x] Expand the allowlist/discovery contract for relevant NHD polygon layers without loading
  unrelated data. (`WATERBODY_LAYER_ALLOWLIST` + `discover_waterbody_layers` in `src/loading.py`,
  kept separate from `HYDRO_LAYER_ALLOWLIST`.)
- [x] Preserve per-feature attributes in `Layer` and define `WaterbodyFeature`/policy objects.
  (`PyogrioLayerLoader.load_waterbody_layers` populates `Layer.attributes`; `src/waterbodies.py`
  adds `WaterbodyFeature`, the versioned `FTYPE_CLASS` policy, and `classify_*`.)
- [x] Add fixture tests for layer discovery and source-type/code classification.
  (`tests/test_waterbodies.py`, plus waterbody-discovery tests in `tests/test_loading.py`.)

## Task Group 2: Polygon normalization and selection

- [ ] Implement polygon repair/reprojection/area measurement/clip path, preserving holes and
  multipart geometry.
- [ ] Implement deterministic threshold and conservative coastal policies with selection report.
- [ ] Add tests for invalid polygons, clipped fragments, area boundaries, holes, and duplicates.

## Task Group 3: Rendering and configuration

- [ ] Add validated waterbody settings plus YAML/CLI precedence.
- [ ] Render dedicated layered SVG groups with stable IDs and no fill.
- [ ] Add style/z-order behavior and tests verifying existing flowline output is unchanged when
  waterbody outlines are disabled.

## Task Group 4: Geographic QA and performance

- [ ] Validate real Clark County, Oregon, and Washington samples against source feature IDs.
- [ ] Establish approved state/county/print thresholds and coastal examples.
- [ ] Measure SVG size/rasterization impact and establish a documented detail policy.

## Verification gates

1. All policy and geometry transforms have offline fixture tests.
2. A waterbody selection report accounts for every candidate feature as selected or excluded.
3. SVG parses in vector tools and preserves holes/multipart features.
4. The normal existing test suite and disabled-default SVG output remain byte-identical.
