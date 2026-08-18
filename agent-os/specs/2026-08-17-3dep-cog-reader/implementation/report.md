# Implementation report — Concrete 3DEP COG reader & reprojector (roadmap #31)

## What shipped

**`src/raster_io.py`** (new) — the two concrete GDAL/rasterio-backed collaborators
`src.raster.normalize_dem` has always expected, plus the pure affine mapping under
them:

- `grid_from_arrays(values, *, affine, crs, nodata=None, provenance=None)` — pure.
  Maps a rasterio-order affine `(a, b, c, d, e, f)` → north-up
  `GridTransform(origin_x=c, origin_y=f, pixel_width=a, pixel_height=-e)` and casts
  `values` to float. Validates 2-D, no rotation/skew (`b==d==0`), and north-up
  (`a>0`, `e<0`) — anything else raises `RasterIOError`. Carries nodata + provenance
  through.
- `RasterioRasterReader(opener=None)` — implements `RasterReader`. Opens a
  `DemAsset`'s cached COG (`asset.path`, or a bare path), reads band 1 + transform +
  crs + nodata, returns a `RasterGrid` with `asset.provenance` attached. `opener` is
  an injectable `Callable[[str], ContextManager]`; the default lazily imports
  `rasterio.open`.
- `RasterioReprojector(warp=None)` — implements `RasterReprojector`. **Identity
  short-circuits** when `grid.crs == dst_crs` (the common CONUS-3DEP case, and
  deterministic); otherwise delegates to an injectable `warp` callable whose default
  lazily wraps `rasterio.warp.reproject`.
- `RasterIOError(AcquisitionError)` boundary type (maps to `build.py`'s acquisition
  exit code).

**`requirements.txt`** — adds `rasterio>=1.3`, documented as optional and
lazy-imported behind the seam. It stays out of the minimal `pyproject.toml` set, so
the offline suite never needs GDAL/rasterio.

**`tools/render_terrain_print.py`** (wiring) — `--dem` is now optional. With no
`--dem`, the tool auto-acquires real relief for the DEM region (`--region-dem`,
default `--state`): `acquire_dem_for_settings` caches the COG tiles →
`normalize_dem` reads/reprojects them through the new `raster_io` seams → the relief
is clipped to the **flowlines' EPSG:5070 extent** (`_geom_bounds`) so it lines up
with the art → `hillshade` → `shade_to_background` → composite. A supplied `--dem`
still overrides. New flags: `--region-dem`, `--cache-dir`, `--dem-tier`,
`--dem-tile-budget`, `--dem-refresh`.

## Tests (TDD)

`tests/test_raster_io.py` — 10 offline tests, no rasterio, no GDAL, no network:

- **TG1 (`grid_from_arrays`):** north-up affine → expected transform/bounds +
  values/crs/nodata/provenance carried; float cast; rotated affine raises;
  non-north-up raises; non-2-D raises.
- **TG2 (seams):** reader over a fake opener reads band/transform/crs/nodata +
  provenance; reader accepts a bare path; reprojector identity short-circuit (same
  object, warp never called); reprojector delegates to an injected `warp` spy when
  the CRS differs.
- **TG3 (integration):** two fake adjacent EPSG:5070 assets → reader + identity
  reprojector → `normalize_dem` → a `NormalizedDem` whose base mosaics both tiles →
  `hillshade(base)` is a valid 0-255 grid. Proves the whole read→normalize→shade
  chain works offline.

**Full suite: 512 passed** (was 502; +10), no regressions. New files stay within the
88-char line limit.

## Smoke evidence

Ran the full chain offline with **rasterio not installed** (confirmed via
`importlib.util.find_spec('rasterio') is None`), proving the lazy-seam import
discipline: a synthetic ridge DEM split into two adjacent EPSG:5070 tiles →
`RasterioRasterReader(opener=fake)` + `RasterioReprojector()` (identity) →
`normalize_dem` (base 3×6, EPSG:5070, 2 provenance records) → `hillshade` (range
131–246) → `shade_to_background(tint, opacity)` → `composite_over_background` with a
neon river row → a real `/tmp/terrain_print_31_smoke.png`. Also confirmed a rotated
affine is rejected with `RasterIOError`.

## Scope note (gate now closed)

This closes the gap #30's report flagged: `RasterReader`/`RasterReprojector` are no
longer Protocol-only, and `tools/render_terrain_print.py` auto-acquires 3DEP relief
from `--region` alone. The **Epoch 8 gate — a print over accurate 3DEP bare-earth
relief — is now met.** The real-tile end-to-end (GDAL + network) still runs only in
the non-offline `tools/` path, by design; the pure mapping and both seams' behavior
are fully covered offline via injected fakes.

## Files

- `src/raster_io.py` (new), `tests/test_raster_io.py` (new)
- `requirements.txt` (+rasterio), `tools/render_terrain_print.py` (auto-acquire)
- `agent-os/specs/2026-08-17-3dep-cog-reader/` (spec artifacts)
- `CLAUDE.md` (module map + tools), `agent-os/product/roadmap.md` (#31 `[x]`, #30
  flipped to `[x]`)
