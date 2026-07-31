# Implementation Report — W1: Waterbody source layers & classification

_Date: 2026-07-29 · Roadmap Epoch 1.5, Phase 1.5.1 (W1) · Task Group 1 only._

## Scope

Delivered the **ingestion & taxonomy contract** for areal water. This is the
classification layer only — no pipeline stage, no config surface, and no
rendering (those are W2/W3). Default 2D builds are therefore unchanged and
byte-identical; nothing in the live pipeline calls the new code yet.

## Resolved decisions (baked into policy/docs, applied fully in W2/W3)

1. Enablement: **on by default** (render-stage concern, W3).
2. Inland threshold: `min_inland_area_m2` = **0** (keep all valid; W2 selection).
3. Color: **single distinct water color**, independent of watershed palette (W3).
4. Coast: **conservative** — classify bays/inlets/estuaries; exclude SeaOcean
   and clip-boundary fragments until a reviewed coastal mode exists.

## Changes

- `src/loading.py`
  - `WATERBODY_LAYER_ALLOWLIST = ("NHDWaterbody", "NHDArea")` — deliberately
    **separate** from `HYDRO_LAYER_ALLOWLIST` so waterbody polygons never leak
    into the flowline/graph load path.
  - `WATERBODY_ATTRIBUTE_FIELDS` — the source columns retained for
    classification + provenance (FType, FCode, GNIS_Name, Permanent_Identifier,
    ReachCode, AreaSqKm).
  - `discover_waterbody_layers()` — case-insensitive discovery wrapper.
  - `PyogrioLayerLoader.load_waterbody_layers()` — real loader that populates
    `Layer.attributes` (parallel to geometries) from the present attribute
    columns. Marked `# pragma: no cover` (needs GDAL + real data); the offline
    suite exercises the contract via injected fake `Layer`s.
- `src/waterbodies.py` (new)
  - `WaterbodyFeature` immutable value object with full source provenance
    (source_id, layer, dataset, huc4, ftype/fcode, name, crs, attributes,
    class, inclusion_reason, qa_flags).
  - Versioned policy: `WATERBODY_POLICY_VERSION`, `WATERBODY_CLASSES`,
    `FTYPE_CLASS` (FType → normalized class), `FTYPE_LABELS`.
  - `classify_waterbody()` / `classify_layer()`. Classification is FType-driven;
    name is *secondary only* (splits BayInlet into bay vs. inlet). Missing/
    unknown FType → `excluded` + `missing_ftype` QA flag (never guessed).
  - No GIS imports; pure/offline. Repair, reprojection, area measurement, and
    threshold selection are intentionally deferred to W2.

## Classification policy (v2026-07-29.1)

| FType | Label       | Class     | Note                                   |
|-------|-------------|-----------|----------------------------------------|
| 390   | LakePond    | lake      | pond split is area-based (W2)          |
| 436   | Reservoir   | reservoir |                                        |
| 493   | Estuary     | coastal   |                                        |
| 312   | BayInlet    | bay       | name refines bay↔inlet                 |
| 445   | SeaOcean    | excluded  | conservative coast policy              |
| 460   | StreamRiver | excluded  | areal river → drawn as flowline        |
| 466   | SwampMarsh  | excluded  | wetland, not open water                |
| 361   | Playa       | excluded  |                                        |
| 378   | IceMass     | excluded  |                                        |
| 336   | CanalDitch  | excluded  |                                        |

## Tests

- `tests/test_waterbodies.py` (7): FType classification for lake/reservoir/
  estuary; bay↔inlet name refinement; SeaOcean exclusion; missing-FType QA
  flag; `classify_layer` provenance/ordering; stable policy version & vocab.
- `tests/test_loading.py` (+2): waterbody allowlist is separate from flowline
  discovery; `discover_waterbody_layers` case-insensitive filtering.
- New tests: 9. Full suite: **159 passed**, no regressions.

## Follow-ups (W3+)

- W3: `waterbodies` config block (enabled/color/threshold/coast) + a pipeline
  stage + dedicated no-fill SVG layers.
- Wire `load_waterbody_layers` + `process_waterbodies` into the pipeline and
  persist the `WaterbodySelection` report to `RunContext.artifacts` (unused
  until W3).

---

# W2 — Waterbody repair, clipping & selection

_Date: 2026-07-29 · Epoch 1.5, Phase 1.5.2 · Task Group 2._

## Scope

Added the **normalization & cartographic selection** library. Still no pipeline
stage/config/rendering (W3), so default 2D builds remain byte-identical.

## Changes

- `src/waterbodies.py`: added `area_m2: float | None = None` to
  `WaterbodyFeature` (populated during selection; W1 tests unaffected).
- `src/waterbody_selection.py` (new):
  - `process_waterbodies()` runs each classified feature through
    repair → reproject(EPSG:5070) → region clip → area → policy, reusing
    `src.geometry.repair_geometry` and `src.clipping.clip_geometry` so
    waterbodies inherit identical repair/clip semantics (holes + multipart
    preserved by shapely). Reprojection is an injectable seam whose default
    lazily imports pyproj — offline tests pass EPSG:5070 inputs so it's a
    no-op.
  - `WaterbodySelectionPolicy`: `min_inland_area_m2` (default **0**),
    `min_coastal_area_m2`, `pond_max_area_m2` (0 disables lake→pond split),
    `coastal_mode` (default **conservative**).
  - **Conservative coast policy**: a coastal-class feature (bay/inlet/coastal)
    trimmed by the region clip is a clip-boundary fragment → excluded. Open
    ocean is already excluded upstream (W1). Inland features near the border
    are trimmed and kept (flagged `clipped`).
  - `WaterbodySelection` report: `selected`/`excluded` (every candidate in
    exactly one bucket), `counts` (candidates/selected/excluded/by_class),
    `policy_version`, and `shared_edge_pairs`.
  - Determinism: input order preserved; exact-duplicate footprints
    de-duplicated via normalized-WKB key (first kept, rest excluded);
    shared coincident boundary segments counted via STRtree and flagged
    `shared_edge` (informs W3 stroke de-dup).

## Area semantics

EPSG:5070 is equal-area, so shapely's planar `area` is directly m². Thresholds
compare `area_m2 >= threshold` (inclusive), so `min_*_area_m2 = 0` keeps every
valid feature.

## Tests

- `tests/test_waterbody_selection.py` (8): m² measurement + zero threshold;
  inclusive area boundary; invalid (bowtie) repair then measure; hole
  preservation reduces area; clip trims partial / drops outside; conservative
  coast excludes clipped bay but keeps inland bay; duplicate-geometry dedup;
  report completeness + shared-edge flag.
- New tests: 8. Full suite: **167 passed**, no regressions.

---

# W3 — Waterbody rendering & configuration

_Date: 2026-07-30 · Epoch 1.5, Phase 1.5.3 · Task Group 3._

## Scope

Wired the W1/W2 library into the live pipeline: a validated `waterbodies` config
block, dedicated no-fill SVG outline layers, and pipeline plumbing that loads →
classifies → selects → renders areal water. This is the first item to change the
default 2D build — but only when areal-water data is actually present: with a
river-only loader (or `--no-waterbodies`) the output stays byte-identical.

## Changes

- `src/config.py`
  - `WaterbodySettings` frozen dataclass (enabled, color, stroke_width,
    min_inland_area_m2, min_coastal_area_m2, coastal_mode, render_order) as a new
    `Settings.waterbodies` field.
  - `DEFAULTS["waterbodies"]` (on by default, `#2ec4ff`, stroke 0.45, thresholds
    0, conservative, below) + `SUPPORTED_COASTAL_MODES`/`SUPPORTED_RENDER_ORDERS`.
  - `_coerce_waterbodies()` validates at the boundary (hex color, positive
    stroke, non-negative areas, allowlisted coastal_mode/render_order) and
    tolerates a partial mapping by filling missing sub-keys from defaults.
- `src/cli.py`
  - `--waterbodies/--no-waterbodies` (BooleanOptionalAction), `--waterbody-color`,
    `--waterbody-stroke-width`. Overrides collect under a nested `waterbodies`
    block; `resolve_settings` **deep-merges** it so YAML < CLI precedence holds
    per sub-key (e.g. `--no-waterbodies` keeps a YAML `stroke_width`).
- `src/rendering.py`
  - `polygon_path_d()` — one explicitly-closed `M…L…Z` subpath per ring
    (exterior + holes, multipart-aware), dropping shapely's duplicate closing
    vertex.
  - `_waterbody_lines()` — emits `<g id="waterbodies" fill="none" stroke=… …>`
    with per-feature `<g id="waterbody_{id}" data-class="{cls}">` and
    `<path id="waterbody_{id}_outline">`.
  - `render_svg` gained `waterbodies`/`waterbody_color`/`waterbody_stroke_width`/
    `waterbody_order` params. `waterbodies=None`/`[]` → byte-identical to the
    prior river-only render; bounds only extend when items are present;
    `below`/`above` control z-order relative to the flowline layers.
- `src/pipeline.py`
  - `validate` stage additionally loads waterbody layers, but only when
    `settings.waterbodies.enabled` **and** `hasattr(loader,
    "load_waterbody_layers")` — river-only loaders are untouched.
  - `generate_svg` calls `_select_waterbody_outlines()` (classify → `process_
    waterbodies` against the reprojected `region_boundary` → outline items),
    stashes the `WaterbodySelection` in `artifacts["waterbody_selection"]`, and
    passes outlines + configured style/order to `render_svg`.

## Byte-identical guarantee

Three layers of protection keep default builds unchanged where there's no areal
water: `render_svg` returns identical bytes for `waterbodies=None`; the validate
stage skips loading unless enabled AND supported; and `_select_waterbody_outlines`
returns `[]` (→ `waterbodies=None`) when disabled or empty. Verified by
`test_disabled_waterbodies_build_is_byte_identical`.

## Tests

- `tests/test_waterbody_config.py` (8): defaults on/valid; partial dict fills
  defaults; invalid color/coastal_mode/stroke_width raise; YAML override; CLI
  `--no-waterbodies` keeps YAML sub-keys; CLI color/width override.
- `tests/test_waterbody_rendering.py` (5): ring closure (exterior+hole); no-
  waterbody render byte-identical; fill:none group with stable IDs; configured
  color/width; below-vs-above z-order.
- `tests/test_waterbody_pipeline.py` (4): river-only loader has no group;
  disabled build byte-identical; enabled loader renders a lake outline; the
  `WaterbodySelection` lands in artifacts.
- New tests: 17. Full suite: **184 passed**, no regressions.

## Follow-ups (W4)

- Geographic QA against real Clark County / Oregon / Washington samples;
  approved state/county/print thresholds + coastal examples; SVG size /
  rasterization impact and a documented detail policy.

---

# W4 — Waterbody QA & regional presets (offline slice)

_Date: 2026-07-30 · Epoch 1.5, Phase 1.5.4 · Task Group 4 (partial by design)._

## Scope

W4 mixes work I can do offline with parts that require real NHD data (NAS +
GDAL) and approved art-direction numbers. Per an explicit scoping decision with
the user, this delivers only the **offline-verifiable slice** plus a **runnable
harness** for the real-data part; preset values and the real-region visual
validation are deferred (see below), so W4's checkbox is intentionally partial.

## Changes

- `src/rendering.py` — spec-conformance: the `<g id="waterbodies">` group now
  declares `stroke-linecap="round" stroke-linejoin="round"` explicitly. The root
  `<svg>` already sets these (they inherit), so rendered output is visually
  unchanged; the explicit attributes keep outlines correct when a single group
  is **extracted standalone** (as `tools/rasterize_layered.py` does per layer).
- `tools/waterbody_qa.py` (new) — real-data QA harness. Loads NHD waterbody/area
  polygons for a region, runs the *same* `classify_waterbody` +
  `process_waterbodies` the pipeline uses, and prints a report cross-checking the
  `WaterbodySelection`: class counts, hole/multipolygon counts, coastal
  kept-vs-dropped, coastal-fragment and duplicate-geometry drops, shared-edge
  pairs, and source-id traceability. Clips to a US state (Census shapefile, as
  `render_region_clip.py`), an optional county, or `--no-clip`. Eager GIS
  imports → outside the offline suite.

## Tests

- `tests/test_waterbody_qa.py` (5): waterbodies group declares round line
  join/cap; a donut's hole survives into the outline path (2 subpaths); a
  MultiPolygon renders as one group with a multi-subpath path; conservative
  coast drops a clipped bay end-to-end while keeping an inland lake (and the
  render omits the dropped bay); shared-edge lakes are both kept, flagged, and
  rendered rather than silently dropped.
- New tests: 5. Full suite: **189 passed**, no regressions.

## Real-region validation (executed 2026-07-30, NAS mounted)

Ran `tools/waterbody_qa.py --state {Oregon,Washington}` against the local
extracted NHDPlus HR datasets (basins 1701–1712, 161,744 candidate polygons
each). Both pass every acceptance criterion:

| Metric | Washington | Oregon |
|--------|-----------:|-------:|
| Candidates | 161,744 | 161,744 |
| Selected | 42,304 | 46,844 |
| Excluded | 119,440 | 114,900 |
| Lakes / reservoirs | 39,934 / 2,272 | 45,140 / 1,661 |
| Coastal kept (bay/inlet/coastal) | 98 | 43 |
| **Coastal fragments dropped** | **99** | **23** |
| Holes (features) | 2,781 (682) | 2,491 (679) |
| Multipolygons | 7 | 6 |
| Duplicate geoms dropped | 9 | 4 |
| Shared-edge pairs | 162 | 388 |
| Untraceable selected | 0 | 0 |

**No accidental coast closure**: the conservative policy excluded 99 (WA) / 23
(OR) coastal clip-boundary fragments while retaining genuine bays/inlets/coastal
water — the core Epoch-1.5 gate. Holes and multipolygons survive selection;
duplicates are de-duped; coincident edges are counted/flagged (not silently
dropped); every selected feature carries a source id.

## Still deferred

1. **Clark County, WA county-level clip** — the harness supports `--county-shp
   --county Clark --state-fp 53`, but the Census counties shapefile
   (`cb_2023_us_county_500k.shp`) isn't present locally; drop it in to run.
   Clark sits in HUC4 1708 (inland Lower Columbia); the statewide WA run above
   already validates its lakes and the coastal policy.
2. **Regional presets & detail policy** — exact print/screen threshold and
   stroke/size numbers are art-direction decisions the spec says must be
   approved before coding; deferred pending those values.
