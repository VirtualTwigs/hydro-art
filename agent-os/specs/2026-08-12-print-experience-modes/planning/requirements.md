# Requirements — Print/experience modes (roadmap #22)

## Roadmap text

> 22. Print/experience modes — Add terrain-aware 2D hillshade, animation/camera
> paths, and web delivery without compromising the canonical data model or
> reproducibility. `XL`

## Scope this pass — terrain-aware 2D hillshade

#22 is `XL` and spans three concerns:

1. **Terrain-aware 2D hillshade** — a shaded-relief surface computed from the
   normalized DEM, for print-quality 2D output.
2. Animation / camera paths — interpolated camera motion over the 3D scene.
3. Web delivery — serving/exporting the experience for the browser.

Per the user's decision (2026-08-12), **this pass delivers concern #1 only** —
the flagship "print mode," and the most self-contained, fully offline-testable
slice (a pure numpy computation over the existing `RasterGrid`). Concerns 2–3 are
deferred to later passes.

## Why hillshade first

Hillshade is the terrain-aware 2D print feature: it turns the bare-earth DEM into
a Lambertian shaded-relief image (sun azimuth + altitude), giving the flat river
art a sense of the underlying topography without leaving 2D. It sits naturally in
the raster subsystem next to `normalize_dem` / `RasterGrid`, is deterministic,
and needs no new dependencies (numpy only).

## Functional requirements

- **Input**: an elevation `RasterGrid` (north-up, row 0 = north), as produced by
  the DEM normalization pipeline.
- **Output**: a same-shape/same-transform/same-CRS `RasterGrid` of relief values
  in `[0, 255]` (float), suitable for rasterizing behind the river layers.
- **Algorithm**: Horn's 3×3 method for `dz/dx` / `dz/dy`, then the standard
  ESRI/GDAL Lambertian hillshade with configurable sun **azimuth** (compass
  degrees) and **altitude** (degrees above horizon) and a vertical **z_factor**.
- **Deterministic**: identical grid + parameters ⇒ identical output array.
- **Nodata-aware, never invented**: a cell that is itself nodata, or whose 3×3
  neighborhood touches a nodata cell (so its gradient would be corrupted), is
  emitted as the output nodata sentinel — never a fabricated shade.
- **Edge-defined**: border cells (no full 3×3 neighborhood) use edge replication
  for the gradient so the output stays the same shape (matches GDAL
  `-compute_edges`), while true source-nodata still propagates as above.
- **Boundary-validated**: azimuth in `[0, 360)`, altitude in `(0, 90]`,
  `z_factor > 0`, else a `HillshadeError` (subclass of `ElevationError`).

## Non-functional / guardrails

- Pure, deterministic, offline: `src/hillshade.py` imports only numpy +
  `src.raster` (`RasterGrid`) + `src.elevation` (`ElevationError`). Part of the
  parallel elevation/terrain subsystem — **not** wired into `PIPELINE_STAGES`.
- Frozen/immutable inputs; no global state; a single pure function.
- Reuses `RasterGrid`/`GridTransform` unchanged; no edits to other modules.

## Out of scope (deferred, tracked on roadmap #22)

- Animation / camera paths (interpolated `CameraPreset` motion over the scene).
- Web delivery of the print/experience output.
- Blending hillshade under the river SVG / a `tools/` print renderer — the
  shaded-relief engine ships here; compositing it into a final print is a
  non-offline follow-on (needs real DEM + the rasterizer).
- Multidirectional/soft hillshade; a single Lambertian light is the first cut.
