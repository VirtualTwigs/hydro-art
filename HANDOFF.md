# Handoff — hydro-art

_Last updated: 2026-08-12, after Epoch 6 (#23–#28) complete, a roadmap bookkeeping audit (W1–W3 + #11 marked done, committed `c254d47`), Epoch 5 #20 (accuracy validation suite, committed `43d1635`), #21 offline-packaging slices (portable cache manifests `f5997d8` + DEM tile-budget `0825475`), and the #22 terrain-aware-hillshade slice (implemented, commit pending)._

## Current state (2026-08-12)

- **#22 Print/experience modes — 2D hillshade slice implemented, commit pending.** #22 is `XL`
  and spans three concerns; per the user's scoping this pass delivers only the flagship, fully-
  offline **terrain-aware 2D hillshade**. New pure module `src/hillshade.py` (spec
  `agent-os/specs/2026-08-12-print-experience-modes/`): `hillshade(grid, *, azimuth_deg=315,
  altitude_deg=45, z_factor=1.0, nodata=-1.0)` computes Lambertian shaded relief (0-255) from a
  `RasterGrid` via Horn's 3×3 `dz/dx`/`dz/dy` + the ESRI/GDAL illumination model; edge-replicated
  borders keep the input shape, nodata is **never invented** (a cell or its 8-neighborhood touching
  nodata → output sentinel), `z_factor` is shading-only (never alters source Z), boundary-validated
  (`HillshadeError`), deterministic. numpy + `src.raster`/`src.elevation` only; not in
  `PIPELINE_STAGES`. Tested in `tests/test_hillshade.py` (8 tests). Suite: **409 passing** (+8).
  **Deferred on #22:** animation/camera paths (interpolated `CameraPreset` motion over `src/scene.py`),
  web delivery, and compositing hillshade under the river SVG in a `tools/` print renderer.
- **#21 Regional scale & offline packaging — two offline slices committed (`f5997d8`, `0825475`).** #21 is `XL` and spans four concerns; per the user's scoping decision this pass
  delivers only the fully-offline **portable cache manifests**. New pure module
  `src/manifest.py` (spec `agent-os/specs/2026-08-12-regional-scale-offline-packaging/`) turns
  a `Cache`'s recorded provenance into a deterministic, portable manifest: `build_manifest` /
  `manifest_for_settings` (region→manifest via `resolve_required_files`, so OR/WA/CA round-trip
  through one manifest), stable sorted JSON with **cache-relative** paths (no wall-clock time →
  byte-identical for equal state), `verify_manifest` (recomputes sha256+size → ok/missing/
  mismatched, never mutates), and `diff_manifests` (added/removed/changed/unchanged). **numpy-
  free & GDAL-free** (imports only stdlib + `src.datasets`/`src.config`/`src.cache`; verified no
  heavy modules pulled in). Not wired into `PIPELINE_STAGES`. Tested in `tests/test_manifest.py`
  (13 tests). A second slice added **tile-budget controls**: `ElevationSettings.tile_budget`
  (0 = unlimited, boundary-validated in `_coerce_elevation`) + `src/dem.py` `count_tiles` (pure
  offline preflight) + an `acquire_dem(max_tiles=…)` guard that raises `ElevationError` **before any
  COG download** when a region's tile count exceeds the budget (+4 config, +4 dem tests). Also
  confirmed **resumable jobs** are essentially already built — `src/download.py` `Downloader` streams
  to `.part`, resumes via HTTP `Range`, verifies, atomically moves; `acquire`/`acquire_dem` skip
  cached files — so an interrupted acquisition resumes on re-run. Suite: **401 passing** (+21 across
  both slices). **Deferred on #21:** region expansion beyond OR/WA/CA (needs real WBD), wiring
  `tile_budget` into a live DEM entry point, and `tools/` packaging/preflight CLIs over a real NAS
  cache.
- **#20 Accuracy validation suite — committed (`43d1635`).** New pure module
  `src/accuracy.py` (spec `agent-os/specs/2026-08-12-accuracy-validation-suite/`),
  the first Epoch 5 item. Compares terrain/river vertices sampled from a DEM fixture
  against known truths and reports CRS/units/nodata-coverage/QA: `error_metrics`
  (max/mean abs error, RMSE, residuals; nodata/uncovered points are **skipped**, never
  zero-filled), `coverage_report`, `crs_report` (verbatim from `ElevationProvenance`),
  `qa_rollup` (river-profile inversions, structural over `ProfileQA` so no numpy import),
  and `AccuracyReport` + `validate_against_sampler` over the injected `ElevationSampler`
  seam with a `within_tolerance` verdict (inversions reported, not gating). **numpy-free
  & GDAL-free** (imports only stdlib + `src.elevation`; verified no heavy modules pulled
  in). Not wired into `PIPELINE_STAGES`. Tested in `tests/test_accuracy.py` (19 tests).
  Real-3DEP harness deferred (needs the GIS stack/NAS). Suite: **380 passing** (+19).
- **Roadmap bookkeeping (committed `c254d47`).** An audit found four items fully
  implemented but never ticked: **W1/W2/W3** (waterbody taxonomy/selection/rendering) and
  **#11** (elevation settings + provenance) — all marked `[x]` with evidence notes;
  Epoch 2 is now complete. **W4** stays `[ ]`: OR/WA real-region QA passed, but the Clark
  County run (Census shapefile not mounted) and print/screen preset **values**
  (art-direction) remain.
- **#28 Presets & shareable render recipes — committed (`b80296d`).**
  Added a **recipe** layer to the control surface (spec
  `agent-os/specs/2026-08-12-presets-and-recipes/`). All logic is pure and lives
  in `web/shared/hydro-ux.js`: a canonical serializable subset of `state`
  (`RECIPE_KEYS`, preview-only fields excluded) with `toRecipe`/`sanitizeRecipe`/
  `encodeRecipe`/`decodeRecipe`/`applyRecipe`, a named `PRESETS` catalog
  (`or-screen`, `clark-print`, `print-mono`, `screen-glow`) + `presetById`/
  `applyPreset`, and base64url primitives (`btoa`/`atob` with a Node `Buffer`
  fallback). `decodeRecipe` sanitizes every field against the same option catalogs
  the UX uses, so a shared/hand-edited link can never inject invalid state; the
  round-trip is exact (`decodeRecipe(encodeRecipe(s))` deep-equals `toRecipe(s)`).
  The module is now Node-loadable (`module.exports`) and round-trip-tested
  headlessly in `tests/test_recipe_roundtrip.cjs` (11 tests, stdlib `node` only).
  `web/studio.html` adds a **Presets & sharing** fieldset (buttons + "⧉ Copy share
  link" → `location.hash`), a `syncControls()` that pushes `state` back onto every
  DOM control, and a boot `restoreFromHash()`. Closes **Epoch 6**. Deferred: the
  live `file://` browser smoke (Chrome extension wasn't connected this session);
  the pure logic and inline-script syntax are verified headlessly. Suite:
  **361 passing** (unchanged — `src/`/offline suite keep no dependency on `web/`).
- **#27 Live pipeline integration — committed (`3613ed8`).** Wired the
  control surface to a **local job runner** that runs the real pipeline and
  returns the produced SVG (spec
  `agent-os/specs/2026-08-12-live-pipeline-integration/`). New `src/jobs.py`
  (stdlib + `src.config` only, GDAL-free): `settings_from_payload` whitelists the
  DEFAULTS keys and validates via `build_settings`; `JobRunner` validates at
  `submit` (→ 400) then runs an **injected**, duck-typed pipeline off-thread
  (default 1-worker `ThreadPoolExecutor`; tests inject an inline executor),
  tracking `pending→running→succeeded|failed` and capturing
  `export_paths`/`svg_sha256`. New `src/server.py` (stdlib `http.server`): pure
  `handle_request` dispatcher (`POST /api/render`, `GET /api/jobs/<id>`,
  `GET …/artifact?fmt=`, static `web/` with a path-traversal guard) + a thin
  `serve()`. New top-level `serve.py` builds the real
  `Pipeline(cache_dir=NAS_CACHE_DIR)` and serves localhost. `web/shared/hydro-ux.js`
  adds a pure `renderRequest(state)` payload builder; `web/studio.html` gains a
  "Run pipeline" button (enabled only when served, disabled over `file://`) that
  POSTs → polls → shows the SVG + download. `color_by=elevation` and non-annual
  `--months` surface as a **failed job** with the honest fail-fast message.
  Deferred: the browser + real-dataset smoke needs the GIS stack/NAS. Suite:
  **361 passing** (+8 `test_jobs.py`, +8 `test_server.py`).
- **#26 Web control surface — committed (`0f2c7eb`).** Promoted
  `web/proto-a-studio.html` (via `git mv`) to the canonical `web/studio.html` (spec
  `agent-os/specs/2026-08-10-web-control-surface/`). Because #23–#25 have shipped,
  `cliMapping`/`yamlMapping` in `web/shared/hydro-ux.js` were rewritten to emit those
  as **real `build.py` flags** (`--color-by`/`--single-color`, `--width-by` +
  `--width-min/max/gamma`, `--county`, `--months`) instead of `(proposed)` markers.
  Two options are shipped-as-flags but still fail fast in the 2D pipeline and carry an
  honest caveat note (appended as commented `# notes:` lines below the command, so the
  paste stays runnable): `color_by=elevation` (needs the DEM subsystem →
  `tools/render_state_mono.py`) and non-annual `--months` (live frames land in #27 →
  `tools/render_monthly.py`). Base `line_width`/`background` are YAML-only (no CLI
  flag). Added source-pointer comments at the `MONTH_ABBR`/`HUC_LEVELS` option blocks
  and a `mappingSelfCheck(state)` helper (exported on `window.HydroUX`). Verified
  headless: `node --check` on both scripts pass; `mappingSelfCheck` returns
  `{ok:true}`; `bash -n` on the shipped-only command passes. Manual live-DOM browser
  pass still pending (Chrome extension not connected during the attempted automation).
  Still a **mapping target only** — no live pipeline run (that's #27).
- **#25 Monthly-flow rendering option — committed (`6c18a0d`).** Promoted
  the disaggregation + fixed year-max width scale into tested `src/` code and
  added a validated `--months` option (spec
  `agent-os/specs/2026-08-12-monthly-flow-option/`, scope: "promote algorithms +
  option", mirroring #23). New `src/monthly_flow.py` (numpy-only, no pyogrio)
  holds `snow_available_water`/`normalize_shape`/`accumulate_downstream`/
  `disaggregate_monthly` + constants. `src/rendering.py` adds the fixed-span
  helpers `fixed_flow_span`/`widths_on_span`/`monthly_width_frames`.
  `src/config.py` adds `months: tuple[int,...]` (empty = annual) via pure
  `parse_months` (single/name/range/wrap; `DEFAULTS["months"]="annual"`);
  `src/cli.py` adds `--months`. `src/pipeline.py` `_generate_svg_stage` fails fast
  with `ConfigError` on non-annual months (2D pipeline doesn't load per-reach
  monthly discharge — same limitation as `color_by=elevation`; points to
  `tools/render_monthly.py`). Annual default is byte-identical. `tools/monthly_flow.py`
  and `tools/render_monthly.py` now delegate to `src/` (re-export
  `MONTH_ABBR`/`build_monthly_flow`/`_value_column`/`FLOOR`/`fixed_widths`).
  Deferred to #27: loader/graph discharge plumbing + multi-frame export for a live
  `build.py --months` run. Suite: **345 passing**.
- **#24 County scope in the pipeline — committed (`489b511`).** New
  first-class `--county` build option clips hydrography to a single Census county
  polygon within the selected state (spec
  `agent-os/specs/2026-08-12-county-scope/`). `src/config.py` adds `county:
  str|None` (requires exactly one region when set); `src/cli.py` adds `--county`;
  new `src/counties.py` seam holds `STATE_FIPS` + `state_fips_for_region` +
  `county_boundary` + an injectable `CountyBoundaryProvider`/`CensusCountyProvider`
  (lazy geopandas, stays GDAL-free at import). `src/pipeline.py` `_clip_stage`
  branches on `settings.county` (county polygon vs. WBD region boundary, stored as
  the `region_boundary` artifact so waterbodies reuse it) and `_export_stage`
  names the file after the county (e.g. `oregon-hood-river.svg`). Default (no
  county) is byte-identical. Download is still whole-state then clip (county HUC4
  download scoping deferred). Suite: **310 passing**.
- **#23 Color & line-width art-direction options — committed (`5910141`).**
  `color_by` (watershed/single/elevation) + `width_by` (uniform/flow) with
  min/max/gamma in `src/config.py`/`cli.py`/`rendering.py`; defaults byte-identical.

## Prior state (2026-08-11)

- **California added end-to-end (`5512675`, `80bfac3`):** third supported
  region. `SUPPORTED_REGIONS` (`src/config.py`), `REGION_HUC4` (`src/datasets.py`),
  `STATE_HUC4` (`tools/render_common.py`), and `HydroUX.STATES`/`COUNTIES`
  (`web/shared/hydro-ux.js`) all carry CA. HUC4s derived authoritatively from the
  WBD `states` attribute (region 18 all-CA + region 17's 1710/1712); HU2 15/16
  desert fringes omitted pending those archives.
- **`tools/derive_state_huc4.py` (`5512675`):** new helper deriving a state's
  HUC4 basins by intersecting its Census polygon with WBD `WBDHU4` — the repeatable
  way to add the next state. Supports `--wbd-hu4`, `--all`, `--min-overlap-frac`.
- **Renderer/tools batch (`6e9dcce`, `884770f`, `d9d1f01`, `84d0717`):** monthly-flow
  disaggregation (`tools/monthly_flow.py`), the 12-frame/year-in-motion renderers
  (`render_monthly.py`, `render_infographic.py`, `render_infographic_year.py`),
  hypsometric mono (`render_state_mono.py`), layered rasterizer (`rasterize_layered.py`),
  all unified on the shared `render_common.py` art recipe.
- **Pipeline hardening (`9079141`):** vectorized `clip_to_region`
  (`shapely.prepare`/`covers`/`intersects` — inside geoms skip intersection),
  cycle-tolerant stream ordering (`nx.condensation` fallback, no longer raises on
  cycles), and `NAS_CACHE_DIR` staging in `build.py`.
- **Web control surface (Epoch 6, `ae6d56e`, `15a970a`, `0678890`, `6e347c9`):**
  shared `web/shared/` foundation (`ux.css` + `hydro-ux.js`) + three prototypes
  (`proto-a/b/c`); chosen direction is Prototype A studio + Prototype B month
  timeline (spec `agent-os/specs/2026-08-10-web-control-surface/`). CLI/YAML output
  contract emits shipped flags in the command with `(proposed)` #23–#25 flags as
  comments. Roadmap **Epoch 6 (#23–#28)** now formalized in `roadmap.md`. Still a
  **mapping target only** — no live pipeline run (that's #27).
- **3D Lab upgrade (`10b0624`):** `web/3d.html` gains NOAA-style solar-position
  terrain lighting (real reading date/time), a filled sun-shaded terrain mesh,
  Terrain/Hydrography/Terrain-only layer toggles, and 4K–12K print PNG export.
- **`.theia/` gitignored (`6db2c7d`).** Working tree clean.
- Full suite: **276 passing**. All of #23–#28 are still **spec/mapping only** —
  the pipeline itself is unchanged behind the new UX; promoting the proposed flags
  (#23–#25) and wiring live runs (#27) is the next implementation work.

---

## Prior state (2026-07-30) — DEM/3D spec complete

- **Epoch 1 (#1–10):** complete and committed.
- **Epoch 1.5 waterbodies (W1–W4):** complete and committed
  (`46a0766`…`fc60c5c`). Note: the roadmap.md restructure that adds Epochs
  1.5–5 does not tick W1–W4 (pre-existing inconsistency, left as-is).
- **Epoch 2 #11 (elevation settings & provenance contract):** committed
  `33a60d9`. `src/config.py` elevation block, `src/elevation.py`, CLI flags.
- **Epoch 2 #12 (3DEP DEM discovery & cache):** committed `d2296aa`. `src/dem.py`
  — deterministic 1-degree COG-grid discovery on the `prd-tnm` S3 bucket for
  `preview`/`state` tiers; `local` (1 m) deferred. Decisions resolved: AWS S3
  COGs; normalize-to-NAVD88 (identity for CONUS 3DEP).
- **Epoch 2 #13 (DEM mosaic/clip/pyramid + bilinear sampling):** committed
  `c3468f0`. `src/raster.py` — numpy `RasterGrid`, `mosaic`/`clip_grid`/
  `build_pyramid`, `sample_bilinear` + `GridSampler`, `normalize_dem`
  orchestrating read→reproject(EPSG:5070)→mosaic→clip→pyramid via injected
  `RasterReader`/`RasterReprojector` seams.
- **Epoch 3 #14 (terrain sampling service):** committed. `src/terrain.py` +
  `tests/test_terrain.py` (8): `densify_line`
  at DEM-cell spacing, `TerrainSampler` over an injected `ElevationSampler`,
  `SampledLine` diagnostics, `dem_cell_size`/`sampler_for_dem`.
- **Epoch 3 #15 (river Z attribution & QA):** committed.
  `src/hydro_z.py` + `tests/test_hydro_z.py` (8): `ElevatedLine`
  (immutable source Z, preserved 2D path), `profile_qa` downstream-inversion
  detection, opt-in render-only `repair_monotonic` + `RepairPolicy`, `render_z`.
- **Epoch 3 #16 (adaptive terrain mesh):** committed `4b4c0a6`. `src/mesh.py` +
  `tests/test_mesh.py` (8): `build_terrain_mesh` = greedy error-bounded TIN
  (Garland–Heckbert), crack-free fan retriangulation, nodata-footprint dropping,
  `max_points` cap, true-1×-meter `TerrainMesh` with source-raster + deterministic
  geometry hashes; `mesh_from_dem` selects a pyramid LOD. Decision #3 (mesh/error
  budget) resolved: error-bounded max-vertical-deviation.
- **Epoch 4 #17 (3D scene assembly):** committed `4702a50`. `src/scene.py` +
  `tests/test_scene.py` (8): `assemble_scene` → immutable `SceneModel` joining
  terrain, Z-rivers (source Z at 1× m), deduped `Material`s, N/S/E/W
  `CardinalAnnotation`s + `AxisInfo`, deterministic top/iso/south `CameraPreset`s,
  display-only `DisplaySettings`; `render_river_vertices` applies exaggeration+lift
  on demand; deterministic `scene_hash`; no browser state. Task Group 5 complete.
- **Epoch 4 #19 (reproducible 3D export):** committed. `src/export3d.py` +
  `tests/test_export3d.py` (8):
  `scene_to_glb` (pure-stdlib deterministic binary glTF), `scene_to_obj`
  (OBJ/MTL), `build_manifest` (source/raster/geometry/scene hashes + settings),
  `export_scene` (writes .glb/.obj/.mtl/.manifest.json via injected writer, with
  per-asset SHA-256). Geometry exported at true 1× m; exaggeration recorded, not
  baked. **Decision #4 resolved: GLB + OBJ** (GeoTIFF deferred). Built before #18
  per the spec's Phase F→G dependency. No open spec decisions remain.
- **Epoch 4 #18 (progressive 3D preview):** committed (`6b0df6a`).
  `src/preview.py` + `tests/test_preview.py` (8):
  `build_preview_asset` → deterministic coarse-`interaction` + fine-`commit`
  heightfield tiles (row-major z, nodata → `null`), bounds/z-range from the
  commit grid, per-LOD `cell_size_m`, optional Z-rivers as `[x,y,z]` meter
  polylines; `preview_json` = stable `sort_keys` serializer. `web/3d.html` gains
  a "Load DEM preview…" control; `elevationAt()` bilinearly samples the
  interaction tile while orbiting / commit tile on release, replacing the
  synthetic field (now labeled experimental, still toggleable).
- **Spec complete:** all coded items (#11–19) done. Remaining acceptance gate:
  a real (non-offline) Clark County / Oregon end-to-end DEM build to generate a
  live preview asset — needs GDAL + network.
- Full suite: **276 passing**. Spec artifacts:
  `agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling/`.

---


## Project
Hydrographic Vector Art Generator: a Python 3.12+ (running 3.14.6) GIS→SVG
pipeline turning USGS hydrography into neon river art for Oregon/Washington.
Built incrementally following the Builder Methods Agent OS spec-driven workflow
(specs in `agent-os/specs/YYYY-MM-DD-<name>/`).

## Per-item workflow (repeat for each roadmap item)
User drives with two commands:
1. **"create tasks and implement item #N"** — write spec artifacts
   (`planning/requirements.md`, `spec.md`, `tasks.md`), then TDD-implement in
   task groups (2–8 tests first per group, run ONLY those), mark `tasks.md`
   checkboxes, write `implementation/report.md`, run full suite for
   regressions, smoke-test, then report and STOP.
2. **"commit item #N"** — commit that item as a separate explicit step. Never
   commit without this.

## Status
All 10 roadmap items implemented — the PRD §8 pipeline runs end-to-end with no
stubs. Items 1–9 committed; **item #10 commit pending** (awaiting "commit item
#10"). Full suite: 147 tests passing (as of item #10).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | committed (70d96c6) |
| 7 | Deterministic basin coloring | committed (31f93ca) |
| 8 | Layered SVG rendering | committed (3c3df62) |
| 9 | Optional glow & SVG optimization | committed (06869ba) |
| 10 | Multi-format export & reproducibility | implemented; commit pending |

## Key conventions
- Run tests: `.venv/bin/python -m pytest -q`
- Config precedence: defaults < YAML < CLI; argparse flags default to `None` so
  unset flags never clobber YAML. Allowlist validation at the boundary in
  `build_settings` (`src/config.py`), raising `ConfigError`.
- Pipeline stages (`src/pipeline.py`) are DI'd via `RunContext`, share results
  through `context.artifacts`, no global state. Heavy GIS libs are lazy-imported
  behind injectable seams (Downloader, LayerLoader) so tests run offline with
  hand-built shapely/graph inputs — no GDAL, no real data.
- Module errors subclass `AcquisitionError` (`src/datasets.py`).

## Roadmap complete — where things stand
- The full PRD §8 pipeline is implemented (`download → extract → validate →
  repair_geometries → reproject → clip_to_region → build_graph →
  compute_watersheds → assign_colors → generate_svg → optimize_svg → export`);
  no stage is a stub.
- `export` (`src/pipeline.py` `_export_stage`) writes `output_dir/<regions>.<fmt>`
  for each `settings.outputs`, records `artifacts["export_paths"]` and
  `artifacts["svg_sha256"]`. SVG is written with pure stdlib.
- External tools are optional and injected, both degrading gracefully when
  absent: `svgo` (`SvgoOptimizer`, optimize_svg) and `rsvg-convert`
  (`FileExporter`, export). Installing them unlocks optimized / rasterized
  outputs; without them SVG still ships.
- Possible follow-ups (not roadmap items): package/document the optional CLI
  tools (or add a `cairosvg` fallback), real raster tiling for 65536px, and the
  PRD §33 future-work outputs (web/animated/GeoJSON/vector tiles).
