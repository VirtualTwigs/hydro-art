# Specification: Hydro-Structure Taxonomy & Loader (Epoch 16, Item #65)

## Goal
Classify the engineered-water infrastructure NHD already ships — dams/weirs, gates, lock chambers,
spillways, gaging stations, water intakes/outflows, and areal canals/ditches — into a versioned,
FType-driven taxonomy, and add the one new loader seam (`NHDLine`) needed to reach them. Deliver a
tested, source-traceable classification foundation that a later item (#67) will render, with the
default build byte-for-byte unchanged.

## User Stories
- As a builder, I want engineered-water features classified from authoritative NHD FType codes with
  full provenance so a later rendering item can draw dams, gauges, locks, and diversions as editable,
  source-traceable water-only layers.
- As a maintainer, I want the structure taxonomy complementary to the waterbody and natural-feature
  taxonomies so each NHD feature is owned by exactly one taxonomy and never double-classified.

## Specific Requirements

**Versioned hydro-structure taxonomy — new `src/hydro_structures.py`**
- Mirror `src/point_features.py` structurally: `HYDRO_STRUCTURE_POLICY_VERSION`,
  `HYDRO_STRUCTURE_CLASSES`, `HYDRO_STRUCTURE_FTYPE_CLASS`, `HYDRO_STRUCTURE_FTYPE_LABELS`, a frozen
  `HydroStructure` dataclass, and `classify_hydro_structure` / `classify_hydro_structure_layer`.
- Reuse the `_lookup` / `_as_int` case-insensitive attribute helpers and the
  missing-FType → `excluded` + `missing_ftype` QA-flag pattern (identical rule to the other taxonomies).
- Normalized classes: `dam_weir`, `gate`, `lock_chamber`, `gaging_station`, `water_intake_outflow`,
  `spillway`, `canal_ditch`, `excluded`.
- FType → class table, keyed on the NHD `FType` code (the same code carries the same meaning across
  `NHDLine`/`NHDPoint`/`NHDArea`, so one table serves all three source layers). Confirmed / to-confirm
  codes (Group 0): `343` DamWeir → `dam_weir`; `369` Gate → `gate`; `398` LockChamber → `lock_chamber`;
  `367` Gaging Station → `gaging_station` (domain-verified, Epoch 15); `485` Water Intake/Outflow →
  `water_intake_outflow` (domain-verified, Epoch 15); `336` CanalDitch → `canal_ditch`; `455`
  SpillwayArea → `spillway`. Any code confirmed-uncertain by Group 0 is flagged UNCONFIRMED in the
  module docstring (never silently guessed); the classification RULE is fixed regardless of the literal
  values.
- **Reservoir stays with waterbodies:** `436 Reservoir` is intentionally NOT in the structure table
  (waterbodies owns it) — documented policy note, preserving the non-overlapping invariant.
- No geometry math and no GDAL imports at module top level; consumes attribute dicts +
  `src.loading.Layer` objects only, so it runs fully offline.
- Retain provenance per feature: `source_id`, `source_layer`, `dataset_id`, `huc4`, `geometry`,
  `ftype`, `fcode`, `name`, `struct_class`, `source_crs`, `attributes`, `inclusion_reason`, `qa_flags`.
- `classify_hydro_structure_layer(layer)` classifies every geometry in a loaded `Layer` in source
  order, pairing each with its parallel attribute dict (empty-dict fallback), mirroring
  `classify_point_layer`.

**NHDLine loader seam — extend `src/loading.py`**
- Add `LINE_LAYER_ALLOWLIST = ("NHDLine",)` and `LINE_ATTRIBUTE_FIELDS`
  (`FType`, `FCode`, `GNIS_Name`, `Permanent_Identifier`, `ReachCode`), kept independent of the
  existing `HYDRO_LAYER_ALLOWLIST`, `WATERBODY_LAYER_ALLOWLIST`, and `POINT_LAYER_ALLOWLIST` so line
  structures never leak into the flowline/graph, waterbody, or point-feature load paths.
- Add `discover_line_layers(layer_names)` (filtering to `LINE_LAYER_ALLOWLIST`) and a
  `load_line_features` method on `PyogrioLayerLoader`, mirroring `load_point_features`
  (case-insensitive field selection, geometry + parallel attribute dicts preserved). Do NOT overload
  `load_point_features` / `load_waterbody_layers`.
- Keep `pyogrio`/`shapely` lazy-imported behind the loader seam; tests inject a fake loader / hand-built
  `Layer` objects.
- **No new point or area loader.** Structure points ride the existing `load_point_features`
  (`NHDPoint`); structure areas ride the existing `load_waterbody_layers` (`NHDArea`). Item #65 classifies
  those already-loaded layers through the new taxonomy; the pipeline wiring that feeds them through is a
  later item (#67 rendering / its selection step), not this one.

**Complementarity guarantee (tested)**
- The included (non-`excluded`) FType codes of `HYDRO_STRUCTURE_FTYPE_CLASS` are disjoint from the
  included codes of `src.waterbodies`, `src.point_features`, and `src.areal_features`. A test asserts no
  collision, so one NHD feature is owned by exactly one taxonomy.

## Existing Code to Leverage

**`src/point_features.py` — versioned classification taxonomy (primary template)**
- Exact structural template for `src/hydro_structures.py`: policy-version constant, FType→class table,
  labels table, frozen feature dataclass, `classify_*` + `classify_*_layer`, and the `_lookup`/`_as_int`
  helpers + missing-FType→excluded QA-flag pattern.

**`src/loading.py` — loader seam**
- `POINT_LAYER_ALLOWLIST` / `POINT_ATTRIBUTE_FIELDS` / `discover_point_layers` /
  `PyogrioLayerLoader.load_point_features` are the exact template for the new `NHDLine` seam.

**`agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md`**
- Records the NHDPoint infrastructure codes already domain-verified against a real 1807 GDB
  (367/369/436/485) and the verification method (decode the embedded `NHDFCode` domain table, not memory)
  to reuse for the NHDLine/NHDArea codes.

## Out of Scope
- #66 engineered-channel styling on `NHDFlowline` (CanalDitch/Pipeline/ArtificialPath).
- #67 structure symbology & rendering (`src/rendering.py`) and its selection/clip step.
- #68 QA, presets, config settings, and CLI flags for structures.
- Repair/reproject/clip/select of structure geometries.
- `436 Reservoir` reclassification (stays a waterbody).
- Any change to `PIPELINE_STAGES` order or the stub mechanism.
- Any `web/`, fulfillment/rights-gate, elevation/3D, or monthly-flow interaction.
- Changing default (features-disabled) output bytes — the default build must stay byte-for-byte
  identical.
