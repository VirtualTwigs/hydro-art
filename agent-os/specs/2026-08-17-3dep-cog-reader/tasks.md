# Tasks — Concrete 3DEP COG reader & reprojector (roadmap #31)

## TG1 — Pure affine→grid mapping (`grid_from_arrays`)
- [x] Write tests: north-up affine → expected `GridTransform`/bounds + values/crs/
      nodata/provenance carried through; values cast to float; rotated affine
      (`b`/`d`) raises; non-north-up (`a<=0`/`e>=0`) raises; non-2-D raises — all
      `RasterIOError`.
- [x] Implement `RasterIOError` + `grid_from_arrays` in `src/raster_io.py`.
- [x] Run ONLY the TG1 tests green.

## TG2 — Concrete seams (`RasterioRasterReader`, `RasterioReprojector`)
- [x] Write tests (fakes, no rasterio): reader over a fake opener → expected grid
      + provenance carried; reader accepts a bare path; reprojector identity
      short-circuit (same object, warp not called); reprojector delegates to an
      injected `warp` spy when CRS differs.
- [x] Implement `RasterioRasterReader(opener=None)` + `RasterioReprojector(warp=None)`
      with lazy-rasterio defaults behind the seam.
- [x] Run ONLY the TG2 tests green.

## TG3 — Integration + wiring + docs
- [x] Write test: two fake EPSG:5070 assets → reader + identity reprojector →
      `normalize_dem` → `NormalizedDem` base mosaics both tiles → `hillshade(base)`
      is a valid 0-255 grid (whole chain offline, no rasterio).
- [x] Add `rasterio` to `requirements.txt` (lazy, optional; not in pyproject).
- [x] Wire `tools/render_terrain_print.py`: `--dem` optional; auto-acquire relief
      from `--region-dem`/`--state` via `acquire_dem_for_settings` → `normalize_dem`
      (new reader/reprojector) → `hillshade`; supplied `--dem` still overrides.
- [x] Update CLAUDE.md (module map: new `raster_io.py`; note #30 gap now closed)
      and write `implementation/report.md`.
- [x] Full suite green (no regressions). Smoke the offline chain. Mark #31 `[x]`
      in the roadmap once the two collaborators + wiring ship and are tested.
