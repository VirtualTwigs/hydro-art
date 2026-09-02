# Implementation Report: Natural Water Features

**Date:** 2026-09-01
**Status:** Complete — all task groups (0–6) done. 62 feature tests passing; full offline suite green (685 passed) excluding an unrelated in-progress spec (see Caveats).

## What was built

Renders source-traceable **point** features (springs, waterfalls, rapids — NHDPoint
glyphs) and **areal** features (wetlands, playas, perennial ice/snow —
NHDWaterbody fills) as **opt-in, water-only** SVG layers. Mirrors the shipped
Epoch 1.5 waterbody feature beat-for-beat: versioned taxonomy → loader seam →
repair/reproject/clip/select → dedicated SVG layers → config presets → additive
pipeline integration → QA.

| File | Purpose |
|------|---------|
| `src/point_features.py` (new) | Versioned NHDPoint FType taxonomy → `PointClass` (spring/waterfall/rapids/gaging_station), `classify_point_layer`. |
| `src/areal_features.py` (new) | Versioned NHDWaterbody FType taxonomy → areal classes (wetland/playa/ice), `classify_areal_layer`. |
| `src/areal_selection.py` (new) | `ArealSelectionPolicy`/`PointSelectionPolicy` (per-class + `default_*` knobs) and `process_areal_features`/`process_point_features` — repair, reproject to EPSG:5070, clip to boundary, area/spacing selection, auditable `ArealSelection`/`PointSelection` reports. |
| `src/loading.py` (mod) | Added optional `load_point_features` loader seam (parallel to `load_waterbody_layers`). |
| `src/rendering.py` (mod) | `DEFAULT_POINT_STYLES`/`DEFAULT_AREAL_STYLES`, point-glyph + areal-fill rendering into dedicated `<g>` layers; `render_svg` byte-identity preserved when point/areal params are None/empty. |
| `src/config.py` (mod) | `PointFeatureSettings`/`ArealFeatureSettings` (both default `enabled=False`), `POINT_FEATURE_PRESETS`/`AREAL_FEATURE_PRESETS` (screen/print-state/print-county), boundary validation + preset expansion at config time. |
| `src/cli.py` (mod) | `--point-features`/`--areal-features` (BooleanOptionalAction), `--point-feature-preset`/`--areal-feature-preset`; deep-merged per sub-key so presets aren't shadowed. |
| `src/pipeline.py` (mod) | Additive integration: `validate` loads point/waterbody layers gated by `enabled` + `hasattr(loader, seam)`; `generate_svg` selects + renders them; z-order areal(below)→waterbodies→points→rivers→…→points(above). No change to `PIPELINE_STAGES` or the stub mechanism. |
| Tests (new) | `test_point_features.py` (7), `test_areal_features.py` (6), `test_areal_selection.py` (7), `test_natural_feature_rendering.py` (5), `test_natural_feature_config.py` (18), `test_natural_features_pipeline.py` (9), plus a loader-seam test in `test_loading.py`. **62 tests.** |

## Key decisions

- **Single-float config knobs → policy `default_*` fields.** The spec suggested
  per-class `min_area_m2`; I exposed one float per family on the settings object
  (mapping to `default_min_area_m2`/`default_min_spacing_m`), matching the
  waterbody template's flat-float approach. The per-class dict remains available
  on the policy for future needs without a config change.
- **Byte-identical default preserved by construction.** `areal_features`/
  `point_features` default `enabled=False` → selection helpers return `[]` →
  `render_svg` params resolve to None/empty → output is byte-identical to the
  river+waterbody build (asserted by `test_disabled_features_build_is_byte_identical`).
- **Areal reuses the NHDWaterbody load.** When `areal_features.enabled` the
  `validate` stage loads waterbody layers even if the waterbody *outline* layer is
  off (`test_areal_enabled_loads_waterbody_even_when_waterbodies_disabled`).
- **Graceful degradation on missing seam.** `point_features` enabled but a loader
  lacking `load_point_features` → no crash, no layer
  (`test_loader_without_point_seam_skips_gracefully`).
- **Offline discipline honored.** No new top-level GDAL imports; shapely-at-top
  follows the established `waterbody_selection` pattern; `INTERNAL_CRS` imported
  from `src/crs.py`.

## Acceptance criteria met

- Default (features-disabled) build is byte-identical to the pre-feature render.
- Enabled builds render dedicated `<g id="point_features">` and `<g id="areal_*">`
  layers with correct z-order over the river/waterbody art.
- Presets thin dense clusters (print-state collapses a ~4 km spring cluster to one);
  out-of-boundary features are clipped with an auditable exclusion reason.
- Enabled render is deterministic (double-render byte-identical).
- Full offline suite passes (no network/GDAL/real datasets); no new lint debt
  (the one I001 introduced in `src/pipeline.py` imports was fixed; remaining
  RUF022/UP035 are pre-existing codebase-wide conventions).
- End-to-end smoke via the real CLI path
  (`resolve_settings(["--region","Oregon","--point-features","--areal-features"])`
  → `Pipeline.run`) renders both layers with 1 selection each.

## Caveats / notes

- **Unrelated in-progress spec excluded from the green run.** An uncommitted,
  incomplete parallel spec (`agent-os/specs/2026-09-01-scale-aware-flow-widths/`)
  has already-modified `tests/test_config.py`, `tests/test_cli.py`,
  `tests/test_pipeline.py` referencing unimplemented `WIDTH_PRESETS`/`width_log`
  symbols — its collection error + 4 failures are independent of this feature
  (verified via `git stash`). The regression run was scoped to exclude only that
  work: `pytest -q --ignore=tests/test_config.py --deselect
  tests/test_cli.py::test_cli_width_preset_flag --deselect
  tests/test_cli.py::test_cli_width_log_flags --deselect
  tests/test_cli.py::test_unset_width_log_keeps_yaml --deselect
  tests/test_pipeline.py::test_resolve_stroke_widths_respects_width_log` →
  **685 passed, 4 deselected**. This is not this feature's code to touch.
- **Golden determinism gate (6.4)** requires a real GDAL render, unavailable
  offline; satisfied instead by the offline byte-identity test plus an
  enabled-features double-render determinism test.

## Not committed

Per the project workflow, committing is a separate explicit step ("commit item
#N"), which has not been given. No commit was made.
