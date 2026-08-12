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

---

# Tasks — Animation camera paths (roadmap #22, experience-mode slice)

## TG-C1 — Camera interpolation + open path

- [x] Write tests first (`tests/test_camera.py`): `interpolate_camera(a, b, t)`
      endpoints reproduce the keyframe poses (`t=0`→a, `t=1`→b); midpoint is the
      component-wise average of position/target/fov; an open `camera_path` hits the
      first and last keyframes exactly with length `(n-1)*steps + 1`; determinism
      (`==` over two identical calls).
- [x] `src/camera.py`: `CameraPose` (name-less viewpoint), `interpolate_camera`
      (lerp position/target/fov, normalized-lerp up), `camera_path(keyframes, *,
      steps_per_segment, loop=False)` — pure/offline, imports only `math` +
      `src.scene.CameraPreset`; not in `PIPELINE_STAGES`.
- [x] Run ONLY the new tests; green.

## TG-C2 — Loop, validation, up-normalization

- [x] Write tests first: a looping path is seamless (length `n*steps`, no
      duplicated closing keyframe, last sample is on the way back to the start);
      every pose's up vector is unit-length even from non-unit keyframe ups; invalid
      inputs raise `CameraPathError` (`<2` keyframes, `steps_per_segment=0`, `t`
      outside `[0,1]`, a zero-length up vector).
- [x] `src/camera.py`: `CameraPathError(ValueError)`; wrap segment for `loop`;
      boundary validation; `_normalize`/`_nlerp_up` up-normalization (zero up →
      `CameraPathError`).
- [x] Run ONLY the new tests; green.

## TG-C3 — Verify + docs

- [x] Confirm the full Python suite passes (regression check): **416 passed**.
- [x] Extend `spec.md`/`implementation/report.md`; tick this `tasks.md`.
- [x] Update the roadmap #22 progress note, `HANDOFF.md`, and the `CLAUDE.md`
      module map (camera-path slice shipped; web delivery + compositing still open).
      Report; STOP (commit is a separate explicit step).
