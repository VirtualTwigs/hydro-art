# Requirements — Infrastructure rendering (Epoch 16, Item #67)

## Goal
Make the engineered-water structures already classified by `src/hydro_structures.py`
(#65) **visible** on the river art: select/clip them to the region, give each class a
distinct symbol, and draw them in dedicated `<g>` layers z-ordered **above** the water
so a dam reads on the channel it crosses. Disabled by default; the default build stays
byte-for-byte identical.

## Source layers & geometry types (all three already load)
Structures span three NHD source layers, each with its own existing loader — no new
loader is needed:
- **`NHDLine`** (lines) — dam/weir, gate — via `load_line_features` (#65).
- **`NHDPoint`** (points) — gaging station, water intake/outflow, gate — via
  `load_point_features` (Epoch 15).
- **`NHDArea`** (polygons) — spillway, lock chamber, canal/ditch, water intake/outflow —
  via `load_waterbody_layers` (`WATERBODY_LAYER_ALLOWLIST` already includes `NHDArea`).

Because a single FType table classifies all three (#65), the same loaded `NHDPoint` /
`NHDArea` layers are re-classified through the **structure** taxonomy at selection time
(complementary-taxonomy-over-one-load, exactly as areal features re-use the waterbody
load). Included structure codes are disjoint from the waterbody/point/areal taxonomies,
so no feature is double-drawn.

## Functional requirements

### R1 — Structure selection module (`src/hydro_structure_selection.py`, NEW)
Mirror `src/areal_selection.py`. Repair → reproject (injectable seam, lazy pyproj) →
clip to region boundary, then geometry-type-aware selection:
- **Polygon** structures (spillway/lock/canal/area intakes): per-class `min_area_m2`
  threshold (m² measured in `INTERNAL_CRS` EPSG:5070); below-threshold → excluded.
- **Point** structures (gaging/intake/gate): per-family `min_spacing_m` deterministic
  density thinning in source order.
- **Line** structures (dam/weir/gate): clip only (optionally a `min_length_m` knob,
  default 0 = keep all clipped). No geometry invented.
- Emit frozen `HydroStructureSelectionPolicy` + `HydroStructureSelection` value objects
  with `selected` / `excluded` tuples, `policy_version`, and `counts`. No top-level GDAL;
  `shapely` only where already used behind the seam pattern; no eager pyproj.

### R2 — Config (`src/config.py`, MODIFY)
- Frozen `HydroStructureSettings`: `enabled: bool = False`, `color: str = ""`,
  `size: float = 1.0` (point-marker multiplier), `opacity: float` (areal fill),
  `dash: str` (areal outline), `min_area_m2: float = 0.0`, `min_spacing_m: float = 0.0`,
  `render_order: str = "above"` (structures sit above water by default).
- `HYDRO_STRUCTURE_PRESETS` (`screen` / `print-state` / `print-county`) expanded at
  config time via a `preset`-style directive (`defaults < preset < explicit`), NOT stored
  on frozen settings — same mechanism as `PointFeatureSettings` / `WaterbodySettings`.
- Validated in `build_settings` against allowlists → `ConfigError`; **disabled by
  default** so no-preset / river-only builds are byte-identical.

### R3 — Rendering (`src/rendering.py`, MODIFY)
- Symbol set keyed on `struct_class` + geometry type:
  - **dam_weir / gate on lines** → a line symbol (bar/thick perpendicular stroke) that
    reads as crossing the channel.
  - **gaging_station / water_intake_outflow / gate on points** → point markers (reuse the
    Epoch 15 point-glyph seam: distinct glyph per family, e.g. square / diamond / triangle).
  - **spillway / lock_chamber / canal_ditch on polygons** → areal treatment (fill/outline).
- Dedicated `<g id="hydro_structures">` (with per-class child `<g>`s) drawn **above** the
  water layers by default (`render_order`), so structures overlay the channels.
- `render_svg` gains `hydro_structures` + `hydro_structure_styles` params (default
  `None`/empty); when absent, output is byte-identical to today.
- Palette/style tables: `DEFAULT_HYDRO_STRUCTURE_STYLES` per class, overridable via the
  config `color`/`size`/`opacity`/`dash`.

### R4 — Pipeline integration (`src/pipeline.py`, MODIFY)
- `validate` additively loads `NHDLine` via `load_line_features`, gated on
  `settings.hydro_structures.enabled AND hasattr(loader, "load_line_features")`; store in
  a new artifact key (e.g. `"line_layers"`). NHDPoint/NHDArea already load when their own
  features are enabled — but structures must also work when only `hydro_structures` is on,
  so ensure the NHDPoint/NHDArea loads are additionally triggered by
  `hydro_structures.enabled` (widen the existing `needs_*` gates, staying additive).
- `generate_svg` adds `_select_hydro_structures(ctx)` — classify the loaded line/point/area
  layers via `classify_hydro_structure_layer`, build the policy from settings, run
  `process_hydro_structures`, map selected → `(feature_id, geometry, struct_class)` tuples,
  and pass to `render_svg`. Returns `[]` when disabled or no layers.
- All loads/selects gated on **both** the setting AND loader support, so
  disabled/river-only builds stay byte-identical.

## Non-functional requirements / invariants
- **Offline-suite discipline:** no top-level GDAL imports in `src/` or `tests/`; heavy
  libs lazy behind seams; the selection module does no eager GDAL/pyproj import.
- **CRS:** import `INTERNAL_CRS` from `src/crs.py`; never inline `"EPSG:5070"`.
- **Byte-identical default:** nothing changes the default (infrastructure-disabled) render;
  verify via `tools/verify_determinism.py`.
- **Complementarity:** structures re-classify the shared NHDPoint/NHDArea loads through the
  structure taxonomy; disjoint codes guarantee no double-draw.
- **Rights gate:** NHDLine/NHDPoint/NHDArea are USGS public domain — no new rights gate.
- Every new `src/<name>.py` gets a matching `tests/test_<name>.py`; TDD 2–8 tests first
  per group, run only those until green, full suite at the end.

## Out of scope (later Epoch 16 items)
- **#66** — engineered-channel styling on `NHDFlowline` (CanalDitch/Pipeline/ArtificialPath).
- **#68** — real Oregon/Washington/Clark validation, duplicate-suppression QA, preset tuning.
- Confirming `398 LockChamber` / line-area `369 Gate` against a lock-bearing HUC4 (#65 debt).
