# Spec: Infrastructure rendering (Epoch 16, Item #67)

## Summary
Render the engineered-water structures classified in #65 (`src/hydro_structures.py`) onto
the river art. Add a structure **selection/clip** module, a **symbol set** with dedicated
above-water `<g>` layers, **config** settings + presets, and **pipeline** wiring — all
disabled by default so the default build stays byte-for-byte identical. Mirrors the Epoch
15 natural-water-features machinery beat-for-beat (`areal_selection` → `config` →
`rendering` → `pipeline`).

## Context & templates to mirror (parallel exactly — do not duplicate)
- `src/areal_selection.py` / `tests/test_areal_selection.py` — repair→reproject→clip→select,
  frozen policy + selection value objects, per-class `min_area_m2`, per-family
  `min_spacing_m`, injectable reproject seam (lazy pyproj).
- `src/config.py` — `PointFeatureSettings` / `ArealFeatureSettings`, `POINT_FEATURE_PRESETS`
  / `AREAL_FEATURE_PRESETS`, the `_coerce_*` preset-expansion + `build_settings` validation.
- `src/rendering.py` — `POINT_GLYPHS` / `DEFAULT_POINT_STYLES` / `_point_features_lines`,
  `DEFAULT_AREAL_STYLES` / `_areal_family_lines` / `_areal_lines_for_order`, and the
  `render_svg` z-order block.
- `src/pipeline.py` — `_validate_stage` additive loads + `_generate_svg_stage`
  `_select_point_glyphs` / `_select_areal_features` + `_point_feature_styles` bridges.
- `src/hydro_structures.py` (#65) — `HydroStructure` (`struct_class`, geometry, provenance),
  `classify_hydro_structure_layer`, `HYDRO_STRUCTURE_CLASSES`.

## Design

### Structure class → geometry → symbol
| struct_class | primary source | geometry | symbol treatment |
|---|---|---|---|
| `dam_weir` | NHDLine (+NHDArea) | line/poly | line symbol — bold bar across the channel |
| `gate` | NHDPoint/NHDLine | point/line | small point marker / short bar |
| `gaging_station` | NHDPoint | point | point marker (e.g. square) |
| `water_intake_outflow` | NHDPoint/NHDArea | point/poly | point marker (e.g. diamond) / areal |
| `spillway` | NHDArea | polygon | areal fill/outline |
| `lock_chamber` | NHDArea | polygon | areal fill/outline |
| `canal_ditch` | NHDArea | polygon | areal outline (dashed) |

Dispatch is by **geometry type first** (Point → glyph, LineString → line symbol, Polygon →
areal), refined by `struct_class` for color/shape. This differs from Epoch 15 (points-only
vs. polygons-only modules) because structures span all three geometry types in one taxonomy —
the renderer branches on geometry kind.

### `src/hydro_structure_selection.py` (NEW)
```
HydroStructureSelectionPolicy(frozen):
    min_area_m2: dict[str, float]       # per polygon class
    default_min_area_m2: float = 0.0
    min_spacing_m: dict[str, float]     # per point family
    default_min_spacing_m: float = 0.0
    # lines: clip only (no threshold in v1)

HydroStructureSelection(frozen):
    selected: tuple[HydroStructure, ...]
    excluded: tuple[HydroStructure, ...]
    policy: HydroStructureSelectionPolicy
    policy_version: str
    counts: dict[str, int]

process_hydro_structures(features, *, boundary, policy, reproject=None) -> HydroStructureSelection
```
Pipeline per feature: `repair_geometry` → reproject (injectable; default lazy-pyproj) →
`clip_geometry` to boundary (drop empties, flag clipped) → branch on geometry type:
polygon area-threshold, point spacing-thin (deterministic, source order), line keep-clipped.
Retains provenance from the source `HydroStructure`. No top-level GDAL; `shapely` behind the
same seam pattern `areal_selection` uses; `INTERNAL_CRS` from `src/crs.py` for the metric CRS.

### `src/config.py` (MODIFY)
`HydroStructureSettings` frozen dataclass (fields per requirements R2), default in `DEFAULTS`
(`enabled=False`), `HYDRO_STRUCTURE_PRESETS` (`screen`/`print-state`/`print-county`),
`_coerce_hydro_structures` (preset expand + merge, `defaults < preset < explicit`) called from
`build_settings`, added to the `Settings` dataclass. All new string knobs validated against
allowlists (`render_order ∈ {"above","below"}`, hex color, etc.).

### `src/rendering.py` (MODIFY)
- `HYDRO_STRUCTURE_GLYPHS` (point-family class → glyph shape) + `DEFAULT_HYDRO_STRUCTURE_STYLES`
  (per class: color, size/opacity/dash, geometry treatment).
- `_hydro_structure_lines(...)` builds `<g id="hydro_structures">` with per-class child `<g>`s,
  dispatching each feature by geometry type to a glyph / line-symbol / areal path.
- `render_svg` gains `hydro_structures: Iterable[tuple] | None = None` and
  `hydro_structure_styles: Mapping | None = None`; drawn in the z-order block per
  `render_order` (default `above`, after water/waterbody/point/areal layers). When `None`,
  emits nothing → byte-identical.

### `src/pipeline.py` (MODIFY)
- `_validate_stage`: widen additive loads so `hydro_structures.enabled` also triggers the
  NHDPoint and NHDArea loads (structures reuse them) and add the `NHDLine` load via
  `load_line_features` → `artifacts["line_layers"]`, each gated on setting AND loader support.
- `_generate_svg_stage`: `_select_hydro_structures(ctx)` classifies line/point/area layers via
  `classify_hydro_structure_layer`, runs `process_hydro_structures`, maps selected →
  `(feature_id, geometry, struct_class)`; `_hydro_structure_styles(ctx)` bridges settings →
  per-class overrides; both passed to `render_svg`. Returns `[]`/`None` when disabled.

## Acceptance criteria
- Structures from NHDLine/NHDPoint/NHDArea select, clip, and render into a dedicated
  above-water `<g id="hydro_structures">`, distinct symbol per class, source-traceable.
- Selection applies per-class `min_area_m2` (polygons) and per-family `min_spacing_m`
  (points) deterministically; lines are clip-only.
- Config `HydroStructureSettings` + presets validate and expand `defaults < preset < explicit`;
  **disabled by default**.
- The DEFAULT (infrastructure-disabled) build is **byte-for-byte identical** to current output
  (`tools/verify_determinism.py`); no new top-level GDAL import in any default path.
- Full offline suite passes (no network/GDAL/real data); lint clean; every new `src/` module
  has a matching test module.

## Risks / notes
- **Geometry-type dispatch** is the main new complexity vs. Epoch 15 — test all three kinds.
- **Shared-load reuse:** ensure enabling only `hydro_structures` still loads NHDPoint/NHDArea
  (widen gates additively) without changing behavior when point/areal features drive the load.
- Keep `render_svg` new params keyword-only with `None` defaults to guarantee byte-identity.
