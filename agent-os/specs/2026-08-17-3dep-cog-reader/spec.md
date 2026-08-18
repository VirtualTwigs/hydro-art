# Spec — Concrete 3DEP COG reader & reprojector (roadmap #31)

## New module: `src/raster_io.py`

A thin, GDAL/rasterio-backed adapter layer implementing the two `src.raster`
Protocols. `rasterio` is imported lazily inside the default I/O path only, so the
module (and everything importing it) stays offline-importable.

### `RasterIOError(AcquisitionError)`

Boundary error type. Subclasses `AcquisitionError` (like `ElevationError` /
`GeometryError`) so `build.py` maps it to the acquisition exit code, consistent
with DEM I/O being an acquisition concern.

### `grid_from_arrays(values, *, affine, crs, nodata=None, provenance=None) -> RasterGrid`

Pure. Maps a GDAL/rasterio affine + a 2-D array to a north-up `RasterGrid`.

- `affine` is any 6+ element sequence `(a, b, c, d, e, f)` in rasterio order:
  `x = a·col + b·row + c`, `y = d·col + e·row + f`. For a north-up raster:
  - `a` = pixel width (> 0),
  - `e` = pixel height (< 0; magnitude is the cell height),
  - `b == d == 0` (no rotation/skew),
  - `c` = west edge (origin_x), `f` = north edge (origin_y).
- Builds `GridTransform(origin_x=c, origin_y=f, pixel_width=a, pixel_height=-e)`.
- `values` cast to `float` (consistent with the rest of the raster subsystem);
  must be 2-D.
- `crs` stringified via `str(crs)` (rasterio `CRS` → `"EPSG:5070"`).
- Validation → `RasterIOError`: non-2-D array; `b`/`d` non-zero (rotated);
  `a <= 0`; `e >= 0` (not north-up).

### `RasterioRasterReader(opener=None)`

Dataclass implementing `RasterReader`.

- `opener`: injectable `Callable[[str], ContextManager]` returning a dataset that
  exposes `.read(1) -> 2D array`, `.transform` (affine), `.crs`, `.nodata`.
  Defaults to a lazy wrapper around `rasterio.open` (raises `RasterIOError` with
  an install hint if rasterio is absent).
- `read(asset)`: resolves `asset.path` (falls back to treating `asset` as a path),
  opens it via the opener context manager, reads band 1 + transform + crs +
  nodata, and returns `grid_from_arrays(...)` carrying `asset.provenance` through.

### `RasterioReprojector(warp=None)`

Dataclass implementing `RasterReprojector`.

- `warp`: injectable `Callable[[RasterGrid, str], RasterGrid]`. Defaults to a lazy
  wrapper around `rasterio.warp.reproject` (raises `RasterIOError` if rasterio is
  absent).
- `reproject(grid, dst_crs)`: **identity short-circuit** — if `grid.crs ==
  dst_crs`, return `grid` unchanged (no warp, deterministic, and the common case
  for CONUS 3DEP already staged in the internal CRS). Otherwise delegate to
  `warp(grid, dst_crs)`.

## Wiring: `tools/render_terrain_print.py` (non-offline)

Make `--dem` optional; add auto-acquisition when it's omitted:

- Keep `_load_dem_grid` (supplied `--dem` path — unchanged override).
- Add `_acquire_relief_grid(region, *, boundary_bounds, cache_dir, tier, ...)`:
  build `Settings` with elevation force-enabled (mirroring `tools/acquire_dem.py`'s
  `_settings_for_region`), `acquire_dem_for_settings(...)` → assets,
  `normalize_dem(assets=…, boundary=…, reader=RasterioRasterReader(),
  reprojector=RasterioReprojector())` → `NormalizedDem`, return `.base`.
- The relief boundary is the flowlines' EPSG:5070 extent (from the clipped
  geometries) so the shaded relief lines up with the art; DEM discovery uses the
  region's EPSG:4326 `region_bounds`.
- CLI: `--dem` no longer `required`; add `--region-dem` (the DEM region name;
  defaults to `--state` when that's a supported region) and `--cache-dir`. If
  neither `--dem` nor a resolvable DEM region is available, fail fast with a clear
  message.
- Downstream (`hillshade` → `shade_to_background` → resize → composite) is
  unchanged.

Because this file eagerly imports the GIS stack and shells out to `resvg`, it
stays outside the offline suite; the new pure adapter (`grid_from_arrays`) and the
seam behavior (fake opener / identity+injected warp) are what the tests cover.

## Dependencies

`requirements.txt` gains `rasterio` (kept out of the minimal `pyproject.toml` set).
Lazy-imported behind the seam, so the offline suite never needs it installed.

## Tests (`tests/test_raster_io.py`, offline)

**TG1 — `grid_from_arrays` (pure):**
1. North-up affine maps to the expected `GridTransform` (origin/pixel sizes) and
   the values/crs/nodata/provenance carry through; `bounds` are correct.
2. Values cast to float; dtype is float.
3. Rotated affine (`b` or `d` != 0) raises `RasterIOError`.
4. Non-north-up (`a <= 0` or `e >= 0`) raises `RasterIOError`.
5. Non-2-D array raises `RasterIOError`.

**TG2 — reader & reprojector (fakes, no rasterio):**
6. `RasterioRasterReader` over a fake opener reads band 1 + transform + crs +
   nodata into the expected grid and carries `asset.provenance`.
7. Reader accepts a bare path (no `.path`/`.provenance` attrs) too.
8. `RasterioReprojector.reproject` identity short-circuits when
   `grid.crs == dst_crs` (returns the same object, warp never called).
9. `RasterioReprojector.reproject` delegates to the injected `warp` when the CRS
   differs (spy records the call; returns the warp's grid).

**TG3 — end-to-end through `normalize_dem` (offline):**
10. Two fake EPSG:5070 assets (adjacent tiles) → `RasterioRasterReader(opener=…)`
    + `RasterioReprojector()` (identity) → `normalize_dem` → a `NormalizedDem`
    whose `base` mosaics/clips both tiles; then `hillshade(base)` yields a valid
    0-255 `RasterGrid` of the right shape. Proves the whole read→normalize→shade
    chain works offline with zero rasterio.
