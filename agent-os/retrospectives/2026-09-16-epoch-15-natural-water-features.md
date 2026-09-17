# Retrospective — Epoch 15: Natural water features (#61–#64)

_Closed 2026-09-16. Implemented 2026-09-01. Single commit `4f460c3`, documented
in `645fe43`. No `planning/pre-analysis.md` was written; this is a narrative
closeout with a graded check against `planning/requirements.md` instead._

## What the epoch was

Add the six **natural water features** USGS NHD already encodes in the GDBs the
pipeline consumes — springs/seeps, waterfalls, rapids (NHDPoint glyphs) and
wetlands, playas, perennial ice (NHDWaterbody areal fills) — as opt-in,
source-traceable, water-only SVG layers with screen/print presets. The structural
template is Epoch 1.5 (waterbody outlines), mirrored beat-for-beat: versioned
taxonomy, loader seam, repair/reproject/clip/select, dedicated `<g>` layers,
config presets, additive pipeline integration. Every new family defaults
`enabled: False` so the default build stays byte-identical.

Four roadmap items shipped (#61–#64). Task Group 0 (FType code verification
against a real GDB) was completed — codes confirmed against HUC4 1807 and
documented in `planning/group0-ftype-findings.md` — but its task checkboxes in
`tasks.md` were left unchecked, and the roadmap carries a "deferred" note that is
now stale. The verification was done; only the bookkeeping lagged.

## What shipped

### #61 — Point-feature taxonomy + loader seam (`4f460c3`)

`src/point_features.py` (new, 223 lines): versioned `POINT_POLICY_VERSION`
FType/FCode taxonomy mirroring `src/waterbodies.py`. Classes: `spring` (FType
458), `waterfall` (487), `rapids` (431); classified-but-excluded: `well` (488),
`sinkhole` (450). Missing FType -> `excluded` + `missing_ftype` QA flag. Full
provenance per feature (`source_id`, `source_layer`, `dataset_id`, `huc4`,
`ftype`, `fcode`, `name`, `source_crs`, `attributes`, `inclusion_reason`,
`qa_flags`). No geometry math, no GDAL imports at top level.

`src/loading.py` gained `POINT_LAYER_ALLOWLIST` (`NHDPoint`),
`POINT_ATTRIBUTE_FIELDS`, `discover_point_layers`, and `load_point_features` on
`PyogrioLayerLoader` — independent of `WATERBODY_LAYER_ALLOWLIST`, so point
features never leak into the flowline/graph or waterbody load paths.

Tests: `tests/test_point_features.py` (7) + loader-seam tests in
`tests/test_loading.py`.

### #62 — Areal taxonomy + areal/point selection (`4f460c3`)

`src/areal_features.py` (new, 220 lines): versioned `AREAL_POLICY_VERSION` for
the three NHDWaterbody FTypes the waterbody taxonomy already sends to `excluded`:
466 SwampMarsh -> `wetland`, 361 Playa -> `playa`, 378 IceMass ->
`perennial_ice`. Complementary by construction — every NHDWaterbody polygon is
classified by exactly one taxonomy.

`src/areal_selection.py` (new, 347 lines): `ArealSelectionPolicy` (per-class
`min_area_m2`) + `process_areal_features` (repair -> reproject EPSG:5070 ->
region-clip -> area-measure -> threshold-select), and `PointSelectionPolicy` +
`process_point_features` (repair -> reproject -> clip -> deterministic
per-family minimum-spacing thinning with duplicate suppression). Both produce
auditable selection reports. Reuses `src.geometry.repair_geometry`,
`src.clipping.clip_geometry`, and the injectable `reproject` seam with a lazy
pyproj default.

**Key Group 0 finding:** the spec originally assumed areal features came from
`NHDArea`; real GDB inspection (`planning/group0-ftype-findings.md`) confirmed
they are `NHDWaterbody` FTypes, so the existing `load_waterbody_layers` seam is
reused — no new areal loader needed.

Tests: `tests/test_areal_features.py` (6) + `tests/test_areal_selection.py` (7).

### #63 — Point-glyph + areal rendering (`4f460c3`)

`src/rendering.py` extended with `DEFAULT_POINT_STYLES` / `DEFAULT_AREAL_STYLES`
and two new layer emitters:
- Point glyphs: `<g id="point_features">` -> per-family `<g id="point_<family>">`
  with stable element IDs. Springs = `<circle>` dots, waterfalls = chevron
  `<path>`, rapids = tick/zigzag `<path>`.
- Areal fills: per-family `<g id="areal_<family>">` groups with `data-class`.
  Wetlands = hatch/stipple (`<pattern>` fill), perennial ice = low-opacity fill,
  playas = dashed outline (`stroke-dasharray`, no fill).

Z-order: areal groups beneath flowlines/waterbodies; point glyphs on top of
everything. Each family's z-order individually configurable. With no
point/areal items supplied, `render_svg` output is byte-identical to the
pre-feature render.

Tests: `tests/test_natural_feature_rendering.py` (5).

### #64 — Config, presets, CLI + pipeline integration (`4f460c3`)

`src/config.py` gained frozen `PointFeatureSettings` and `ArealFeatureSettings`
(both default `enabled=False`), `POINT_FEATURE_PRESETS` and
`AREAL_FEATURE_PRESETS` (`screen`/`print-state`/`print-county`), and
`_coerce_point_features`/`_coerce_areal_features` with
`defaults < preset < explicit` precedence. Preset expansion at config time, NOT
stored on frozen `Settings` (mirroring `_coerce_waterbodies`).

`src/cli.py` gained `--point-features`/`--no-point-features`,
`--areal-features`/`--no-areal-features`,
`--point-feature-preset`/`--areal-feature-preset`. Unset flags default to
`None`; nested blocks deep-merged per sub-key.

`src/pipeline.py`: additive integration in existing stages. `validate`
additively loads point layers (gated on `settings.point_features.enabled` AND
`hasattr(loader, "load_point_features")`) and widens the waterbody layer load
gate (loads when EITHER `waterbodies.enabled` OR `areal_features.enabled`).
`generate_svg` gained `_select_point_glyphs(ctx)` and
`_select_areal_features(ctx)` mirroring `_select_waterbody_outlines`. Returns
`[]` when disabled, so the render is unchanged.

Tests: `tests/test_natural_feature_config.py` (18) +
`tests/test_natural_features_pipeline.py` (9).

## Test summary

**52 dedicated Epoch 15 tests** across six new test files:
- `test_point_features.py`: 7
- `test_areal_features.py`: 6
- `test_areal_selection.py`: 7
- `test_natural_feature_rendering.py`: 5
- `test_natural_feature_config.py`: 18
- `test_natural_features_pipeline.py`: 9

Plus loader-seam extensions in `tests/test_loading.py`. Full suite at epoch
close: **685 passed** (per implementation report, scoped to exclude an unrelated
in-progress spec). Current full suite: **1027 passed** (6 unrelated failures in
`test_min_order.py`, an uncommitted future spec).

## Real-data findings

### FType code verification (Group 0, HUC4 1807 Oregon coast)

Confirmed against the `NHDFCode` domain table embedded in the real extracted GDB
(`datasets/nhdplus_hr/1807/NHDPLUS_H_1807_HU4_GDB.gdb`):
- **Point families:** spring 458 (1119 in 1807), waterfall 487 (15), rapids 431
  (0 in 1807 — code confirmed via domain table, absent from this coastal sample).
  Classified-but-excluded: well 488 (2610), sinkhole 450 (126).
- **Areal families:** wetland 466 SwampMarsh (135), playa 361 (1), perennial_ice
  378 IceMass (0 in 1807 — expected in high-elevation HUC4s, not coastal).

The spec's guess of 487 for waterfalls was correct. Rapids (431) and perennial
ice (378) have confirmed domain codes but no real-geometry sample in 1807;
fixtures synthesize them.

### Source-layer correction

The spec originally framed wetland/playa/ice as `NHDArea` features. The Group 0
GDB inspection proved they are `NHDWaterbody` FTypes — the same layer
`load_waterbody_layers` already loads. This meant **no new areal loader** was
needed; the `validate` stage just widened its waterbody load gate to fire when
either `waterbodies.enabled` OR `areal_features.enabled`. This is the closest
thing to "the bug the real run surfaced": a spec assumption about source layers
that offline fixtures could not disprove, caught by reading the actual GDB domain
table before implementation. It saved building an unnecessary loader seam and
kept the two taxonomies genuinely complementary on the same underlying layer.

### No live render run

Unlike Epochs 1.5 and 16, no statewide real-data QA run was performed for the
natural water features (no `tools/natural_feature_qa.py` analog). The FType code
verification was done against the raw GDB, not through the selection pipeline on
real geometry. This is the epoch's main evidence gap — the selection thresholds
in the presets are provisional, not calibrated against real-data density. Epoch
16's hydro-structure QA (which used the Epoch 15 seams) partially validates the
plumbing, but the natural-feature-specific preset values remain untested at
state/county scale.

## Invariants held

- **Offline suite:** 52 dedicated tests + loader extensions; full suite green (685
  at epoch close, 1027 current). No GDAL, no network, no real data in the suite.
  No GDAL-backed imports leaked into `src/` or `tests/` top level; `shapely`
  at top level in `src/areal_selection.py` follows the established
  `src/waterbody_selection.py` pattern.
- **2D default output byte-identical:** yes. Both `point_features.enabled` and
  `areal_features.enabled` default to `False`; selection helpers return `[]`;
  `render_svg` receives `None`/empty and emits unchanged output. Guarded by
  `test_disabled_features_build_is_byte_identical` in the pipeline tests.
- **`PIPELINE_STAGES` untouched:** yes. No stage added or reordered. Additive
  loads live inside existing `validate` and `generate_svg` stages, gated on
  setting + loader support — the Epoch 1.5 integration pattern.
- **Rights gate:** N/A. NHDPoint/NHDWaterbody features are USGS federal public
  domain, same as flowlines and waterbody outlines. Sellable with attribution.
  `fulfillment.assert_sellable` unaffected.

## Graded against requirements

No `pre-analysis.md` was written; grading against `planning/requirements.md`
(the requirements discussion) and the spec's acceptance criteria.

| Requirement | Result |
|-------------|--------|
| All six families end-to-end | **Shipped.** Springs, waterfalls, rapids (point), wetlands, playas, perennial ice (areal). |
| Wells/sinkholes classified-but-excluded | **Shipped.** Present in taxonomy, mapped to `excluded`. |
| Falls/rapids from NHDPoint only | **Shipped.** Flowline-coded network falls/rapids deferred per plan. |
| Separate NHDPoint allowlist + `load_point_features` seam | **Shipped.** Independent of waterbody path. |
| Configurable size/color per family | **Shipped.** `DEFAULT_POINT_STYLES` / `DEFAULT_AREAL_STYLES`. |
| Z-order: areals beneath, points on top | **Shipped.** Each family individually configurable. |
| Presets control areal min-area + point density/spacing | **Shipped.** `screen`/`print-state`/`print-county`. |
| Additive pipeline integration | **Shipped.** Load in `validate`, select/render in `generate_svg`. |
| Default (disabled) build byte-identical | **Shipped.** Guarded by test. |
| Offline-suite discipline preserved | **Shipped.** No top-level GDAL imports. |
| No new data source / no new rights gate | **Shipped.** |

All 10 requirements-discussion answers ("all defaults") were implemented as
accepted. No requirement was partially met or missed.

## What went well

- **The Epoch 1.5 template held perfectly.** Every structural decision — taxonomy
  shape, selection pipeline, loader seam, config preset mechanism, additive
  pipeline integration, byte-identical-when-off discipline — was a direct mirror
  of the waterbody work. The epoch was genuinely "six new families through proven
  plumbing," not a reinvention.
- **Group 0 FType verification caught the source-layer misattribution early.**
  Reading the real GDB domain table before coding the areal taxonomy prevented
  building an unnecessary `NHDArea` loader seam. The correction (areal features
  are NHDWaterbody, not NHDArea) is documented in `group0-ftype-findings.md` and
  propagated through the spec, implementation, and pipeline integration cleanly.
- **Complementary taxonomy design is provably correct.** The waterbody taxonomy
  sends FTypes 466/361/378 to `excluded`; the areal taxonomy sends everything
  else to `excluded`. Every NHDWaterbody polygon is classified by exactly one
  taxonomy. This was asserted in tests and confirmed against the real 1807 GDB.
- **Single commit for the whole epoch.** All six task groups (0-6) landed in one
  coherent commit (`4f460c3`, 3502 insertions across 22 files), keeping the
  history clean and the epoch boundary sharp.

## Carry-forwards

- **No real-data QA run through the selection pipeline.** FType codes were
  verified against the raw GDB, but no statewide or county-level run exercised
  `process_areal_features` / `process_point_features` on real geometry at scale
  (unlike Epoch 1.5's Oregon/Washington/Clark County waterbody QA and Epoch 16's
  HUC4 1807 structure QA). The preset thresholds (`screen`/`print-state`/
  `print-county`) are provisional, not calibrated. A
  `tools/natural_feature_qa.py` harness and a real run would close this gap.
  **Open, not passed.**
- **Task Group 0 bookkeeping.** The FType verification was done and documented,
  but the task checkboxes in `tasks.md` remain unchecked and the roadmap carries
  a stale "deferred" note. Cosmetic, but should be reconciled.
- **Flowline-coded (network) falls/rapids.** Deferred per plan — NHDPoint only
  for the first cut. Styling NHDFlowline segments as falls/rapids is a separate
  concern, tracked as out-of-scope in the spec.
- **`rapids` (431) and `perennial_ice` (378) are untested against real geometry.**
  Both have confirmed domain codes but were absent from the 1807 sample. Fixtures
  synthesize them. A run against a high-elevation or whitewater HUC4 would
  confirm the classification + rendering path on real features.
- **Full byte-identical build compare was not run with GDAL.** The invariant is
  held by `test_disabled_features_build_is_byte_identical` in the offline suite
  and by the gated-loader architecture, not by a live `verify_determinism.py`
  double-render. This was resolved for the default path by Epoch 16's #67
  (`e6b9bd6cfaf7...`), but an enabled-features live determinism check remains
  open.

## Lessons

- **Read the real data before coding the taxonomy.** The Group 0 verification
  caught a source-layer assumption (NHDArea vs. NHDWaterbody) that would have
  produced a dead-code loader seam. Ten minutes with `ogrinfo` saved a wasted
  abstraction. This is the epoch's strongest process outcome.
- **When the template fits, use it without invention.** The entire epoch was six
  parallel copies of the waterbody pattern — no new I/O shape, no new pipeline
  mechanism, no new config convention. The result is boring and correct, which is
  the point.
- **Provisional presets are fine — label them honestly.** The `print-state` /
  `print-county` thresholds ship without a real-data calibration run. That is
  acceptable only because they are labeled as provisional and the preset mechanism
  allows value-only tuning without replumbing (the Epoch 1.5 lesson, confirmed
  again here).
- **Single-commit epochs keep the history clean** but make the individual task
  groups harder to attribute. For a six-group epoch this was the right trade;
  for larger epochs, per-group commits would be better.
- **Restore pre-analysis for future epochs.** Like Epoch 16, no
  `pre-analysis.md` / watch-list was written. The source-layer correction was
  caught by Group 0's ad-hoc GDB inspection, not by a pre-registered risk. A
  watch-list entry like "verify areal FTypes are actually in NHDArea" would have
  made this systematic rather than lucky.
