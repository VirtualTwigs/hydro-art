# Implementation Report: Infrastructure Rendering (Epoch 16, Item #67)

**Date:** 2026-09-03
**Status:** Complete — all four task groups done, item gate met, disabled-default
byte-identity verified against the live Oregon double-render.

## What shipped
Makes the #65-classified engineered-water structures visible on the river art, disabled by
default so the default build stays byte-for-byte identical. Mirrors the Epoch 15
natural-water machinery (`areal_selection` → `config` → `rendering` → `pipeline`),
branching on geometry type.

- **`src/hydro_structure_selection.py`** (new) — `HydroStructureSelectionPolicy`,
  `HydroStructureSelection`, `process_hydro_structures(features, *, boundary, policy,
  reproject=None)`: repair → reproject (injectable, lazy-pyproj default) → clip →
  geometry-type-aware select (polygon `min_area_m2`, point `min_spacing_m` deterministic
  thinning in source order, line clip-only). Frozen dataclasses, `INTERNAL_CRS` from
  `src/crs.py`, no top-level GDAL, provenance retained, exact-duplicate WKB dedupe.
- **`src/config.py`** — frozen `HydroStructureSettings` (`enabled=False`), `DEFAULTS`
  entry, `HYDRO_STRUCTURE_PRESETS` (`screen`/`print-state`/`print-county`),
  `_coerce_hydro_structures` (preset expand + merge `defaults < preset < explicit`,
  allowlist validation → `ConfigError`), wired into `build_settings` + `Settings`.
- **`src/rendering.py`** — `HYDRO_STRUCTURE_GLYPHS`, `DEFAULT_HYDRO_STRUCTURE_STYLES`,
  `_hydro_structure_lines` (geometry-type dispatch: point glyph / line bar / areal path),
  and keyword-only `hydro_structures` / `hydro_structure_styles` /
  `hydro_structure_order="above"` params on `render_svg`. `None`/empty → no markup
  (byte-identical).
- **`src/pipeline.py`** — additive `NHDLine` load → `artifacts["line_layers"]`; widened
  `needs_waterbody`/`needs_point` gates so `hydro_structures.enabled` also triggers the
  shared NHDArea/NHDPoint loads; `_select_hydro_structures` + `_hydro_structure_styles` in
  `_generate_svg_stage`. Every load/select gated on setting AND loader support.
- **Tests** — `tests/test_hydro_structure_selection.py` (7), additions in
  `test_config.py`, `test_rendering_svg.py`, `test_rendering_pipeline.py`.

## Symbol set (geometry-type dispatch)
- **Point** structures (gaging_station / water_intake_outflow / gate) → glyph markers
  (square / diamond / triangle), reusing the Epoch 15 point-glyph seam.
- **Line** structures (dam_weir / gate) → a perpendicular bar centered on the line's
  midpoint, oriented across local flow — a dam reads as a stroke spanning the channel
  (open 2-point path, no `Z`).
- **Polygon** structures (spillway / lock_chamber / canal_ditch) → areal treatment (solid
  low-opacity fill for spillway/lock, dashed outline for canal_ditch).
- Drawn in a dedicated `<g id="hydro_structures">` with per-class child `<g>`s, z-ordered
  **above** the water layers by default (`render_order="above"`).

## Complementarity (no double-draw)
Structure taxonomy codes `{343, 369, 398, 367, 485, 455, 336}` are disjoint from
waterbodies `{390, 436, 493, 312}`, point_features `{458, 487, 431}`, areal_features
`{466, 361, 378}`; a geometry owned by one taxonomy is `excluded` (dropped pre-render) by
the others, so each draws under exactly one layer. The shared NHDPoint/NHDArea loads feed
all subsystems; a mixed-code fixture proves each geometry draws once.

## Verification (Task Group 4)
- **4.1 Gap tests (3 / ≤5):** line-bar-vs-polygon dispatch
  (`test_hydro_structures_line_bar_is_open_path_distinct_from_polygon`);
  complementarity/no-double-draw (`test_shared_loads_are_complementary_no_double_draw`);
  split the order-dependent TG1 pyproj test into a subprocess-isolated
  `test_module_import_does_not_pull_pyproj_eagerly` + `test_injectable_reproject_seam_used`.
- **4.2 Byte-identical default — PASS:** `tools/verify_determinism.py --region Oregon`
  real double-render off pre-extracted GDBs → run-to-run OK, `svg_sha256
  e6b9bd6cfaf78f927ff439b22bc1cda4f93ad4f68a2688298b6935ee6732e96a`, `0 hydro structure(s)`
  on the default path, hash **identical to #65's recorded default**; no GDAL-backed lib in
  `sys.modules` on the default path; PNG compare skipped (resvg unavailable), svg_sha256
  stands.
- **4.3 Suite + lint:** 780 passed, 0 failed offline; stable across ordering. Ruff:
  pre-existing findings in the four `src/` files left alone (UP035/RUF022/ISC004/PLR1730/
  I001); pre-existing test-file findings confirmed at HEAD; the NEW deviations in the
  rewritten selection test (I001/PLW1510/ISC004) fixed — that file is ruff clean. No `src/`
  change for lint.

## Item gate: GREEN
Source-traceable dams/weirs, gaging stations, intakes, spillways, locks, and canals overlay
the water art from NHDLine/NHDPoint/NHDArea, controlled by setting/preset, with the disabled
default byte-for-byte identical (`e6b9bd6cfaf7…`). Ready for #68.

## Follow-ons
- **#68** real-data QA & preset tuning (structure-on-network placement, duplicate
  suppression, canal/natural separation; screen/print preset tuning).
- **#66** engineered-channel styling on `NHDFlowline`.
- `398 LockChamber` and line/area `369 Gate` still UNCONFIRMED against a lock-bearing HUC4
  (carried from #65).
- Prefer the fresh-interpreter subprocess pattern over `assert "x" not in sys.modules` for
  eager-import checks in future epochs.
