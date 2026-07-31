# Task Breakdown: DEM-backed Elevation & 3D Modeling

## Status

**Task Group 1 (roadmap item 11) implemented 2026-07-30** — elevation config
contract + provenance model + injected protocols, TDD-first, no change to
default 2D behavior.

**Task Group 2 (roadmap item 12) implemented 2026-07-30** — 3DEP discovery +
cache over the deterministic 1-degree COG grid on the `prd-tnm` S3 bucket
(`src/dem.py`), TDD-first, offline. Delivery decisions #1 (AWS S3 COGs) and #2
(normalize to NAVD88) resolved in `planning/requirements.md`. The 1 m `local`
tier is deferred (needs project-based discovery).

**Task Group 3 (roadmap item 13) implemented 2026-07-30** — DEM raster
normalization in `src/raster.py` (mosaic/clip/reproject-seam to EPSG:5070,
deterministic pyramids, bilinear sampling with coverage/nodata diagnostics),
TDD-first and offline on synthetic numpy grids.

**Task Group 4 (roadmap items 14 & 15) implemented 2026-07-30** — terrain
sampling service (`src/terrain.py`: densification + injected sampler) and river
Z attribution/QA (`src/hydro_z.py`: `ElevatedLine`, downstream-inversion QA,
opt-in render-only monotonic repair, `render_z`), TDD-first and offline. Groups
5–6 remain planning-only and are blocked on the two still-open decisions (mesh
budget, GLB-vs-OBJ).

## Proposed implementation groups

### Task Group 1: Elevation contract and configuration — done

- [x] Define `ElevationSettings`, resolution tiers, source/provenance dataclasses, and output
  selection without changing default 2D behavior. (`ElevationSettings` +
  `DEFAULTS["elevation"]` + `SUPPORTED_ELEVATION_SOURCES`/`_TIERS`/`SUPPORTED_CACHE_POLICIES`
  in `src/config.py`; `ElevationProvenance` immutable metadata in `src/elevation.py`.
  Elevation is **off by default** and unwired from every pipeline stage, so a
  default build stays byte-identical 2D.)
- [x] Add boundary validation, YAML/CLI precedence, and focused config tests.
  (`_coerce_elevation` validates source/tier/cache_policy allowlists +
  `vertical_exaggeration > 0`; `--elevation/--no-elevation`, `--elevation-source`,
  `--elevation-tier`, `--vertical-exaggeration`, `--cache-policy` deep-merged per sub-key in
  `src/cli.py`; `tests/test_elevation_config.py`, 10 tests.)
- [x] Establish injected protocols for tile discovery, raster reading, and sampling.
  (Plain `Protocol`s `TileDiscoverer`/`RasterReader`/`ElevationSampler` + value objects
  `TileRef`/`ElevationSample` + `ElevationError(AcquisitionError)` in `src/elevation.py`;
  `tests/test_elevation.py`, 9 tests. Decision applied: preserve source vertical
  reference only — provenance records datum/units verbatim, never normalizes.)

### Task Group 2: 3DEP discovery and cache — done

- [x] Select/document the primary USGS discovery/download mechanism. (AWS S3 COGs on
  `prd-tnm`; deterministic 1-degree grid, documented in `src/dem.py` module docstring and
  `planning/requirements.md`.)
- [x] Discover tiles by region boundary and resolution policy; cache and verify assets.
  (`geographic_cells` + `ThreeDEPDiscoverer.discover_tiles` for `preview`/`state`; `local`
  raises `ElevationError`. `acquire_dem` bridges each `TileRef` to a `FileDescriptor` and
  reuses the existing `Cache`/`DownloaderLike` for reuse/refresh + checksum; builds per-tile
  `ElevationProvenance`.)
- [x] Add offline fixture/fake tests for discovery, caching, provenance, and cache hits.
  (`tests/test_dem.py`, 9 tests: grid math, per-tier URLs, unsupported tier, download,
  cache-hit reuse, refresh re-download, provenance fields, determinism.)

### Task Group 3: Raster normalization and sampling — done

- [x] Implement lazy-loaded mosaic/clip/reproject behavior to EPSG:5070.
  (`src/raster.py`: `RasterGrid`/`GridTransform` value objects; pure `mosaic`
  (aligned tiles, CRS/pixel-size guarded) + `clip_grid` (pixel-snapped window);
  `normalize_dem` orchestrates read → reproject → mosaic → clip → pyramid via
  the injected `RasterReader`/`RasterReprojector` GDAL seams, preserving each
  tile's vertical datum/units verbatim.)
- [x] Build deterministic preview/state/local raster pyramids. (`build_pyramid`
  = 2x2 block-mean, nodata-aware, finest-first, bounded by `max_levels`.)
- [x] Implement bilinear sampling with nodata/coverage diagnostics and unit tests
  using tiny synthetic rasters. (`sample_bilinear` + `GridSampler`
  (`ElevationSampler`): interior/edge-clamp interpolation, `covered=False`
  outside extent, `nodata=True` when any neighbor is nodata — never a silent
  substitution. `tests/test_raster.py`, 11 tests with hand-computed results.)

### Task Group 4: Z-enabled hydrography and QA — done

Split across roadmap items 14 (terrain sampling service) and 15 (Z attribution & QA).

- [x] Densify flowlines and attribute sampled elevation to every generated vertex.
  (Item 14 `src/terrain.py`: `densify_line` at DEM-cell spacing preserving
  originals; `TerrainSampler` over an injected `ElevationSampler` →
  `SampledLine`/`SampledPoint` with coverage/nodata diagnostics;
  `dem_cell_size`/`sampler_for_dem` select a pyramid level. Item 15
  `src/hydro_z.py`: `attribute_line` → `ElevatedLine` (immutable source Z per
  vertex, original 2D path preserved, nodata count, dem_id/interpolation).)
- [x] Add downstream-profile QA and explicit render-only monotonic repair policy.
  (`profile_qa` flags downstream inversions (never alters); `repair_monotonic` +
  `RepairPolicy` gate an opt-in, render-only non-increasing water surface that
  leaves source Z intact; `render_z` = source_z·exaggeration + lift.)
- [x] Add integration tests from a small DEM fixture through clipped flowline
  output. (`tests/test_terrain.py` 8 + `tests/test_hydro_z.py` 8, incl. a
  synthetic single-row DEM with a deliberate uphill bump flagged as an inversion
  and removed by the opt-in repair.)

### Task Group 5: Terrain mesh and 3D scene

- [ ] Generate deterministic clipped terrain meshes at bounded LODs.
- [ ] Assemble mesh, rivers, materials, annotations, and camera metadata into a scene model.
- [ ] Validate 1× physical scale versus display-only exaggeration.

### Task Group 6: GLB/export and browser handoff

- [ ] Select a GLB-writing strategy that preserves testability and deterministic output.
- [ ] Emit manifest with source/raster/geometry hashes and settings.
- [ ] Generate browser-ready preview assets; replace synthetic Z in the 3D lab.
- [ ] Verify Clark County, WA end-to-end before statewide rollout.

## Suggested verification gates

1. Unit tests for each pure geometry/raster transform plus fixture-backed tests for I/O seams.
2. A tiny known DEM with hand-computed bilinear results and nodata cases.
3. A Clark County smoke build with source/datum/units printed in its manifest.
4. Determinism test: identical cached DEM + hydrography + settings → identical mesh/GLB hashes.
5. Regression suite: the present 2D pipeline remains offline-testable and unchanged by default.
