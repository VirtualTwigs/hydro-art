# Implementation Report: Hydro-Structure Taxonomy & Loader (Epoch 16, Item #65)

**Date:** 2026-09-03
**Status:** Complete — all three task groups done, gate met, byte-identical default verified.

## What shipped
- **`src/hydro_structures.py`** (new) — versioned, FType-driven taxonomy classifying engineered-water
  NHD structures into `dam_weir` / `gate` / `lock_chamber` / `gaging_station` / `water_intake_outflow`
  / `spillway` / `canal_ditch` / `excluded`. Mirrors `src/point_features.py` beat-for-beat: policy
  version, FType→class table, labels table, frozen `HydroStructure` dataclass, `classify_hydro_structure`
  / `classify_hydro_structure_layer`, shared `_lookup`/`_as_int` helpers, missing-FType→`excluded` +
  `missing_ftype` QA-flag rule. No geometry math, no top-level GDAL imports. One table serves all three
  source layers (`NHDLine`/`NHDPoint`/`NHDArea`) since a given FType carries the same meaning on each.
- **`src/loading.py`** (extended) — new NHDLine loader seam: `LINE_LAYER_ALLOWLIST = ("NHDLine",)`,
  `LINE_ATTRIBUTE_FIELDS`, `discover_line_layers`, `PyogrioLayerLoader.load_line_features`, all exported
  in `__all__`. Independent of the flowline/waterbody/point paths; pyogrio/geopandas kept lazy-imported
  inside the method. `NHDPoint` (Epoch 15 `load_point_features`) and `NHDArea` (Epoch 1.5
  `load_waterbody_layers`) already load with the needed attributes, so no new point/area loader.
- **Tests** — `tests/test_hydro_structures.py` (9) + `tests/test_loading.py` (+4 NHDLine seam cases).

## FType → class table (Group 0 — domain-verified against real GDB 1807, Oregon coast)
Decoded the embedded `NHDFCode` domain table (not from memory). Findings in
`planning/group0-findings.md`.

| FType | Class | Real-GDB status |
|------:|-------|-----------------|
| 343 | `dam_weir` | Confirmed (NHDLine 146, NHDArea 29) |
| 336 | `canal_ditch` | Confirmed (NHDArea 52) |
| 455 | `spillway` | Confirmed (NHDArea 15) |
| 485 | `water_intake_outflow` | Confirmed (NHDArea 1; NHDPoint Epoch 15) |
| 367 | `gaging_station` | Confirmed (NHDPoint, Epoch 15) |
| 369 | `gate` | Confirmed on NHDPoint; UNCONFIRMED on line/area (absent from 1807) |
| 398 | `lock_chamber` | UNCONFIRMED — absent from coastal 1807; standard NHD code, flagged in docstring |

`436 Reservoir` deliberately excluded (waterbodies owns it) — documented policy note.

## Complementarity (tested, passed cleanly)
Included structure codes `{343, 336, 455, 485, 367, 369, 398}` are disjoint from the included codes of
every sibling taxonomy — waterbodies `{390, 436, 493, 312}`, point_features `{458, 487, 431}`,
areal_features `{466, 361, 378}`. Asserted by `test_included_codes_disjoint_from_other_taxonomies`.

## Verification
- **Full offline suite:** 761 passed, 0 failed — no network, no GDAL, no real datasets.
- **Byte-identical default:** `tools/verify_determinism.py --region Oregon` → run-to-run byte-identical
  (svg sha256 `e6b9bd6cfaf7…`); render log shows 0 structures loaded into any default path.
- **No GDAL leakage:** importing `src.hydro_structures` pulls no pyogrio/geopandas/shapely/rasterio/
  fiona/osgeo into `sys.modules`.
- **Lint:** only the deliberate declaration-order `__all__` (RUF022) matching the sibling taxonomies;
  no new deviation.

## Follow-ons (later Epoch 16 items — out of scope here)
- #66 engineered-channel styling on `NHDFlowline` (CanalDitch/Pipeline/ArtificialPath).
- #67 structure symbology & rendering + the selection/clip step.
- #68 QA, presets, config settings, CLI flags.
- Confirm `398 LockChamber` and line/area `369 Gate` against a lock-bearing HUC4.
