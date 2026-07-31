# Implementation Report: DEM Elevation & 3D Modeling

## Task Group 1 — Elevation contract and configuration (roadmap item 11)

Implemented 2026-07-30, TDD-first. This is the configuration + provenance
*contract only*; no pipeline stage reads it yet (DEM acquisition is item 12), so
a default 2D build is unchanged.

### Confirmed art-direction decisions (applied here)

1. **Off by default** — `elevation.enabled = False`. Nothing in the pipeline
   reads `Settings.elevation`, so default builds stay byte-identical 2D.
2. **Preserve source vertical reference only** — `ElevationProvenance` records
   the DEM's own `vertical_crs`/`vertical_units` verbatim (including `None` when
   the source states none). There is deliberately **no** normalize-to-NAVD88
   option; that stays a later, explicit decision.
3. **Default resolution tier = `preview`** — the coarse, cheap tier. `state`/
   `local` escalate detail only when explicitly requested (no statewide 1 m
   default, per the non-functional budget constraint).

### What landed

- **`src/config.py`**
  - Allowlists: `SUPPORTED_ELEVATION_SOURCES = ("3dep",)`,
    `SUPPORTED_ELEVATION_TIERS = ("preview", "state", "local")`,
    `SUPPORTED_CACHE_POLICIES = ("reuse", "refresh")`.
  - `DEFAULTS["elevation"]` block (`enabled=False`, `source="3dep"`,
    `tier="preview"`, `vertical_exaggeration=1.0`, `cache_policy="reuse"`). Being
    a `DEFAULTS` key also means an `elevation:` YAML block no longer trips the
    "unknown config keys" warning in `load_yaml`.
  - `ElevationSettings` frozen dataclass + `_coerce_elevation` validator
    (tolerates a partial mapping like `_coerce_waterbodies`; validates the three
    allowlists and `vertical_exaggeration > 0`). New `elevation` field on
    `Settings`, wired through `build_settings`; exports updated.

- **`src/elevation.py`** (new)
  - `ElevationProvenance` immutable metadata: `source_product`, `source_url`,
    `acquisition_date`, `horizontal_crs`, `vertical_crs`, `vertical_units`,
    `resolution_m`, `checksum`, `processing_parameters`.
  - `build_provenance(...)` boundary validation: required identity fields
    (`source_product`/`source_url`/`acquisition_date`/`horizontal_crs`/`checksum`)
    non-empty, `resolution_m > 0`; vertical fields optional and preserved
    verbatim. Raises `ElevationError(AcquisitionError)` so `build.py` maps it to
    the acquisition exit code (2).
  - Value objects `TileRef` and `ElevationSample(value_m, covered, nodata)`.
  - Plain (non-`runtime_checkable`) protocols `TileDiscoverer`, `RasterReader`,
    `ElevationSampler` — the injected seams items 12/13/14 will implement with
    GDAL-backed classes while tests inject fakes. No heavy raster libs imported.

- **`src/cli.py`**
  - Flags `--elevation/--no-elevation` (BooleanOptionalAction),
    `--elevation-source`, `--elevation-tier`, `--vertical-exaggeration` (float),
    `--cache-policy`; collected under a nested `overrides["elevation"]` and
    **deep-merged** per sub-key in `resolve_settings` (mirrors the waterbodies
    precedence), so `defaults < YAML < CLI` holds per sub-key.

### Tests

- `tests/test_elevation_config.py` (10): defaults, partial-dict fill,
  invalid tier/source/cache_policy, non-positive exaggeration, YAML override,
  CLI-over-YAML per-sub-key precedence, and a guard that a default build keeps
  elevation disabled.
- `tests/test_elevation.py` (9): provenance records all fields, immutability,
  missing-required-field + non-positive-resolution rejection,
  `ElevationError ⊂ AcquisitionError`, absent vertical reference preserved as
  `None`, sample/tile value objects, and structural conformance of all three
  protocols against fakes.

### Verification

- New tests: **19 passed**.
- Full suite: **208 passed** (was 189; +19), no regressions.
- Smoke test: `resolve_settings([])` → elevation disabled/preview; flag
  combination applies tier/exaggeration/cache; invalid tier rejected with a
  user-facing `ConfigError`.
- `ruff` not installed in the offline venv; not run.

### Deferred (later task groups / gated on decisions)

Groups 3–6 (raster normalization/sampling, Z-hydrography, mesh/scene, GLB
export) remain planning-only. Groups 5–6 are blocked on the two still-open
decisions in `planning/requirements.md` (mesh/error budget, GLB-vs-OBJ). The
injected protocols added here are the seams those groups plug into.

## Task Group 2 — 3DEP discovery and cache (roadmap item 12)

Implemented 2026-07-30, TDD-first, fully offline. Delivers DEM tile discovery +
caching; no raster is opened or reprojected yet (that is item 13), so a default
2D build is still unchanged and never touches the network.

### Resolved decisions applied

1. **DEM delivery = AWS S3 COGs** on the USGS `prd-tnm` staged-products bucket
   (same host as the hydrography archives). The seamless 1"/13" products are
   staged one COG per 1°×1° cell named by its NW corner (`n45w124`), so
   discovery is deterministic and offline-constructible from a lon/lat bbox —
   no discovery API call, mirroring `datasets.py`'s region→URL mapping.
2. **Normalize to NAVD88.** 3DEP 1"/13" are natively NAD83 (EPSG:4269) /
   NAVD88 / meters, so normalization is identity for these tiers and recorded
   verbatim in each tile's provenance. A real transform for non-NAVD88 sources
   is deferred to the raster-normalization stage (item 13).

### What landed

- **`src/dem.py`** (new)
  - `DemProduct` + `TIER_PRODUCTS` registry: `preview`→`1` (1", 30 m),
    `state`→`13` (1/3", 10 m). `local` (1 m) intentionally absent.
  - `cell_name` / `geographic_cells`: deterministic 1-degree grid math from a
    lon/lat bbox (west-edge `floor`, north-edge `floor(lat)+1`), sorted output.
  - `ThreeDEPDiscoverer` (a `TileDiscoverer`): one `TileRef` per covering cell;
    accepts a shapely-like `.bounds` object or a 4-tuple; raises
    `ElevationError` for unsupported tiers (`local`) with a clear message.
  - `dem_descriptor`: bridges a `TileRef` to a `FileDescriptor`
    (`dem/<product_key>/<file>`) so the existing `Cache` + `DownloaderLike`
    provide resume/verify/record for free.
  - `acquire_dem`: discovers, downloads-or-reuses (reuse vs `refresh` policy),
    computes each tile's `sha256:` checksum, and builds a per-tile
    `ElevationProvenance` (source product/URL, injected retrieval date,
    EPSG:4269 / NAVD88 / meters, cell size, `{tier, delivery}` lineage).
    Returns `DemAsset(tile, path, provenance)` in deterministic order.

### Tests

- `tests/test_dem.py` (9): grid naming, `preview`/`state` URL + resolution,
  unsupported-tier rejection, registry contents, download+cache+provenance,
  cache-hit reuse (no re-download), `refresh` re-download, and determinism
  (same inputs → same tile URLs + checksums with a fixed clock).

### Verification

- New tests: **9 passed**. Full suite: **217 passed** (was 208; +9), no
  regressions. Smoke: Oregon bbox → 45 deterministic 1" tiles with correct
  `prd-tnm` COG URLs; `local` raises `ElevationError`.
- `ruff` not installed in the offline venv; not run.

### Deferred

The 1 m `local` tier (project/UTM-tiled, needs project-based discovery). Raster
I/O (mosaic/clip/reproject/sample) is item 13 — see below.

## Task Group 3 — Raster normalization and sampling (roadmap item 13)

Implemented 2026-07-30, TDD-first, fully offline on synthetic numpy grids. Turns
the cached DEM tiles from item 12 into a single normalized, queryable elevation
surface. No pipeline stage is wired to it yet (Z-attribution is item 14), so a
default 2D build is unchanged and never opens a raster.

### Design

- **numpy for the grid, GDAL behind seams.** `src/raster.py` imports numpy
  directly (consistent with `clipping.py`/`graph.py`); the GDAL-dependent work
  — reading COG tiles and warping between CRSs — stays behind the injected
  `RasterReader` / `RasterReprojector` protocols, so the module and tests run
  with no rasterio/GDAL. Tests use tiny hand-checked grids + fakes.
- **Horizontal reprojection only; vertical preserved.** `normalize_dem` warps to
  EPSG:5070 via the reprojector seam and carries each tile's `ElevationProvenance`
  (vertical CRS/units) through untouched — the resolved NAVD88 decision is
  identity for CONUS 3DEP, so there is no vertical transform here (that stays a
  later, explicit step if a non-NAVD88 source is ever added).

### What landed (`src/raster.py`, new)

- `GridTransform` (north-up origin + pixel size) and `RasterGrid`
  (values/transform/crs/nodata/provenance) with `bounds`/`height`/`width`.
- `sample_bilinear` + `GridSampler` (an `ElevationSampler`): deterministic
  bilinear interpolation; `covered=False` outside the extent; `nodata=True`
  (value `None`) when any of the four neighbors is nodata — never a silent
  synthetic substitution; edge neighbor indices clamped so within-extent points
  past the outer pixel centers still interpolate against real cells.
- `mosaic` (aligned same-CRS tiles → union grid, gaps = nodata, guarded against
  pixel-size/CRS mismatch), `clip_grid` (outward pixel-snapped window to a
  bbox), `build_pyramid` (2x2 block-mean, nodata-aware, finest-first, bounded).
- `normalize_dem`: read → reproject(→EPSG:5070) → mosaic → clip → pyramid,
  returning `NormalizedDem(base, pyramid, provenance)`.

### Tests

- `tests/test_raster.py` (11): transform bounds; bilinear at a pixel center,
  four-neighbor midpoint average, out-of-bounds (uncovered), and nodata
  neighbor; `GridSampler` conformance; two-tile mosaic + mismatch rejection;
  clip window; deterministic 2x pyramid; and `normalize_dem` end-to-end with
  fake reader/reprojector (asserts EPSG:5070 output + preserved NAVD88 vertical).

### Verification

- New tests: **11 passed**. Full suite: **228 passed** (was 217; +11), no
  regressions. Smoke: a 10×10 grid → pyramid shapes `[(10,10),(5,5),(2,2),(1,1)]`,
  interior sample = 49.5, out-of-bounds `covered=False`, clip to (2,2,5,5) →
  3×3 at origin (2,5).
- `ruff` not installed in the offline venv; not run.

### Deferred

The GDAL-backed `RasterReader`/`RasterReprojector` implementations (real COG
reads + warp) are the production seams, exercised by fakes here and wired when
running non-offline. Z-attribution onto flowlines using `GridSampler` is item 14
(Group 4) — see below.

## Task Group 4 — Z-enabled hydrography and QA (roadmap items 14 & 15)

Implemented 2026-07-30, TDD-first, fully offline on synthetic grids. Delivers the
terrain sampling service (item 14) and river Z attribution + profile QA (item
15). Still not wired into the pipeline (that is the item-16+ scene work), so a
default 2D build is unchanged.

### Item 14 — terrain sampling service (`src/terrain.py`, new)

- `densify_line(coords, spacing)`: splits each segment into
  `ceil(length/spacing)` equal parts, preserving every original vertex (exact 2D
  path retained); spacing is normally `dem_cell_size` so no DEM cell is skipped.
- `TerrainSampler(sampler)`: wraps any injected `ElevationSampler` (e.g. a
  `GridSampler`); `sample_line` densifies then samples, returning a `SampledLine`
  of `SampledPoint`s with `n_covered`/`n_nodata`/`coverage` diagnostics.
- `dem_cell_size(dem, level)` / `sampler_for_dem(dem, level)`: pick a pyramid
  level (coarse for interactive preview, level 0 for commit).
- Tests: `tests/test_terrain.py` (8) over a tilted-plane DEM (value == x+y) with
  hand-checked elevations, plus off-grid coverage and nodata cases.

### Item 15 — river elevation attribution & QA (`src/hydro_z.py`, new)

- `attribute_line(...) -> ElevatedLine`: densifies + samples a flowline; each
  `ElevatedVertex` carries **immutable source Z** (`None` at nodata); the line
  also keeps the original 2D geometry verbatim, `dem_id`, interpolation method,
  and a `nodata_count`.
- `profile_qa`: flags downstream **inversions** (Z rising in vertex/downstream
  order beyond a tolerance), reporting indices + max rise — it never alters data.
- `repair_monotonic` + `RepairPolicy`: opt-in (`enabled=False` by default),
  **render-only** non-increasing water surface; returns a new surface and never
  mutates source Z; nodata preserved as gaps.
- `render_z(source_z, vertical_exaggeration, river_lift)`: display-only
  `source_z·exaggeration + lift`, `None`-safe.
- Tests: `tests/test_hydro_z.py` (8), incl. a single-row DEM with a deliberate
  uphill bump flagged as an inversion and clamped by the opt-in repair, and a
  guard that source Z is untouched.

### Verification

- New tests: **16 passed** (8 + 8). Full suite: **244 passed** (was 228; +16),
  no regressions.
- `ruff` not installed in the offline venv; not run.

## Task Group 5 (mesh slice) — roadmap item 16: adaptive terrain mesh

Implemented 2026-07-30. `src/mesh.py` + `tests/test_mesh.py` (8). Offline and
deterministic on synthetic numpy grids. Resolves decision #3 (mesh/error budget)
as **error-bounded (max vertical deviation)**.

- `build_terrain_mesh(grid, *, error_budget_m, boundary_id, max_points, lod)`:
  greedy TIN (Garland–Heckbert incremental refinement). Seeds two triangles over
  the valid grid corners, then repeatedly inserts the DEM sample with the largest
  vertical deviation from the current surface until every sample is within
  `error_budget_m` (or `max_points` is reached). Insertion is a **fan
  retriangulation** of the containing triangle(s) with zero-area fans dropped, so
  the mesh stays **crack-free** even when a sample lands on a shared edge.
- Nodata-aware: nodata samples are never candidates/vertices, and any triangle
  whose footprint contains a nodata sample is dropped.
- `TerrainMesh` carries **true 1× meter** positions (exaggeration stays
  display-only), triangle indices, `boundary_id`, `lod`, requested + achieved
  (`max_error_m`) error, CRS/vertical units, and both a `source_raster_hash` and
  a deterministic `geometry_hash`.
- `mesh_from_dem(dem, *, level, ...)` builds from a chosen pyramid level (LOD).
- Tests: flat plane → 4 corners/2 triangles; true-meter positions (no
  exaggeration); a central peak forces refinement within budget; looser budget →
  coarser mesh; deterministic geometry hash; `max_points` cap; nodata triangles
  dropped; pyramid-level selection.

### Verification (item 16)

- New tests: **8 passed**. Full suite: **252 passed** (was 244; +8), no regressions.

## Task Group 5 (scene slice) — roadmap item 17: 3D scene assembly

Implemented 2026-07-30. `src/scene.py` + `tests/test_scene.py` (8). Offline and
deterministic; pure composition over the item 15/16 value objects (no GDAL,
shapely, or browser dependency).

- `assemble_scene(*, terrain, rivers, segment_colors, vertical_exaggeration,
  river_lift, cameras)` → immutable `SceneModel` joining: the `TerrainMesh`;
  `RiverFeature`s (source `(x, y, z|None)` at 1× meters, referencing a shared
  material); deduped `Material`s (one per distinct watershed color);
  `CardinalAnnotation`s (N/S/E/W) + `AxisInfo` derived from terrain bounds;
  deterministic `CameraPreset`s (top / isometric / south) via `default_cameras`;
  and a display-only `DisplaySettings`.
- **Geographic/styling separation:** stored geometry is always true 1× meters
  with immutable source Z; `render_river_vertices(feature, display)` applies
  `render_z = source_z·exaggeration + lift` only on demand. Exaggeration never
  mutates stored positions.
- No browser/runtime state is embedded; a deterministic `scene_hash` covers
  geometry + materials + annotations + cameras + display for reproducibility.
- Tests: terrain/river/material join; material dedup + sharing; source Z
  preserved while exaggeration stays display-only; nodata vertex preserved;
  cardinals at bounds edges; camera presets deterministic; `scene_hash` changes
  with exaggeration while `terrain.geometry_hash` stays stable; default display
  is identity.

### Verification (item 17)

- New tests: **8 passed**. Full suite: **260 passed** (was 252; +8), no regressions.

### Deferred

Group 6 (GLB export + provenance manifest, browser preview handoff; roadmap items
18–19) remains planning-only and is still blocked on the open decision #4
(GLB-only vs. also OBJ/GeoTIFF).
