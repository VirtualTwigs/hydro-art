# Tasks — Golden-output fixtures for one small region (#40)

## Group 1 — DEM mosaic fingerprint · offline (`src/raster.py`)

- [x] 1.1 Write 3–5 tests in `tests/test_raster.py` for `grid_checksum`: (a) identical
  grids → identical hash; (b) a change in each of values / transform / crs / nodata →
  different hash; (c) NaN in values is canonical (two grids with NaN in the same cell hash
  equal, and `nan != nan` doesn't break it); (d) endianness/contiguity-stable (a
  non-contiguous or big-endian view of the same data hashes identically). Run ONLY these.
- [x] 1.2 Implement `grid_checksum(grid: RasterGrid) -> str` — versioned header + crs +
  transform/shape (canonical LE) + nodata sentinel + C-contiguous LE float64 values with
  NaN normalized. Numpy + hashlib only. `normalize_dem` untouched.
- [x] 1.3 Group-1 tests green.

## Group 2 — Two-checksum golden registry · offline (`src/determinism.py`)

- [x] 2.1 Update/extend `tests/test_determinism.py` for the two-checksum schema: object-form
  registry parse (svg + optional dem), bare-string legacy value still loads as svg-only,
  DEM golden match / mismatch / unrecorded (soft), `record_golden` merges both halves,
  `format_verdict` shows a dem line, `ok`/`needs_recording` account for DEM. Run ONLY these.
- [x] 2.2 Implement `Golden` value type + evolve `load_registry` / `evaluate(..., dem_sha=)`
  / `record_golden` / `format_verdict` / `DeterminismVerdict` (add `dem_sha`,
  `golden_dem_sha`, `dem_ok`). Stdlib-only (+`src.config`). Preserve #39 SVG semantics.
- [x] 2.3 Group-2 tests green.

## Group 3 — CLI wiring + committed fixture · non-offline (`tools/verify_determinism.py`)

- [x] 3.1 Add `--check-dem` / `--dem <path>` flags; compute the region's DEM mosaic checksum
  via `--dem` load or `acquire_dem_for_settings` → `normalize_dem` → `grid_checksum`
  (reusing the `render_terrain_print.py` wiring), clipped to the region; degrade to a clear
  "dem: skipped" on any DEM error so the SVG check stands. Feed `dem_sha` into
  `evaluate`/`record_golden`. **County-aware:** with `--county` (and no `--dem-region`),
  clips the DEM to the county polygon bounds so a county golden doesn't over-acquire the
  whole state's 3DEP; also fixed a latent #39 `export_paths` str→`Path` bug in `_render_once`.
- [x] 3.2 Smoke on the GDAL/NAS host: picked **Wahkiakum, WA** (smallest WA county, HUC4 1708),
  ran the verifier (`--record`) end-to-end (full GDAL pipeline, twice) → run-to-run OK; also
  computed the county-scoped DEM mosaic checksum twice (reproducible). Numbers below.
- [x] 3.3 Commit-ready fixture: `tests/fixtures/golden/registry.json` has the Wahkiakum entry
  with **both** halves (SVG sha cross-host invariant + DEM mosaic sha same-host regression).

## Group 4 — Close out · offline

- [x] 4.1 Full offline suite green (regression check) + the two node harnesses; confirm 2D
  default output byte-identical (no `PIPELINE_STAGES` touched). **644 passed**, node 11+8.
- [x] 4.2 Write `implementation/report.md`; update `HANDOFF.md`; tick roadmap #40.
- [ ] 4.3 (On `commit item #40`) — separate, explicit step.

## Smoke numbers (filled during 3.2)

- **County:** Wahkiakum, WA (smallest WA county by area; HUC4 1708). County clip:
  2,313,111 → 19,395 flowlines; 19,375 segments; SVG 3,701,866 bytes.
- **SVG sha256** (run-to-run OK, cross-host invariant):
  `3c725d66bbc764f93976339827fc8b7509458dff754f63ad9865c5f26457fafc`
- **DEM mosaic sha256** (county-scoped, reproducible twice; same-host regression —
  GDAL/PROJ-version sensitive, not a cross-host invariant): single 3DEP tile
  `USGS_1_n47w124.tif` → `a84769ec01ae9e59122db80b9b77a49e02aa04665f1214b2e886194a7c6ae92a`
- **PNG rasterization:** skipped (resvg unavailable on host) — svg_sha256 stands.
