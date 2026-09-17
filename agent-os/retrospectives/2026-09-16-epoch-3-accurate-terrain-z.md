# Retrospective — Epoch 3: Accurate terrain and hydrography Z (#14–#16)

_Closed 2026-07-30; retrospective written 2026-09-16 (retroactive — the
retrospective practice started in Epoch 9 #38). Spec:
`agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling/` (shared across Epochs
2–4). No `planning/pre-analysis.md` exists for this epoch._

## What the epoch was

Replace the synthetic `elevationAt()` Z field with **real, source-traceable
elevation**: a bilinear terrain sampler (#14), per-vertex river Z attribution
with downstream-inversion QA and opt-in monotonic repair (#15), and an adaptive
error-bounded terrain mesh with boundary clipping and LOD controls (#16). All
three items sit between the Epoch 2 raster foundation (mosaic/clip/pyramid in
`src/raster.py`) and the Epoch 4 scene assembly (`src/scene.py`). The hard
invariant: these are **parallel subsystems, not `PIPELINE_STAGES` edits** — the
canonical 2D pipeline and its default output are untouched.

## What shipped

### #14 — Terrain sampling service (`342fd57`)

`src/terrain.py` (141 lines) + `tests/test_terrain.py` (8 tests):

- `densify_line(coords, spacing)` — splits each segment into
  `ceil(length/spacing)` equal parts at DEM-cell spacing, preserving every
  original vertex so the exact 2D path is retained and no DEM cell is skipped.
- `TerrainSampler(sampler)` — wraps any injected `ElevationSampler`; `sample_line`
  densifies then samples, returning a `SampledLine` of `SampledPoint`s with
  `n_covered` / `n_nodata` / `coverage` diagnostics.
- `dem_cell_size(dem, level)` / `sampler_for_dem(dem, level)` — pyramid level
  selectors (coarse for interactive preview, level 0 for commit).

### #15 — River elevation attribution and QA (`342fd57`)

`src/hydro_z.py` (209 lines) + `tests/test_hydro_z.py` (8 tests):

- `attribute_line` -> `ElevatedLine` — densifies + samples a flowline; each
  `ElevatedVertex` carries **immutable source Z** (`None` at nodata); the line
  also keeps the original 2D geometry verbatim, `dem_id`, interpolation method,
  and a `nodata_count`.
- `profile_qa` — flags downstream inversions (Z rising in vertex/downstream
  order beyond a tolerance) with indices + max rise. Reports, never alters.
- `repair_monotonic` + `RepairPolicy` — opt-in (`enabled=False` default),
  render-only non-increasing water surface; returns a new surface and never
  mutates source Z; nodata preserved as gaps.
- `render_z(source_z, vertical_exaggeration, river_lift)` — display-only
  transform, `None`-safe.

Items #14 and #15 shipped together in one commit (`342fd57`); the spec's Task
Group 4 bundled them because the terrain sampler is the direct upstream of the
Z-attribution path.

### #16 — Adaptive terrain mesh (`4b4c0a6`)

`src/mesh.py` (327 lines) + `tests/test_mesh.py` (8 tests):

- `build_terrain_mesh(grid, *, error_budget_m, boundary_id, max_points, lod)` —
  greedy TIN (Garland-Heckbert incremental insertion). Seeds two triangles over
  the valid grid corners, then repeatedly inserts the DEM sample with the largest
  vertical deviation until every sample is within `error_budget_m` or
  `max_points` is reached.
- **Crack-free fan retriangulation** — insertion of a point on a shared edge
  splits both adjacent triangles; zero-area degenerate fans are dropped.
- **Nodata-aware** — nodata samples are never candidates/vertices, and any
  triangle whose footprint contains a nodata sample is dropped.
- `TerrainMesh` carries true 1x meter positions (exaggeration is display-only),
  triangle indices, `boundary_id`, `lod`, achieved `max_error_m`, CRS/vertical
  units, `source_raster_hash`, and a deterministic `geometry_hash`.
- `mesh_from_dem(dem, *, level, ...)` builds from a chosen pyramid level (LOD).

Decision #3 (mesh/error budget) was resolved here: **error-bounded max vertical
deviation** rather than fixed grid decimation or triangle-count caps, because it
keeps a stated, auditable accuracy guarantee while naturally spending triangles
only where terrain is rugged.

## Test summary

| Module | Tests | File |
|--------|------:|------|
| `src/terrain.py` | 8 | `tests/test_terrain.py` |
| `src/hydro_z.py` | 8 | `tests/test_hydro_z.py` |
| `src/mesh.py` | 8 | `tests/test_mesh.py` |
| **Epoch total** | **24** | |

Suite before Epoch 3: **228 passing** (end of Epoch 2 #13).
Suite after Epoch 3: **252 passing** (+24, no regressions).
All 24 tests still pass today (verified 2026-09-16, 0.07s).

## Invariants held

- **Offline suite:** 252 passing (was 228). No network, no GDAL, no real data.
  All three modules import only stdlib + `src.elevation` / `src.raster` (which
  themselves import only numpy + stdlib); no rasterio/geopandas/pyogrio at any
  level.
- **2D default output byte-identical:** yes. All three modules are parallel
  subsystems, not wired into `PIPELINE_STAGES`. Nothing in `build.py` or the 2D
  pipeline touches `terrain.py`, `hydro_z.py`, or `mesh.py`.
- **`PIPELINE_STAGES` untouched:** yes. No stage added, removed, or reordered.
- **Rights gate:** N/A. Epoch 3 adds pure offline geometry; no new data source,
  no commercial-use concern.

## What went well

- **The Epoch 2 seam investment paid off immediately.** `TerrainSampler` wraps
  the `ElevationSampler` protocol from `src/elevation.py`; `mesh_from_dem` reads
  the `NormalizedDem` pyramid from `src/raster.py`. Both items consumed the Epoch
  2 contracts exactly as designed — no raster module was re-opened, and the tests
  inject the same fakes the Epoch 2 tests use. The "define protocols first, wire
  implementations later" discipline kept the epoch focused on geometry, not I/O.

- **Task Group 4 bundling (#14 + #15) was the right call.** The terrain sampler
  (`src/terrain.py`) and the Z-attribution layer (`src/hydro_z.py`) are
  producer-consumer: `TerrainSampler.sample_line` feeds `attribute_line`. Shipping
  them in one commit (`342fd57`) meant the integration surface was tested end-to-end
  in the same pass — a synthetic tilted-plane DEM with a deliberate uphill bump
  flowed through densification, sampling, inversion detection, and opt-in repair
  in a single test fixture.

- **The mesh error-budget decision produced a clean, auditable primitive.** The
  greedy TIN approach means the mesh carries a `max_error_m` that is a *true
  measured bound*, not an estimate. A flat plane → 4 corners / 2 triangles; a
  central peak forces exactly the refinement the budget demands. The `geometry_hash`
  is deterministic, so reproducibility is trivially verified.

## What was tricky

- **Crack-free fan retriangulation.** Inserting a vertex on a shared triangle
  edge must split both adjacent triangles, not just the one found first. The
  implementation detects edge-sharing via a tolerance, finds both triangles,
  replaces each with a fan from the new point, and drops degenerate (zero-area)
  fans. Getting the tolerance right (shared-edge detection without false positives
  on near-miss vertices) required careful testing against hand-built grids.

- **Nodata propagation across three modules.** Each module handles nodata
  differently and correctly: `GridSampler` returns `nodata=True` (value `None`)
  when any bilinear neighbor is nodata; `attribute_line` preserves `None` per
  vertex and counts `nodata_count`; `build_terrain_mesh` excludes nodata samples
  from candidates AND drops triangles whose footprint touches nodata. The
  discipline is "never invent elevation" — but it means each module's nodata path
  needed explicit test coverage (it got it).

- **The repair/QA split.** `profile_qa` reports inversions; `repair_monotonic`
  fixes them. The temptation was to combine them, but the spec's requirement #7
  ("flags, but does not silently alter") mandated the split. The test fixture
  uses a deliberate uphill bump: `profile_qa` flags it with the index and max
  rise; `repair_monotonic` clamps it; a separate assertion confirms source Z is
  untouched. This two-function design survived into Epoch 4's scene assembly
  unchanged.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this epoch. The spec's
`planning/requirements.md` listed 12 product requirements; here is how Epoch 3
(#14-#16) addressed its share:

| Requirement | Status |
|-------------|--------|
| #5: Bilinear sampler with coverage/nodata diagnostics | Shipped (#14 `GridSampler` via Epoch 2 #13; `TerrainSampler` wraps it) |
| #6: Densify at DEM cell size, retain 2D geometry | Shipped (#14 `densify_line`) |
| #7: Flag inversions, explicit render-only repair | Shipped (#15 `profile_qa` + `repair_monotonic`) |
| #8: Adaptive terrain mesh with LOD and boundary clipping | Shipped (#16 `build_terrain_mesh` + `mesh_from_dem`) |
| #9: Exaggeration never modifies source Z | Shipped (#15 `render_z` display-only; #16 `TerrainMesh` stores 1x meters) |
| #12: Deterministic given identical inputs | Shipped (all three modules are pure functions of their inputs; `geometry_hash` verifies mesh determinism) |

The spec predicted a single shared commit per task group and that each group
would be independently testable without GDAL. Both predictions held exactly.

## Carry-forwards

- **Real-data terrain sampling not yet exercised.** All 24 tests use synthetic
  numpy grids with hand-computed results. The first real 3DEP DEM pass through
  `TerrainSampler` / `attribute_line` happened in Epoch 8 #32 (terrain-print
  closeout, `0954c69`), which surfaced the mosaic-before-warp resolution-drift
  bug. That bug was in the Epoch 2 `src/raster.py` layer (not in Epoch 3 code),
  but it confirms the pattern: offline fakes structurally cannot exercise the
  warp/mosaic branches that real tiles fire.
- **No live mesh from real DEM produced during Epoch 3.** The first real mesh
  was produced in Epoch 4's scene assembly; confirmed correct there but not
  independently validated at the Epoch 3 boundary.
- **`repair_monotonic` not yet exercised on real river profiles.** The opt-in
  repair was tested on a synthetic single-row DEM with a deliberate bump. Real
  NHDPlus HR flowlines may have more complex inversion patterns (confluences,
  braided channels); the repair's behavior on those is untested.

## Lessons

- **Protocol-first design makes the consumer epoch fast.** Epoch 3 consumed
  Epoch 2's `ElevationSampler` / `RasterGrid` / `NormalizedDem` without
  reopening any Epoch 2 module. The same protocols flowed into Epoch 4 (#17
  scene, #18 preview, #19 export) equally smoothly. Define seams before
  implementations.
- **Bundle producer-consumer pairs.** #14 (sampler) and #15 (Z attribution) are
  tightly coupled; shipping them together avoided a half-wired intermediate state.
  #16 (mesh) is independent of the river Z path and correctly shipped as a
  separate commit.
- **Test nodata at every layer boundary.** The "never invent elevation" invariant
  must be re-asserted at each module's output, not just at the sampler. The
  epoch's nodata coverage (sampler returns `None`, attribution counts it, mesh
  excludes it) is the template for future additive layers.
- **Write the retrospective at epoch close, not months later.** This retroactive
  write (2026-09-16 for a 2026-07-30 close) reconstructed details from commit
  messages, the implementation report, and HANDOFF.md. A same-day closeout would
  have captured the crack-free retriangulation debugging and any other real-time
  observations that the artifacts don't record. The practice was established in
  Epoch 9 (#38); Epoch 3 predates it.
