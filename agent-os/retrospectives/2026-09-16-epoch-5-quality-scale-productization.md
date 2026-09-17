# Retrospective — Epoch 5: Quality, scale, and productization (#20–#22)

_Closed 2026-08-13 (all items shipped). Retrospective written 2026-09-16 — a
latecomer; the practice started in Epoch 9 (#38), and Epoch 5 predated it. No
pre-analysis was written for any of the three items, so this is a narrative
closeout rather than a graded one._

## What the epoch was

Three parallel productization concerns that moved the project from "it renders"
to "it validates, scales, and delivers." Each item was `XL`-scoped (or close)
and sliced into multiple offline passes:

1. **#20 — Accuracy validation suite.** Can we quantify how well the DEM subsystem
   actually samples ground truth?
2. **#21 — Regional scale & offline packaging.** Can we add states, cap tile
   downloads, verify a cache is portable, and give the DEM a real entry point?
3. **#22 — Print/experience modes.** Can we produce a shaded-relief hillshade, a
   camera path for animation, and package both into a browser-loadable experience
   document?

Hard constraint: all new modules pure/offline/deterministic, none wired into
`PIPELINE_STAGES`, no GDAL import at `src/` top-level, default 2D output
byte-identical. Held throughout.

## What shipped

### #20 — Accuracy validation suite (`43d1635`)

`src/accuracy.py` — numpy-free, GDAL-free. `error_metrics` (max/mean abs error,
RMSE, residuals; nodata/uncovered skipped, never zero-filled), `coverage_report`,
`crs_report` (verbatim from `ElevationProvenance`), `qa_rollup` (river-profile
inversions, structural-only so no `hydro_z` chain imported), `AccuracyReport` +
`validate_against_sampler` over the injected `ElevationSampler` seam.
`within_tolerance` verdict separates vertical accuracy (gating) from inversions
(reported, not gating). Tests: `tests/test_accuracy.py` (19 tests). Suite went
361 -> 380.

### #21 — Regional scale & offline packaging (6 slices, 8 commits)

| Slice | Commit | Module | Tests added |
|-------|--------|--------|-------------|
| Portable cache manifests | `f5997d8` | `src/manifest.py` | 13 |
| Tile-budget controls | `0825475` | `src/config.py`, `src/dem.py` | +8 |
| Package preflight planner | uncommitted at epoch close | `src/packaging.py` | +7 |
| Settings-driven DEM acquisition | uncommitted at epoch close | `src/dem.py` | +5 |
| Manifest packaging CLI | `14a2107` | `src/manifest.py` (formatters) + `tools/cache_manifest.py` | +4 |
| Idaho as fourth region | `fbb8960` | `src/config.py`, `src/datasets.py`, `src/counties.py` | +2 |
| Real DEM acquisition entry point | `cb992f5` | `src/dem.py` (`REGION_BOUNDS`, `region_bounds`) + `tools/acquire_dem.py` | +4 |

Key deliverables:
- **`src/manifest.py`**: `build_manifest` / `manifest_for_settings` / `write_manifest`
  / `read_manifest` / `verify_manifest` / `diff_manifests` / `format_verification` /
  `format_diff`. Cache-relative POSIX paths, wall-clock time excluded from the
  canonical form so equal cache state -> byte-identical JSON.
- **Tile-budget controls**: `ElevationSettings.tile_budget` (0 = unlimited),
  `count_tiles` preflight, `acquire_dem(max_tiles=...)` fail-fast before any
  download.
- **`src/packaging.py`**: `plan_package` -> frozen `PackagePlan` with
  `is_complete` / `within_tile_budget` / `is_ready`; `format_plan` human summary.
  Driven by `tools/package_cache.py`.
- **Idaho**: HUC4s `("1701","1704","1705","1706")` derived via
  `tools/derive_state_huc4.py Idaho --min-overlap-frac 0.01`. Bear River corner
  (HU2 16) omitted (same caveat as California's desert fringes). Three existing
  tests used "Idaho" as the canonical unsupported region — repointed to "Nevada."
- **Resumable jobs**: investigation confirmed already built (`Downloader` `.part` +
  HTTP `Range` resume + cache-skip). No new work needed.
- **`src/dem.py` `REGION_BOUNDS` + `region_bounds`**: Census per-state EPSG:4326
  envelopes (DEM counterpart to `REGION_HUC4`), drift-guarded against
  `SUPPORTED_REGIONS`. `tools/acquire_dem.py` drives `acquire_dem_for_settings`
  with a real `Downloader(UrllibFetcher())`.

Suite went 380 -> 462 across the six slices (+82 tests).

### #22 — Print/experience modes (3 slices, 3 commits)

| Slice | Commit | Module | Tests added |
|-------|--------|--------|-------------|
| Terrain-aware 2D hillshade | `a0674c4` | `src/hillshade.py` | 8 |
| Animation camera paths | `d22a0d1` | `src/camera.py` | 7 |
| Web delivery experience document | `2001a1e` | `src/delivery.py` + `web/experience.html` | 7 |

- **`src/hillshade.py`**: Horn's 3x3 `dz/dx`/`dz/dy` + ESRI/GDAL Lambertian
  illumination (azimuth/altitude/z_factor). Edge-replicated borders (no shape
  shrinkage). Nodata never invented — a cell or its 8-neighborhood touching nodata
  -> output sentinel (3x3 OR-dilation). `z_factor` is shading-only, never alters
  source Z. numpy + `src.raster` only.
- **`src/camera.py`**: `interpolate_camera` (lerp position/target/fov,
  normalized-lerp up), `camera_path` (open: `(n-1)*steps + 1` poses ending
  exactly on the last keyframe; loop: `n*steps` seamless cycle via a wrap
  segment). `math` + `src.scene` only.
- **`src/delivery.py`**: `hillshade_layer` (row-major shade, nodata->None,
  valid-only `value_range`), `camera_track`, `experience_document` (stable
  `sort_keys` JSON), `experience_json`. Mirrors `src/preview.py` conventions.
  `web/experience.html` loads a document, paints hillshade to `<canvas>`,
  plays/scrubs the camera track — `file://`-safe, `node --check` clean.

Suite went 401 -> 423 across the three slices (+22 tests).

## Invariants held

- **Offline suite:** 462 passing at epoch close (was 361 at entry; +101 across
  the epoch). No network, no GDAL, no real data touched by the suite.
- **2D default output byte-identical:** yes. No module is wired into
  `PIPELINE_STAGES`; all are parallel subsystems with their own entry points.
  Default `build.py` path is unchanged.
- **`PIPELINE_STAGES` untouched:** yes. No stage added, removed, or reordered.
- **Rights gate:** N/A — no new data source introduced. All modules operate on
  USGS public-domain data (sellable with attribution).
- **Import discipline:** `src/accuracy.py` imports only stdlib + `src.elevation`
  (numpy-free). `src/manifest.py` imports only stdlib + `src.datasets`/`config`/
  `cache`. `src/packaging.py` imports only stdlib + `src.manifest`/`datasets`/
  `config`/`cache`. `src/hillshade.py` imports only numpy + `src.raster`/
  `src.elevation`. `src/camera.py` imports only `math` + `src.scene`.
  `src/delivery.py` imports only `json` + `src.raster`/`src.camera`. All verified
  no heavy modules pulled in.

## What went well

- **Slicing XL items into offline-first passes was the right call.** Each of the
  three items was scoped as XL, but the slicing discipline (manifests first, then
  budget, then planner, then region, then entry point) meant each pass was a
  self-contained TDD cycle with a clear boundary. No slice depended on GDAL or
  real data, so every one ran in the offline suite.

- **Resumable jobs were already built.** The #21 investigation that confirmed
  `Downloader`'s `.part` + `Range` resume + cache-skip meant no new work was
  needed. This is a genuine "the architecture already handles it" moment — the
  seam-first design from Epoch 1 paid off.

- **Idaho repointing exercise caught three tests.** Adding Idaho to
  `SUPPORTED_REGIONS` broke three tests that used "Idaho" as the canonical
  unsupported region. This is a healthy signal — those tests were brittle to
  region expansion and the fix (repoint to "Nevada") is permanent.

- **`web/experience.html` is self-contained.** The experience viewer loads a JSON
  document, paints a canvas, and scrubs a camera track with zero dependencies
  beyond the browser. It stays `file://`-safe and `node --check`-clean, which
  means the web layer costs nothing to maintain.

## What was tricky

- **#21 was genuinely XL.** Six slices across manifests, config, DEM, packaging,
  regions, and CLI tooling. Each was individually clean, but the accumulated
  commit history (some committed, some pending at epoch close) made the
  in-progress state harder to track. The HANDOFF bullets for #21 are the longest
  in the project.

- **"Deferred to a GDAL/NAS host" recurs across all three items.** `#20`'s
  real-DEM accuracy harness, `#21`'s real-tile acquire+verify, and `#22`'s
  hillshade-over-river compositing all need a GIS environment the offline suite
  cannot provide. At epoch close these were honestly labeled as open, but the
  pattern of deferring the real-data validation to a future epoch is a recurring
  cost — it was the Epoch 8 lesson (mosaic-before-warp bug) all over again, just
  without a bug surfacing this time.

- **The `REGION_BOUNDS` drift guard is the right idea applied late.** The test
  that asserts `REGION_BOUNDS.keys() == SUPPORTED_REGIONS` catches future
  expansion mistakes, but Idaho was the fourth region before the guard existed.
  Oregon, Washington, and California were added without it. Write the drift guard
  at the same time as the first entry, not the fourth.

## Carry-forwards

- **Real-DEM accuracy harness** (`tools/accuracy_report.py` over `normalize_dem`
  output) — deferred from #20. The offline engine is tested; the tool that
  compares against real 3DEP tiles needs a GDAL/NAS host. Open, not passed.
- **Hillshade-under-river compositing** in a `tools/` print renderer over a real
  normalized DEM — deferred from #22. The hillshade function ships; blending it
  into a final print product is a non-offline follow-on. (Later picked up in
  Epoch 8 #30.)
- **Richer camera motion** — easing curves, Catmull-Rom smoothing, quaternion
  orientation — deferred from #22. The linear first cut is correct and
  sufficient for the initial experience document.
- **Bear River / HU2 16 coverage for Idaho** — the SE corner is omitted because
  the national WBD GDB wasn't locally available. A documented gap, not a bug.
- **Live `/api/experience` server route** over a real DEM — deferred from #22.

## Lessons

- **Slicing XL items into offline-first passes works.** The seam-first,
  inject-fake, test-offline discipline from Epochs 1-4 scaled cleanly to
  productization concerns. Each slice was independently useful and independently
  testable. Repeat this.
- **Write the drift guard with the first entry, not the fourth.** `REGION_BOUNDS`
  vs. `SUPPORTED_REGIONS` is the right invariant, but it should have existed when
  Oregon was the first entry, not when Idaho was the fourth. The cost of not having
  it was low (no bug), but the cost of having it early is zero.
- **"Already built" is a valid finding.** The resumable-jobs investigation saved
  real work by confirming the architecture already handled it. Don't invent new
  code when the existing seams suffice — but do write the investigation note so
  the finding is durable.
- **No pre-analysis was written for Epoch 5.** This is the same process
  regression later called out in the Epoch 16 retrospective. The practice of
  pre-registering risks before implementation would have sharpened the "what needs
  a real run" watch-list. Restore it for future epochs.
