# Task Breakdown: Infrastructure rendering (Epoch 16, Item #67)

## Overview
Total: 4 task groups. Make #65's classified structures visible — selection/clip module →
config + symbology → pipeline wiring → determinism/regression gate. Mirrors Epoch 15 natural
water features beat-for-beat. Additive and byte-identical: the default (infrastructure
disabled) build must stay BYTE-FOR-BYTE identical.

## Cross-cutting constraints (apply to every relevant group)
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green; no exhaustive coverage.
- **Matching test file:** `src/hydro_structure_selection.py` → `tests/test_hydro_structure_selection.py`;
  config/rendering/pipeline changes tested in `tests/test_config.py` / `tests/test_rendering_svg.py`
  / `tests/test_rendering_pipeline.py`.
- **Offline discipline:** NO top-level GDAL-backed imports (`pyogrio`/`geopandas`/`shapely`/
  `rasterio`/`pyproj`) in `src/` or `tests/`; keep them lazy behind seams. The selection module
  uses the same injectable-reproject + lazy-shapely pattern as `src/areal_selection.py`.
- **CRS:** import `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`.
- **Byte-identical default:** `render_svg`'s new params are keyword-only with `None` defaults;
  disabled/river-only builds emit no structure markup and stay byte-for-byte identical.
- **Complementarity:** structures re-classify the shared NHDPoint/NHDArea loads via the structure
  taxonomy; disjoint codes guarantee no double-draw.

---

## Task List

### Task Group 1: Structure selection module
**Dependencies:** #65 (`src/hydro_structures.py`, done)

- [x] 1.0 `src/hydro_structure_selection.py` + tests, mirroring `src/areal_selection.py`
  - [x] 1.1 Write 2–8 focused tests FIRST in `tests/test_hydro_structure_selection.py`:
    - polygon structure below `min_area_m2` → excluded; at/above → selected (area in EPSG:5070).
    - point structures thinned by per-family `min_spacing_m`, deterministic in source order.
    - line structure (dam/weir) clipped to boundary → kept; fully-outside → excluded.
    - a feature straddling the boundary is clipped (clipped flag/geometry) not dropped.
    - `HydroStructureSelection` carries `selected`/`excluded`/`policy_version`/`counts`; provenance
      (`source_id`, `struct_class`) preserved from the source `HydroStructure`.
    - injectable `reproject` seam is used (fake reproject), no eager pyproj import.
    - Run ONLY these tests.
  - [x] 1.2 Implement `HydroStructureSelectionPolicy`, `HydroStructureSelection`,
    `process_hydro_structures(features, *, boundary, policy, reproject=None)`:
    repair → reproject (injectable, default lazy pyproj) → clip → geometry-type-aware select
    (polygon `min_area_m2`, point `min_spacing_m` thinning, line clip-only). Frozen dataclasses,
    `INTERNAL_CRS` from `src/crs.py`, no top-level GDAL, provenance retained.
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** 1.1 tests pass; module has no top-level GDAL/pyproj; per-class/per-family
thresholds + line clip work; selection value objects + provenance correct.

---

### Task Group 2: Config settings + rendering symbology
**Dependencies:** Task Group 1

- [x] 2.0 `HydroStructureSettings` + `HYDRO_STRUCTURE_PRESETS` in `src/config.py`; symbol set in
  `src/rendering.py`
  - [x] 2.1 Write tests FIRST:
    - `tests/test_config.py`: `HydroStructureSettings` defaults (`enabled=False`); a `preset`
      directive expands `defaults < preset < explicit`; invalid `render_order` → `ConfigError`;
      disabled by default (no preset → default settings).
    - `tests/test_rendering_svg.py`: `render_svg` with a hand-built point/line/polygon structure
      set emits a `<g id="hydro_structures">` above the water layers with distinct per-class
      children; with `hydro_structures=None` the output is byte-identical to a no-structures render.
    - Run ONLY these tests.
  - [x] 2.2 `src/config.py`: add frozen `HydroStructureSettings`, `DEFAULTS` entry (disabled),
    `HYDRO_STRUCTURE_PRESETS` (`screen`/`print-state`/`print-county`), `_coerce_hydro_structures`
    (preset expand + merge), wire into `build_settings` + the `Settings` dataclass; validate knobs
    against allowlists → `ConfigError`.
  - [x] 2.3 `src/rendering.py`: add `HYDRO_STRUCTURE_GLYPHS`, `DEFAULT_HYDRO_STRUCTURE_STYLES`,
    `_hydro_structure_lines(...)` (geometry-type dispatch: glyph / line-symbol / areal), and the
    keyword-only `hydro_structures` / `hydro_structure_styles` params on `render_svg` drawn in the
    z-order block per `render_order` (default above). `None` → no markup (byte-identical).
  - [x] 2.4 Run ONLY the 2.1 tests until green.

**Acceptance:** 2.1 tests pass; settings validate + expand + default-disabled; structures render in
a dedicated above-water group with per-class symbols; `None` path byte-identical.

---

### Task Group 3: Pipeline integration
**Dependencies:** Task Group 2

- [x] 3.0 Wire selection + render into the pipeline (`src/pipeline.py`)
  - [x] 3.1 Write tests FIRST in `tests/test_rendering_pipeline.py`:
    - with `hydro_structures={"enabled": True, ...}` and a fake loader yielding NHDLine/NHDPoint/
      NHDArea, the rendered SVG contains the `hydro_structures` group with selected features.
    - with `hydro_structures` disabled (default), the render is byte-identical to the current
      river-only output (no `line_layers` load, no structure markup).
    - enabling ONLY `hydro_structures` still loads NHDPoint/NHDArea (shared-load reuse) — structures
      appear even when point/areal features are off.
    - Run ONLY these tests.
  - [x] 3.2 `_validate_stage`: add the additive `NHDLine` load via `load_line_features` →
    `artifacts["line_layers"]`, and widen the NHDPoint/NHDArea load gates so
    `hydro_structures.enabled` also triggers them; each gated on setting AND loader support.
  - [x] 3.3 `_generate_svg_stage`: add `_select_hydro_structures(ctx)` (classify line/point/area via
    `classify_hydro_structure_layer`, build policy from settings, `process_hydro_structures`, map to
    tuples) and `_hydro_structure_styles(ctx)`; pass both to `render_svg`. Return `[]`/`None` when
    disabled.
  - [x] 3.4 Run ONLY the 3.1 tests until green.

**Acceptance:** 3.1 tests pass; enabling structures renders them from all three source layers;
disabled build byte-identical; shared NHDPoint/NHDArea load reuse works; gates are setting AND
loader-support.

---

### Task Group 4: Determinism, QA & full-suite regression gate
**Dependencies:** Task Group 3

- [x] 4.0 Validate the item and guard against regressions
  - [x] 4.1 Review the tests from TG1–TG3; identify critical gaps for THIS item only (geometry-type
    dispatch, complementarity/no-double-draw, z-order above water). Add up to 5 strategic tests max.
  - [x] 4.2 Verify the BYTE-IDENTICAL default gate: `tools/verify_determinism.py --region Oregon`
    (or golden-fixture byte-identity if no region offline); confirm no default import path pulls GDAL
    and 0 structures load on the default path.
  - [x] 4.3 Run the FULL offline suite: `.venv/bin/python -m pytest -q` (no network/GDAL/real data).
    Lint: `.venv/bin/ruff check src tests` (pip install ruff if absent).
  - [x] 4.4 Write `implementation/report.md`.

**Acceptance:** all item-specific tests pass; ≤5 gap-filling tests added; DEFAULT build byte-for-byte
identical (determinism tooling / golden); full offline suite green; lint clean. Item gate: a build
can overlay source-traceable dams/weirs, gaging stations, intakes, spillways, locks, and canals on
the water art, controllable by setting/preset, with the default (disabled) output byte-for-byte
identical — ready for #68 (real-data QA & preset tuning).

---

## Execution Order
1. Structure selection module (TG1).
2. Config + rendering symbology (TG2).
3. Pipeline integration (TG3).
4. Determinism, QA & regression gate (TG4).
