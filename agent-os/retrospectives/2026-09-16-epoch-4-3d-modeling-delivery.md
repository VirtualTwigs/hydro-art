# Retrospective — Epoch 4: 3D modeling and delivery (#17–#19)

_Closed 2026-09-16. Written retroactively (Epoch 4 code landed 2026-07-30; this
practice started in Epoch 9 #38, 2026-08-25). Graded against the requirements in
`agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling/planning/requirements.md`
and the four resolved spec decisions._

## What the epoch was

Compose the prior epochs' terrain + Z-hydrography primitives (Epochs 2-3: DEM
pyramid, bilinear sampler, river Z attribution, adaptive mesh) into a deliverable
3D product: an immutable scene model, a progressive browser preview backed by real
DEM heightfields, and reproducible GLB + OBJ export with per-asset provenance.
The hard constraint: **the 2D pipeline, its `PIPELINE_STAGES`, and its
byte-identical default output are untouched** — the 3D subsystem is a parallel
data model sharing CRS conventions, with its own `tools/` entry points. Held.

## What shipped

- **#17** — 3D scene assembly. `src/scene.py` + `tests/test_scene.py` (8 tests).
  `assemble_scene` composes a `TerrainMesh`, Z-attributed `ElevatedLine`s, and
  watershed `segment_colors` into an immutable `SceneModel` — deduped `Material`s
  (one per distinct watershed color), N/S/E/W `CardinalAnnotation`s + `AxisInfo`
  from terrain bounds, deterministic top/isometric/south `CameraPreset`s, and a
  display-only `DisplaySettings`. `render_river_vertices` applies
  `render_z = source_z * exaggeration + lift` on demand; stored geometry stays
  true 1x meters with immutable source Z. Deterministic `scene_hash` covers
  geometry + materials + annotations + cameras + display. No browser state.
  Commit `4702a50`.

- **#19** — Reproducible 3D export. `src/export3d.py` + `tests/test_export3d.py`
  (8 tests). `scene_to_glb` — a pure-stdlib binary glTF writer: terrain as
  `TRIANGLES`, rivers as `LINE_STRIP`, per-watershed PBR materials, 4-byte-aligned
  buffer views, `sort_keys` JSON chunk for byte-deterministic output. `scene_to_obj`
  — deterministic OBJ/MTL pair. `build_manifest` — JSON provenance carrying
  `scene_hash`, `terrain_geometry_hash`, `source_raster_hash`, exaggeration/lift/
  lod/error budget, material + camera lists, vertex/triangle/river counts. Per-asset
  SHA-256. Geometry exported at true 1x meters; exaggeration recorded, not baked.
  Resolved decision #4: GLB + OBJ (terrain GeoTIFF deferred). Built before #18 per
  the spec's Phase F then G dependency. Commit `8680dce`.

- **#18** — Progressive 3D preview. `src/preview.py` + `tests/test_preview.py`
  (8 tests). `build_preview_asset` emits deterministic coarse-`interaction` + fine-
  `commit` heightfield tiles (row-major z, nodata as `null`), bounds/z-range from
  the commit grid, per-LOD `cell_size_m`, optional Z-rivers as `[x,y,z]` meter
  polylines. `preview_json` = stable `sort_keys` serializer. `web/3d.html` gained a
  "Load DEM preview..." control; `elevationAt()` bilinearly samples the interaction
  tile while orbiting, commit tile on release (progressive detail), replacing the
  synthetic field (now labeled experimental, still toggleable). Commit `6b0df6a`.

- **`web/3d.html` visual upgrade** (separate from #18). NOAA-style solar-position
  terrain lighting (reading date/time), filled sun-shaded terrain mesh,
  Terrain/Hydrography/Terrain-only layer toggles, 4K-12K print PNG export.
  Commit `10b0624`.

**Test counts:** Epoch 4 added 24 tests (8 + 8 + 8) across three modules. Suite
grew from 252 (end of Epoch 3 #16) to 276 (end of Epoch 4 #18). Today those 24
tests still pass (verified 2026-09-16). Full suite: 1027 passing (6 unrelated
failures in `test_min_order.py` — a red-first TDD stub for Epoch 26 #107, not
Epoch 4 debt).

## What went well

- **Phased dependency chain.** The spec laid out seven phases (A through G) with
  explicit dependencies: the scene assembler (#17) needed the mesh and Z-rivers
  from Epochs 2-3; the export (#19) needed the scene; the preview (#18) needed the
  export layer. Each phase was independently testable and committed without touching
  the prior. The export was deliberately built before the preview (Phase F before G)
  so the browser consumed a stable data contract, not a moving target.

- **Four resolved decisions, zero left open.** The spec started with four blocking
  decisions (DEM delivery format, vertical reference, mesh error budget, export
  format). All four were resolved during implementation and documented in
  `planning/requirements.md` with rationale. No decision was deferred or left
  ambiguous across a task-group boundary, which is why Group 6 (export) could ship
  immediately after Group 5 (scene) without a planning pause.

- **Pure-stdlib GLB writer.** Writing binary glTF with only stdlib (`struct`,
  `json`) eliminated a glTF library dependency, kept the output byte-deterministic
  (sorted JSON chunk + little-endian floats + 4-byte alignment), and let the
  offline suite validate the full binary format (header magic, chunk types, buffer
  view offsets) without any external tool. The tradeoff is a narrower feature set
  (no skinning, no texture atlas), but the current product needs terrain + rivers +
  materials, and the writer covers that exactly.

- **Nodata discipline held end-to-end.** From `src/raster.py` (bilinear sample
  yields `nodata=True` when any neighbor is nodata), through `src/hydro_z.py`
  (`ElevatedVertex.z = None` at nodata), to `src/preview.py` (row-major `null` in
  the heightfield), nodata is always an explicit gap, never silently substituted.
  The tests for each layer carry a nodata case that asserts this.

## Invariants held

- Offline suite: 24 Epoch 4 tests passing (verified 2026-09-16).
- 2D default output byte-identical: yes. None of `src/scene.py`, `src/export3d.py`,
  or `src/preview.py` is wired into `PIPELINE_STAGES`. The modules import only
  stdlib + `src.raster`/`src.elevation`/`src.mesh`/`src.hydro_z`/`src.scene` (all
  parallel subsystem modules). A default `build.py` run never imports them.
- `PIPELINE_STAGES` untouched: yes.
- Rights gate: N/A (3D subsystem consumes 3DEP bare-earth DEMs, U.S. federal public
  domain; no PRISM dependency).

## Graded against requirements

The spec's `planning/requirements.md` listed 12 product requirements. Status:

| Req | Summary | Met? |
|-----|---------|------|
| 1 | Request elevation at named tier | Yes (Epoch 2 #11) |
| 2 | Discover + cache minimal 3DEP tiles | Yes (Epoch 2 #12) |
| 3 | Source provenance on every artifact | Yes (`ElevationProvenance` through scene + manifest) |
| 4 | Mosaic/clip/reproject to 5070, vertical untouched | Yes (Epoch 2 #13) |
| 5 | Bilinear sampler + coverage/nodata diagnostics | Yes (Epoch 2 #13) |
| 6 | Densify flowlines at DEM cell spacing | Yes (Epoch 3 #14) |
| 7 | Flag but don't silently alter inversions/nodata | Yes (Epoch 3 #15, `profile_qa`) |
| 8 | Adaptive terrain mesh from DEM | Yes (Epoch 3 #16) |
| 9 | Vertical exaggeration display-only, never mutates Z | Yes (#17 `render_river_vertices`) |
| 10 | Progressive preview (low LOD during interaction) | Yes (#18 interaction/commit tile) |
| 11 | GLB export + JSON provenance manifest | Yes (#19 `scene_to_glb` + `build_manifest`) |
| 12 | Deterministic given identical inputs | Yes (`scene_hash`, `geometry_hash`, `sort_keys`) |

The spec's four acceptance criteria:

1. **Clark County DEM-backed scene with no synthetic Z** — partially met. The
   offline deterministic path is complete and tested. The real non-offline Clark
   County run was deferred (tasks.md final checkbox: "Verify Clark County, WA
   end-to-end before statewide rollout" remains unchecked). This was later
   exercised in Epoch 8 #32's real-tile closeout, which ran the full DEM path
   through `rasterio` for the first time and surfaced the mosaic-before-warp bug.

2. **Every river vertex has source-derived Z or explicit nodata diagnostic** — met
   (`ElevatedVertex.z = None` with `nodata_count`, not synthetic).

3. **Preview uses lower LOD during interaction, full on commit** — met
   (`interaction_level=1`, `commit_level=0`).

4. **GLB + manifest export deterministically** — met (pure-stdlib writer,
   `sort_keys`, SHA-256 per asset).

5. **2D SVG path unaffected** — met (no `PIPELINE_STAGES` edit, no elevation
   import at pipeline load).

## Carry-forwards

- **Real-data Clark County DEM build** was deferred from Epoch 4 and landed in
  Epoch 8 #32 (`0954c69`). The real run surfaced the mosaic-before-warp bug that
  offline fakes structurally could not: per-tile EPSG:4269 to 5070 warp drifted
  pixel resolution with latitude. Fixed in `src/raster.py`. This is Epoch 4's
  instance of the project's recurring lesson — injected-fake coverage cannot
  substitute for one real run when a branch only fires on real data.

- **1 m `local` tier** still raises `ElevationError`. Project-based UTM-tiled
  discovery was scoped out of the first implementation (non-functional constraint:
  "do not download statewide 1 m data by default"). Not blocking any current
  product deliverable.

- **Terrain GeoTIFF export** deferred when decision #4 resolved as GLB + OBJ.
  Would need the `rasterio` write seam (GDAL-backed, lazy-imported). Not requested
  by any downstream epoch.

## Lessons

- **Resolve blocking decisions before the implementation group that needs them, not
  during it.** Decisions #3 (mesh error budget) and #4 (GLB vs OBJ) were both
  resolved at the start of the groups they unblocked (Groups 5 and 6 respectively).
  This is why six task groups shipped in a single day (2026-07-30) with no mid-group
  replanning. The pattern to repeat: if a group has an open question, resolve it in
  the planning commit, not the code commit.

- **Build the export layer before the browser layer.** Phase F (export) shipped
  before Phase G (preview) because the browser preview consumes a data contract the
  export defines. Doing it the other way would have either duplicated the data
  format or forced the preview to work against a moving target. The dependency arrow
  was specified and honored.

- **Pure-stdlib binary writers are worth the upfront cost.** The GLB writer is more
  code than a `pygltflib` call, but it eliminated a dependency, made the output
  byte-deterministic without fighting a library's internal serialization choices,
  and kept the full binary format (header, chunks, buffer views) testable in the
  offline suite. Apply the same pattern if OBJ/MTL ever needs a more structured
  writer.

- **Progressive detail is the right default for browser terrain.** The
  interaction/commit tile split means the 3D lab stays responsive during orbit even
  on large DEMs, and the quality ratchet is invisible to the user. This pattern
  (coarse during input, fine on release) should extend to any future interactive
  terrain view.
