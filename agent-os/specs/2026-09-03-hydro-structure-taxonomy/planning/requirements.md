# Requirements: Hydro-Structure Taxonomy & Loader (Epoch 16, Item #65)

## Context
Epoch 16 (Hydro-infrastructure layers) adds the engineered water infrastructure NHD already
encodes — dams/weirs, gates, lock chambers, spillways, gaging stations, water intakes/outflows,
and areal canals/ditches — as dedicated, source-traceable, opt-in layers over the existing
flowline + waterbody + natural-feature art. Item #65 is the **foundation**: the versioned
classification taxonomy plus the loader seam for the one new source layer. It produces no visible
art on its own (rendering is #67), exactly as Epoch 15 shipped its taxonomy (Item 61) before its
rendering (Item 63).

## In scope (Item #65 only)
1. A new versioned taxonomy module `src/hydro_structures.py` classifying engineered-water NHD
   FTypes across `NHDLine`, `NHDPoint`, and `NHDArea` into a normalized class vocabulary, mirroring
   `src/point_features.py` / `src/areal_features.py` structurally.
2. A loader seam extension in `src/loading.py` for the one genuinely-new source layer: `NHDLine`
   (`LINE_LAYER_ALLOWLIST`, `LINE_ATTRIBUTE_FIELDS`, `discover_line_layers`, `load_line_features`).
   `NHDPoint` (Epoch 15 `load_point_features`) and `NHDArea` (Epoch 1.5 `load_waterbody_layers`)
   already load with the needed attributes — the structure taxonomy is a **complementary** taxonomy
   over those already-loaded layers, so no new point/area loader is added.
3. Real-data confirmation of the NHDLine/NHDArea structure FType codes (Group 0), mirroring the
   Epoch 15 Group 0 discipline. The NHDPoint infrastructure codes are already domain-table-verified
   in `agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md`
   (367 Gaging Station, 369 Gate, 436 Reservoir-point, 485 Water Intake/Outflow).

## User stories
- As a builder, I want engineered-water features classified from the authoritative NHD FType codes
  with full provenance so a later rendering item can draw dams, gauges, and diversions as editable,
  source-traceable layers.
- As a maintainer, I want the structure taxonomy to be complementary to (never overlapping with) the
  waterbody and natural-feature taxonomies, so each NHD feature is owned by exactly one taxonomy.

## Classification policy (mirrors waterbodies / natural features exactly)
- **FType-driven.** The normalized class is keyed on the NHD `FType` code (versioned policy table).
- **Name only refines, never decides.** GNIS name retained for provenance only.
- **Missing/unknown FType → `excluded`** with a `missing_ftype` QA flag — never guessed.
- **`excluded` is a first-class outcome** so every candidate feature is accounted for, not dropped.
- Normalized classes: `dam_weir`, `gate`, `lock_chamber`, `gaging_station`,
  `water_intake_outflow`, `spillway`, `canal_ditch`, plus `excluded`.
- **Reservoir stays with waterbodies.** `436 Reservoir` is already a waterbody class; the structure
  taxonomy does NOT reclassify it (kept out to preserve the non-overlapping invariant). Recorded as a
  deliberate policy note; revisit only if #67 needs a distinct reservoir-structure glyph.

## Complementarity invariant
The structure FType codes are disjoint from the waterbody FType table (`src/waterbodies.py`) and the
natural-feature FType tables (`src/point_features.py`, `src/areal_features.py`). A test asserts the
structure `FTYPE_CLASS` keys do not collide with the included (non-`excluded`) codes of the other
three taxonomies, so one NHD feature is owned by exactly one taxonomy.

## Non-functional constraints
- **Offline-suite discipline:** no top-level GDAL-backed imports (`pyogrio`/`geopandas`/`shapely`/
  `rasterio`) in `src/` or `tests/`; keep them lazy-imported behind the loader seam. The taxonomy
  module does no geometry math and imports no GIS libs — it consumes attribute dicts + `Layer`s.
- **Matching test file:** `src/hydro_structures.py` gets `tests/test_hydro_structures.py`; the loader
  extension is tested in `tests/test_loading.py`.
- **Byte-identical default:** nothing here touches `PIPELINE_STAGES`, rendering, config defaults, or
  the CLI, so the default build stays byte-for-byte identical (verified in the regression gate).
- **CRS:** if any CRS is referenced, import `INTERNAL_CRS` from `src/crs.py`; never inline the literal.
- **Rights:** USGS NHD is federal public domain — record per-feature source provenance like the other
  taxonomies; **no new rights gate**, no `fulfillment.assert_sellable` change.

## Out of scope (later Epoch 16 items)
- #66 — engineered-channel styling on the `NHDFlowline` network (CanalDitch/Pipeline/ArtificialPath).
- #67 — structure symbology & rendering (`src/rendering.py` point/line/area glyph layers).
- #68 — QA, presets, and CLI/config surface for structures.
- Repair/reproject/clip/select of structure geometries (selection is part of a later item, mirroring
  how `areal_selection` followed the Epoch 15 taxonomy).
- Any change to `PIPELINE_STAGES`, the default output bytes, `web/`, or the fulfillment rights gate.
