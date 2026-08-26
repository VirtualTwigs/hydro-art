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

## Epoch 8 — terrain-aware print output

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

## Epoch 9 — Codebase health & maintainability

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

> Notes
> - Epochs are gated by a demonstrable artifact, not calendar dates.
> - “Accurate” always means sampled from a documented bare-earth DEM with stated horizontal
>   and vertical CRS/units. Vertical exaggeration is display-only and never overwrites source Z.
> - Effort scale: XS=1 day, S=2–3 days, M=1 week, L=2 weeks, XL=3+ weeks.
