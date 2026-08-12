# Product Roadmap

## Epoch 1 — 2D hydrographic art foundation · complete

1. [x] Configuration & CLI foundation `S`
2. [x] Dataset acquisition & cache `L`
3. [x] Data loading & geometry validation/repair `M`
4. [x] Projection & region clipping `M`
5. [x] Hydrography graph construction `M`
6. [x] Stream ordering & watershed grouping `M`
7. [x] Deterministic basin coloring `S`
8. [x] Layered SVG rendering `L`
9. [x] Optional glow & SVG optimization `M`
10. [x] Multi-format export & reproducibility hardening `L`

Outcome: a deterministic, editable GIS-to-SVG pipeline for original hydrographic art.

## Epoch 1.5 — waterbody outlines

**Phase 1.5.1 — Water-feature ingestion & taxonomy**

W1. [x] Waterbody source layers and classification — Load NHD waterbody/area polygons with the
attributes needed to identify lakes, reservoirs, ponds, bays, inlets, and coastal water; define
a reviewed inclusion taxonomy rather than relying on names alone. `M`
(`src/waterbodies.py`: immutable `WaterbodyFeature` + versioned `WATERBODY_POLICY_VERSION`,
`FTYPE_CLASS` FType-driven taxonomy — name only refines bay/inlet, missing FType → excluded,
never guessed. `src/loading.py` allowlists NHDWaterbody/NHDArea + attribute fields and adds
`load_waterbody_layers`. Tested in `tests/test_waterbodies.py` + `tests/test_loading.py`.)

**Phase 1.5.2 — Polygon quality & cartographic selection**

W2. [x] Waterbody repair, clipping & selection — Repair, reproject, and region-clip water
polygons; retain topology and provenance; apply configurable area/detail policies that preserve
lakes and meaningful inlets/bays while controlling tiny pond clutter. `L`
(`src/waterbody_selection.py`: `process_waterbodies` = repair → reproject(5070) → clip → area
measure → policy select, reusing `src.geometry`/`src.clipping` (holes + multipart preserved).
`WaterbodySelectionPolicy` (inland/coastal area thresholds, pond split, conservative vs.
permissive coast); deterministic dedup + shared-edge detection; full `selected`/`excluded`
provenance report. Tested in `tests/test_waterbody_selection.py`.)

**Phase 1.5.3 — Layered rendering & export**

W3. [x] Waterbody-outline rendering — Add closed, editable, fill-free outlines as dedicated SVG
layers with stable feature identifiers and configurable stroke/color behavior. Keep flowlines
visually legible at overlaps. `M`
(`WaterbodySettings` in `src/config.py` + `--waterbodies`/`--waterbody-color`/`-stroke-width`
in `src/cli.py`; `src/rendering.py` emits a `fill="none"` `#waterbodies` group of closed
per-feature `<path>`s with stable ids + configurable stroke/color/z-order; `src/pipeline.py`
loads (validate) and selects/renders (generate_svg) additively — byte-identical when disabled.
Tested in `tests/test_waterbody_config.py`, `test_waterbody_rendering.py`, `test_waterbody_pipeline.py`.)

**Phase 1.5.4 — Validation & art direction**

W4. [ ] Waterbody QA and regional presets — Validate fixture and real Oregon/Washington/Clark
County outputs for holes, multipolygons, coastal boundaries, duplicate edges, and size/detail
thresholds; establish print and screen presets. `L`
(Mostly done: offline fixture QA in `tests/test_waterbody_qa.py` (holes/multipolygons/coastal/
shared-edge) + a real-region harness `tools/waterbody_qa.py` executed 2026-07-30 against Oregon
(46,844 selected, 0 untraceable) and Washington (42,304 selected, 0 untraceable) — holes,
multipolygons, coastal boundaries, duplicate edges, traceability all pass. **Left:** (1) the
Clark County, WA county-level run (harness supports it, but the Census county shapefile isn't
mounted locally), and (2) the actual print/screen **preset values** — an art-direction decision
on stroke/size/detail thresholds, pending human review of the real-region output.)

Epoch gate: a build can produce original, source-traceable outlines for lakes, large ponds,
bays, and inlets without filling or incorrectly closing coastal water.

## Epoch 2 — elevation data foundation

**Phase 2.1 — Elevation contracts & provenance**

11. [x] Elevation settings and provenance model — Add validated settings for elevation source,
resolution tier, vertical-exaggeration display setting, and cache policy. Define immutable
metadata for source product, acquisition date, horizontal CRS, vertical CRS/datum, units,
resolution, checksum, and processing parameters. `M`
(`src/config.py`: `ElevationSettings` (enabled/source/tier/vertical_exaggeration/cache) +
`SUPPORTED_ELEVATION_SOURCES`/`SUPPORTED_ELEVATION_TIERS` + cache policy + `_coerce_elevation`
boundary validation; `src/elevation.py`: immutable `ElevationProvenance` (+ `build_provenance`)
recording source product, acquisition date, horizontal + vertical CRS/datum, units, resolution,
checksum, processing parameters, plus the `TileDiscoverer`/`RasterReader`/`ElevationSampler`
seams. Spec `agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling`; tested in
`tests/test_elevation_config.py` + `tests/test_elevation.py` (19 tests). Closes Epoch 2.)

**Phase 2.2 — Authoritative DEM acquisition**

12. [x] 3DEP DEM discovery, download & cache — Discover USGS 3DEP bare-earth DEM tiles for a
region, select a resolution tier, download/cache them through an injected seam, and record
their complete provenance. Start with CONUS; design the interface so Alaska/other sources can
be added without changing downstream code. `XL`

**Phase 2.3 — Raster normalization**

13. [x] DEM mosaic, clip & pyramid — Mosaic only the needed tiles, clip to the selected
boundary, reproject to EPSG:5070, preserve source vertical metadata, and generate a
deterministic multi-resolution raster pyramid for interactive, statewide, and county output.
`XL`

Epoch gate: a cached, source-traceable, numerically testable bare-earth DEM can be queried at
any point in the selected region.

## Epoch 3 — accurate terrain and hydrography Z

**Phase 3.1 — Ground-elevation sampling**

14. [x] Terrain sampling service — Provide an injectable bilinear sampler over normalized DEMs;
return elevation plus nodata/coverage diagnostics. Densify river lines at a spacing tied to
the active DEM resolution before sampling. `L`

**Phase 3.2 — Z-enabled hydrography**

15. [x] River elevation attribution & QA — Attach ground elevation to river vertices, preserve
the original 2D geometry path, identify nodata and implausible downstream inversions, and
offer an explicitly opt-in render-only monotonic water-surface repair. `L`

**Phase 3.3 — Terrain representation**

16. [x] Adaptive terrain mesh — Build deterministic terrain meshes from DEM pyramids with
boundary clipping and level-of-detail controls. Rivers use a configurable microlift solely to
avoid z-fighting; no artificial terrain is used in accurate mode. `XL`

Epoch gate: a state/county build has physically meaningful coordinates `(x, y, z)` in meters,
with enough metadata to reproduce and audit every height.

## Epoch 4 — 3D modeling and delivery

**Phase 4.1 — 3D render model**

17. [x] 3D scene assembly — Produce a scene containing terrain, Z-attributed rivers, watershed
materials, axis/cardinal annotations, camera presets, and display-only vertical exaggeration.
Separate geographic data from camera and artistic styling. `L`

**Phase 4.2 — Interactive preview**

18. [x] Progressive 3D preview — Replace the prototype's synthetic `elevationAt()` field with
DEM-backed tiles; use low-resolution interaction previews and commit full detail on release.
Support Oregon and Clark County, WA first. `L`
(`src/preview.py` builds deterministic coarse-interaction + fine-commit heightfield tiles;
`web/3d.html` samples them in place of the synthetic field. Real end-to-end Clark County build
still needs a non-offline DEM run.)

**Phase 4.3 — 3D export**

19. [x] Reproducible 3D export — Export a documented, interoperable 3D scene (GLB as the
primary deliverable; OBJ/GeoTIFF terrain as optional follow-ons) and a provenance manifest.
The same inputs must yield deterministic geometry and manifest values. `XL`
(Built before #18 per the spec's Phase F→G dependency; GLB + OBJ shipped, GeoTIFF deferred.)

Epoch gate: users can orbit an accurate terrain-and-rivers model and export a portable 3D
asset whose geography and elevation source are documented.

## Epoch 5 — quality, scale, and productization

20. [x] Accuracy validation suite — Compare sampled terrain/river vertices against known DEM
fixtures; report horizontal/vertical CRS, units, nodata coverage, and downstream QA results.
`L`
(`src/accuracy.py` (pure, offline, numpy-free): `error_metrics` (max/mean abs error + RMSE +
residuals, nodata/uncovered points skipped — never zero-filled), `coverage_report`
(covered/nodata/uncovered + fraction), `crs_report` (CRS/units/resolution verbatim from
`ElevationProvenance`), `qa_rollup` (river-profile inversion QA, structural over `ProfileQA`),
and `AccuracyReport` + `validate_against_sampler` over the injected `ElevationSampler` seam
with a `within_tolerance` verdict. Spec `agent-os/specs/2026-08-12-accuracy-validation-suite`;
tested in `tests/test_accuracy.py` (19 tests). Real-3DEP harness deferred (needs the GIS stack).)
21. [ ] Regional scale & offline packaging — Expand from Oregon/Washington to additional U.S.
states, with tile-budget controls, resumable jobs, and portable cache manifests. `XL`
(Partial — **portable cache manifests** shipped: `src/manifest.py` (pure, offline, numpy/GDAL-free)
turns `Cache` provenance into a deterministic, portable manifest — `build_manifest`/
`manifest_for_settings` (region→manifest via `resolve_required_files`), stable sorted JSON with
cache-relative paths, `verify_manifest` (sha256+size → ok/missing/mismatched), `diff_manifests`
(added/removed/changed/unchanged). Spec `agent-os/specs/2026-08-12-regional-scale-offline-packaging`;
tested in `tests/test_manifest.py` (13 tests). Also **tile-budget controls**: `ElevationSettings.tile_budget`
(0 = unlimited, boundary-validated) + `src/dem.py` `count_tiles` (pure offline preflight) + an
`acquire_dem(max_tiles=…)` guard that fails fast before any COG download when a region's tile count
exceeds the budget (tests in `tests/test_elevation_config.py` + `tests/test_dem.py`). **Resumable jobs**
found already-built (`Downloader` `.part`+HTTP-Range resume + `acquire`/`acquire_dem` cache-skip).
**Left:** region expansion beyond OR/WA/CA (needs real WBD), wiring `tile_budget` into a live DEM entry
point, and `tools/` packaging/preflight CLIs over a real NAS cache.)
22. [x] Print/experience modes — Add terrain-aware 2D hillshade, animation/camera paths, and
web delivery without compromising the canonical data model or reproducibility. `XL`
(All three concerns shipped across three offline slices. **(1) Terrain-aware 2D hillshade**:
`src/hillshade.py` (pure, offline, numpy over `RasterGrid`) computes Lambertian shaded relief (0-255)
via Horn's 3×3 gradients + a configurable sun (azimuth/altitude) and shading-only `z_factor`;
edge-replicated borders keep shape, nodata is never invented (a cell or its 8-neighborhood touching
nodata → sentinel), boundary-validated (`HillshadeError`), deterministic; `tests/test_hillshade.py`
(8 tests). **(2) Animation/camera paths**: `src/camera.py` (`math` + `src.scene` only) interpolates
`CameraPreset` keyframes into a tuple of `CameraPose` samples — lerp position/target/fov +
normalized-lerp up; open paths end exactly on the last keyframe, looping paths are seamless;
`CameraPathError` validation; `tests/test_camera.py` (7 tests). **(3) Web delivery**: `src/delivery.py`
(`json` + `src.raster` + `src.camera`) packages the hillshade grid + a camera path into one stable,
`sort_keys` JSON **experience document** (`hillshade_layer`/`camera_track`/`experience_document`/
`experience_json`, `DeliveryError` on empty inputs, nodata→`null`), consumed by a self-contained
`web/experience.html` viewer (canvas relief + camera-track playback); `tests/test_delivery.py`
(7 tests). All pure/deterministic/offline, not in `PIPELINE_STAGES`. Spec
`agent-os/specs/2026-08-12-print-experience-modes`. **Deferred (not gating #22):** compositing the
hillshade under the river SVG in a `tools/` print renderer, a live `/api/experience` server route over
a real DEM, and richer camera motion (easing/quaternion) beyond the linear first cut.)

## Epoch 6 — interactive art-direction UX

Turn the ad-hoc `tools/` renderers and the `web/` mockups into one guided control surface: pick a
state, drill to a county or keep the whole state, choose a single month / month range / annual
mean, and set coloring and line-thickness — with a live preview and a deterministic, reproducible
build behind it. The chosen direction is Prototype A (dense left-rail studio,
shipped as `web/studio.html`) using Prototype B's click-to-set month timeline for single/range
selection. Several controls the UX exposes are currently ad-hoc `tools/` recipes or client-side
simulations; this epoch promotes them to first-class, tested pipeline options so the UX drives the
real generator, not a mock.

**Phase 6.1 — Art-direction flag parity (pipeline)**

23. [x] Color & line-width art-direction options — Promote the "proposed" style controls into
`src/config.py`/`src/cli.py`/`src/rendering.py` as validated options: `color_by`
(`watershed`|`single`|`elevation`, the last mirroring `tools/render_state_mono.py`'s hypsometric
tint) and `width_by` (`flow`|`uniform`) with min/max/gamma. Deterministic; defaults keep existing
builds byte-identical. `M`

**Phase 6.2 — Scope & time as first-class build options**

24. [x] County scope in the pipeline — Promote `tools/render_county_clip.py`'s county clip into a
first-class `--county` build option (Census county polygon clip, validated against the selected
state), so scope selection isn't a separate script. `M`
25. [x] Monthly-flow rendering option — Promote `tools/monthly_flow.py` disaggregation + the fixed
year-max width scale into a first-class `--months` option (single month, month range → one frame
per month/animation, or annual mean), conserving each reach's annual QAMA. `L`

**Phase 6.3 — Control surface & integration (web)**

26. [x] Web control surface — Build the Prototype A studio panel (with B's month timeline) on the
shared `web/shared/ux.css` + `web/shared/hydro-ux.js` foundation: live client-side preview and a
render-request model that emits a ready-to-run `build.py` command + `config.yaml` matching the
selections. `L`
27. [x] Live pipeline integration — Wire the control surface to a local job runner that executes
the real pipeline for the selected options and returns the produced SVG/PNG for preview and
download, keeping determinism and the offline test posture intact. `XL`
28. [x] Presets & shareable render recipes — Named state/county/print presets and encodable render
recipes (URL/JSON) so a look can be saved, shared, and reproduced exactly. `M`
(`web/shared/hydro-ux.js` gains pure recipe helpers — `toRecipe`/`sanitizeRecipe`/
`encodeRecipe`/`decodeRecipe`/`applyRecipe`, a `PRESETS` catalog, base64url with a Node
`Buffer` fallback — round-trip-tested headlessly in `tests/test_recipe_roundtrip.cjs`;
`web/studio.html` adds a Presets fieldset, "Copy share link", `syncControls()`, and
`location.hash` restore. Closes Epoch 6.)

Epoch gate: a user can, from one screen, select state → county/whole-state, a month/range/annual,
coloring, and line thickness, see a faithful live preview, and produce the identical deterministic
artifact the CLI would.

> Notes
> - Epochs are gated by a demonstrable artifact, not calendar dates.
> - “Accurate” always means sampled from a documented bare-earth DEM with stated horizontal
>   and vertical CRS/units. Vertical exaggeration is display-only and never overwrites source Z.
> - Effort scale: XS=1 day, S=2–3 days, M=1 week, L=2 weeks, XL=3+ weeks.
