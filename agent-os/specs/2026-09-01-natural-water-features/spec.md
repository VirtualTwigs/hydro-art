# Specification: Natural Water Features (Epoch 15)

## Goal
Extend the water-only SVG art vocabulary past waterbody outlines (Epoch 1.5) to the other natural water features USGS NHD already ships in the same GDBs — springs/seeps, waterfalls, rapids, wetlands (marsh/swamp), playas, and perennial ice (glacier/snowfield) — rendered as dedicated, source-traceable, opt-in point-glyph and areal layers, integrated additively so a default (features-disabled) build stays byte-for-byte identical.

## User Stories
- As an art buyer, I want springs, waterfalls, rapids, wetlands, playas, and perennial ice to appear as distinct, editable layers over the existing flowline + waterbody art so a print reads as a richer water portrait.
- As a builder, I want each family to be opt-in and preset-controlled so tiny features don't clutter at small scale and the default build never changes rendered bytes.

## Specific Requirements

**Versioned point-feature taxonomy — new `src/point_features.py`**
- Mirror `src/waterbodies.py`: define `POINT_POLICY_VERSION`, `POINT_CLASSES`, `POINT_FTYPE_CLASS`, `POINT_FTYPE_LABELS`, a frozen `PointFeature` dataclass, and `classify_point_feature` / `classify_point_layer`, keyed on NHD `FType`/`FCode` with GNIS name only refining ambiguous codes.
- Included classes: `spring` (FType 458 SpringSeep), `waterfall` (487 Rapids/Falls per source coding — see falls/rapids note), `rapids`; excluded-but-classified: `well`, `sinkhole` (present in the table, mapped to `excluded` outcome by default policy so they are accounted for, never guessed).
- Missing `FType` → `excluded` with a `missing_ftype` QA flag, never guessed (identical rule to waterbodies).
- No geometry math and no GDAL imports at module top level; consumes attribute dicts + `src.loading.Layer` objects only, so it runs fully offline.
- Retain provenance per feature (`source_id`, `source_layer`, `dataset_id`, `huc4`, `ftype`, `fcode`, `name`, `source_crs`, `attributes`, `inclusion_reason`, `qa_flags`).
- Falls/rapids sourced from NHDPoint only for the first cut; flowline-coded (network) falls/rapids are deferred (out of scope).

**Point-feature loader seam — extend `src/loading.py`**
- Add a separate `POINT_LAYER_ALLOWLIST` (e.g. `("NHDPoint",)`) and `POINT_ATTRIBUTE_FIELDS` (`FType`, `FCode`, `GNIS_Name`, `Permanent_Identifier`, `ReachCode`), kept independent of `WATERBODY_LAYER_ALLOWLIST` so point features never leak into the flowline/graph or waterbody load paths.
- Add `discover_point_layers` and a `load_point_features` method on `PyogrioLayerLoader` mirroring `load_waterbody_layers` (case-insensitive field selection, geometry + parallel attribute dicts preserved). Do NOT overload `load_waterbody_layers`.
- Keep `pyogrio`/`shapely` lazy-imported behind the loader seam; tests inject a fake loader.

**Versioned areal-feature taxonomy — new `src/areal_features.py`**
- Mirror `src/waterbodies.py` for `NHDWaterbody` polygons: `AREAL_POLICY_VERSION`, `AREAL_CLASSES` (`wetland`, `playa`, `perennial_ice`, `excluded`), `AREAL_FTYPE_CLASS` (466 SwampMarsh→wetland, 361 Playa→playa, 378 IceMass→perennial_ice), labels table, `ArealFeature` dataclass, and `classify_areal_feature` / `classify_areal_layer`.
- FType-driven, name-only-refining, missing FType → excluded; no GDAL imports at top level.
- **Source correction (Group 0, verified against real 1807 GDB):** SwampMarsh/Playa/IceMass are `NHDWaterbody` FTypes, NOT `NHDArea`. Reuse the EXISTING `load_waterbody_layers` seam (already loads `NHDWaterbody` + `NHDArea` with the needed attributes) — **no new areal loader**. Classify the loaded `NHDWaterbody` layer through this new areal taxonomy; `src/waterbodies.py` already sends 466/361/378 → `excluded`, so the two taxonomies are complementary, not overlapping. See `planning/group0-ftype-findings.md`.

**Areal selection & clipping — new `src/areal_selection.py`**
- Mirror `src/waterbody_selection.py`: `ArealSelectionPolicy` (per-class `min_area_m2` thresholds) + `ArealSelection` report + `process_areal_features` running repair → reproject(`INTERNAL_CRS`) → region-clip → area-measure → threshold-select, accounting for every candidate as selected/excluded.
- Reuse `src.geometry.repair_geometry` and `src.clipping.clip_geometry`; preserve holes and multipart membership (shapely `make_valid`/`intersection`).
- Import `INTERNAL_CRS` from `src.crs`; use the injectable `reproject` seam with a lazy default so offline EPSG:5070 inputs never import pyproj.
- Measure area in EPSG:5070 (equal-area) → planar `area` in m²; deterministic input-order processing; dedupe exact-duplicate geometries by normalized WKB.

**Point selection & density cap — in `src/point_features.py` or `src/areal_selection.py` seam**
- Provide a `process_point_features` pass: repair (point geometries), reproject to `INTERNAL_CRS`, clip to region boundary (drop points outside), then apply a deterministic density cap / minimum-spacing knob per family so dense clusters thin predictably at small scale.
- Density thinning must be deterministic (stable source-order tie-break); duplicate-point suppression by normalized coordinates.

**Point-glyph rendering — extend `src/rendering.py`**
- Add a `_point_glyph_layer` emitting a `<g id="point_features">` with one child `<g id="point_<family>">` per family, containing stable-id glyph elements: springs = dots (`<circle>`), waterfalls = chevrons (`<path>`), rapids = tick/zigzag marks (`<path>`); reference `tools/overlay_facilities.py` marker shapes as the precedent.
- Per-family configurable marker/size/color; stable element ids (`point_<family>_<feature_id>`); reuse `transform_coords`/`format_number` for coordinate mapping.
- Point glyphs render on top of everything (after flowlines and waterbodies) per the z-order default.

**Areal rendering — extend `src/rendering.py`**
- Add differentiated areal treatments, each its own `<g>` with configurable z-order: wetlands = hatch/stipple (SVG `<pattern>` fill), perennial ice = low-opacity fill, playas = dashed outline (`stroke-dasharray`, no fill).
- Reuse `polygon_path_d` for ring/hole path serialization; emit `<g id="areal_<family>">` groups with per-family style and `data-class`.
- Areal groups default beneath flowlines and waterbodies; each family's z-order individually configurable.

**Config settings, presets & precedence — extend `src/config.py`**
- Add frozen `PointFeatureSettings` and `ArealFeatureSettings` (per family or per-group: `enabled`, `color`, size/opacity/dash fields, per-class `min_area_m2`, point density/spacing, `render_order`) with fail-fast `ConfigError` validation against allowlists (hex color, positive sizes, valid `render_order`).
- Every new family defaults `enabled: False` so the default build stays byte-identical.
- Add `POINT_FEATURE_PRESETS` and `AREAL_FEATURE_PRESETS` (`screen`/`print-state`/`print-county`) alongside `WATERBODY_PRESETS`; presets control areal min-area thresholds AND the point density cap/spacing knob.
- Add `_coerce_point_features`/`_coerce_areal_features` with `defaults < preset < explicit` precedence; preset expansion happens at config time and is NOT stored on the frozen `Settings` (mirroring `_coerce_waterbodies`), so no-preset builds stay byte-identical.

**Additive pipeline integration — extend `src/pipeline.py`**
- In the `validate` stage: additively load point/areal layers only when the respective family is enabled AND the loader exposes the seam (`hasattr(ctx.loader, "load_point_features")`), stashing into `ctx.artifacts["point_layers"]` / reusing `ctx.artifacts["waterbody_layers"]`-style artifacts for areal.
- In `generate_svg`: add `_select_point_glyphs(ctx)` and `_select_areal_features(ctx)` mirroring `_select_waterbody_outlines`, passing selection reports into artifacts and render items into `render_svg`.
- Do NOT change `PIPELINE_STAGES` order or the `_stub` mechanism; reuse `ctx.artifacts["region_boundary"]` for clipping; return `[]` when disabled so the render is unchanged.

**CLI flags — extend `src/cli.py`**
- Add `--point-features`/`--no-point-features`, `--areal-features`/`--no-areal-features` (or per-family), plus `--point-feature-preset`/`--areal-feature-preset`, mirroring the waterbody flag wiring.
- Unset argparse flags default to `None` so YAML is never clobbered; nested blocks merged per-sub-key (mirroring the waterbody deep-merge in `src/cli.py`); precedence `defaults < config.yaml < CLI flags`.

## Existing Code to Leverage

**`src/waterbodies.py` — versioned classification taxonomy**
- Exact structural template for `src/point_features.py` and `src/areal_features.py`: policy-version constant, FType→class table, labels table, frozen feature dataclass, `classify_*` + `classify_*_layer`.
- Reuse the `_lookup`/`_as_int` case-insensitive attribute helpers and the missing-FType→excluded QA-flag pattern.

**`src/waterbody_selection.py` — repair/reproject/clip/select pipeline**
- Direct template for `src/areal_selection.py` (`process_areal_features`) and point selection: injectable `reproject` seam with lazy pyproj default, `INTERNAL_CRS` target, WKB-dedup, deterministic input-order processing, selected/excluded accounting report.

**`src/config.py` — settings, presets, precedence**
- `WaterbodySettings` / `WATERBODY_PRESETS` / `_coerce_waterbodies` are the template for the new settings dataclasses, preset tables, and `_coerce_*` functions (fail-fast validation, `defaults < preset < explicit`, preset not stored on frozen `Settings`).

**`src/rendering.py` — fill-free `<g>` layer emission**
- `_waterbody_lines`, `polygon_path_d`, `transform_coords`, `format_number`, and the `waterbody_order` below/above placement in `render_svg` are the template for the new point-glyph and areal `<g>` layers and their z-ordering.

**`src/pipeline.py` + `tools/overlay_facilities.py` — additive integration + point markers**
- `_validate_stage` waterbody load guard and `_select_waterbody_outlines` are the template for additive load + select; `tools/overlay_facilities.py` `_marker` (circle/shape drawing) is the precedent for glyph shapes (dots/chevrons/ticks).

## Out of Scope
- Flowline-network (NHDFlowline) falls/rapids styling — NHDPoint only for the first cut; deferred to a future note.
- NWI (National Wetlands Inventory) as a wetlands source — NHD `NHDArea` only.
- Wells and sinkholes rendering — classified in the taxonomy but excluded/off by default.
- Any elevation / 3D / DEM / terrain interaction, and any monthly-flow / year-over-year interaction.
- `web/studio.html` (or any `web/`) control-surface wiring, recipe/preset, or mapping changes.
- Any rights-gate / `fulfillment.assert_sellable` change (USGS NHD is federal public domain, sellable with attribution; record source provenance per feature like waterbodies do — no new gate).
- Roads, political basemap, or any non-water theme layer (water-only).
- Any new data source — all six families already exist in the USGS NHD GDBs the pipeline consumes.
- Any change to `PIPELINE_STAGES` order or the stub mechanism.
- Changing default (features-disabled) output bytes — the default build must remain byte-for-byte identical (verifiable via Epoch 10 determinism tooling / `tools/verify_determinism.py`).
