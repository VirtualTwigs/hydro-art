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
opt-in render-only monotonic repair, `render_z`), TDD-first and offline.

**Task Group 5, mesh slice (roadmap item 16) implemented 2026-07-30** — adaptive
error-bounded terrain mesh in `src/mesh.py` (greedy TIN, crack-free, nodata-aware,
deterministic hashes), TDD-first and offline. Decision #3 (mesh/error budget)
resolved as error-bounded max-vertical-deviation.

**Task Group 5, scene slice (roadmap item 17) implemented 2026-07-30** — 3D scene
assembly in `src/scene.py` (`SceneModel` joining terrain, Z-rivers, deduped
materials, cardinal/axis annotations, camera presets, and display-only
exaggeration; deterministic `scene_hash`; no browser state), TDD-first and
offline. Group 5 is now complete. Group 6 (GLB/export) is still blocked on the
open decision #4 (GLB-vs-OBJ).

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

- [x] Generate deterministic clipped terrain meshes at bounded LODs. (Item 16
  `src/mesh.py`: `build_terrain_mesh` = greedy error-bounded TIN (Garland–Heckbert
  incremental insertion) that refines until every DEM sample is within
  `error_budget_m`; crack-free fan retriangulation with degenerate-fan dropping;
  nodata-footprint triangles dropped; `max_points` cap; `TerrainMesh` carries
  true-meter positions, boundary_id, lod, achieved `max_error_m`, source-raster
  + deterministic geometry hashes. `mesh_from_dem` selects a pyramid level.
  `tests/test_mesh.py`, 8 tests on synthetic grids.)
- [x] Assemble mesh, rivers, materials, annotations, and camera metadata into a scene model.
  (Roadmap item 17 `src/scene.py`: `assemble_scene` composes a `TerrainMesh`,
  Z-attributed `ElevatedLine`s, and watershed `segment_colors` into an immutable
  `SceneModel` — deduped `Material`s, N/S/E/W `CardinalAnnotation`s + `AxisInfo`
  from bounds, deterministic top/isometric/south `CameraPreset`s, and a
  display-only `DisplaySettings`; carries no browser state and a deterministic
  `scene_hash`. `tests/test_scene.py`, 8 tests.)
- [x] Validate 1× physical scale versus display-only exaggeration. (`SceneModel`
  stores terrain + river geometry at true 1× meters with immutable source Z;
  `render_river_vertices` applies `render_z = source_z·exaggeration + lift` only
  on demand, and a test asserts terrain positions/geometry_hash are invariant to
  exaggeration while `scene_hash` reflects the display change.)

### Task Group 6: GLB/export and browser handoff

- [x] Select a GLB-writing strategy that preserves testability and deterministic output.
  (Item 19 `src/export3d.py`: `scene_to_glb` — a pure-stdlib binary-glTF writer,
  terrain as `TRIANGLES` + rivers as `LINE_STRIP`, per-watershed PBR materials,
  4-byte-aligned buffer views, `sort_keys` JSON chunk → byte-deterministic, no
  external glTF dependency.)
- [x] Emit manifest with source/raster/geometry hashes and settings.
  (`build_manifest` → JSON with `scene_hash`, `terrain_geometry_hash`,
  `source_raster_hash`, exaggeration/lift/lod/error budget, material + camera
  lists, counts, and per-asset SHA-256; `export_scene` bundles GLB + OBJ + MTL +
  manifest through an injected `writer` seam. `tests/test_export3d.py`, 8 tests.
  Resolves decision #4: GLB + OBJ this epoch, terrain GeoTIFF deferred.)
- [ ] Generate browser-ready preview assets; replace synthetic Z in the 3D lab.
  (Roadmap item 18 — browser/Phase G work on `web/3d.html`; next up.)
- [ ] Verify Clark County, WA end-to-end before statewide rollout. (Depends on a
  real (non-offline) DEM run; the deterministic offline path is covered by tests.)

## Suggested verification gates

1. Unit tests for each pure geometry/raster transform plus fixture-backed tests for I/O seams.
2. A tiny known DEM with hand-computed bilinear results and nodata cases.
3. A Clark County smoke build with source/datum/units printed in its manifest.
4. Determinism test: identical cached DEM + hydrography + settings → identical mesh/GLB hashes.
5. Regression suite: the present 2D pipeline remains offline-testable and unchanged by default.
