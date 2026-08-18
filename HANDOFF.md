# Handoff — hydro-art

_Last updated: 2026-08-12, after Epoch 6 (#23–#28) complete, a roadmap bookkeeping audit (W1–W3 + #11 marked done, committed `c254d47`), Epoch 5 #20 (accuracy validation suite, committed `43d1635`), #21 offline-packaging slices (portable cache manifests `f5997d8` + DEM tile-budget `0825475`), and the #22 terrain-aware-hillshade slice (committed `a0674c4`), the #22 animation/camera-paths
slice (committed `d22a0d1`), the #22 web-delivery slice (which completed roadmap #22), the third
#21 slice — the **package preflight planner** (`src/packaging.py` + `tools/package_cache.py`,
committed `1c01574`), plus a fourth #21 slice — the **settings-driven DEM acquisition entry point**
(`acquire_dem_for_settings` in `src/dem.py`, implemented, commit pending)._

## Current state (2026-08-17)

- **#29 DONE — external-storage layout & output migration — implemented, commit
  pending.** Opens Epoch 7. Puts the large files a build reads/writes (extracted
  GDB datasets, the archive cache, rendered output) on a configurable external
  drive instead of local disk. New pure/offline `src/storage.py` (stdlib-only, not
  in `PIPELINE_STAGES`): `resolve_storage(...)` maps one `--external-root` (or
  `$HYDRO_ART_EXTERNAL_ROOT`) into `cache`/`datasets`/`output` subdirs with per-kind
  explicit overrides and a **mount-aware** local fallback (`drive_available` = root
  or its parent/mount-point exists) so an unmounted drive never crashes a build;
  `plan_migration`/`apply_migration` move an existing local tree (default `output/`)
  onto the drive and leave a directory **symlink** behind so old paths keep
  resolving (idempotent/resumable; mount guard → `StorageError` before any move).
  Wired into `build.py` (new `--external-root`/`--datasets-dir`/`--output-dir`/
  `--staging`; NAS cache default preserved when no external root) and `serve.py`
  (`_serve_roots`, keeps its NAS-when-mounted cache default). Optional `--staging`
  local working copy threaded through `_export_stage` (render locally, move finished
  file to output; `None` = byte-identical). New thin `tools/migrate_storage.py`
  (`python -m tools.migrate_storage --external-root … [--kind output|datasets]
  [--dry-run] [--no-symlink]`; drive-mounted check → non-zero + StorageError). Storage
  location is **not** in `Settings` and never affects rendered bytes; a no-flag/no-env
  build is byte-identical. TDD: `tests/test_storage.py` (+14), `test_build.py` (+4),
  `test_serve.py` (+3), `test_migrate_storage.py` (+4, stdlib-only → offline),
  `test_export_pipeline.py` (+1 staging). Suite: **488 passing** (+26), no regressions.
  Smoke: dry-run reported the real `output/` (352 files, 2.3 GiB); missing-root and
  unmounted-drive exit 1. Spec `agent-os/specs/2026-08-17-external-storage-layout/`.
- **#21 DONE — real (non-offline) DEM acquisition entry point — implemented, commit
  pending.** Closes #21's final "Left" gap, so **roadmap #21 is now marked `[x]`**.
  `src/dem.py` already had `acquire_dem_for_settings` (settings-driven acquisition)
  but nothing outside the tests called it. This slice adds the one tested `src/`
  primitive that was missing — pure/offline `REGION_BOUNDS` + `region_bounds(region)`,
  the EPSG:4326 per-region envelope (Census state extents; DEM counterpart to
  `datasets.REGION_HUC4`, drift-guarded against `SUPPORTED_REGIONS`) that feeds
  `count_tiles`/`acquire_dem` — and a thin, untested `tools/acquire_dem.py` CLI over
  `acquire_dem_for_settings`: per `--region` it turns `region_bounds` into a boundary,
  force-enables elevation (honoring `--tier`/`--tile-budget`/`--refresh`), and either
  `--dry-run` counts tiles + checks the budget (no network) or downloads/caches the
  3DEP COG tiles via a real `Downloader(UrllibFetcher())`, printing each tile's
  id/cache-path/checksum (non-zero exit on over-budget/config/boundary errors). TDD:
  `tests/test_dem.py` +4. Suite: **462 passing** (+4). Smoke-tested offline (dry-run
  budget checks + fake-downloader acquire with a reuse cache hit). **The DEM subsystem
  stays out of `PIPELINE_STAGES` by design (CLAUDE.md) — that integration is a
  deliberate non-goal, not a gap; this CLI *is* the real entry point.** With this,
  every #21 concern (CA+Idaho states, tile-budget, resumable jobs, portable manifests,
  real acquisition entry point) is met.
- **#21 Region expansion → Idaho — implemented, commit pending.** Adds Idaho as a
  fourth supported region (the first of #21's two remaining directions). HUC4 basins
  derived from local WBD via `tools/derive_state_huc4.py Idaho --min-overlap-frac 0.01`
  → `("1701", "1704", "1705", "1706")` (Snake system + panhandle, all HU2 region 17;
  the SE Bear-River corner in HU2 16 is omitted, same caveat as California's desert
  fringes — no national WBD locally or on the NAS). Wired into `SUPPORTED_REGIONS`
  (`src/config.py`), `REGION_HUC4` (`src/datasets.py`), `STATE_FIPS` (`src/counties.py`),
  and the `tools/render_common.STATE_HUC4` mirror. TDD: `tests/test_config.py` (Idaho
  accepted), `tests/test_datasets.py` (resolves the four basins + WBD `{17}`),
  `tests/test_counties.py` (FIPS `16`). Three suite tests used "Idaho" as their
  canonical *unsupported* region and were repointed to "Nevada" (`test_config.py`,
  `test_counties.py`, `test_build.py`). Suite: **458 passing** (+2). This is
  acquisition/config plumbing — a full Idaho render additionally fetches the region-17
  NHDPlus HR archives (1704/1705/1706) on demand via the download-skip-aware pipeline.
  **Left on #21 (at the time):** a real (non-offline) DEM entry point — since closed
  by the `tools/acquire_dem.py` slice above; `PIPELINE_STAGES` integration was a
  deliberate non-goal.
- **#21 Manifest packaging CLI — committed (`14a2107`).** Closes the last
  small offline-packaging gap on #21: a CLI that writes/verifies/diffs a portable
  cache manifest over a real (e.g. NAS) cache. `src/manifest.py` gains two pure,
  tested formatters — `format_verification` (COMPLETE/INCOMPLETE + `ok`/total, then
  lists any missing/mismatched keys) and `format_diff` (one "in sync" line, else the
  non-empty added/removed/changed groups + unchanged count). New thin
  `tools/cache_manifest.py` (mirrors `tools/package_cache.py`; reads a real cache, so
  not in the offline suite) has three subcommands: `write --region … --cache-dir …
  [--out] [--strict]` (`manifest_for_settings` → `write_manifest`; `--strict` → exit 1
  on an un-recorded required file), `verify MANIFEST --cache-dir …` (exit 0 iff
  complete), `diff OLD NEW` (exit 0 iff synced). Smoke-tested `main()` offline against
  a fabricated Oregon tmp cache — all exit codes correct. Tests: `tests/test_manifest.py`
  (+4). Suite: **456 passing** (+4), no regressions. **Left on #21:** region expansion
  beyond OR/WA/CA (needs real WBD) and wiring the DEM subsystem into a real
  (non-offline) entry point / `PIPELINE_STAGES`.
- **#27 Run-pipeline reconcile — committed (`5dc8ebf`; roadmap note `c5a6b2d`).** The served
  "Run pipeline" button now actually completes a real render offline. Two root
  causes fixed: (1) `_download_stage` unconditionally fetched archives even when
  the extracted GDBs already exist — `extract_all` would skip them, so the fetch
  was pure waste that also required the NAS. `src/cache.py` gains
  `is_extracted(datasets_root, descriptor)` and `ensure_cached` takes a
  `datasets_root` param that skips already-extracted descriptors before touching
  the cache/downloader; `src/pipeline.py` wires `ctx.datasets_dir` into
  `_download_stage`. This lets a build run with **zero downloads** off
  pre-extracted `datasets/` (no NAS, no network). (2) `serve.py` hardcoded the
  NAS cache dir, so an unmounted NAS crashed the run with
  `[Errno 13] Permission denied: '/Volumes/home'`. New `_resolve_cache_dir()`
  prefers the NAS only when mounted (its parent exists), else falls back to local
  `cache/`; a `--cache-dir` flag always wins. **Verified end-to-end**: served
  `POST /api/render` `{"region":["Oregon"],"county":"Deschutes","output":["svg"]}`
  → job `succeeded` → artifact `output/oregon-deschutes.svg` (8.4 MB, sha256
  `0f1f0976e6c4b93e2cc46f136ce84c8e5cf3cdad1e259bad03309a89a4055733`), identical
  to the direct `Pipeline` build, with **no downloads triggered**. Tests:
  `tests/test_cache.py` (+4), `tests/test_acquisition_integration.py` (+1),
  new `tests/test_serve.py` (+3). Suite: **452 passing** (+8), no regressions.
- **#22 Print/experience modes — web-delivery slice implemented, commit pending; completes #22
  (hillshade `a0674c4`, camera paths `d22a0d1`).** #22 is `XL` and spans three concerns; all three
  offline slices have now shipped. **(3) Web delivery** (commit pending): new pure module
  `src/delivery.py` (same spec `agent-os/specs/2026-08-12-print-experience-modes/`) packages the two
  prior products — a hillshade `RasterGrid` + a camera path of `CameraPose`s — into one stable,
  browser-loadable **experience document**: `hillshade_layer(grid)` (row-major `shade`, nodata→`None`,
  `bounds`/`cell_size_m`/valid-only `value_range`), `camera_track(poses)`
  (`[{position,target,up,fov_deg}]`), `experience_document(*, hillshade_grid, camera_poses, crs=None)`
  → `{generator, crs, hillshade, camera:{frame_count, track}}`, and `experience_json` (deterministic
  `sort_keys`). `DeliveryError` on empty grid / empty path. Mirrors `src/preview.py`'s conventions;
  imports only `json` + `src.raster`/`src.camera`; not in `PIPELINE_STAGES`; `src/` never imports
  `web/`. New self-contained `web/experience.html` viewer loads a document, paints the hillshade to a
  `<canvas>` (grayscale, nodata transparent), and plays/scrubs the camera track. Tested in
  `tests/test_delivery.py` (7 tests); viewer script `node --check`-clean and a real document parses
  browser-side. Suite: **423 passing** (+7). **Deferred (not gating #22):** hillshade↔river-SVG
  compositing in a `tools/` print renderer, a live `/api/experience` server route over a real DEM, and
  richer camera motion (easing/quaternion). — Prior slices below.

- **#22 slices 1-2 (context).** #22 spans three concerns; the first two offline slices shipped.
  **(1) Terrain-aware 2D hillshade** (committed `a0674c4`): `src/hillshade.py` `hillshade(grid, *,
  azimuth_deg=315, altitude_deg=45, z_factor=1.0, nodata=-1.0)` computes Lambertian shaded relief
  (0-255) from a `RasterGrid` via Horn's 3×3 `dz/dx`/`dz/dy` + the ESRI/GDAL illumination model;
  edge-replicated borders keep the input shape, nodata is **never invented** (a cell or its
  8-neighborhood touching nodata → output sentinel), `z_factor` is shading-only, boundary-validated
  (`HillshadeError`), deterministic (numpy + `src.raster`/`src.elevation` only). Tested in
  `tests/test_hillshade.py` (8 tests). **(2) Animation/camera paths** (commit pending): new pure module
  `src/camera.py` (same spec `agent-os/specs/2026-08-12-print-experience-modes/`) interpolates
  `scene.CameraPreset` keyframes into a tuple of `CameraPose` samples — `interpolate_camera(a, b, t)`
  lerps position/target/fov + normalized-lerps the up vector; `camera_path(keyframes, *,
  steps_per_segment, loop=False)` samples each segment start-inclusive/end-exclusive so shared
  keyframes never duplicate — **open** paths append a closing pose ending exactly on the last keyframe
  (`(n-1)·steps + 1`), **looping** paths add a `last→first` wrap for a seamless cycle (`n·steps`).
  Up vectors are always unit-length; `CameraPathError` guards `<2` keyframes / `steps_per_segment<1`
  / `t∉[0,1]` / zero-length up. `math` + `src.scene` only, offline/deterministic, not in
  `PIPELINE_STAGES`. Tested in `tests/test_camera.py` (7 tests). Suite: **416 passing** (+7).
  **Deferred on #22:** web delivery (serving the hillshade image + camera-path animation), compositing
  hillshade under the river SVG in a `tools/` print renderer, and richer camera motion (easing /
  quaternion) beyond the linear first cut.
- **#21 Regional scale & offline packaging — four offline slices (`f5997d8`, `0825475` committed; package preflight + DEM-acquisition wiring uncommitted).** #21 is `XL` and spans four concerns; per the user's scoping decision this pass
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
  cached files — so an interrupted acquisition resumes on re-run. A third (uncommitted) slice adds a
  **package preflight planner**: pure/offline `src/packaging.py` composes the manifest + tile-budget
  primitives into one "is this cache ready to ship?" verdict — `plan_package(cache, settings, *,
  tile_count=None)` → frozen `PackagePlan` (disjoint `present`/`missing`/`corrupt` over
  `resolve_required_files`, `total_bytes`, injected-tile-count preflight) with `is_complete` /
  `within_tile_budget` / `is_ready`, plus `format_plan` for a one-block summary. Driven by the thin
  non-offline `tools/package_cache.py` (`--region`/`--cache-dir`/`--config`/`--tile-count`; exits 0
  ready / 1 not). Imports only stdlib + `src.manifest`/`datasets`/`config`/`cache`; not in
  `PIPELINE_STAGES`. Tested in `tests/test_packaging.py` (7 tests). A fourth (uncommitted) slice adds
  a **settings-driven DEM acquisition entry point**: `src/dem.py`
  `acquire_dem_for_settings(settings, *, boundary, cache, downloader)` reads
  `elevation.tier`/`tile_budget`/`cache_policy` off the validated `Settings` and forwards to
  `acquire_dem` — guarding on `enabled` (disabled → `ElevationError` before any discovery), mapping
  `cache_policy=="refresh"` → `refresh=True`, and feeding `tile_budget` into the existing fail-fast
  budget guard. This is the "wire `tile_budget` into a live DEM entry point" gap closed; new import
  `from src.config import Settings` is cycle-free. Tested in `tests/test_dem.py` (+5). Suite:
  **435 passing** (+5 over the packaging slice's 430).
  **Deferred on #21:** region expansion beyond OR/WA/CA (needs real WBD), putting the DEM subsystem
  into a real (non-offline) entry point / `PIPELINE_STAGES`, and a `write_manifest`-to-disk packaging
  CLI over a real NAS cache.
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
  Epoch 2 is now complete. **W4** stays `[ ]`: OR/WA + Clark County real-region QA all passed;
  what remains is optional further tuning of the print preset **values** (art-direction).
- **W4 waterbody preset *mechanism + scale-split values* — uncommitted.** Closes the W4 "establish
  print and screen presets" plumbing (spec `agent-os/specs/2026-08-12-waterbody-regional-presets/`).
  `src/config.py` `WATERBODY_PRESETS` now holds three bundles: `screen` (default on-screen), plus
  scale-specific print presets — `print-state` (100k/250k m², whole-state/large-format) and
  `print-county` (25k/50k m², single-county). The split is backed by real evidence: at county zoom the
  state thresholds over-prune (Clark County, WA: 100k m² keeps only 24 of 830 waterbodies; 25k m² keeps
  a readable ~62). `_coerce_waterbodies` pops a `preset` directive and layers `defaults < preset <
  explicit` (unknown → `ConfigError`), consuming `preset` so it never lands on the frozen
  `WaterbodySettings` (no-preset builds byte-identical). `src/cli.py` `--waterbody-preset`
  (`choices=SUPPORTED_WATERBODY_PRESETS`, auto-derived) and — critically — a nested `waterbodies` merge
  base of `{}` (not `dict(DEFAULTS["waterbodies"])`) so a preset isn't shadowed by pre-seeded defaults.
  Tests in `tests/test_waterbody_config.py` (17 passing). **Optional follow-up:** further art-direction
  tuning of the numbers; the mechanism + a defensible per-scale default are in place.
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
