# Task Breakdown: Natural Water Features (Epoch 15)

## Overview
Total Tasks: 6 task groups (roadmap items 61–64 plus a pre-flight verification and a final regression/QA gate)

This feature mirrors the shipped Epoch 1.5 waterbody feature beat-for-beat:
versioned taxonomy → loader seam → repair/reproject/clip/select → dedicated
fill-free/point SVG layers → config presets → additive pipeline integration → QA.
Every task group follows the project TDD discipline: **write 2–8 focused tests
FIRST, run ONLY those, then implement to green.** The full offline suite runs once
at the end (Task Group 6) for regressions.

Templates to mirror (do not duplicate — parallel these exactly):
- `src/waterbodies.py` / `tests/test_waterbodies.py` — versioned classification taxonomy
- `src/waterbody_selection.py` / `tests/test_waterbody_selection.py` — repair/reproject/clip/select
- `src/loading.py` (`WATERBODY_LAYER_ALLOWLIST`, `load_waterbody_layers`) — loader seam
- `src/config.py` (`WaterbodySettings`, `WATERBODY_PRESETS`, `_coerce_waterbodies`) — settings/presets/precedence
- `src/rendering.py` (`_waterbody_lines`, `polygon_path_d`, `render_svg` z-order) — fill-free `<g>` emission
- `src/pipeline.py` (`_validate_stage` load guard, `_select_waterbody_outlines`) — additive integration
- `tools/overlay_facilities.py` (`_marker`) — point-glyph shape precedent

## Cross-cutting constraints (apply to every relevant group; repeated in acceptance criteria)
- **TDD:** 2–8 focused tests first per group; run ONLY those tests until green; no exhaustive coverage.
- **Matching test file:** every new `src/<name>.py` gets a matching `tests/test_<name>.py`; pipeline integration goes in `tests/test_natural_features_pipeline.py`.
- **Offline-suite discipline:** NO top-level GDAL-backed imports (`pyogrio`/`geopandas`/`shapely`/`rasterio`) in `src/` or `tests/` — keep them lazy-imported behind the loader/reproject seams; tests inject fake loaders + hand-built shapely/geometry inputs; suite stays fully offline (no network, no real datasets).
- **CRS:** import `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`.
- **Deterministic + opt-in default:** every new family defaults `enabled: False`; preset/enablement resolved off the frozen `Settings` (mirroring `_coerce_waterbodies`); the DEFAULT (features-disabled) build must stay BYTE-IDENTICAL.
- **Additive pipeline only:** load in the `validate` stage, select/render in `generate_svg`; do NOT change `PIPELINE_STAGES` order or the `_stub` mechanism.

---

## Task List

### Pre-flight

#### Task Group 0: Confirm NHDPoint FType codes against a real GDB
**Dependencies:** None
**Note:** This is a verification step, NOT a blocker for the offline test structure. The
classification RULE (FType-driven, name-only-refining, missing→excluded) is fixed and
can be built immediately; only the placeholder numeric FType code VALUES for
waterfalls vs. rapids need confirming before fixtures hardcode them.

- [ ] 0.0 Confirm falls/rapids FType codes
  - [ ] 0.1 Inspect a real NHDPoint layer in a cached/extracted GDB (e.g. an Oregon or Washington HUC4 under `datasets/`) to read the actual `FType`/`FCode` values used for waterfalls vs. rapids (spec flags `487` and the spring `458` as needing confirmation).
    - Use an out-of-suite `tools/`-style ad-hoc inspection or notebook — this reads real GIS data and is NOT part of the offline suite.
    - Cross-check the confirmed codes against the areal complement: `src/waterbodies.py` currently maps `466 SwampMarsh`, `361 Playa`, `378 IceMass` → `excluded`, so the new areal taxonomy is complementary, not overlapping.
  - [ ] 0.2 Record the confirmed `FType`/`FCode` → class code values (spring/waterfall/rapids for points; wetland/playa/perennial_ice for areals, plus classified-but-excluded well/sinkhole) so downstream fixtures use real codes.
    - If a real GDB is unavailable offline, proceed with the spec's placeholder codes but flag them clearly in the taxonomy module docstring as UNCONFIRMED so a later verification can correct them without changing the rule.

**Acceptance Criteria:**
- Confirmed (or explicitly flagged-as-placeholder) FType→class code values are documented for all point and areal families.
- The classification RULE is unchanged regardless of the code confirmation; only literal code values are pinned.
- No change to the offline suite from this step.

---

### Point taxonomy & loader seam (Roadmap Item 61)

#### Task Group 1: Point-feature taxonomy + point loader seam
**Dependencies:** Task Group 0

- [ ] 1.0 Complete point-feature classification and the NHDPoint loader seam
  - [ ] 1.1 Write 2–8 focused tests FIRST
    - `tests/test_point_features.py`: spring (`458`) classifies to `spring`; waterfall/rapids codes classify correctly; missing `FType` → `excluded` with a `missing_ftype` QA flag (never guessed); `well`/`sinkhole` classify to the `excluded` outcome (accounted-for, not dropped); provenance fields populated on `PointFeature`.
    - `tests/test_loading.py` (extend): `discover_point_layers` selects only `NHDPoint`; `load_point_features` (on a FAKE loader) preserves geometry + parallel attribute dicts with case-insensitive field selection; point load path does NOT touch/overload `load_waterbody_layers`.
    - Run ONLY these tests; do NOT run the full suite yet.
  - [ ] 1.2 Create `src/point_features.py` mirroring `src/waterbodies.py`
    - `POINT_POLICY_VERSION`, `POINT_CLASSES`, `POINT_FTYPE_CLASS`, `POINT_FTYPE_LABELS`, frozen `PointFeature` dataclass, `classify_point_feature` / `classify_point_layer`.
    - Classes: `spring` (FType 458 SpringSeep), `waterfall`, `rapids`; classified-but-excluded: `well`, `sinkhole` (mapped to `excluded` by default policy so they are accounted for, never guessed).
    - Reuse the `_lookup`/`_as_int` case-insensitive helpers and the missing-FType→`excluded` + `missing_ftype` QA-flag pattern from `src/waterbodies.py`.
    - Provenance per feature: `source_id`, `source_layer`, `dataset_id`, `huc4`, `ftype`, `fcode`, `name`, `source_crs`, `attributes`, `inclusion_reason`, `qa_flags`.
    - NO geometry math, NO GDAL imports at module top level; consumes attribute dicts + `src.loading.Layer` objects only.
    - Falls/rapids from NHDPoint only (flowline-coded network falls/rapids are out of scope).
  - [ ] 1.3 Extend `src/loading.py` with the point loader seam
    - Add `POINT_LAYER_ALLOWLIST` (e.g. `("NHDPoint",)`) and `POINT_ATTRIBUTE_FIELDS` (`FType`, `FCode`, `GNIS_Name`, `Permanent_Identifier`, `ReachCode`), independent of `WATERBODY_LAYER_ALLOWLIST`.
    - Add `discover_point_layers` and a `load_point_features` method on `PyogrioLayerLoader`, mirroring `load_waterbody_layers` (case-insensitive field selection, geometry + parallel attribute dicts). Do NOT overload `load_waterbody_layers`.
    - Keep `pyogrio`/`shapely` lazy-imported behind the loader seam.
  - [ ] 1.4 Ensure Task Group 1 tests pass
    - Run ONLY the tests written in 1.1; do NOT run the entire suite.

**Acceptance Criteria:**
- The 2–8 tests in 1.1 pass.
- `src/point_features.py` has a matching `tests/test_point_features.py`; no top-level GDAL imports in either.
- Point allowlist/attributes/loader are independent of the waterbody path (no leakage into flowline/graph or waterbody loads).
- Missing FType → `excluded` + `missing_ftype`; well/sinkhole accounted-for as `excluded`; provenance retained.
- `INTERNAL_CRS` imported from `src/crs.py` where CRS is referenced (never inlined).

---

### Areal taxonomy, selection & point selection (Roadmap Item 62)

#### Task Group 2: Areal taxonomy + areal selection/clipping + point selection/density cap
**Dependencies:** Task Group 1

- [x] 2.0 Complete areal classification, areal selection pipeline, and point selection
  - [x] 2.1 Write 2–8 focused tests FIRST
    - `tests/test_areal_features.py`: `466 SwampMarsh`→`wetland`, `361 Playa`→`playa`, `378 IceMass`→`perennial_ice`; missing FType → `excluded`; complementary-with-waterbodies sanity (these codes are `excluded` in `src/waterbodies.py`).
    - `tests/test_areal_selection.py`: `process_areal_features` runs repair→reproject(`INTERNAL_CRS`)→region-clip→area-measure→threshold-select on hand-built shapely polygons; per-class `min_area_m2` threshold selects/excludes correctly; holes + multipart membership preserved; exact-duplicate geometries deduped by normalized WKB; every candidate accounted for as selected/excluded; deterministic input-order.
    - Point selection tests (in `tests/test_areal_selection.py` or `tests/test_point_features.py`, wherever the seam lives): `process_point_features` repairs→reprojects→clips (drops points outside boundary), applies a deterministic density cap / min-spacing per family, and suppresses duplicate points by normalized coordinates.
    - Run ONLY these tests; do NOT run the full suite.
  - [x] 2.2 Create `src/areal_features.py` mirroring `src/waterbodies.py`
    - `AREAL_POLICY_VERSION`, `AREAL_CLASSES` (`wetland`, `playa`, `perennial_ice`, `excluded`), `AREAL_FTYPE_CLASS` (466→wetland, 361→playa, 378→perennial_ice), labels table, frozen `ArealFeature` dataclass, `classify_areal_feature` / `classify_areal_layer`.
    - FType-driven, name-only-refining, missing FType → `excluded`; NO GDAL imports at top level.
    - Reuse `WATERBODY_LAYER_ALLOWLIST`'s `NHDArea` discovery for loading (same layer), but classify through this new areal taxonomy — complementary to (never overlapping) the waterbody taxonomy.
  - [x] 2.3 Create `src/areal_selection.py` mirroring `src/waterbody_selection.py`
    - `ArealSelectionPolicy` (per-class `min_area_m2`) + `ArealSelection` report + `process_areal_features`: repair → reproject(`INTERNAL_CRS`) → region-clip → area-measure (planar m² in equal-area EPSG:5070) → threshold-select, accounting for every candidate.
    - Reuse `src.geometry.repair_geometry` and `src.clipping.clip_geometry`; preserve holes + multipart membership (shapely `make_valid`/`intersection`).
    - Import `INTERNAL_CRS` from `src.crs`; injectable `reproject` seam with a lazy pyproj default so offline EPSG:5070 inputs never import pyproj.
    - Deterministic input-order processing; dedupe exact-duplicate geometries by normalized WKB.
  - [x] 2.4 Add point selection & density cap
    - Provide `process_point_features` (in `src/point_features.py` or an `src/areal_selection.py` seam): repair point geometries → reproject to `INTERNAL_CRS` → clip to region boundary (drop outside points) → deterministic per-family density cap / minimum-spacing knob.
    - Density thinning deterministic (stable source-order tie-break); duplicate-point suppression by normalized coordinates.
  - [x] 2.5 Ensure Task Group 2 tests pass
    - Run ONLY the tests written in 2.1; do NOT run the entire suite.

**Acceptance Criteria:**
- The 2–8 tests in 2.1 pass.
- `src/areal_features.py` → `tests/test_areal_features.py`; `src/areal_selection.py` → `tests/test_areal_selection.py`; no top-level GDAL imports.
- Areal + waterbody taxonomies are complementary (SwampMarsh/Playa/IceMass are the areal families, not double-classified).
- Selection preserves holes/multipart, dedupes by WKB, is deterministic, and reports every candidate as selected/excluded.
- Point selection reprojects to `INTERNAL_CRS` (imported, not inlined), clips to boundary, and thins deterministically with duplicate suppression.

---

### Rendering (Roadmap Item 63)

#### Task Group 3: Point-glyph + differentiated areal rendering
**Dependencies:** Task Group 2

- [x] 3.0 Complete point-glyph and areal rendering in `src/rendering.py`
  - [x] 3.1 Write 2–8 focused tests FIRST
    - `tests/test_rendering.py` (extend) or `tests/test_natural_feature_rendering.py`: point-glyph layer emits `<g id="point_features">` with one child `<g id="point_<family>">` per family and stable ids (`point_<family>_<feature_id>`); springs=`<circle>` dots, waterfalls=chevron `<path>`, rapids=tick/zigzag `<path>`; areal layer emits `<g id="areal_<family>">` groups with `data-class`; wetlands=hatch/stipple `<pattern>` fill, perennial ice=low-opacity fill, playas=dashed outline (`stroke-dasharray`, no fill).
    - Z-order test: point glyphs render on top of everything (after flowlines + waterbodies); areal groups default beneath flowlines + waterbodies; per-family z-order configurable.
    - Empty-input test: passing no point/areal items produces output identical to the pre-feature render (returns `[]` / emits nothing).
    - Run ONLY these tests.
  - [x] 3.2 Add `_point_glyph_layer` to `src/rendering.py`
    - Emit `<g id="point_features">` → per-family `<g id="point_<family>">` → stable-id glyph elements; springs dots, waterfalls chevrons, rapids ticks/zigzags (reference `tools/overlay_facilities.py` `_marker` shapes).
    - Per-family configurable marker/size/color; stable element ids; reuse `transform_coords`/`format_number` for coordinate mapping.
    - Point glyphs on top of everything per the z-order default.
  - [x] 3.3 Add differentiated areal treatments to `src/rendering.py`
    - Each family its own `<g id="areal_<family>">` with `data-class` and configurable z-order: wetlands hatch/stipple (`<pattern>` fill), perennial ice low-opacity fill, playas dashed outline (`stroke-dasharray`, no fill).
    - Reuse `polygon_path_d` for ring/hole serialization; areal groups default beneath flowlines + waterbodies; each family's z-order individually configurable.
  - [x] 3.4 Wire the new layers into `render_svg` z-ordering
    - Mirror the `waterbody_order` below/above placement pattern; keep flowlines + waterbodies legible at overlaps.
  - [x] 3.5 Ensure Task Group 3 tests pass
    - Run ONLY the tests written in 3.1.

**Acceptance Criteria:**
- The 2–8 tests in 3.1 pass.
- Point glyphs and areal families each emit their own stable-id `<g>` groups with the specified differentiated treatments.
- Z-order matches the spec (areals beneath, points on top; each configurable).
- With no point/areal items supplied, `render_svg` output is byte-identical to the pre-feature render.

---

### Config, presets, CLI & additive integration (Roadmap Item 64)

#### Task Group 4: Config settings + presets + CLI wiring
**Dependencies:** Task Group 3

- [x] 4.0 Complete settings, presets, and CLI flags
  - [x] 4.1 Write 2–8 focused tests FIRST
    - `tests/test_natural_feature_config.py` (mirror `tests/test_waterbody_config.py`): `PointFeatureSettings` + `ArealFeatureSettings` validate against allowlists (hex color, positive sizes/opacity, valid `render_order`, per-class `min_area_m2`) → `ConfigError` on bad input; every family defaults `enabled: False`; `POINT_FEATURE_PRESETS`/`AREAL_FEATURE_PRESETS` `screen`/`print-state`/`print-county` expand with `defaults < preset < explicit`; preset is NOT stored on frozen `Settings`.
    - CLI precedence test (`tests/test_cli.py` extend): unset flags default to `None` (YAML not clobbered); nested blocks deep-merged per sub-key; `defaults < config.yaml < CLI flags`.
    - Run ONLY these tests.
  - [x] 4.2 Add settings dataclasses to `src/config.py`
    - Frozen `PointFeatureSettings` and `ArealFeatureSettings` (per family/group: `enabled`, `color`, size/opacity/dash fields, per-class `min_area_m2`, point density/spacing, `render_order`) with fail-fast `ConfigError` validation against allowlists.
    - Every new family defaults `enabled: False` (byte-identical default build).
  - [x] 4.3 Add preset tables + coercion to `src/config.py`
    - `POINT_FEATURE_PRESETS` and `AREAL_FEATURE_PRESETS` (`screen`/`print-state`/`print-county`) alongside `WATERBODY_PRESETS`; presets control areal min-area thresholds AND the point density cap/spacing knob.
    - `_coerce_point_features` / `_coerce_areal_features` with `defaults < preset < explicit`; preset expansion at config time, NOT stored on frozen `Settings` (mirror `_coerce_waterbodies`).
  - [x] 4.4 Add CLI flags to `src/cli.py`
    - `--point-features`/`--no-point-features`, `--areal-features`/`--no-areal-features` (or per-family), `--point-feature-preset`/`--areal-feature-preset`, mirroring the waterbody flag wiring.
    - Unset argparse flags default to `None`; nested blocks deep-merged per sub-key (mirror the waterbody merge); precedence `defaults < config.yaml < CLI flags`.
  - [x] 4.5 Ensure Task Group 4 tests pass
    - Run ONLY the tests written in 4.1.

**Acceptance Criteria:**
- The 2–8 tests in 4.1 pass.
- Bad config fails fast with `ConfigError`; every family defaults `enabled: False`.
- Presets expand `defaults < preset < explicit` at config time and are NOT stored on frozen `Settings` (no-preset builds byte-identical).
- CLI precedence `defaults < config.yaml < CLI flags`; unset flags never clobber YAML; nested blocks deep-merged per sub-key.

#### Task Group 5: Additive pipeline integration
**Dependencies:** Task Group 4

- [x] 5.0 Integrate point/areal features additively into the pipeline
  - [x] 5.1 Write 2–8 focused tests FIRST in `tests/test_natural_features_pipeline.py`
    - With features disabled (default): pipeline output is byte-identical to the current river/waterbody render; no point/areal artifacts populated.
    - With point features enabled AND a fake loader exposing `load_point_features`: `validate` stashes `ctx.artifacts["point_layers"]`; `generate_svg` `_select_point_glyphs` populates a selection report + render items.
    - With areal features enabled: `_select_areal_features` selects into its own render items via the reused `NHDArea` load + `ctx.artifacts["region_boundary"]` clipping.
    - Guard test: when the loader lacks `load_point_features` (no `hasattr`), the pipeline skips gracefully (no crash, render unchanged).
    - Run ONLY these tests.
  - [x] 5.2 Extend the `validate` stage in `src/pipeline.py`
    - Additively load point/areal layers ONLY when the respective family is enabled AND the loader exposes the seam (`hasattr(ctx.loader, "load_point_features")`), stashing into `ctx.artifacts["point_layers"]` and reusing a `waterbody_layers`-style artifact for areal.
    - Mirror the existing `_validate_stage` waterbody load guard.
  - [x] 5.3 Extend `generate_svg` in `src/pipeline.py`
    - Add `_select_point_glyphs(ctx)` and `_select_areal_features(ctx)` mirroring `_select_waterbody_outlines`; pass selection reports into `ctx.artifacts` and render items into `render_svg`.
    - Reuse `ctx.artifacts["region_boundary"]` for clipping; return `[]` when disabled so the render is unchanged.
  - [x] 5.4 Preserve the pipeline invariants
    - Do NOT change `PIPELINE_STAGES` order or the `_stub` mechanism; no global state; stages communicate only via `ctx.artifacts`.
  - [x] 5.5 Ensure Task Group 5 tests pass
    - Run ONLY the tests written in 5.1.

**Acceptance Criteria:**
- The 2–8 tests in 5.1 pass.
- Features load in `validate` and select/render in `generate_svg`, additively — `PIPELINE_STAGES` order and the `_stub` mechanism are unchanged.
- Disabled (default) => `_select_*` returns `[]` and the render is unchanged.
- Loader-seam guard (`hasattr`) skips gracefully when the seam is absent.
- `region_boundary` artifact reused for clipping; no new global state.

---

### QA & regression gate (Roadmap Item 64 gate + Epoch determinism gate)

#### Task Group 6: Feature QA, determinism, and full-suite regression
**Dependencies:** Task Groups 1–5

- [x] 6.0 Validate the epoch gate and guard against regressions
  - [x] 6.1 Review the tests written in Task Groups 1–5
    - Confirm coverage of: point placement, wetland holes/multipolygons, coastal/boundary clipping, duplicate suppression, density thresholds, preset behavior. (Existing feature tests ≈ 10–40.)
  - [x] 6.2 Analyze gaps for THIS feature only
    - Identify critical end-to-end/QA workflows lacking coverage — focus ONLY on this spec's requirements (do NOT assess whole-app coverage).
  - [x] 6.3 Write up to 10 additional strategic tests maximum
    - Fill critical gaps (e.g. an end-to-end enabled-features render on fixture inputs; a preset-driven small-scale density-cap check; a wetland-with-holes clip-at-boundary case). Skip edge/perf/accessibility cases unless business-critical.
  - [x] 6.4 Verify the BYTE-IDENTICAL default-output gate
    - Run `tools/verify_determinism.py` (e.g. `--region Oregon`) to confirm the DEFAULT (features-disabled) build is byte-for-byte identical to the pre-feature golden output; if a real region is unavailable offline, assert byte-identity of the disabled-features render against the golden fixture / registry (`tests/fixtures/golden/registry.json`).
    - Confirm an enabled-features render is itself deterministic (identical inputs → identical bytes) via a double-render check.
  - [x] 6.5 Run the FULL offline suite for regressions
    - `.venv/bin/python -m pytest -q` — the entire suite must pass offline (no network, no GDAL, no real datasets).
    - Lint: `.venv/bin/ruff check src tests` (install ruff first if absent from `.venv`).
  - [x] 6.6 Smoke-test an enabled-features build
    - Run a small fixture or region build with a point + areal family enabled (e.g. a `--point-feature-preset`/`--areal-feature-preset`) and eyeball the layered SVG for the new `<g>` groups.

**Acceptance Criteria:**
- All feature-specific tests pass; no more than 10 additional tests added to fill gaps.
- The DEFAULT (features-disabled) build is byte-for-byte identical to current output (verified via determinism tooling / golden fixture).
- An enabled-features render is deterministic (double-render byte-identical).
- The FULL offline suite passes with no network / no GDAL / no real datasets; lint clean.
- Epoch gate met: a build can render source-traceable springs, waterfalls/rapids, wetlands, playas, and perennial ice as dedicated, editable, water-only layers over the existing flowline + waterbody art, with screen/print presets controlling density.

---

## Execution Order

Recommended implementation sequence:
1. Confirm NHDPoint FType codes (Task Group 0) — verification only, non-blocking
2. Point taxonomy + loader seam — Item 61 (Task Group 1)
3. Areal taxonomy + areal/point selection — Item 62 (Task Group 2)
4. Point-glyph + areal rendering — Item 63 (Task Group 3)
5. Config settings + presets + CLI — Item 64 part 1 (Task Group 4)
6. Additive pipeline integration — Item 64 part 2 (Task Group 5)
7. QA, determinism, full-suite regression — Item 64 gate (Task Group 6)
