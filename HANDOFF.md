# Handoff — hydro-art

_Last updated: 2026-09-12, Epoch 24 complete (alpha-journey e2e, #94-98); Generation 1 complete (Epochs 19-23, #79-93); v1.0 ready to tag pending real double-render gate._

## Current state (2026-09-12)

- **Epoch 24 DONE (2026-09-12) — alpha customer-journey e2e (#94-98).** #94 (offline suite):
  draft `png_size` tier (512/1024/2048 added to `SUPPORTED_PNG_SIZES`, default stays 4096, 2D
  output byte-identical). #95-98: a **non-offline, opt-in Playwright harness** under `tests/e2e/`
  that walks the alpha site (`web/start.html` → four catalog pages → a low-res proof per endpoint)
  against a live `serve.py`. Gate green: **`npx playwright test` 13/13 (13.7m)** on a staged Clark
  County, WA — landing/nav 8/8, digital SVG + poster PNG via `/api/render` at the draft tier,
  watershed report figures, animation GIF. Real-run-only findings baked into the harness:
  (1) `serve.py`'s path-traversal guard resolves+rejects the repo's NAS `output/` symlink, so
  `global-setup.js` stages a REAL (non-symlinked) served root (`web/` + `deploy/output/`) served via
  `--web-root <staged>`; staging runs at Playwright config load, not the `globalSetup` hook (readiness
  is probed first). (2) A Clark `/api/render` proof is **~6 min** — the full-Washington GIS load
  dominates (county clip → SVG → PNG is ~13s once reprojected); `RENDER_TIMEOUT_MS` default → 600s.
  (3) County value must be the Census `NAME` `Clark` (not `NAMELSAD`); the county clip needs the
  Census counties shapefile at `/tmp/counties_shp/` (public-domain, documented in the e2e README, not
  committed). Committed `f01a0c3`; spec `agent-os/specs/2026-09-11-alpha-journey-e2e/`; retrospective
  `agent-os/retrospectives/2026-09-12-epoch-24-alpha-journey-e2e.md`.

- **Epoch 14 DONE (2026-09-01) — license-free climate source (#60), PRISM Rights gate
  RETIRED.** Swapped the year-over-year / watershed-report climate dependency from PRISM
  (not public domain — its commercial-use gate blocked selling any PRISM-derived asset) to
  **NOAA NCEI nClimGrid-Monthly** (U.S. federal public domain, free to sell with attribution).
  New pure offline **`src/climate_grid.py`** (numpy-only: `band_for_month` /
  `cells_from_lonlat` / `fill_nodata`, `ClimateGridError`) holds the sampling math so it's
  offline-testable under the "tests never import `tools/`" rule — **`tests/test_climate_grid.py`
  (9 tests)**. New non-offline **`tools/nclimgrid_flow.py`** `NClimGridClimateProvider(root,
  lon,lat)` — drop-in for `PrismClimateProvider` behind the existing
  `src.historical_flow.ClimateProvider` seam; nClimGrid is a stacked NetCDF addressed by band
  (GDAL NETCDF driver), rasterio **lazy-imported** so the module is GDAL-free at import. New
  **`tools/nclimgrid_fetch.py`** stages the two NetCDFs (`prcp` 1.47 GB + `tavg` 1.06 GB, 1579
  bands = Jan 1895 → Jul 2026) with a Content-Length check (caught + fixed a silent truncation).
  Provider is selectable via **`--climate-source {nclimgrid,prism}` (default nclimgrid)** through
  one `_make_provider` factory in `render_state_yoy.py`, threaded into
  `report_common.load_watershed_series` / `build_watershed_report.py`. **Real-data validation:**
  nClimGrid-vs-PRISM Dec-2017 Salmon Creek precip agree to **0.6%** (254.4 vs 255.8 mm); full
  engine peak-flow ratios 0.987 (2017) / 1.091 (2015). Suite **666 passing** (+9); no
  `PIPELINE_STAGES` / `src.historical_flow` / `src.monthly_flow` edit → default render
  byte-identical. Spec `agent-os/specs/2026-09-01-license-free-climate/`. PRISM stays A/B-only via
  `--climate-source prism` and remains **non-sellable**.
- **#40 DONE (2026-08-31) — golden-output fixtures (Phase 10.1 close).** Gave the #39
  verifier a committed fixture + a second checksum dimension. **`src/raster.grid_checksum`**
  (pure/offline: versioned header + crs + canonical-LE transform/shape + nodata sentinel +
  NaN-canonical LE-float64 values → sha256; endianness/contiguity-stable). **Two-checksum
  golden registry** in `src/determinism.py`: new `Golden(svg_sha256, dem_mosaic_sha256=None)`
  value type; `load_registry` parses object form + #39 bare strings; `evaluate(..., dem_sha=)`
  adds a soft `dem_ok`; `record_golden` merges halves; `dump_registry`/`format_verdict` updated.
  **`tools/verify_determinism.py`** grew `--check-dem`/`--dem` (county-aware DEM clip via
  `county_boundary` bounds so a county golden doesn't over-acquire the state's 3DEP) and a
  fixed latent `export_paths` str→`Path` crash in `_render_once`. **Committed fixture**
  `tests/fixtures/golden/registry.json` — **Wahkiakum, WA** (HUC4 1708): SVG sha
  `3c725d66…6457fafc` (run-to-run OK, cross-host invariant) + county-scoped DEM mosaic sha
  `a84769ec…a7c6ae92a` (single tile `USGS_1_n47w124.tif`, reproducible twice — **same-host
  regression only**, GDAL/PROJ-version sensitive; the SVG sha is the stronger invariant).
  Suite **644 passing** (+14), node 11+8; no `PIPELINE_STAGES` touched (2D byte-identical).
  Spec `agent-os/specs/2026-08-31-golden-output-fixtures/`. **#41 (real-data smoke harness)
  remains.** Uncommitted: `src/raster.py`, `src/determinism.py`, `tools/verify_determinism.py`,
  `tests/{test_raster,test_determinism}.py`, `tests/fixtures/golden/registry.json`, spec +
  roadmap/HANDOFF edits (commit pending — separate `commit item #40`).
- **Epoch 12 DONE (2026-08-31) — watershed report analytics (#48–#55).** Promoted the
  one-off `notebooks/salmon_creek_yoy.ipynb` into a reusable, credible watershed report.
  Spec `agent-os/specs/2026-08-30-watershed-report-analytics/`. One pure numpy-only
  offline `src/` module holds all statistics: **`src/flow_metrics.py`** (#48 peak/low/COT/
  flashiness/seasonal-ratio/flow-duration; #49 Mann-Kendall + Sen's slope, percentile
  rank, anomaly, rolling 30-yr normals; #53 subset/outlet/longitudinal helpers; #50
  bias/r/NSE/RMSE/seasonal-skill + `validate`; #51 `align_index`/`correlate`) — the #50/#51
  validation half was folded in from a former `src/flow_validation.py` (one combined
  analysis module). Heavy reads behind seams in `tools/`: `nwis_gauge.py`
  `GaugeProvider` (NWIS monthly means + site location, snapshotted), `climate_index.py`
  `ClimateIndexProvider` (ONI/PDO), `prism_fetch.py --start/--end` back-catalog (#52).
  Report assembly: **`tools/report_common.py`** (shared load + reach selection + 7-panel
  recipe) + **`tools/build_watershed_report.py`** CLI (#54); web report view (#55) —
  `web/shared/ux.css` components + `web/shared/hydro-ux.js` helpers + `web/report.html`.
  **Notebook (#54 task 7.3)** refactored to a thin `report_common` driver (deep-record,
  validation, low-flow/salmon, ENSO sections) and re-executed end-to-end via nbconvert on
  the GIS/NAS host — all cells run, 7 panels render inline. Gotcha: the setup cell
  `os.chdir(REPO)` so `report_common`'s repo-root-relative caches resolve under nbconvert
  (CWD = the notebook dir otherwise). **Credibility finding (#50):** the first run scored
  the basin *outlet* vs the gauge (NSE=−9.86, bias=+166.9) — the outlet is the basin mouth
  ~23 km / ~3.7× drainage below the mid-watershed Battle Ground gauge. Snapping to the
  model reach *at the gauge* (`gauge_reach_index` via the NWIS site lat/lon, idx 597, 10.3 m)
  → **r=0.78, NSE=+0.50, bias=+18.6, RMSE=44.9**; verdict "weak" only because NSE misses the
  0.50 cutoff by 0.0007. Suite: **630 passing**, recipe roundtrip 11 + report helpers 8, no
  regressions; no `PIPELINE_STAGES` touched (2D default byte-identical). Retrospective:
  `agent-os/retrospectives/2026-08-31-epoch-12-watershed-report.md`. Implementation report:
  `agent-os/specs/2026-08-30-watershed-report-analytics/implementation/report.md`. **Rights
  gate:** no PRISM-derived report/animation ships commercially until the PRISM arrangement
  is documented. Uncommitted: the #50 reach-snapping additions to `tools/{report_common,
  nwis_gauge,build_watershed_report}.py` + `notebooks/salmon_creek_yoy.ipynb` + the new
  retro/report + roadmap/HANDOFF edits (commit pending).
- **Epoch 10 partial — roadmap reconciled (2026-08-31).** Commit `87c64fd` (2026-08-30)
  landed #39 (determinism verifier: `src/determinism.py` core + `tools/verify_determinism.py`),
  #42-offline (`tests/test_dem_alignment.py` mosaic-before-warp #32 guard on hand-built
  grids), and #43 (status automation: `src/status.py` + `tools/update_status.py`). Roadmap
  #39/#43 now ticked `[x]`; #42 stays `[ ]` (its real-tile half is bundled into #41's smoke
  harness) with an evidence note; **#40 (golden fixtures) and #41 (real-data smoke harness)
  remain** — both need a GDAL/NAS host. Spec
  `agent-os/specs/2026-08-30-verification-and-real-data-confidence/`.

## Current state (2026-08-30)

- **Epoch 11.5 #56/#57 fulfillment core — implemented, commit pending.** The
  reproducible, rights-compliant **order → deliverable plan → manifest** core for
  made-to-order county watershed prints (Revenue Validation gate). Spec
  `agent-os/specs/2026-08-30-order-fulfillment/`. New **`src/fulfillment.py`** (stdlib-only,
  imports only stdlib + `src.config` `SUPPORTED_REGIONS`; not in `PIPELINE_STAGES`):
  frozen value objects (`Order`/`StyleSpec`/`Size`/`DataSource`/`Deliverable`/
  `DeliverablePlan`), injectable `ORDER_STYLES`/`SIZES` catalogs, `build_order`
  (validate-at-boundary/fail-fast → frozen `Order`, no payload mutation), **Rights gate**
  `assert_sellable` (refuses any `uses_prism` style; the two approved directions
  `neon-basin`/`elevation-tint` are PRISM-free), `attribution_line`/`title_block`
  (deterministic USGS credit), `deliverable_plan` (add-on-order-independent), and
  `fulfillment_manifest` (checksums must cover the plan exactly → `sort_keys`
  byte-identical for equal inputs). TDD: `tests/test_fulfillment.py` (29 tests, 4 groups).
  New non-offline **`tools/fulfill_order.py`** executor (outside the suite): `--order
  order.json`/flags → `build_order` → dispatch on `StyleSpec.renderer` (`pipeline` =
  neon-basin county clip via `render_common`; `mono` fails fast → use `neon-basin`) →
  stamp title block into the SVG → export each plan item at `Size.px` (PNG via `rasterize`,
  PDF via `rsvg-convert`, SVG, license) → sha256 → manifest at
  `output/orders/<order_id>/`. Docs: spec `sample_order.json` + `presets.md`;
  `implementation/report.md`. Suite: **573 passing** (+29), recipe roundtrip 11, no
  regressions; no `PIPELINE_STAGES` touched (2D default byte-identical). **Real smoke
  (Clark County, WA):** clipped 11,374 flowlines from HUC4 1708, 4 deliverables +
  manifest, title block stamped correctly. **Reproducible re-order:** first re-run's PDF
  sha differed (cairo stamped a wall-clock PDF CreationDate) → fixed by pinning
  `SOURCE_DATE_EPOCH=0` on the `rsvg-convert` call; two full re-runs now yield a
  byte-identical manifest (`ed669ae0…`). Roadmap #56/#57 stay `[ ]` (listing + intake +
  funnel ops live in `agent-os/product/revenue-ledger.md`, not code — a status note under
  Epoch 11.5 records the code core landed). **Known executor caveat:** the rasterized
  print takes the county's natural aspect at the ordered width (18x24 → 5400×5862, not
  the full 5400×7200 canvas the plan/manifest record). Smoke needs the public Census
  county/state boundary shapefiles staged under `/tmp/{counties,states}_shp` (not
  repo-tracked).

## Current state (2026-08-25)

- **Epoch 9 DONE (2026-08-25) — codebase health & maintainability (#33–#38).** A
  2026-08-25 audit surfaced maintainability debt (triplicated `clip_flowlines`,
  scattered `EPSG:5070` literal, hand-mirrored `STATE_HUC4`, duplicated `web/` view
  helpers, missing `test_pipeline.py`, uncommitted noise, zero retrospectives). Spec
  `agent-os/specs/2026-08-25-codebase-health-cleanup/`. Landed: **#37** planning
  commit (`tests/test_pipeline.py`); **#33** shared `clip_flowlines` (`extra_vaa_cols`/
  `include_id`, both mono mirrors deleted, `decc9cd`); **#34** `src/crs.py:INTERNAL_CRS`
  (`1351321`); **#35** `STATE_HUC4` derived from `REGION_HUC4` (`d7d46fd`); **#36**
  six `web/` view helpers extracted into `hydro-ux.js` (`0c0ba45`); **#38** housekeeping
  + retrospective closeout — reverted the `/com` corruption, CLAUDE.md `ruff`/`node`
  commands + "Known debt / gotchas" + repaired the hydro-ux.js view-logic claim, first
  `agent-os/retrospectives/` note — `2026-08-25-epoch-9-codebase-health.md` (`6c3038a`).
  Suite green (527), recipe roundtrip
  green (11). Hard invariant held: offline suite green + 2D default output
  byte-identical (the only render-affecting change, #34's constant, is value-identical;
  a real GDAL svg_sha256 compare wasn't possible offline — carry-forward).
- **Epoch 8 #32 DONE (2026-08-25) — terrain-print real-tile closeout.** The real
  WA statewide auto-acquire run surfaced a bug the offline fakes couldn't: `normalize_dem`
  warped each 1°×1° 3DEP tile to EPSG:5070 independently, so per-tile output resolution
  drifted with latitude and the warped tiles no longer shared a pixel grid. Fixed by
  mosaicking the tiles in their shared source CRS first, then warping the single mosaic
  once; `_require_aligned` now compares pixel sizes with a relative tolerance (last-float-
  digit warp drift mosaics, a genuine tier change still rejected). Bug-fix only, no new
  `src/` capability; 12 raster tests green (`0954c69`). Retrospective:
  `agent-os/retrospectives/2026-08-25-epoch-8-terrain-print.md` (`d44dad1`) — the lesson
  is that injected-fake offline coverage exercised only the reprojector's identity
  short-circuit, so the real-tile run first fired the EPSG:4269→5070 warp branch.
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
  **Real NAS migration DONE (2026-08-17):** both `output/` (352 files) and
  `datasets/` (6796 files, 18.8 GiB) migrated onto the Synology NAS
  (`/Volumes/home/data/hydro-art/{output,datasets}`); local paths are now directory
  symlinks. Required a fix (`3d90f4e`): `shutil.move`'s cross-device `copy2` fallback
  calls `os.chflags`, which the SMB share rejects with `OSError(EINVAL)`, aborting the
  move — replaced with `move_file` (copyfile + best-effort copymode, no flags). Gotcha:
  a stray `.DS_Store` left in a source dir blocks the auto-symlink (source not fully
  drained); remove it and re-run to finish the symlink step. **Verified end-to-end** via
  a full `build.py --region Oregon`: read all GDBs through the `datasets` symlink
  (`datasets/nhdplus_hr/1801/…`, `datasets/wbd/{17,18}/…`), download+extract stages
  short-circuited (**zero downloads/network**, first stage to log was `validate`),
  rendered 1.77M segments, and wrote `output/oregon.svg` (1,062,115,316 B) back through
  the `output` symlink onto the NAS — exit 0. `.gitignore` gained slash-less `output`
  and `datasets` entries so the symlinks aren't shown as untracked (`25af46e`,`34a5bea`).
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
