# Requirements — Infrastructure QA and presets (Epoch 16, Item #68)

## Goal
Prove the #67 infrastructure render holds up on REAL Oregon/Washington/Clark data, and
tune the screen/print presets so structures **enrich rather than clutter**. Closes Epoch
16. The default (infrastructure-disabled) build stays byte-for-byte identical.

## The three QA properties to validate (from the roadmap)
1. **Structure-on-network placement** — engineered structures sit ON/near the flowline
   network they belong to (a dam is on its channel, a gaging station on its reach), not
   floating in space. Measure nearest-flowline distance per structure and summarize.
2. **Duplicate suppression** — the same real-world structure classified from more than one
   source layer (e.g. a dam present as both an `NHDLine` feature and an `NHDArea` polygon)
   is not drawn twice. Detect cross-layer near-duplicates by proximity/identity.
3. **Canal / natural separation** — engineered channels (structure `canal_ditch`, and the
   engineered `NHDArea`/flowline FTypes) are distinct from natural water; the complementary
   taxonomy must keep each geometry owned by exactly one class, so no structure double-draws
   a natural feature and canals are visually separable.

## Functional requirements

### R1 — Offline structure-QA module (`src/hydro_structure_qa.py`, NEW)
Pure, deterministic, offline (mirrors `src/determinism.py` / `src/flow_metrics.py` — pure
functions the offline suite tests; heavy real reads live in `tools/`). Provide functions
that take already-classified/selected `HydroStructure` sequences (+ the flowline geometries)
and return QA verdicts/metrics:
- `structure_network_placement(structures, flowlines, *, tolerance_m)` → per-structure
  nearest-flowline distance + summary (count on-network within tolerance, max/median
  distance, off-network list). Uses `INTERNAL_CRS` metric distances.
- `cross_layer_duplicates(structures, *, tolerance_m)` → groups of near-coincident
  structures spanning different `source_layer`s with the same `struct_class` (candidate
  duplicates to suppress).
- `canal_natural_separation(structures, natural_features)` → assert disjointness: no
  structure geometry coincides with a natural (waterbody/areal/point) feature of a
  different taxonomy; report any overlap.
- A small `HydroStructureQAReport` frozen value object aggregating the three.
- **No top-level GDAL imports** (`shapely` is allowed at top level like the sibling
  selection modules; no `pyogrio`/`geopandas`/`rasterio`). No network. `INTERNAL_CRS` from
  `src/crs.py`.

### R2 — Preset tuning (`src/config.py`, MODIFY)
Tune `HYDRO_STRUCTURE_PRESETS` (`screen` / `print-state` / `print-county`) so the density
(`min_area_m2`, `min_spacing_m`) and styling (`size`, `opacity`, `dash`) read as enrichment
at each scale — informed by the real OR/WA render in R4. Keep the mechanism (`_coerce_hydro_
structures`, `defaults < preset < explicit`) unchanged; only values move. The **default
remains disabled** — no preset applies unless asked, so the default build is byte-identical.
Update/extend `tests/test_config.py` to lock the tuned preset invariants (e.g. print-state
thins more aggressively than print-county than screen).

### R3 — Real-data QA tool (`tools/hydro_structure_qa.py`, NEW; non-offline)
Mirror `tools/waterbody_qa.py`: run the SAME pipeline code (`src.hydro_structures` +
`src.hydro_structure_selection` + the new `src.hydro_structure_qa`) against real NHD
`NHDLine`/`NHDPoint`/`NHDArea` from a real GDB, clipped to a state/county, and print a QA
report — class counts, on-network placement stats, cross-layer duplicate groups,
canal/natural separation, and source-id traceability. Reads real `.gdb` and imports GIS
eagerly, so it lives OUTSIDE the offline suite. Support `--state Oregon/Washington`,
`--gdb-glob ... --no-clip`, and a Clark-County path like `waterbody_qa.py`.

### R4 — Surface structures in the real all-features render (`tools/render_state_allfeatures.py`, MODIFY)
Extend the existing all-features preview renderer to also select + draw hydro structures
(reuse `src.hydro_structures` + `src.hydro_structure_selection` + the `render_svg`
`hydro_structures` param), so a real OR/WA render visually confirms structures overlay the
network above water. Structures OFF by default in the tool unless a flag enables them, so
existing invocations are unchanged. Use the observed output to tune R2.

## Non-functional requirements / invariants
- **Offline-suite discipline:** `src/hydro_structure_qa.py` and its test run offline (no
  GDAL beyond top-level shapely, no network, no real data). `tools/` scripts read real data
  and stay out of the suite; `src/` never imports `tools/`.
- **CRS:** `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`.
- **Byte-identical default:** nothing changes the default (infrastructure-disabled) render;
  verify via `tools/verify_determinism.py`. Preset value changes do NOT affect the default
  (no preset applied by default).
- **Rights gate:** NHD sources are USGS public domain — no new rights gate.
- Every new `src/<name>.py` gets a matching `tests/test_<name>.py`; TDD 2–8 tests first per
  group, run only those until green, full suite at the end.

## Epoch-close deliverables
- Item gate met (structures overlay real data, controllable by preset, default byte-identical).
- After #68 ships and is committed, the epoch is complete — offer to write the Epoch 16
  retrospective in `agent-os/retrospectives/` (separate explicit step, per user practice).

## Out of scope
- **#66** (engineered-channel styling on `NHDFlowline`) is a separate, still-open item;
  canal/natural separation here concerns `NHDArea`/structure canals, not flowline restyling.
- Confirming `398 LockChamber` / line-area `369 Gate` against a lock-bearing HUC4 (may be
  opportunistically checked if a lock-bearing GDB is available, but not required).
