# Task Breakdown: Infrastructure QA and presets (Epoch 16, Item #68 — epoch close)

## Overview
Total: 3 task groups. Prove the #67 infrastructure render on REAL OR/WA/Clark data and tune
the screen/print presets so structures enrich not clutter. Offline QA module (fixture-tested)
→ real-data QA tool + all-features render + preset tuning → determinism/regression gate.
Closes Epoch 16. The default (infrastructure-disabled) build stays BYTE-FOR-BYTE identical.

## Cross-cutting constraints
- **TDD:** 2–8 focused tests FIRST per offline group; run ONLY those until green.
- **Matching test file:** `src/hydro_structure_qa.py` → `tests/test_hydro_structure_qa.py`;
  preset changes tested in `tests/test_config.py`.
- **Offline discipline:** `src/hydro_structure_qa.py` + its test run offline — top-level
  `import shapely` is allowed (matches `src/areal_selection.py`), but NO
  `pyogrio`/`geopandas`/`rasterio` and no network. `tools/` scripts read real data + import GIS
  eagerly → OUTSIDE the suite; `src/` never imports `tools/`.
- **CRS:** `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`. QA math is
  projection-free (inputs already in EPSG:5070).
- **Byte-identical default:** preset value changes must NOT change the default build (no preset
  applied by default; infrastructure disabled by default).

---

## Task List

### Task Group 1: Offline structure-QA module
**Dependencies:** #67 (done)

- [x] 1.0 `src/hydro_structure_qa.py` + `tests/test_hydro_structure_qa.py`
  - [x] 1.1 Write 2–8 focused tests FIRST (run ONLY these):
    - `structure_network_placement`: a structure within `tolerance_m` of a flowline counts
      on-network; one far away is reported off-network; median/max distances correct.
    - `cross_layer_duplicates`: a `dam_weir` present as both an `NHDLine` and an `NHDArea`
      feature within `tolerance_m` is grouped as a duplicate; two distinct dams are not.
    - `canal_natural_separation`: a structure geometry coinciding with a natural feature →
      `separation_ok=False` + the offending pair; disjoint inputs → `True`.
    - `build_qa_report` aggregates the three into `HydroStructureQAReport`.
  - [x] 1.2 Implement the module: frozen `HydroStructureQAReport` + `NetworkPlacement`,
    `structure_network_placement`, `cross_layer_duplicates`, `canal_natural_separation`,
    `build_qa_report`. Pure shapely distance/`intersects`; no reprojection; `INTERNAL_CRS`
    referenced for the metric-CRS contract; no `pyogrio`/`geopandas`/`rasterio`; no network.
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** 1.1 tests pass; module offline (no GDAL beyond top-level shapely, no network);
the three QA properties computed correctly; matching test file exists.

---

### Task Group 2: Real-data QA tool + all-features render + preset tuning
**Dependencies:** Task Group 1
**Note:** Non-offline (reads real GDBs under `datasets/nhdplus_hr/`). NOT part of the offline
suite. Preset tuning (config) IS offline and is locked by `tests/test_config.py`.

- [x] 2.0 Real validation + preset tuning
  - [x] 2.1 `tools/hydro_structure_qa.py` (NEW) mirroring `tools/waterbody_qa.py`: load real
    `NHDLine`/`NHDPoint`/`NHDArea`, classify via `classify_hydro_structure_layer`, select via
    `process_hydro_structures`, run `src.hydro_structure_qa.build_qa_report` against the real
    flowline network + natural features, print counts / on-network placement / cross-layer
    duplicate groups / canal-natural separation / source-id traceability. CLI: `--state`,
    `--gdb-glob --no-clip`, `--county-shp/--county/--state-fp`. Eager GIS imports.
  - [x] 2.2 Extend `tools/render_state_allfeatures.py`: add an opt-in `--structures` flag that
    selects + draws hydro structures via the `render_svg` `hydro_structures` param (above water).
    Off by default → existing invocations unchanged.
  - [x] 2.3 Run the tool on a real OR/WA HUC4 (e.g. `datasets/nhdplus_hr/1807`) and a state clip;
    record the observed class counts + placement stats in `implementation/real-data-findings.md`.
  - [x] 2.4 Tune `HYDRO_STRUCTURE_PRESETS` in `src/config.py` (values only) from the observation
    so structures enrich at screen/print-county/print-state; add/extend `tests/test_config.py` to
    lock monotonic thinning (`print-state` ≥ `print-county` ≥ `screen` in `min_area_m2` /
    `min_spacing_m`) and that the default stays disabled. Run ONLY those config tests.

**Acceptance:** the tool runs the pipeline code against a real GDB and prints the QA report;
`render_state_allfeatures --structures` renders structures on a real state; presets tuned with
the monotonic-thinning invariant tested; default still disabled/byte-identical; findings recorded.

---

### Task Group 3: Determinism, full-suite regression & epoch-close gate
**Dependencies:** Task Group 2

- [x] 3.0 Validate and guard against regressions
  - [x] 3.1 Review TG1/TG2 tests; add up to 3 strategic offline gap tests max (e.g. an
    all-clean report, an all-violating report). Skip edge/perf cases.
  - [x] 3.2 Verify the BYTE-IDENTICAL default gate: `tools/verify_determinism.py --region Oregon`
    (or golden-fixture byte-identity if no region offline); confirm the tuned presets do NOT change
    the default path (0 structures on default) and no default `src/` import pulls GDAL.
  - [x] 3.3 Run the FULL offline suite: `.venv/bin/python -m pytest -q` (no network/GDAL/real
    data). Lint: `.venv/bin/ruff check src tests` (fix only NEW deviations; leave pre-existing
    sibling-matching RUF022/UP035 alone).
  - [x] 3.4 Write `implementation/report.md`.

**Acceptance:** all item-specific tests pass; ≤3 gap tests added; DEFAULT build byte-for-byte
identical; full offline suite green; lint clean. **Epoch 16 gate met:** source-traceable structures
overlay the water art, controllable by preset, default disabled + byte-identical. (After commit,
offer the Epoch 16 retrospective — separate step.)

---

## Execution Order
1. Offline structure-QA module (TG1).
2. Real-data QA tool + all-features render + preset tuning (TG2, non-offline).
3. Determinism, regression & epoch-close gate (TG3).
