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

W4. [x] Waterbody QA and regional presets — Validate fixture and real Oregon/Washington/Clark
County outputs for holes, multipolygons, coastal boundaries, duplicate edges, and size/detail
thresholds; establish print and screen presets. `L`
(Done: offline fixture QA in `tests/test_waterbody_qa.py` (holes/multipolygons/coastal/
shared-edge) + a real-region harness `tools/waterbody_qa.py` executed 2026-07-30 against Oregon
(46,844 selected, 0 untraceable) and Washington (42,304 selected, 0 untraceable) — holes,
multipolygons, coastal boundaries, duplicate edges, traceability all pass. The **preset *mechanism***
now ships (spec `agent-os/specs/2026-08-12-waterbody-regional-presets`): `WATERBODY_PRESETS` — `screen`
plus scale-specific `print-state` (100k/250k m²) and `print-county` (25k/50k m²) bundles — +
`SUPPORTED_WATERBODY_PRESETS` in `src/config.py`, expanded in `_coerce_waterbodies` with
`defaults < preset < explicit` precedence, and a `--waterbody-preset` CLI flag (unknown → argparse
exit 2); `preset` is consumed at config time so a no-preset build stays byte-identical (tests in
`tests/test_waterbody_config.py`, 17). The Clark County, WA county-level run executed 2026-08-12
(Census cb_2023 county shapefile now staged at `/tmp/counties_shp/`): clipped to the real Clark polygon
against HUC4 1708, 6,416 candidates → **830 selected** (809 lakes, 21 reservoirs) at screen thresholds,
all source-traceable, coastal/duplicate/shared-edge QA clean. That run drove the **print preset split**:
a single global print threshold can't serve both zooms — the old 100k/250k value dropped 97% of Clark's
waterbodies (830 → 24) at county scale, so `print-state` keeps it for large-format while `print-county`
uses 25k/50k (keeps a readable ~62). The mechanism + defensible per-scale defaults are in place; the
numbers stay human-tunable in `WATERBODY_PRESETS`. **Closed 2026-08-17:** every W4 deliverable —
fixture QA, real Oregon/Washington/Clark County validation, and the screen/`print-state`/`print-county`
preset mechanism — has shipped and its 22 QA/config tests pass; the per-scale thresholds are finalized
as tunable defaults, so the item is complete. This closes Epoch 1.5.)

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
21. [x] Regional scale & offline packaging — Expand from Oregon/Washington to additional U.S.
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
Also a **package preflight planner**: `src/packaging.py` `plan_package`/`PackagePlan`/`format_plan`
(pure, offline) composes `resolve_required_files` + `build_manifest`/`verify_manifest` +
`tile_budget` into one "is this cache ready to ship?" verdict (present/missing/corrupt +
injected-tile-count preflight → `is_ready`), driven by `tools/package_cache.py`
(`--region`/`--cache-dir`/`--tile-count`); tests in `tests/test_packaging.py` (7 tests).
Also a **settings-driven DEM acquisition entry point**: `src/dem.py`
`acquire_dem_for_settings(settings, *, boundary, cache, downloader)` reads
`elevation.tier`/`tile_budget`/`cache_policy` and forwards to `acquire_dem` (guards on
`enabled`; maps `refresh` policy; feeds the fail-fast budget guard) — the `tile_budget`
wiring, tested offline in `tests/test_dem.py` (+5).
Also a **manifest packaging CLI**: `src/manifest.py` gains pure `format_verification`/`format_diff`
(tested) and a thin `tools/cache_manifest.py` with `write`/`verify`/`diff` subcommands over a real
(e.g. NAS) cache — build a portable manifest to disk, verify a moved cache against it, and reconcile
two manifests (exit codes reflect completeness/sync); not in the offline suite (reads a real cache),
tests in `tests/test_manifest.py` (+4).
Also **region expansion to Idaho** (fourth supported region): HUC4 basins derived from local WBD
(`tools/derive_state_huc4.py Idaho`) → `("1701", "1704", "1705", "1706")` (Snake system + panhandle,
all HU2 17; SE Bear-River corner in HU2 16 omitted like CA's desert fringes), wired into
`SUPPORTED_REGIONS` (`config`), `REGION_HUC4` (`datasets`), `STATE_FIPS` (`counties`), and the
`tools/render_common.STATE_HUC4` mirror; tested in `tests/test_config.py`/`test_datasets.py`/
`test_counties.py`. Acquisition/config plumbing — a full render also fetches the region-17 NHDPlus HR
archives on demand.
Finally, a **real (non-offline) DEM entry point**: `src/dem.py` gains a pure, offline
`REGION_BOUNDS` + `region_bounds(region)` (EPSG:4326 per-region envelope, the DEM counterpart to
`REGION_HUC4`, drift-guarded against `SUPPORTED_REGIONS`; tests in `tests/test_dem.py` +4) that turns
a region name into the lon/lat box `count_tiles`/`acquire_dem` discover over, and a thin
`tools/acquire_dem.py` CLI that drives `acquire_dem_for_settings` against a real 3DEP S3 + NAS cache
(`--region`/`--cache-dir`, force-enabling elevation, honoring `--tier`/`--tile-budget`/`--refresh`,
with a network-free `--dry-run` tile-count/budget preflight); not in the offline suite (reads/writes a
real cache + network). The DEM subsystem keeps its own entry points and stays **out** of
`PIPELINE_STAGES` by design (CLAUDE.md) — that integration is a deliberate non-goal, not a gap.)
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
(Run-pipeline reconcile `5dc8ebf`: `_download_stage` now skips fetching when datasets are already
extracted and `serve.py` falls back to a local cache when the NAS is unmounted, so the served
"Run pipeline" button was verified end-to-end offline — Oregon/Deschutes job succeeded with zero
downloads, artifact identical to the direct build.)
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

## Epoch 7 — external storage & data operations

Move the large files a build reads and writes off the size-limited local disk (~35 GB free) onto an
external drive, and make the pipeline reference them there. The "database" files (extracted NHDPlus
HR / WBD `.gdb` datasets and their downloaded archives) and the rendered image outputs (SVG/PNG/PDF)
are the bulk consumers of disk. This builds on Epoch 5 #21, which staged only the *downloaded
archives* on the NAS (`NAS_CACHE_DIR`): this epoch generalizes storage so the *datasets* and *output*
roots can also live on the external drive, migrates existing local output onto it, and keeps a build
resilient when the drive is unmounted (mount-aware fallback to local, mirroring
`serve.py:_resolve_cache_dir`). Storage location never affects the rendered bytes, so `Settings` and
determinism are untouched.

**Phase 7.1 — External storage layout & migration**

29. [x] External-storage layout & output migration — Resolve the cache, datasets, and output roots to
a configurable external-drive location (env var + CLI, mount-aware with a local fallback and an
optional local working copy during generation), and provide a one-time migration that moves existing
local output onto the drive and leaves the local path referencing it (directory symlink). Pure,
deterministic path/plan resolution in `src/storage.py` (stdlib-only, offline-testable, not in
`PIPELINE_STAGES`) with a thin `tools/migrate_storage.py` executor over real drives; wire `build.py`
and `serve.py` to the resolver. Defaults keep current on-disk behavior byte-identical when no external
root is configured. `M` — Done: `src/storage.py` (`resolve_storage` + `plan_migration`/`apply_migration`),
`tools/migrate_storage.py`, `build.py`/`serve.py` wiring + optional `--staging` local working copy;
488 tests pass (spec `2026-08-17-external-storage-layout`).

Epoch gate: with an external drive configured, a build reads its GDB datasets and writes its rendered
images on the external drive (not local disk), existing output has been migrated there and still
resolves through the local path, and a build with the drive unmounted falls back cleanly to local
paths without crashing.

## Epoch 8 — terrain-aware print output · complete

Bring the DEM subsystem's shaded relief into the printed river art. Epoch 5 #22 shipped the pure
hillshade primitive (`src/hillshade.py`) and a web viewer (`web/experience.html`), but the shaded
relief has never been placed *under* the neon flowlines in a rendered image — today's print path
(`tools/rasterize_layered.py`) alpha-composites the river layers over a flat black canvas. This epoch
adds a terrain background: compute hillshade from a region's real DEM, tint it, and composite the
existing river SVG art over it so mountains and valleys read behind the network — without touching the
canonical 2D pipeline, the vector art's determinism, or the offline test posture.

**Phase 8.1 — Shaded-relief compositing**

30. [x] Hillshade print compositing — **Shipped 2026-08-17** (`src/compositing.py` seam +
`tools/render_terrain_print.py`); the Epoch 8 gate (print over accurate 3DEP relief) was closed by the
#31 real-DEM read path, so the earlier progress caveat is resolved. — Composite the river-art SVG over
a DEM-derived shaded-relief background in a print renderer. Add a **pure, offline** compositing seam in `src/` that turns a
hillshade `RasterGrid` (from `src.hillshade.hillshade`) into an RGB(A) background raster — optional
hypsometric/relief tint, configurable opacity and blend, nodata → transparent — and alpha-composites
the rasterized river layers over it (generalizing today's flat-black base in
`tools/rasterize_layered.py` into a supplied background). Deterministic and numpy-only so it stays in
the offline suite with hand-built `RasterGrid`s. A thin non-offline `tools/render_terrain_print.py`
wires the real DEM (`src.dem.acquire_dem_for_settings` → `src.raster.normalize_dem` → `hillshade`) to
the shared render recipe (`tools/render_common.py`) so state/county print output gains terrain relief;
the DEM background must align to the same EPSG:5070 frame/extent as the flowlines. Defaults keep the
existing flat-black print output byte-identical when no DEM background is supplied. `L`
(**In progress — compositing seam shipped, tested; real-3DEP wiring blocked.** `src/compositing.py`
(pure, offline, numpy-only) turns a hillshade `RasterGrid` into a tinted RGBA relief background
(`shade_to_background`: grayscale/tint, opacity, nodata→transparent) and folds the rasterized river
layers over a *supplied* background (`solid_canvas`/`alpha_over`/`composite_over_background`),
generalising `tools/rasterize_layered.py`'s flat-black base; `CompositingError` boundary validation;
`tests/test_compositing.py` (13, offline). `tools/render_terrain_print.py` (non-offline) wires it:
clip flowlines (`render_common`) → art SVG → per-layer resvg → transparent RGBA, DEM grid →
`src.hillshade` → relief → composite → PNG. **Not yet gating-complete:** the DEM→`RasterGrid` read
path does not exist — `RasterReader`/`RasterReprojector` are Protocol-only, `rasterio` isn't a
dependency, and nothing turns cached 3DEP COG tiles into a grid — so the tool takes a *supplied* DEM
(`--dem` .npy/image) instead of auto-acquiring via `acquire_dem_for_settings`→`normalize_dem`. A
concrete COG reader (separate, larger, non-offline) is the follow-on needed to meet the epoch gate.
Spec `agent-os/specs/2026-08-17-hillshade-print-compositing/`; suite 502 passing (+13). Smoke:
synthetic DEM→hillshade→relief→composite over synthetic river layers → a real PNG.
Deferred from #22, whose closing note listed "compositing the hillshade under the river SVG in a
`tools/` print renderer" as an explicit non-gating follow-on. The primitive already exists —
`src/hillshade.py` (`hillshade(grid, *, azimuth_deg, altitude_deg, z_factor, nodata)` → 0-255
`RasterGrid`) — and `tools/rasterize_layered.py` already splits the river SVG into per-layer PNGs and
alpha-composites them over a black canvas; this item swaps that fixed black base for a tinted
shaded-relief background and adds the real-DEM wiring. Needs the full GIS/DEM environment for the
`tools/` entry point, so — like the other real-DEM tools — the executor sits outside the offline suite
while the compositing math stays pure and tested.)

**Phase 8.2 — Concrete DEM reader (unblocks the epoch gate)**

31. [x] 3DEP COG reader & reprojector — **Shipped 2026-08-17** (`src/raster_io.py`:
`grid_from_arrays` + `RasterioRasterReader(opener=…)` + `RasterioReprojector(warp=…)` with an
identity short-circuit, `RasterIOError`; `rasterio` added to `requirements.txt` as an optional,
lazy-imported dep; `tools/render_terrain_print.py` now auto-acquires 3DEP relief from
`--region-dem`/`--state` when no `--dem` is given, clipped to the flowlines' EPSG:5070 extent). Ten
offline tests (`tests/test_raster_io.py`) cover the pure affine mapping + validation, the reader over a
fake opener, the reprojector identity/injected-warp paths, and the full `normalize_dem` → `hillshade`
chain — all with no rasterio installed. This closes the #30 gap: the Epoch 8 gate (print over accurate
3DEP relief) is now met. Original scope below. — Implement the missing concrete `RasterReader` /
`RasterReprojector` seams so cached 3DEP COG tiles become a normalized `RasterGrid`, closing the gap
that keeps #30 from auto-acquiring real relief. Add a rasterio-backed reader that opens a `DemAsset`'s
cached COG (`asset.path`) and returns a north-up `RasterGrid` (values + `GridTransform` + source CRS +
nodata, provenance carried through), and a warp-backed `reproject(grid, dst_crs)` to EPSG:5070 — the
two collaborators `src.raster.normalize_dem(assets, boundary, reader, reprojector, …)` already expects.
Follow the project's injectable-seam rule: rasterio is a **new optional dependency, lazy-imported
behind the seam** (in `requirements.txt`, never at module import of `src/`), so the offline suite stays
GDAL/rasterio-free — the reader is exercised offline against a tiny hand-written GeoTIFF fixture (or a
fake asset), and end-to-end against real 3DEP tiles only in the non-offline tools. Then wire
`tools/render_terrain_print.py` (and a `tools/acquire_dem.py` follow-through) to go
`acquire_dem_for_settings` → `normalize_dem` (with the new reader/reprojector) → `hillshade` →
`src.compositing`, so `--region` alone produces a terrain-backed print with **no `--dem` grid**, the
relief clipped to the flowlines' EPSG:5070 extent. Determinism: identical cached tiles → identical
`RasterGrid` values and identical composited bytes. `L`
(Follow-on isolated during #30: `src.raster.RasterReader.read(asset) -> RasterGrid` and
`RasterReprojector.reproject(grid, dst_crs)` are Protocol-only with no implementation, and `rasterio`
is not a dependency, so nothing turns the COG tiles `acquire_dem_for_settings` caches into a grid.
`normalize_dem`, `DemAsset(tile, path, provenance)`, tile discovery/caching, tile-budget, and the pure
`hillshade`/`compositing` seams all already exist — this item supplies only the two concrete GDAL/
rasterio-backed collaborators and the real-DEM wiring, after which #30 meets the epoch gate. Vertical
CRS/units are recorded verbatim in provenance; the reader never invents nodata.)

**Phase 8.3 — Real-tile validation (produce the gate artifact)**

32. [x] Terrain-print real-tile closeout — Produce and record the *demonstrable artifact* the Epoch 8
gate names. #30 and #31 are code-complete and fully covered by the **offline** suite, but that suite
proves the seam behavior against hand-built grids and **injected fakes** — no terrain-backed print has
ever been rendered from real cached 3DEP COG tiles with `rasterio` actually installed. Per the epoch
rule ("gated by a demonstrable artifact, not calendar dates"), the gate is not truly met until that
image exists. This item runs the auto-acquire path end-to-end in the full GIS/DEM environment,
verifies it, and captures the evidence — it adds **no new `src/` capability** (only bug-fixes if the
real run surfaces one); its deliverable is the artifact + a short validation report. `S`
(Scope: (1) install the GIS/DEM stack incl. `rasterio`/GDAL into `.venv` (already listed in
`requirements.txt`); (2) run `tools/render_terrain_print.py --state <region>` with **no `--dem`** so it
auto-acquires — `acquire_dem_for_settings` over the NAS/local cache → `normalize_dem`
(`RasterioRasterReader`/`RasterioReprojector`) → `hillshade` → `src.compositing` → a real PNG for at
least one whole-state and one `--county` scope; (3) **verify the gate claims**: the shaded relief
aligns to the flowlines' EPSG:5070 frame/extent, nodata reads transparent (no invented terrain), the
neon network reads over the relief, and each tile's provenance is recorded; (4) **determinism**: render
twice → byte-identical composited PNG (identical cached tiles → identical `RasterGrid` → identical
bytes), and confirm the canonical 2D vector pipeline's default output is still byte-identical (no
regression); (5) record the artifact, the source tile ids/checksums/provenance, and any integration
wrinkles the offline fakes could not surface. **Highest-risk untested path:** real 3DEP 1/3" COGs are
delivered in EPSG:4269 (NAD83 geographic), *not* EPSG:5070 — so `RasterioReprojector`'s **non-identity
`_default_warp` branch** (`rasterio.warp.reproject`) fires for the first time in a real run; the
offline suite only exercises the identity short-circuit and an injected warp spy, so watch the warped
grid's transform/nodata/extent and the resvg node cap at print resolution here. Non-offline and
environment-dependent by nature, so — like the other real-DEM tools — it lives outside the offline
suite; its closeout is the recorded artifact + report, not a test.)

Epoch gate: a state or county print image shows the neon river network composited over accurate,
source-traceable bare-earth shaded relief in the same EPSG:5070 frame, produced deterministically from
a documented DEM; the vector pipeline and its byte-for-byte default output are unchanged.

## Epoch 9 — Codebase health & maintainability · complete

**No new product capability.** Every item is a refactor, test, or housekeeping fix surfaced by the
2026-08-25 codebase audit (duplication, coverage gaps, uncommitted noise, missing feedback loop). The
hard invariant for the whole epoch: **the offline suite stays green and the 2D pipeline's default
output stays byte-identical** (these are pure internal cleanups, not behavior changes).

**Phase 9.1 — De-duplication (make the "single recipe" claim true)**

33. [x] De-duplicate the `clip_flowlines` render recipe — The GDB-iteration + VAA/EROM join + Strahler
filter + shapely-clip loop is copy-pasted three times: the canonical `tools/render_common.clip_flowlines`,
`tools/render_state_mono.clip_flowlines_elev` (admits "Mirrors …"), and
`tools/render_state_mono_peak.clip_flowlines_elev_ids` (admits "Mirrors …"). Give the canonical
`clip_flowlines` an optional `extra_vaa_cols` (and id-passthrough) parameter and delete both mirror
copies, so the two mono renderers call the shared recipe. `S`
(These are `tools/` scripts outside the offline suite; the closeout is a smoke-render, not a test. Fix
before `render_state_mono_peak.py` is committed as a permanent third copy.)

34. [x] Canonicalize the internal-CRS constant — `src/raster.py` defines `INTERNAL_CRS = "EPSG:5070"`,
but `src/config.py`, `src/mesh.py`, `src/hydro_z.py`, and `src/waterbody_selection.py` hardcode the raw
`"EPSG:5070"` string instead of importing it. Introduce one canonical constant (a small `src/crs.py` or
re-export) and have every internal-CRS reference import it. `XS`
(Pure rename/import change; a test asserts `config`/`mesh` reference the shared constant. Default output
byte-identical.)

35. [x] Derive `STATE_HUC4` from `REGION_HUC4` — `tools/render_common.STATE_HUC4` is a hand-maintained
mirror of `src/datasets.REGION_HUC4` (Washington intentionally adds `1707`). Make `render_common` import
`REGION_HUC4` and extend it, killing the drift hazard where updating one silently diverges from the
other. `XS`

**Phase 9.2 — Web view-helper extraction**

36. [x] Extract duplicated `web/` view helpers into `hydro-ux.js` — `drawSwatches`, `buildTimeline`,
`paintTimeline`, `fillCounties`, `bindRange`, and `seg` are duplicated (several character-for-character)
across `studio.html`, `proto-b-guided.html`, and `proto-c-canvas.html`, contradicting CLAUDE.md's "view
logic lives only in `hydro-ux.js`" rule. Move them into `web/shared/hydro-ux.js` as exported helpers over
the existing `H.PALETTES`/`H.COUNTIES`/`H.MONTH_ABBR` and have each page call them. `S`
(Covered by the existing headless `tests/test_recipe_roundtrip.cjs` harness pattern where practical.)

**Phase 9.3 — Coverage & housekeeping**

37. [x] Pipeline orchestrator unit tests — `src/pipeline.py` (the 12-stage orchestrator, ~550 LOC) has
no `tests/test_pipeline.py`; it is exercised only indirectly through the `test_*_pipeline.py` integration
files. Add direct unit coverage for the structural contracts: canonical stage order, "no stubs remain"
(every `PIPELINE_STAGES` entry has a real `_STAGE_FUNCS` function), `_stub` no-op behavior, `Stage`
immutability, `Pipeline.stage_names`, and that `Pipeline.run` threads a single `RunContext` through the
stages in order sharing `artifacts`. `XS`
(This item's deliverable **is** the test — it ships in the planning commit, green against existing
behavior, and requires no source change.)

38. [x] Housekeeping & retrospective practice — (1) revert the accidental `/com` corruption in
`web/proto-b-guided.html:7`; (2) add the missing invocations to CLAUDE.md's Commands (`ruff check .`,
`node tests/test_recipe_roundtrip.cjs`) and a short "known debt / gotchas" note pointing at the
`pipeline.py` gap and the de-dup items; (3) start a lightweight `agent-os/retrospectives/` practice (the
audit found zero retro/lessons docs) with an epoch-closeout entry. `XS`

Epoch gate: the offline suite is green, the 2D pipeline's default output is byte-for-byte unchanged, no
duplicated copy of `clip_flowlines` or the named `web/` view helpers remains, `src/pipeline.py` has
direct unit coverage, and a retrospective note exists for a closed epoch.

## Epoch 10 — Verification & real-data confidence

**No new product capability.** The 2026-08-27 assessment surfaced the codebase's one structural weak
seam: the offline suite (its greatest strength) sometimes *asserts* invariants it cannot *verify* —
byte-identical output and the real GDAL/warp paths — so real-data runs keep discovering what injected
fakes miss (the #32 latitude-drift mosaic bug; #34's byte-identical claim carried forward unverified).
This epoch makes those invariants *checkable on demand* without disturbing the fully-offline 527-test
suite. Hard invariant: the offline suite stays green and the 2D default output stays byte-identical.
(Commercial note: the determinism verifier + golden-output fixtures double as **fulfillment QA** — a sold
print can be re-generated byte-for-byte on re-order — but this epoch is **not** a prerequisite for the
first manually reviewed digital order in Epoch 11.5.)

**Phase 10.1 — Determinism you can prove**

39. [x] Determinism verifier — `tools/verify_determinism.py`: render a fixed region twice and diff
`svg_sha256` + rasterized PNG; commit per-region golden hashes as fixtures. Closes the "#34 asserted
byte-identical but couldn't verify offline" carry-forward. `S`
(Shipped 2026-08-30, commit `87c64fd`. Pure golden-registry/verdict core `src/determinism.py`
(`DeterminismVerdict`, `evaluate`/`record_golden`/`format_verdict`; GDAL-free, tested in
`tests/test_determinism.py`) + the non-offline `tools/verify_determinism.py` double-render CLI
(`--record`/`--force`, `svg_sha256` + `SOURCE_DATE_EPOCH=0`-pinned rasterized-PNG diff). The
committed per-region golden fixtures + the real GDAL double-render that *exercises* the verifier
are #40 / the epoch-gate closeout.)

40. [x] Golden-output fixtures for one small region — commit a tiny county's expected SVG hash + DEM
mosaic checksum so a machine *with* GDAL catches drift the offline fakes can't. `M`
(Shipped 2026-08-31. Pure `src/raster.grid_checksum` (versioned, endian/contiguity/NaN-canonical DEM
fingerprint) + two-checksum golden registry in `src/determinism.py` (`Golden` value type, `dem_sha`
wired through `evaluate`/`record_golden`/`format_verdict`; bare-string #39 entries still load).
`tools/verify_determinism.py` grew `--check-dem`/`--dem` (county-aware DEM clip) + fixed a latent
`export_paths` str→`Path` bug. Committed fixture `tests/fixtures/golden/registry.json`:
**Wahkiakum, WA** — SVG sha (cross-host invariant) + county-scoped DEM mosaic sha (same-host
regression, GDAL/PROJ-version sensitive). 644 offline tests green.)

**Phase 10.2 — Exercise the paths fakes skip**

41. [ ] Real-data smoke harness (opt-in, outside the offline suite) — a `tools/`-driven check that
fires exactly the branches fakes skip: the reprojector's non-identity EPSG:4269→5070 warp, multi-tile
mosaic alignment (the #32 class), and the cross-device SMB mover. Gated behind an env flag/marker so
the offline suite is untouched. `M`

42. [ ] DEM alignment invariant on real tiles — a targeted regression asserting mosaicked tiles share a
pixel grid *after* the single warp, on ≥2 real 3DEP tiles at different latitudes (the #32 bug). `S`
(Partial — the **offline** guard shipped 2026-08-30 (commit `87c64fd`): `tests/test_dem_alignment.py`
asserts `normalize_dem` mosaics two hand-built two-latitude grids *before* the single warp into one
uniform-pixel grid, and that `_require_aligned` accepts `rel_tol=1e-6` warp drift while rejecting a
genuine tier change — the #32 regression, GDAL-free. The **real-tile** half named here (≥2 real 3DEP
tiles at different latitudes) is bundled into #41's smoke harness (TG3b) and still needs a GDAL/NAS
host.)

**Phase 10.3 — Reduce docs churn**

43. [x] HANDOFF/roadmap status automation — a small script to stamp timestamps + epoch status, so
progress bookkeeping stops costing 3–4 hand-edit commits per epoch. `S`
(Shipped 2026-08-30, commit `87c64fd`. Pure stampers `src/status.py`
(`format`/`stamp_last_updated`, `tick_roadmap_item`, `stamp_epoch_status`; idempotent, GDAL-free,
tested in `tests/test_status.py` + `tests/test_update_status.py`) behind the diff-printing
`tools/update_status.py` CLI.)

Epoch gate: a single command proves determinism (double-render byte-identical) and exercises the real
warp/mosaic/cross-device paths, producing a trustworthy pass/fail without reading the code; the offline
suite is still green and the 2D default output byte-identical.

## Epoch 11 — Year-over-year historical flow (Option C)

Give the "year in motion" render a **year-over-year axis**. Today's twelve monthly frames are a
*synthetic average year* — `tools/monthly_flow.py` disaggregates NHDPlus HR's mean-annual `QAMA` using
the GDB's long-term climate *normals*, with no calendar year attached. This epoch runs the *same*
shared disaggregation (`src.monthly_flow.disaggregate_monthly`) against **real per-year monthly climate
from PRISM** (monthly record from **1895**), for a chosen year or a span of years, across California,
Washington, Oregon, Utah, and Idaho. Chosen over the NWM-retrospective and USGS-gauge routes because it
reuses the existing engine, reaches the deepest history, needs no NHDPlus-V2↔HR crosswalk, and only a
few GB of HTTP-downloadable rasters (it is honestly a model, not observed flow). Mirrors the #23/#25
precedent — promote a pure offline algorithm + option surface into `src/`, keep the heavy raster reads
in a `tools/` executor behind an injectable seam; the default synthetic-year render stays
byte-identical. Spec: `agent-os/specs/2026-08-27-year-over-year-flow/`.

**Phase 11.1 — Pure historical-flow engine**

44. [x] Historical-flow disaggregation engine — `src/historical_flow.py` (numpy-only, offline):
`PRISM_FIRST_YEAR`, `YearlyClimate`, the injectable `ClimateProvider` seam, `normalize_years`/
`year_span` validation, `yearly_flow_series` (per-year `disaggregate_monthly`), and `annual_mean_series`
/`peak_month_series` cross-year reducers; clock-free (`latest` passed in). `M`
(Done in the planning commit: 17 offline tests in `tests/test_historical_flow.py` inject a fake
`ClimateProvider` over a 3-reach chain — validation, parity with `disaggregate_monthly`, once-per-year,
reach-count mismatch, July-spike peaks in July, mass conservation. No source change to the 2D pipeline.)

**Phase 11.2 — PRISM climate ingestion (non-offline)**

45. [x] PRISM monthly climate provider — `tools/historical_flow.py`: `PrismClimateProvider` reads 12
monthly PRISM `ppt`+`tmean` grids per year and samples each catchment centroid → `YearlyClimate`, behind
the `ClimateProvider` seam so `src/` stays GDAL-free; PRISM archive NAS-staged (mount-aware) via
`tools/prism_fetch.py` like the GDBs. `L`

**Phase 11.3 — Year-over-year rendering**

46. [x] Year-over-year render mode — `tools/render_state_yoy.py` drives frames from
`src.historical_flow.yearly_flow_series` for a walk across years, with a **fixed cross-series width span**
(reuse `src.rendering.fixed_flow_span`/`widths_on_span`) so inter-year swell/drought is visible rather
than renormalized away. Proven on WA 2014–2023 (May flow 76M→211M cfs). `M`

**Phase 11.4 — Region expansion**

47. [ ] Add Utah as a supported region — `tools/derive_state_huc4.py` → UT HUC4s; wire
`SUPPORTED_REGIONS`, `datasets.REGION_HUC4`, `counties.STATE_FIPS`, and the `render_common.STATE_HUC4`
mirror; download UT NHDPlus HR GDBs. The well-trodden Idaho (#21) fourth-region path; completes the
CA/WA/OR/UT/ID cohort. `S`
    **Deferred (2026-08-30 revenue amendment):** do not start until the Epoch 11.5 revenue gate passes —
    the existing four-state scope (OR/WA/CA/ID) is enough to validate demand; region/platform expansion
    is gated on revenue, not features.

Epoch gate: a render shows the same network's monthly flow for a chosen historical calendar year (and
can step across years) driven by real PRISM climate for CA/WA/OR/UT/ID, back to a documented start year;
the default synthetic-year render stays byte-identical.

## Epoch 11.5 — Revenue Validation (gated commercial track)

**Sequencing correction, not a technical epoch** (2026-08-30, informed by the initial market review —
`agent-os/product/revenue-validation-amendment.md`). A time-boxed (4–6 week) commercial experiment that
proves a buyer will pay **before** the product surface expands. The current 2D art pipeline
(OR/WA/CA/ID, `--county` scope, editable SVG + print-ready PDF/PNG) is already capable enough to test
demand — **no new rendering capability is required**, so this adds no `src/` code and touches no
`PIPELINE_STAGES`. It is **not a prerequisite** for any other epoch and may run in parallel with technical
work; it *is* the gate that unlocks further commercialization (catalog/POD, self-serve, Utah #47, any
Epoch 12 productization). Sells only **public-domain-sourced** art (USGS NHDPlus HR / NHD / WBD) — **no
PRISM-derived assets** (see the Rights gate in Notes). Outcome is first revenue, not a storefront.

56. [ ] Narrow made-to-order listing — publish an Etsy (or equivalent) made-to-order listing for a
**personalized county watershed print** in the supported geography (OR/WA/CA/ID). Deliver a print-ready
PDF/PNG in 24–48 h; editable SVG + commercial license are paid add-ons. Sell a service, not a platform. `S`
57. [ ] Repeatable fulfillment pack — a customer intake form, two approved art directions, title/subtitle
rules, an export checklist, the source-credit/attribution line, and a proof/approval template. An
operating recipe, not a new pipeline. `S`
58. [ ] Instrument the test — track listing views, favorites, inquiries, paid orders, fulfillment time,
refund rate, requested locations/styles, and net revenue after marketplace fees in
`agent-os/product/revenue-ledger.md`, plus a monthly decision note in the same directory. `XS`
59. [ ] Revenue gate — proceed to catalog/POD and self-serve **only** after **≥ 8 paid orders or $500
gross within 60 days**, with median fulfillment **< 45 min**. Otherwise interview 10 non-buyers, revise
the visual/offer, and run one further test; do **not** build subscriptions. `XS`

Status (2026-08-30): the **reproducible-fulfillment code core** of #57 landed — `src/fulfillment.py`
(order validation, Rights gate, deterministic deliverable plan + provenance manifest; 29 offline tests)
+ the non-offline `tools/fulfill_order.py` executor, spec
`agent-os/specs/2026-08-30-order-fulfillment/`. #56/#57 stay `[ ]`: the actual marketplace listing,
customer intake form, and funnel/ops tracking are operational work in
`agent-os/product/revenue-ledger.md`, not code.

Epoch gate: first paid orders are observed and measured against #59. If the gate passes, unlock
catalog/POD, Utah (#47), and Epoch 12 commercialization; if it fails, iterate the offer per #59 — do not
expand the product surface on marketplace impressions alone.

## Epoch 12 — Watershed report analytics

Turn the one-off `notebooks/salmon_creek_yoy.ipynb` (real PRISM year-over-year flow for a HUC12 group)
into a **reusable, credible watershed report** for any watershed in the CA/WA/OR/ID(/UT) cohort. Today
the notebook answers one question — "how does the seasonal peak shift 2014–2023?" — on 10 uncalibrated
data points. This epoch adds analytical depth and, critically, **credibility**: a deeper temporal
record, an honest model-vs-gauge validation, climate-driver attribution, and spatial decomposition —
plus a parametrized report builder and a web report view. Mirrors the #23/#25/#44 precedent: **promote
the pure statistics into offline, numpy-only `src/` modules; keep the heavy external reads (PRISM
back-catalog, USGS NWIS, ENSO index) in `tools/` executors behind injectable provider seams.** The 2D
pipeline and its byte-identical default output are untouched (these modules are not in `PIPELINE_STAGES`).
Spec: `agent-os/specs/2026-08-30-watershed-report-analytics/`.

**Commercialization gate (2026-08-30 revenue amendment):** treat Epoch 12 as **research / product
discovery, not near-term revenue**. The model-vs-gauge validation (#50) is essential *credibility* work,
but sell a watershed report only after the Epoch 11.5 revenue gate passes **and** buyer-discovery
interviews with watershed organizations, land trusts, or consultancies confirm willingness to pay.
**Rights gate:** the report and every year-over-year animation derive from PRISM climate data, whose terms
require an arrangement with the PRISM Climate Group for sale or other commercial use — do **not** sell any
PRISM-derived report or animation until written permission/licensing is documented or the PRISM dependency
is replaced (see Notes).

**Phase 12.1 — Offline hydrograph-metrics engine**

48. [x] Hydrograph-metrics engine — `src/flow_metrics.py` (pure, numpy-only, offline): per-year
peak / low-flow (summer-minimum) series, center-of-timing (month of 50% cumulative flow), Richards-Baker
flashiness, wet/dry seasonal ratio, and monthly flow-duration percentiles over the
`{year: [n,12]}` series `yearly_flow_series` already produces. `M`
49. [x] Trend, percentile & rolling-normal statistics — extend `src/flow_metrics.py` with
Mann-Kendall + Sen's-slope robust trend, a value's percentile rank against the record, anomaly-vs-normal,
and sliding 30-year normals — the rigor that makes a *deep* record meaningful (replaces the notebook's
OLS-on-10-points). `S`

**Phase 12.2 — Validation & climate signals (credibility)**

50. [x] Model-vs-gauge validation — `src/flow_metrics.py` (pure, offline comparison metrics: bias,
Pearson r, Nash-Sutcliffe efficiency, RMSE, per-month seasonal skill; missing months skipped never
zero-filled, mirroring `src/accuracy.py`) + a `tools/nwis_gauge.py` `GaugeProvider` (USGS NWIS monthly
means, NAS-staged/snapshotted for reproducibility) behind the seam. Turns the "model, not gauge" caveat
into an honest validation plot. `L`
51. [x] Climate-index teleconnection — offline `align_index`/`correlate` helpers (join a per-year flow
metric to a per-year climate index on common years, Pearson + optional lag) in `src/flow_metrics.py`
+ a tiny `tools/climate_index.py` fetch (ENSO ONI / PDO public tables, snapshotted). Answers *why* wet
and dry years happen. `S`

**Phase 12.3 — Deep temporal record**

52. [x] PRISM back-catalog extension — stage PRISM `ppt`+`tmean` for the **full 1895–present record**
(reuses `tools/prism_fetch.py` + `PrismClimateProvider`, no engine change; a `--start/--end` span), so every
temporal metric runs on the complete ~130-year record instead of 10. Non-offline fetch; NAS-staged,
mount-aware, resumable. `M`

**Phase 12.4 — Spatial decomposition**

53. [x] Sub-watershed & longitudinal decomposition — offline `src/flow_metrics.py` helpers: subset a
series by reach-index membership (per-HUC12 hydrographs, e.g. Upper vs Lower Salmon Creek), pick the
outlet (max-accumulated) reach, and build a longitudinal flow-accumulation profile down the mainstem
over the topology. `M`

**Phase 12.5 — Report assembly & UX**

54. [x] Parametrized watershed-report builder — `tools/report_common.py` (shared data-loading + the
matplotlib plotting recipe, mirroring `render_common.py` so notebook and tool never drift) +
`tools/build_watershed_report.py` (any HUC12 group → the full figure set), and refactor
`notebooks/salmon_creek_yoy.ipynb` to consume it. Includes the ecological (salmon low-flow × stream-temp)
framing. `L`

Epoch gate: from a single watershed selection, a reproducible report (CLI builder + notebook) shows a
multi-decade flow record with robust trend statistics, an honest model-vs-gauge validation verdict, a
climate-driver correlation, and sub-watershed/longitudinal structure — all from offline-tested `src/`
statistics fed by snapshotted external data; the 2D pipeline and its byte-for-byte default output are
unchanged.

## Epoch 13 — Web watershed-report view

Surface the Epoch 12 watershed report on the web, over the shared `web/shared/ux.css` +
`web/shared/hydro-ux.js` foundation — no per-page duplication (honors the Epoch 9 anti-drift rule). Split
out of Epoch 12 so the offline analytics/validation core (a research/credibility deliverable) ships
independently of the view layer. Same commercialization + PRISM rights gates as Epoch 12 apply.
Spec: `agent-os/specs/2026-08-30-watershed-report-analytics/`.

55. [x] Web report mode (proposed UX) — a report view over the shared `web/shared/ux.css` +
`web/shared/hydro-ux.js` foundation: metric tiles (peak / summer-low / center-of-timing / percentile),
a model-vs-gauge validation badge, a long-record trend sparkline, and an ENSO-overlay toggle. New shared
CSS components live in `ux.css`; report data/formatting helpers live in `hydro-ux.js` — no per-page
duplication (honors the Epoch 9 anti-drift rule). `M`

Epoch gate: the watershed report from Epoch 12 renders as a shareable web view built entirely on the
shared UX foundation (no duplicated option data, mapping, or view logic), carrying the honest
validation verdict and climate-driver overlay; `src/` and the offline suite stay free of any `web/`
dependency.

## Epoch 14 — License-free climate source (retire the PRISM rights gate)

The year-over-year animation (Epochs 10–11, #45/#46) and the watershed reports (Epoch 12, #52) are the
project's most striking output but are **commercially blocked**: PRISM data is not public domain — sale
of any PRISM-derived asset requires a written arrangement with the PRISM Climate Group (the Rights gate
below). PRISM's own terms state *"commercial use is strictly prohibited unless you have made special
arrangements in advance"* and prohibit redistribution even on the paid 800 m tier; the free 4 km tier
this project uses (`tools/prism_fetch.py`, the NACSE web service) carries the same commercial
prohibition, and a commercial arrangement is an unpriced custom quote. Rather than pay/negotiate, swap
the climate dependency for a **U.S.-government / free-for-any-use gridded alternative** — **NOAA
nClimGrid** (5 km monthly temp+precip, CONUS, federal public domain — the direct PRISM equivalent) is
the cleanest drop-in; **gridMET** (Univ. of Idaho, 4 km daily, free for commercial use) and **Daymet**
(ORNL/NASA, 1 km daily) are fallbacks. This unlocks the animated premium tier for **$0 licensing** and
**removes the PRISM rights gate entirely**. Mirrors the #45 precedent: the climate source is already an
injectable `ClimateProvider` seam (`src/historical_flow.py`), so only a new `tools/` provider impl
changes — the offline `yearly_flow_series` engine and every downstream render stay untouched and
byte-identical.

60. [x] Public-domain climate provider — a new `tools/` `ClimateProvider` implementation (sibling to
`tools/historical_flow.PrismClimateProvider`) that samples **NOAA nClimGrid** monthly `tmean`+`ppt` at
each catchment centroid → `YearlyClimate`, wired into `render_state_yoy.py` / the report builder behind
the existing `src.historical_flow.ClimateProvider` seam. Includes a `tools/` fetch/stage script (the
nClimGrid counterpart to `prism_fetch.py`) and honest nodata handling (ocean → precip 0 / temp fallback,
matching `monthly_flow.py`). The offline `src/` engine and default synthetic-year render stay
byte-identical (no `src/` change beyond docs); once landed, **retire the PRISM Rights gate** in the Notes
below (nClimGrid is federal public domain — free to sell with attribution). `M`

## Epoch 15 — Natural water features beyond waterbodies · proposed

Extend the water-only art vocabulary past lake/pond/reservoir/bay/inlet *outlines* (Epoch 1.5) to
the **other natural water features USGS already ships in the same GDBs**: springs/seeps, waterfalls
and rapids, wetlands (marsh/swamp), playas, and perennial ice (glacier/snowfield). These are native
`FType`-coded features in NHD `NHDPoint` / `NHDArea` (and `NHDFlowline` for falls/rapids on the
network), so this needs **no new data source and no new rights gate** — USGS NHD is federal public
domain, sellable with attribution, exactly like today's flowlines and waterbodies. Deliberately
**water-only**: no roads, no political basemap. Mirrors the Epoch 1.5 waterbody template beat for
beat — versioned taxonomy → repair/reproject/clip/select → dedicated fill-free/point SVG layers →
QA + screen/print presets — and integrates **additively** into `PIPELINE_STAGES` (loaded in
`validate`, selected in `generate_svg`) so a build stays byte-identical when the features are
disabled (the default).

**Phase 15.1 — Point water-feature ingestion & taxonomy**

61. [ ] Point-feature source layers and classification — Load NHD `NHDPoint` (and any `NHDArea`
point-like) features and define a reviewed, versioned inclusion taxonomy (spring/seep, waterfall,
rapids, sinkhole/spring-fed, well) the way `src/waterbodies.py` did for polygons: FType-driven,
name only refining, missing FType → excluded/never guessed. Add a `NHDPoint` allowlist + attribute
fields to `src/loading.py` and a `load_point_features` loader seam mirroring `load_waterbody_layers`.
`M`

**Phase 15.2 — Areal natural features (wetlands, playas, ice)**

62. [ ] Wetland / playa / perennial-ice ingestion, selection & clipping — Classify and select
`NHDArea` (or optional NWI) marsh/swamp, playa, inundation-area, and glacier/snowfield polygons;
repair → reproject(EPSG:5070) → region-clip → area-select with configurable thresholds, reusing
`src/geometry` + `src/clipping` and the `WaterbodySelectionPolicy` pattern (holes + multipart
preserved, provenance retained). `L`

**Phase 15.3 — Point-glyph & areal rendering**

63. [ ] Water-feature rendering — Extend `src/rendering.py` with (a) a point-glyph layer (stable
ids, configurable marker/size/color, e.g. spring dots, waterfall chevrons) and (b) a distinct
areal treatment for wetlands/ice (hatch or low-opacity fill vs. the fill-free waterbody outlines),
each as its own `<g>` with configurable z-order so flowlines and waterbodies stay legible at
overlaps. `M`

**Phase 15.4 — QA & art direction**

64. [ ] Feature QA and presets — Validate fixture and real Oregon/Washington output (point
placement, wetland holes/multipolygons, coastal/boundary clipping, duplicate suppression, density
thresholds); add `screen` / `print-state` / `print-county` preset entries alongside the waterbody
presets so tiny features don't clutter at small scale. `M`

Epoch gate: a build can render source-traceable springs, waterfalls/rapids, wetlands, playas, and
perennial ice as dedicated, editable, water-only layers over the existing flowline + waterbody art,
with screen/print presets controlling density; the default (features disabled) output stays
byte-for-byte identical.

## Epoch 16 — Hydro-infrastructure layers · proposed

Add the **engineered water infrastructure NHD already encodes** — dams/weirs, gates, lock chambers,
spillways, gaging stations, and water intakes/outflows (`NHDPoint` / `NHDLine` / `NHDArea` FTypes),
plus canals/ditches, aqueducts, and pipelines distinguished from natural channels on the
`NHDFlowline` network (FType `CanalDitch` / `Pipeline` / `ArtificialPath`). Still strictly
**water-related** and still **USGS public domain** (sellable, no new rights gate). Reuses the
point/line/area rendering seams built in Epoch 15, so this epoch is mostly taxonomy + symbology +
network styling. This is the layer that turns the art into a story about *how people use the water*
— dams, diversions, and gauges on the network — without importing any non-hydro basemap.

**Phase 16.1 — Structure ingestion & taxonomy**

65. [x] Hydro-structure source layers and classification — Load and classify engineered-water
FTypes across `NHDLine` (dam/weir, gate, lock chamber), `NHDPoint` (gaging station, dam/weir, water
intake/outflow), and `NHDArea` (canal/ditch, lock chamber, spillway, reservoir-as-structure) into a
versioned `HYDRO_STRUCTURE_POLICY_VERSION` taxonomy; extend the `src/loading.py` allowlists +
attribute fields. `M`
(Shipped 2026-09-03. `src/hydro_structures.py` — versioned FType-driven taxonomy
(`dam_weir`/`gate`/`lock_chamber`/`gaging_station`/`water_intake_outflow`/`spillway`/`canal_ditch`/
`excluded`), mirroring `src/point_features.py` (name-only-refining, missing FType → `excluded` +
`missing_ftype`, full provenance, no geometry math, no top-level GDAL). One table serves all three
source layers. Codes domain-verified against real GDB 1807 (343/336/455/485/367 confirmed; 369
line/area + 398 lock_chamber flagged UNCONFIRMED, standard NHD codes); `436 Reservoir` stays a
waterbody (documented policy note). `src/loading.py` gains the NHDLine seam (`LINE_LAYER_ALLOWLIST`,
`LINE_ATTRIBUTE_FIELDS`, `discover_line_layers`, `load_line_features`); NHDPoint/NHDArea already load
via the Epoch 15/1.5 seams. Complementarity tested (structure codes disjoint from waterbody/point/
areal included codes). Spec `agent-os/specs/2026-09-03-hydro-structure-taxonomy/`; 761 offline tests
green, default build byte-identical (verify_determinism `--region Oregon`), no GDAL leakage.
**Follow-ons (#66/#67/#68):** flowline canal/pipeline styling, structure symbology + selection/render,
QA/presets/CLI. This item is taxonomy + loader only — no rendering, no pipeline wiring, byte-identical.)

**Phase 16.2 — Engineered channels on the network**

66. [ ] Canal / ditch / aqueduct / pipeline styling — Flag `NHDFlowline` engineered FTypes
(`CanalDitch`, `Pipeline`, `ArtificialPath`, `Connector`, `UndergroundConduit`) so they can be
styled distinctly from natural streams (e.g. dashed/second color) or optionally excluded — a
config-driven split of the existing flowline layer, deterministic and byte-identical when off. `M`

**Phase 16.3 — Infrastructure symbology & rendering**

67. [x] Infrastructure rendering — Symbol set for structures: dam/weir line symbols, gaging-station
and intake point markers, spillway/lock areal treatment; dedicated `<g>` layers with z-order above
water so a dam reads on the channel it crosses. Reuses the Epoch 15 point-glyph seam. `M`
(Shipped 2026-09-03. Makes #65's classified structures visible, disabled by default. New
`src/hydro_structure_selection.py` (`process_hydro_structures`: repair→reproject→clip→geometry-type
select — polygon `min_area_m2`, point `min_spacing_m` thinning, line clip-only), mirroring
`src/areal_selection.py`. `src/config.py` gains frozen `HydroStructureSettings` (disabled default) +
`HYDRO_STRUCTURE_PRESETS` (`screen`/`print-state`/`print-county`). `src/rendering.py` gains
`HYDRO_STRUCTURE_GLYPHS`/`DEFAULT_HYDRO_STRUCTURE_STYLES`/`_hydro_structure_lines` (point glyph / line
bar / areal path) + keyword-only `hydro_structures`/`hydro_structure_order="above"` on `render_svg`
(None → no markup). `src/pipeline.py` adds the additive NHDLine load (`line_layers`), widens the
shared NHDPoint/NHDArea load gates, and wires `_select_hydro_structures`. Complementarity keeps each
geometry drawn under exactly one taxonomy. Spec `agent-os/specs/2026-09-03-infrastructure-rendering/`;
780 offline tests green, default build byte-identical (`verify_determinism --region Oregon`, svg
sha `e6b9bd6cfaf7…`, 0 structures on default path), no GDAL leakage. Follow-on #68: real-data QA +
preset tuning.)

**Phase 16.4 — QA & presets**

68. [x] Infrastructure QA and presets — Fixture + real Oregon/Washington/Clark County validation
(structure-on-network placement, duplicate suppression, canal/natural separation) and screen/print
presets tuned so infrastructure enriches rather than clutters. `M`
**Shipped (2026-09-04):** pure/offline `src/hydro_structure_qa.py` (network placement, cross-layer
dedup, coincidence-fraction separation) + `tools/hydro_structure_qa.py` real-data cross-check;
`render_state_allfeatures --structures` overlay; tuned `HYDRO_STRUCTURE_PRESETS`
(screen/print-county/print-state monotonic thinning). Real HUC4 1807: 557 structures, 553/557
on-network (median 3.0 m), 1 duplicate group, 77 genuine coincidences. Full suite 790 green;
default byte-identical (sha `e6b9bd6cfaf7…`, 0 structures on default). **Closes Epoch 16.**

Epoch gate: a build can overlay source-traceable dams, weirs, locks, gaging stations, intakes, and
distinctly-styled engineered channels on the water art, controllable by preset, with the default
(infrastructure disabled) output byte-for-byte identical.

## Epoch 17 — Watershed report: creative analytics · complete

Deepen the Epoch 12 watershed report from its current seven figures into a richer, more *engaging*
story, drawing almost entirely on **statistics the engine already computes** (`src/flow_metrics.py`)
and data already staged (`{year:[n,12]}` monthly flow back to 1895, USGS gauges, ONI/PDO indices).
Mirrors the Epoch 12 precedent exactly: **promote pure, numpy-only stats into `src/`, keep heavy
external reads in `tools/` behind provider seams, add figures via `tools/report_common.py`, and
surface them in `web/report.html`** — none of it in `PIPELINE_STAGES`; the 2D pipeline's
byte-identical default output is untouched. Same commercialization + climate rights posture as
Epoch 12/14: the default `--climate-source nclimgrid` path is public-domain and sellable with
attribution; PRISM stays A/B-only and non-sellable.

**Phase 17.1 — Regime & timing signals**

69. [x] Snow-vs-rain regime signature — Surface the snow bucket the disaggregation already models
(`src/monthly_flow.snow_available_water`) as a returned diagnostic (new pure function, no change to
existing outputs) and classify each watershed snowmelt-dominated / rain-dominated / transitional,
with melt-pulse timing shift across decades. The "your river is becoming a rain river" story. `M`
(Shipped 2026-09-07. `src/monthly_flow.snow_available_components(precip,temp) → (rain,melt)` exposes
the two buckets; `snow_available_water` now returns their sum — byte-identical (existing snow test
unchanged). `src/flow_metrics.py` gains numpy-only `snow_fraction`, `classify_regime`
(`REGIME_SNOW_MIN=0.4`/`REGIME_RAIN_MAX=0.2`), `SnowRegime`+`snow_regime` (fraction/label/melt
center-of-timing), and `MeltTimingTrend`+`melt_timing_trend` (Sen's slope + Mann-Kendall on per-year
melt CT → months/year and days/decade; negative = pulse arriving earlier). No `monthly_flow` import
in `flow_metrics` (callers pass arrays). Spec `agent-os/specs/2026-09-07-creative-report-analytics/`.
Suite 861 passing; no `PIPELINE_STAGES` touched (2D byte-identical). Follow-ons #70–#76.)
70. [x] Center-of-timing drift as a hero metric — Promote the existing `center_of_timing()` into a
dedicated trend panel (Mann-Kendall + Sen's slope on CT itself): "the peak arrives N days earlier
per decade," one of the most legible western-hydrology climate signals. `S`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `TimingTrend` + `center_of_timing_trend(yearly_flow,
years=None)` — per-year whole-hydrograph center-of-timing → Sen's slope (months/yr) + Mann-Kendall
verdict → `days_per_decade` (negative = peak arriving earlier). Accepts a `{year:[12]}` mapping or
`[years,12]` matrix. Shares the extracted `_coerce_year_rows` helper with #69's `melt_timing_trend`,
which now delegates to it (`MeltTimingTrend` API unchanged). Numpy-only, no pipeline wiring. Suite
865 passing; 2D default byte-identical. Follow-ons #71–#76.)

**Phase 17.2 — Records & distribution**

71. [x] Analog-year finder — Rank the most-similar historical years to any target year via
`correlate()`/`pearson_r()` over monthly-shape vectors ("2015 looked most like 1934") — a
personal, engaging hook for a buyer's own watershed. `S`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `AnalogYear` + `analog_years(series, target,
n=None)` — ranks every year in a `{year:[12]}` series by Pearson correlation of its 12-month vector
to the target's (reuses `pearson_r`; mean/scale-invariant, so same seasonal *shape* matches even at
different magnitude). Constant year → `nan`, sorts last; ties break by ascending year (deterministic);
`n` keeps the top matches. Numpy-only, no pipeline wiring. Suite 869 passing; 2D default byte-identical.
Follow-ons #72–#76.)
72. [x] Drought / flood record book — Rank years by summer-low and by peak using `percentile_rank()`
("driest summer in 130 years," "top-5 wettest") over the full 1895– record. `S`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `YearRank`/`RecordBook` + `rank_years(metric_by_year,
ascending, n)` (1-based rank + `percentile_rank` position, deterministic year tie-break) and
`record_book(series, summer_months=(6,7,8), n=5)` — reduces a `{year:[12]}` series to summer-low
(ascending → driest) and annual-peak (descending → wettest) leaderboards. Numpy-only, no pipeline
wiring. Suite 874 passing; 2D default byte-identical. Follow-ons #73–#76.)
73. [x] Flow-duration-curve panel — Plot the already-computed `flow_duration()` as a log-scale FDC
with decade overlays, showing how the whole distribution shifts, not just the mean. `S`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `DecadeFDC` + `decade_flow_duration(series,
quantiles, decade_size=10)` — buckets a `{year:[12]}` series into decades, pools each decade's
monthly flows, and computes the exceedance curve via `flow_duration`; returns one `DecadeFDC` per
decade (ascending) so overlays show the distribution shifting. Log-scale plotting itself lands with
the #76 web/tools panel. Numpy-only, no pipeline wiring. Suite 877 passing; 2D default byte-identical.
Follow-ons #74–#76.)

**Phase 17.3 — Climate framing**

74. [x] ENSO / PDO composite hydrographs — Using the per-year ONI/PDO series already fetched, overlay
the mean El Niño-year vs La Niña-year hydrograph ("here's what your river does in each phase") —
more actionable than a single correlation coefficient. `S`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `PhaseComposite` + `composite_hydrographs(series,
index_by_year, warm_min=0.5, cool_max=-0.5)` — splits the years common to the `{year:[12]}` flow
series and the climate index into warm/neutral/cool phases (standard ONI ±0.5; reusable for PDO by
sign) and averages the 12-month hydrograph within each (`None` when a phase is empty), plus the member
years per phase. Numpy-only, no pipeline wiring. Suite 880 passing; 2D default byte-identical.
Follow-ons #75–#76.)

**Phase 17.4 — Longitudinal story**

75. [x] Longitudinal flow-accumulation animation — Animate `longitudinal_profile()` walking
accumulated flow down the mainstem — a direct visual bridge between the *art* and the *data*. `M`
(Shipped 2026-09-07. `src/flow_metrics.py` gains `ProfileFrame` + `longitudinal_frames(accum_flow,
hydroseq, dnhydroseq, path)` — builds the profile via `longitudinal_profile` (same validation) then
emits one reveal frame per path position: `revealed` is the headwater→reach polyline, `fraction` is
accumulated flow as a share of the mouth's (`0..1`, monotone; `0` when the mouth carries no flow).
The GIF rendering itself lands with the #76 `tools/` animation renderer. Numpy-only, no pipeline
wiring. Suite 884 passing; 2D default byte-identical. Follow-on #76 (assembly & web).)

**Phase 17.5 — Assembly & web surfacing**

76. [x] Report assembly & web view — Fold the new panels into `tools/report_common.py` +
`tools/build_watershed_report.py` (figures to `notebooks/figures/`) and surface the new metrics/
toggles in `web/report.html` on the shared `web/shared/*` foundation (no per-page duplication,
honoring the Epoch 9 anti-drift rule). `M`
(Done 2026-09-07 — `tools/report_common.py` gains five figures over the outlet `{year:[12]}` series,
each driving an already-tested `src.flow_metrics` function: `fig_timing_drift` (#70 CT drift),
`fig_analog_years` (#71), `fig_record_book` (#72), `fig_decade_fdc` (#73 log-scale decade overlays),
`fig_composites` (#74); wired into `build_report` behind a `creative` flag + `--no-creative` CLI
toggle. `web/report.html` surfaces regime / analog-years / record-book / decade-FDC / composites
panels over the shared `web/shared/hydro-ux.js` foundation; two new pure helpers there
(`classifyRegime`, `centerOfTimingIndex`) mirror the Python thresholds and are node-tested
(`tests/test_report_web.cjs`, +5). #69 snow-regime needs precip/temp and #75 longitudinal needs
network topology — those stay in the render tools; the web report shows the regime as a synthetic
mock badge. Python suite 884 passing (no `src/` change); node 5+11 green; no `PIPELINE_STAGES` touched
→ 2D default byte-identical. **Epoch 17 complete.**)

Epoch gate: from a single watershed selection, the report additionally shows a snow-vs-rain regime
verdict, a center-of-timing drift trend, an analog-year match, a drought/flood record book, a
flow-duration curve, ENSO/PDO composite hydrographs, and a longitudinal flow animation — all from
offline-tested `src/` statistics fed by already-staged data, surfaced in the shared web report; the
2D pipeline and its byte-for-byte default output are unchanged.

## Epoch 18 — Scale-aware flow-width presets · complete

Turn the flow→width mapping from a set of raw numeric knobs (`width_min`/`width_max`/`width_gamma`)
into **named, scale-appropriate presets** the way Epoch 1.5 did for waterbodies. The insight is that
one width mapping cannot serve every extent: discharge spans ~5 orders of magnitude across a whole
state (a Cascade trickle → the Columbia), so a **logarithmic** mapping is the only thing that keeps
headwaters visible next to the trunk; but for a single basin or watershed the dynamic range is small
enough that a **power-law** mapping (`w ∝ Qᵇ`) reads as both legible *and* geomorphologically honest
— real rivers obey downstream hydraulic geometry `w ∝ Q^0.5` (Leopold & Maddock). This epoch encodes
three presets — `state` (log, ~10:1), `basin` (`Q^0.45`), `watershed` (`√Q`) — plus **exposes the
`scaled_widths` `log` knob** that `Settings` currently hides. It reuses the existing `width_by=flow`
seam and `WATERBODY_PRESETS`/`_coerce_waterbodies` template exactly; it adds no new render behavior,
stays fully offline-tested, and is **byte-for-byte identical when no preset is named** (default
`width_by=uniform`, `width_log=False`).

**Phase 18.1 — Expose the log knob & preset table**

77. [x] `width_log` setting + `WIDTH_PRESETS` — Add a validated `width_log: bool` field to `Settings`
(default `False`, wired through `_resolve_stroke_widths` into `scaled_widths(log=...)`) and a
`WIDTH_PRESETS` table (`state`/`basin`/`watershed`) + `SUPPORTED_WIDTH_PRESETS` allowlist, mirroring
`WATERBODY_PRESETS`. Each preset bundles `width_by`/`width_min`/`width_max`/`width_gamma`/`width_log`.
Fail-fast `ConfigError` validation; preset expansion (`defaults < preset < explicit`) happens at
config time and is not stored on frozen `Settings`, so a no-preset build stays byte-identical. `S`
(Verified complete during Epoch 17 close-out 2026-09-07 — `src/config.py` carries the `WIDTH_PRESETS`
table, `SUPPORTED_WIDTH_PRESETS` allowlist, `width_log` field, and `width_preset` config directive;
spec `agent-os/specs/2026-09-01-scale-aware-flow-widths/`. Roadmap checkbox reconciled — was stale.)

**Phase 18.2 — CLI surface**

78. [x] `--width-preset` flag — Add `--width-preset {state,basin,watershed}` to `src/cli.py` with the
usual precedence (`defaults < config.yaml < CLI`; unset argparse flag defaults to `None` so YAML is
never clobbered), mirroring the waterbody-preset flag wiring. `XS`
(Verified complete 2026-09-07 — `src/cli.py` wires `--width-preset` and `--width-log`; 22 width/preset
tests in `tests/test_config.py`/`test_cli.py`/`test_pipeline.py` pass. Roadmap checkbox reconciled.)

Epoch gate: a build can select `state` / `basin` / `watershed` flow-width presets (via config or
`--width-preset`) that shape the flow→width ramp appropriately for the extent — including the
newly-exposed logarithmic mapping — with fail-fast validation; the default (no preset,
`width_by=uniform`) output stays byte-for-byte identical.

---

# Generation 1 — Production Release

Epochs 1–18 built a feature-complete engine: a deterministic 2D pipeline plus parallel
elevation/3D, flow, report, and fulfillment subsystems, and four kinds of deliverable. Generation 1
does **not** add art features — it hardens what exists into a documented, fully tested, reproducible
**version 1.0** with four stable customer endpoints, a complete test pyramid (unit → integration →
end-to-end), one flagship end-to-end proof that walks a single region to **all four** endpoints, a
rights-clean high-resolution marketing gallery, and a tagged release behind a reproducibility gate.

The **four production endpoints** this generation stabilizes and proves:

| Endpoint | Deliverable | Current entry point |
| --- | --- | --- |
| Digital image | Layered SVG + PNG | `build.py` (2D pipeline) |
| Animation | Year-in-motion GIF/MP4 | `tools/render_monthly.py` · `tools/render_state_yoy.py` |
| Print image | Archival print raster over relief | `tools/render_terrain_print.py` |
| Report | Watershed analytics report | `tools/build_watershed_report.py` |

Discipline constraints carried forward: the **offline suite stays fully offline** (no GDAL/network),
so the in-suite e2e test drives the endpoint orchestrators with injected fakes, while the *real-artifact*
e2e proof is an **opt-in `tools/` harness** (like `verify_determinism.py`) requiring GDAL + staged
data. Default 2D output stays **byte-for-byte identical**. Only **public-domain** sources ship in any
marketing asset (Rights gate).

## Epoch 19 — Production endpoint contracts & hardening · complete

Give each of the four endpoints a documented, versioned **output contract** and a single stable entry
point, so the test pyramid and the flagship e2e have something concrete to assert against. Reuses the
`src/fulfillment` request→deliverable seam rather than duplicating renderer recipes.

79. [x] Endpoint output contracts — Define and document, for each endpoint, the artifact contract:
file types, naming, a sidecar provenance/manifest (source version, attribution, checksum), and the
success/failure signals. Encode as pure/offline dataclasses + validators mirroring `src/fulfillment`. `M`
80. [x] Endpoint dispatch consolidation — A thin, documented dispatcher mapping a validated request →
the correct renderer per endpoint (extend `src/fulfillment.build_order` / a `tools/` orchestrator), with
**no duplicated recipe logic** (extend `render_common.py`). `M`
81. [x] Provenance & failure-mode hardening — Every endpoint stamps source version + attribution +
checksum and fails fast under the `ConfigError`/`AcquisitionError` taxonomy; the Rights gate
(`assert_sellable`) runs before any asset is marked deliverable. `S`

Epoch gate: each endpoint produces a documented, provenance-stamped artifact from one validated
request; default 2D output stays byte-identical.

## Epoch 20 — Unit & integration test completion · complete

Close the base of the pyramid. Coverage-audit every `src/` module, fill unit gaps, and add offline
integration tests that drive each endpoint orchestrator end-of-path with injected fakes.

82. [x] Unit-coverage audit & gap closure — Measure per-module coverage; add offline unit tests for any
`src/` module below the agreed threshold; keep GDAL/network out of the suite. `M`
83. [x] Endpoint integration tests (offline) — For each of the four endpoints, an offline integration
test that drives its orchestrator through the full code path to an asserted output contract, using
injected fakes + hand-built shapely/graph inputs. `M`
84. [x] Coverage gate & reporting — Wire a coverage measurement into the suite run (report-only first,
then an enforced threshold) so regressions in coverage are visible. `S`

Epoch gate: the offline suite covers every `src/` module and all four endpoint orchestrators to the
agreed threshold; default output byte-identical.

## Epoch 21 — Flagship end-to-end proof (all four endpoints) · complete

The headline deliverable: **one path, one region, all four endpoints.** Two layers respect the offline
discipline — an in-suite orchestration test with fakes, and an opt-in real-artifact harness.

85. [x] Offline all-endpoints e2e orchestration test — One in-suite test that walks a single
settings/request object through the digital-image, animation, print-image, and report code paths with
injected fakes, asserting each endpoint's contract **and** determinism. `M`
86. [x] Real-data e2e harness (opt-in, outside the suite) — A `tools/` command that takes one small
public-domain county and produces **all four** real artifacts (SVG+PNG, GIF/MP4, print raster, report)
plus a combined provenance manifest and a double-render determinism check. `L`
87. [x] E2E golden fixture — Commit the small region's expected artifact hashes/manifest as a golden
fixture (extends `tests/fixtures/golden/`) so the e2e path is regression-guarded. `S`

Epoch gate: `tools/<e2e>.py --county <small>` produces all four deliverables with provenance and passes
a determinism re-render; the offline orchestration e2e is green in the suite.

## Epoch 22 — High-resolution marketing gallery · complete

Curated, rights-clean, high-resolution examples per style/endpoint for the website — the visual proof
of the engine's range. Public-domain sources only.

88. [x] Curated style matrix — Select regions × styles × endpoints that show the range (neon basin,
elevation mono, year-in-motion, terrain print, watershed report); record the selection + rationale. `S`
89. [x] High-res render & export — Render each at marketing/print resolution; export web-optimized and
full-resolution variants; all from public-domain sources. `M`
90. [x] Gallery provenance & rights ledger — A per-asset ledger (source version, attribution, checksum,
sellable flag) via the Rights gate; wire the gallery into the marketing web surface (`web/` foundation). `S`

Epoch gate: a rights-clean, high-res marketing gallery covering all four endpoints is published on the
web surface, each asset traceable to a public-domain source.

## Epoch 23 — Release packaging, CI & reproducibility gate · complete

Turn "green suite + artifacts" into a tagged, reproducible **v1.0**.

91. [x] CI for the full test pyramid — Run offline unit+integration+e2e on every change; run the opt-in
real-data e2e + determinism as a scheduled/gated job. `M`
92. [x] Reproducibility release gate — Block the release tag unless double-render is byte-identical and
golden fixtures match (extends `tools/verify_determinism.py`). `S`
93. [x] Version, changelog & distribution packaging — Tag `v1.0`, generate a changelog from the epoch
history, and package the CLI + docs for distribution. `M`

Epoch gate: `v1.0` is tagged only when the full pyramid is green, determinism holds, and the marketing
gallery + docs ship — a reproducible Generation 1 production release.

## Epoch 24 — Alpha customer-journey end-to-end tests (browser, low-res proofs) · proposed

Prove the **alpha customer site works end to end in a real browser.** The landing page
(`web/start.html`, served at the alpha URL) fans out to the four catalog pages — poster
(`proto-b-guided.html`), watershed report (`report.html`), digital image (`studio.html`), and
year-in-motion animation (`proto-c-canvas.html`). A scripted **Playwright** harness walks that whole
journey against a **live `serve.py`** (the real `Pipeline` + `JobRunner` behind `/api/render`),
producing a **low-resolution proof** for each of the four endpoints so the suite runs fast enough to
use during design iteration. This is a **non-offline, opt-in harness** (needs the GIS stack + a
pre-extracted small county, like the Clark County, WA the landing already showcases) that lives
outside the Python offline suite — the same posture as the Epoch 21 real-data e2e harness. The only
change that enters the offline suite is a small **draft `png_size` tier** so proofs render quickly.

94. [x] Draft render tier (offline-suite change) — Add a small `png_size` draft/preview tier
(e.g. 512/1024/2048) to `SUPPORTED_PNG_SIZES` in `src/config.py` (fail-fast validated, default stays
4096), update the `--png-size` help, and unit-test it in `tests/test_export_config.py`. Default 2D
output stays byte-identical. `S`
(`SUPPORTED_PNG_SIZES` now `(512, 1024, 2048, 4096, 8192, 16384, 32768, 65536)`, sorted, default
still 4096; `--png-size` help lists the draft tiers; `tests/test_export_config.py` asserts the tiers
are present/sorted/accepted with the default + reject-unsupported paths unchanged. Full offline suite
892 green; no `PIPELINE_STAGES` edit.)
95. [ ] Playwright harness scaffold — Add Node + Playwright dev tooling under `tests/e2e/`
(`package.json`, `playwright.config`), a fixture that boots `serve.py` on a test port with a
temporary output dir and tears it down, and a smoke test that `start.html` loads with no console
errors and its catalog/landing assets resolve. Kept out of the Python offline suite. `M`
96. [ ] Landing + navigation e2e — Assert the landing renders (hero, catalog grid of four cards, how
-it-works), and that every catalog link + the gallery link navigates to a page that loads without JS
errors. `S`
97. [ ] Four-endpoint low-res proof e2e — For each endpoint (poster, report, digital, animation),
drive the journey to a **low-res proof** via the render backend at the draft tier and assert a proof
artifact/preview is produced. `L`
98. [ ] Run docs & optional CI wiring — Document `npx playwright test` (prerequisites: extracted
county, `serve.py`), and wire an opt-in/gated CI job (never in the offline Python suite). `S`

Epoch gate: `npx playwright test` (against a live `serve.py` on a pre-extracted small county) walks
`start.html` → all four catalog pages → a low-res proof for each endpoint, green; the draft
`png_size` tier ships in the offline suite and default 2D output stays byte-identical.

---

## Proposed customer-to-operations experience blueprint

The four-artifact catalog, no-account buyer journey, operations intake, production
workspace, proof/revision loop, and asset-library model are documented in
`agent-os/specs/2026-09-05-customer-operations-experience/spec.md`. The compact
cradle-to-grave flowchart is `workflow.mmd` in that directory. This is an
**experimental UX and operations design brief**, not authorization to bypass the
Epoch 11.5 revenue gate for catalog/POD, self-serve, or commercial expansion.

> Notes
> - Epochs are gated by a demonstrable artifact, not calendar dates.
> - “Accurate” always means sampled from a documented bare-earth DEM with stated horizontal
>   and vertical CRS/units. Vertical exaggeration is display-only and never overwrites source Z.
> - Effort scale: XS=1 day, S=2–3 days, M=1 week, L=2 weeks, XL=3+ weeks.
> - **Rights gate (commercial data use).** USGS NHDPlus HR / NHD / WBD are U.S. federal public domain and
>   free to sell — but record the source version + attribution line for every sold art asset. **The PRISM
>   climate Rights gate is RETIRED (Epoch 14 #60, 2026-09-01):** the year-over-year / watershed-report
>   climate dependency now defaults to **NOAA NCEI nClimGrid-Monthly, which is U.S. federal public
>   domain** — free to sell with attribution *"Climate data: NOAA NCEI nClimGrid-Monthly (public
>   domain)."* The default `--climate-source nclimgrid` path (spans #45–#55) is therefore commercially
>   clear at $0. PRISM stays selectable via `--climate-source prism` for A/B comparison **only**; **any
>   PRISM-derived asset remains non-sellable** (PRISM is not public domain and its commercial use needs a
>   written PRISM Climate Group arrangement) — so never ship a `--climate-source prism` render
>   commercially.
> - **Revenue gate (commercial expansion).** Catalog/POD, self-serve, subscriptions, and region expansion
>   beyond OR/WA/CA/ID (Utah #47) are gated on the Epoch 11.5 revenue outcome — proven demand, not shipped
>   features. Validation-first: prove a buyer will pay before widening the product surface.
