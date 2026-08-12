# Tasks — Terrain-aware 2D hillshade (roadmap #22, print-mode slice)

## TG-H1 — Hillshade core (Horn gradients + Lambertian illumination)

- [x] Write tests first (`tests/test_hillshade.py`): flat DEM → uniform
      `255*sin(radians(altitude))`; tilted plane brighter lit from up-slope than
      down-slope; output preserves shape/CRS/transform + valid values in
      `[0, 255]`; determinism (`np.array_equal`); larger `z_factor` deepens the
      darkest shadow (contrast).
- [x] `src/hillshade.py`: `hillshade(grid, *, azimuth_deg=315, altitude_deg=45,
      z_factor=1.0, nodata=-1.0)` — Horn 3×3 `dz/dx`/`dz/dy` (edge-padded),
      slope/aspect, ESRI Lambertian shade clamped to `[0, 255]`; returns a
      `RasterGrid` (numpy + `src.raster` only).
- [x] Run ONLY the new tests; green.

## TG-H2 — Nodata propagation + boundary validation

- [x] Write tests first: interior nodata cell propagates to itself + 8 neighbors
      (sentinel), far cells stay valid; no-nodata source yields no sentinel;
      invalid `altitude_deg` (0, 91) / `azimuth_deg` (360) / `z_factor` (0) each
      raise `HillshadeError`.
- [x] `src/hillshade.py`: `HillshadeError(ElevationError)`; 3×3 OR-dilation of the
      invalid mask → output nodata; parameter validation at the boundary.
- [x] Run ONLY the new tests; green.

## TG-H3 — Verify + docs

- [x] Confirm the full Python suite passes (regression check).
- [x] Write `implementation/report.md`; tick this `tasks.md`.
- [x] Add a roadmap #22 progress note (hillshade slice shipped; camera paths /
      web delivery still open); update `HANDOFF.md` + `CLAUDE.md` module map.
      Report; STOP (commit is a separate explicit step).
