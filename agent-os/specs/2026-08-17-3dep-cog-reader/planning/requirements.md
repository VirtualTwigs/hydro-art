# Requirements — Concrete 3DEP COG reader & reprojector (roadmap #31)

## Problem

The DEM subsystem's read path is Protocol-only. `src.raster` declares
`RasterReader.read(asset) -> RasterGrid` and `RasterReprojector.reproject(grid,
dst_crs) -> RasterGrid` as bare `Protocol`s with **no concrete implementation**,
and `rasterio` is not a dependency. So although `src.dem.acquire_dem_for_settings`
downloads and caches real 3DEP COG tiles (`DemAsset(tile, path, provenance)`), and
`src.raster.normalize_dem(assets, boundary, reader, reprojector, …)` expects those
two collaborators, nothing in the repo turns a cached COG into a `RasterGrid`.

This is the single blocker that keeps roadmap #30 (hillshade print compositing)
from auto-acquiring accurate 3DEP relief — `tools/render_terrain_print.py` today
takes a *supplied* `--dem` grid instead.

## Scope (this item)

Supply **only** the two concrete collaborators + the real-DEM wiring:

1. A pure mapping from a GDAL/rasterio affine + array to a north-up `RasterGrid`.
2. A rasterio-backed `RasterReader` that opens a `DemAsset`'s cached COG
   (`asset.path`), reads band 1, and returns a `RasterGrid` (values +
   `GridTransform` + source CRS + nodata, provenance carried through).
3. A warp-backed `RasterReprojector` that reprojects a grid to EPSG:5070, with an
   **identity short-circuit** when the grid is already in the destination CRS.
4. Wire `tools/render_terrain_print.py` so `--region` alone (no `--dem`) produces
   a terrain-backed print: `acquire_dem_for_settings` → `normalize_dem` (new
   reader/reprojector) → `hillshade` → `src.compositing`, relief clipped to the
   flowlines' EPSG:5070 extent.

Everything else already exists: `normalize_dem`, `DemAsset`, tile discovery/
caching, tile-budget, and the pure `hillshade`/`compositing` seams.

## Constraints (carried from the project)

- **Injectable-seam rule.** `rasterio` is a **new optional dependency,
  lazy-imported behind the seam** — never at module import time of anything under
  `src/`. `requirements.txt` gains it; `pyproject.toml` (the minimal offline set)
  does not. The offline test suite stays GDAL/rasterio-free.
- **Offline-testable.** The reader is exercised offline via an **injected
  `opener`** (a fake dataset object exposing `.read(1)`, `.transform`, `.crs`,
  `.nodata` as a context manager) — no real GeoTIFF, no rasterio import. The
  reprojector is exercised via its identity short-circuit and an **injected
  `warp`** callable. An end-to-end test drives the whole chain
  (`normalize_dem` → `hillshade`) with the fake-opener reader + identity
  reprojector, proving the wiring offline.
- **North-up only, validate at the boundary.** The affine→grid mapping accepts
  only a north-up affine (no rotation/skew, positive pixel width, negative pixel
  height) and 2-D arrays; anything else raises a `RasterIOError` boundary type.
- **Determinism.** Identical cached tiles → identical `RasterGrid` values →
  identical composited bytes. No randomness, no silent nodata substitution
  (nodata is carried verbatim into the grid so `sample_bilinear`/`hillshade`
  honor it).
- **Provenance carried through.** `read` copies `asset.provenance` onto the grid
  so `normalize_dem` can roll it into the `NormalizedDem`.

## Non-goals

- Vertical datum transforms (3DEP CONUS tiles are natively NAVD88 — identity).
- Any change to `PIPELINE_STAGES` (the DEM subsystem stays parallel/offline).
- A real-tile end-to-end smoke inside the suite (that needs GDAL + network; it's
  the non-offline `tools/` path only).

## Acceptance

- `src/raster_io.py` provides `grid_from_arrays`, `RasterioRasterReader`,
  `RasterioReprojector`, `RasterIOError` — all importable with no rasterio
  installed (lazy import only fires on the real read/warp path).
- New offline tests cover the affine mapping (incl. validation errors), the
  reader over a fake opener, the reprojector identity + injected-warp delegation,
  and the full `normalize_dem` → `hillshade` chain.
- `tools/render_terrain_print.py` auto-acquires relief from `--region` when no
  `--dem` is given; `--dem` still works as the supplied-grid override.
- Full suite green (no regressions); `requirements.txt` gains `rasterio`.
