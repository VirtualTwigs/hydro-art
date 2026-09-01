# Implementation report — Golden-output fixtures for one small region (#40)

Shipped 2026-08-31. Closes Phase 10.1 by giving the #39 determinism verifier something
committed to compare against, plus a second checksum dimension (the DEM mosaic) that
exercises the real GDAL warp/mosaic path the offline fakes only simulate.

## What shipped

### Group 1 — DEM mosaic fingerprint (offline, `src/raster.py`)
`grid_checksum(grid: RasterGrid) -> str` — a deterministic sha256 over a versioned header
(`hydro-art.raster.v1`) + crs + transform/shape (canonical little-endian) + a nodata
sentinel + C-contiguous LE float64 values with NaN normalized. Numpy + hashlib only;
`normalize_dem` untouched. 5 tests in `tests/test_raster.py` (stable/hex, changes with
each of values/transform/crs/nodata, NaN-canonical, endianness/contiguity-stable).

### Group 2 — Two-checksum golden registry (offline, `src/determinism.py`)
Introduced the `Golden(svg_sha256, dem_mosaic_sha256=None)` frozen value type. `load_registry`
now returns `dict[str, Golden]` and parses both the object form and #39-era bare strings
(svg-only). Added `dump_registry` (omits the dem key when None). `evaluate(..., dem_sha=None)`
adds a third `dem_ok` (True/False/None) dimension; `record_golden` merges halves so recording
one never clobbers the other. `format_verdict` prints a dem line. Stdlib-only (+`src.config`);
#39 SVG semantics preserved. 19 tests in `tests/test_determinism.py`.

### Group 3 — CLI wiring + committed fixture (non-offline, `tools/verify_determinism.py`)
Added `--check-dem` / `--dem <path>` (+ `--dem-region`/`--dem-cellsize`/`--dem-nodata`/
`--dem-tier`/`--dem-tile-budget`/`--dem-refresh`). `_dem_mosaic_sha` computes the mosaic
checksum via a supplied `.npy` or auto-acquires real 3DEP relief
(`acquire_dem_for_settings` → `normalize_dem` with the `src.raster_io` reader/reprojector →
`grid_checksum`). **County-aware:** with `--county` (and no `--dem-region`) it clips the DEM
to the county polygon bounds so a county golden doesn't over-acquire the whole state's 3DEP.
Any DEM error degrades to a clear yellow "dem: skipped" so the SVG check is never held hostage.
Also fixed a latent #39 bug: `_render_once` now coerces `export_paths` to `Path` (they arrive
as strings), which had crashed the PNG-rasterization step after a passing verdict.

## Committed fixture

`tests/fixtures/golden/registry.json` — **Wahkiakum, WA** (smallest WA county, HUC4 1708):
- `svg_sha256` = `3c725d66bbc764f93976339827fc8b7509458dff754f63ad9865c5f26457fafc`
  (run-to-run OK over two full GDAL pipeline renders — the cross-host invariant)
- `dem_mosaic_sha256` = `a84769ec01ae9e59122db80b9b77a49e02aa04665f1214b2e886194a7c6ae92a`
  (county-scoped, single 3DEP tile `USGS_1_n47w124.tif`, reproducible twice)

## Honesty caveats

- The **SVG sha is the strong cross-host invariant** (pure-Python render). The **DEM mosaic
  sha is a same-host regression only** — it fingerprints the real GDAL/PROJ warp/mosaic, whose
  last-digit output is library-version sensitive. This is recorded in the module docstring and
  the registry semantics (DEM golden is opt-in via `--check-dem`; unrecorded is a soft
  "record me", never a hard failure).
- PNG rasterization was skipped on the smoke host (resvg unavailable); the svg_sha256 check
  stands on its own (byte-identical over two renders).

## Regression / invariants

- Full offline suite: **644 passed** (was 630 at Epoch 12 close; +14 from grid_checksum +
  registry evolution). Node harnesses: 11 + 8 green.
- 2D default output byte-identical: no `PIPELINE_STAGES` stage touched; `grid_checksum` and the
  registry changes are pure/offline and outside the pipeline.
