# Task Breakdown: Hydro-Structure Taxonomy & Loader (Epoch 16, Item #65)

## Overview
Total Tasks: 3 task groups (a pre-flight FType verification, the taxonomy + NHDLine loader seam,
and a regression/QA gate).

This item is the taxonomy + loader foundation of Epoch 16, mirroring how Epoch 15 shipped
`src/point_features.py` (Item 61) before its rendering. It parallels the Epoch 15 template
beat-for-beat: versioned FType-driven taxonomy → loader seam → offline tests, additive and
byte-identical (nothing here touches rendering, config defaults, the CLI, or `PIPELINE_STAGES`).

Templates to mirror (do not duplicate — parallel these exactly):
- `src/point_features.py` / `tests/test_point_features.py` — versioned classification taxonomy
- `src/loading.py` (`POINT_LAYER_ALLOWLIST`, `discover_point_layers`, `load_point_features`) — loader seam
- `agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md` — real-GDB
  FType verification method (decode the embedded `NHDFCode` domain table)

## Cross-cutting constraints (apply to every relevant group; repeated in acceptance criteria)
- **TDD:** 2–8 focused tests first per group; run ONLY those tests until green; no exhaustive coverage.
- **Matching test file:** `src/hydro_structures.py` → `tests/test_hydro_structures.py`; the loader
  extension is tested in `tests/test_loading.py`.
- **Offline-suite discipline:** NO top-level GDAL-backed imports (`pyogrio`/`geopandas`/`shapely`/
  `rasterio`) in `src/` or `tests/`; keep them lazy-imported behind the loader seam. The taxonomy
  module does NO geometry math and imports NO GIS libs — it consumes attribute dicts + `Layer` objects.
- **CRS:** if any CRS is referenced, import `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`.
- **Complementary taxonomy:** structure FType codes are disjoint from the included codes of
  `src.waterbodies` / `src.point_features` / `src.areal_features` (tested); `436 Reservoir` stays a
  waterbody, NOT a structure.
- **Byte-identical default:** nothing here touches `PIPELINE_STAGES`, rendering, config defaults, or the
  CLI — the default build must stay BYTE-FOR-BYTE identical.

---

## Task List

### Pre-flight

#### Task Group 0: Confirm NHDLine / NHDArea structure FType codes against a real GDB
**Dependencies:** None
**Note:** Verification step, NOT a blocker for the offline test structure. The classification RULE
(FType-driven, name-only-refining, missing→excluded) is fixed and can be built immediately; only the
literal numeric FType VALUES for NHDLine (dam/weir, gate, lock chamber) and NHDArea (canal/ditch, lock
chamber, spillway) need confirming. The NHDPoint infrastructure codes (367/369/436/485) are already
domain-verified in the Epoch 15 Group 0 findings.

- [x] 0.0 Confirm structure FType codes
  - [x] 0.1 Inspect a real extracted GDB's `NHDLine` and `NHDArea` layers (e.g. an Oregon/Washington
    HUC4 under `datasets/`), decoding the authoritative embedded `NHDFCode` domain table (NOT from
    memory), to read the actual FType/FCode values for dam/weir (`343`), gate (`369`), lock chamber
    (`398`), canal/ditch (`336`), and spillway (`455`). Use an out-of-suite `tools/`-style ad-hoc
    inspection or notebook — this reads real GIS data and is NOT part of the offline suite.
    - Cross-check against the complement: confirm none of the confirmed structure codes collide with the
      included codes in `src/waterbodies.py`, `src/point_features.py`, `src/areal_features.py`.
  - [x] 0.2 Record the confirmed FType → class values (dam_weir/gate/lock_chamber/gaging_station/
    water_intake_outflow/spillway/canal_ditch) so the taxonomy fixtures use real codes.
    - If a real GDB is unavailable offline, proceed with the standard NHD codes above but flag any
      unconfirmed value clearly in the taxonomy module docstring as UNCONFIRMED so a later verification
      can correct it without changing the rule.

**Acceptance Criteria:**
- Confirmed (or explicitly flagged-as-UNCONFIRMED) FType→class values documented for all structure classes.
- The classification RULE is unchanged regardless of code confirmation; only literal code values pinned.
- No collision between confirmed structure codes and the included codes of the other three taxonomies.
- No change to the offline suite from this step.

---

### Taxonomy & loader seam (Roadmap Item 65)

#### Task Group 1: Hydro-structure taxonomy + NHDLine loader seam
**Dependencies:** Task Group 0

- [x] 1.0 Complete the hydro-structure classification and the NHDLine loader seam
  - [x] 1.1 Write 2–8 focused tests FIRST
    - `tests/test_hydro_structures.py`: `343`→`dam_weir`, `369`→`gate`, `398`→`lock_chamber`,
      `367`→`gaging_station`, `485`→`water_intake_outflow`, `336`→`canal_ditch`, `455`→`spillway`;
      missing `FType` → `excluded` with a `missing_ftype` QA flag (never guessed); an out-of-scope code
      (e.g. `436` Reservoir, `458` Spring) → `excluded`; provenance fields populated on `HydroStructure`;
      `classify_hydro_structure_layer` returns one feature per geometry in source order.
    - Complementarity test (in `tests/test_hydro_structures.py`): the included (non-`excluded`)
      `HYDRO_STRUCTURE_FTYPE_CLASS` keys are disjoint from the included codes of `src.waterbodies`,
      `src.point_features`, and `src.areal_features`.
    - `tests/test_loading.py` (extend): `discover_line_layers` selects only `NHDLine`;
      `load_line_features` (on a FAKE loader / hand-built `Layer`) preserves geometry + parallel attribute
      dicts with case-insensitive field selection; the line load path does NOT touch/overload
      `load_point_features` or `load_waterbody_layers`.
    - Run ONLY these tests; do NOT run the full suite yet.
  - [x] 1.2 Create `src/hydro_structures.py` mirroring `src/point_features.py`
    - `HYDRO_STRUCTURE_POLICY_VERSION`, `HYDRO_STRUCTURE_CLASSES`, `HYDRO_STRUCTURE_FTYPE_CLASS`,
      `HYDRO_STRUCTURE_FTYPE_LABELS`, frozen `HydroStructure` dataclass, `classify_hydro_structure` /
      `classify_hydro_structure_layer`.
    - Classes: `dam_weir`, `gate`, `lock_chamber`, `gaging_station`, `water_intake_outflow`, `spillway`,
      `canal_ditch`, `excluded`.
    - Reuse the `_lookup`/`_as_int` case-insensitive helpers and the missing-FType→`excluded` +
      `missing_ftype` QA-flag pattern from `src/point_features.py`.
    - Provenance per feature: `source_id`, `source_layer`, `dataset_id`, `huc4`, `geometry`, `ftype`,
      `fcode`, `name`, `struct_class`, `source_crs`, `attributes`, `inclusion_reason`, `qa_flags`.
    - NO geometry math, NO GDAL imports at module top level; consumes attribute dicts + `src.loading.Layer`.
    - Document the `436 Reservoir` policy note (stays a waterbody) and flag any Group-0-UNCONFIRMED code.
  - [x] 1.3 Extend `src/loading.py` with the NHDLine loader seam
    - Add `LINE_LAYER_ALLOWLIST = ("NHDLine",)` and `LINE_ATTRIBUTE_FIELDS` (`FType`, `FCode`,
      `GNIS_Name`, `Permanent_Identifier`, `ReachCode`), independent of the existing allowlists; export
      them in `__all__`.
    - Add `discover_line_layers` and a `load_line_features` method on `PyogrioLayerLoader`, mirroring
      `discover_point_layers` / `load_point_features` (case-insensitive field selection, geometry +
      parallel attribute dicts). Do NOT overload the point/waterbody loaders.
    - Keep `pyogrio`/`shapely` lazy-imported behind the loader seam.
  - [x] 1.4 Ensure Task Group 1 tests pass
    - Run ONLY the tests written in 1.1; do NOT run the entire suite.

**Acceptance Criteria:**
- The 2–8 tests in 1.1 pass.
- `src/hydro_structures.py` has a matching `tests/test_hydro_structures.py`; no top-level GDAL imports in
  either; no geometry math in the taxonomy module.
- Line allowlist/attributes/loader are independent of the waterbody/point/flowline paths (no leakage).
- Missing FType → `excluded` + `missing_ftype`; out-of-scope codes accounted-for as `excluded`;
  provenance retained.
- Structure included codes are disjoint from the other three taxonomies (complementarity test passes).
- `INTERNAL_CRS` imported from `src/crs.py` wherever CRS is referenced (never inlined).

---

### QA & regression gate

#### Task Group 2: Complementarity/QA review, determinism, and full-suite regression
**Dependencies:** Task Group 1

- [x] 2.0 Validate the item and guard against regressions
  - [x] 2.1 Review the tests written in Task Group 1
    - Confirm coverage of: each in-scope FType→class mapping, missing/unknown FType handling,
      provenance retention, layer-level classification order, complementarity, and the NHDLine loader seam.
  - [x] 2.2 Analyze gaps for THIS item only
    - Identify critical classification/loader workflows lacking coverage — focus ONLY on this item's
      requirements (do NOT assess whole-app coverage).
  - [x] 2.3 Write up to 5 additional strategic tests maximum
    - Fill critical gaps only (e.g. a same-FType-across-layers case — `343` on NHDLine and NHDPoint both
      → `dam_weir`; a labels-table-covers-all-included-codes check). Skip edge/perf cases.
  - [x] 2.4 Verify the BYTE-IDENTICAL default-output gate
    - Confirm the DEFAULT build is byte-for-byte identical: this item adds a new module + loader methods
      but changes no default code path. Assert via `tools/verify_determinism.py` (e.g. `--region Oregon`)
      if a real region is available offline; otherwise assert byte-identity of the default render against
      the golden fixture / registry (`tests/fixtures/golden/registry.json`) and confirm no default import
      path now pulls GDAL.
  - [x] 2.5 Run the FULL offline suite for regressions
    - `.venv/bin/python -m pytest -q` — the entire suite must pass offline (no network, no GDAL, no real
      datasets).
    - Lint: `.venv/bin/ruff check src tests` (install ruff first if absent from `.venv`).

**Acceptance Criteria:**
- All item-specific tests pass; no more than 5 additional tests added to fill gaps.
- The DEFAULT build is byte-for-byte identical to current output (verified via determinism tooling /
  golden fixture); no new top-level GDAL import in any default code path.
- The FULL offline suite passes with no network / no GDAL / no real datasets; lint clean.
- Item gate met: a build can classify source-traceable engineered-water structures (dams/weirs, gates,
  lock chambers, gaging stations, water intakes/outflows, spillways, canals/ditches) from NHDLine,
  NHDPoint, and NHDArea into a versioned, complementary taxonomy, with the NHDLine loader seam in place —
  ready for the #67 rendering item; the default output stays byte-for-byte identical.

---

## Execution Order
1. Confirm NHDLine/NHDArea structure FType codes (Task Group 0) — verification only, non-blocking.
2. Hydro-structure taxonomy + NHDLine loader seam (Task Group 1).
3. QA, determinism, full-suite regression (Task Group 2).
