# Implementation report — Terrain-aware 2D hillshade (roadmap #22 slice)

## What shipped

`src/hillshade.py` — a pure, deterministic, offline numpy function that turns a
bare-earth elevation `RasterGrid` into a Lambertian shaded-relief `RasterGrid`
(0-255). This is the "terrain-aware 2D hillshade" (print-mode) slice of the `XL`
roadmap #22; animation/camera paths and web delivery are deferred to later
passes. Scope confirmed with the user on 2026-08-12.

## Public API (`src/hillshade.py`)

- `HillshadeError(ElevationError)` — invalid azimuth/altitude/z_factor.
- `hillshade(grid, *, azimuth_deg=315.0, altitude_deg=45.0, z_factor=1.0,
  nodata=-1.0) -> RasterGrid` — Horn's 3×3 `dz/dx`/`dz/dy` over the DEM, then the
  standard ESRI/GDAL Lambertian shade for a sun at (azimuth, altitude), clamped
  to `[0, 255]`. Same shape/transform/CRS as the input; `provenance` carried
  through.

## Algorithm & design

- **Horn gradients**: `dz/dx = ((c+2f+i)-(a+2d+g))/(8·pixel_width)`,
  `dz/dy = ((g+2h+i)-(a+2b+c))/(8·pixel_height)` over the north-up 3×3 window
  (row 0 = north, so the ESRI layout applies directly).
- **Illumination**: `slope = atan(z_factor·hypot(dz/dx,dz/dy))`,
  `aspect = atan2(dz/dy, -dz/dx)` wrapped to `[0,2π)`,
  `shade = 255·(cos z·cos slope + sin z·sin slope·cos(az − aspect))` with
  `z = radians(90−altitude)` and `az = radians((360−azimuth+90) mod 360)`.
- **Edges**: `np.pad(values, 1, mode="edge")` gives every cell a neighborhood so
  the output keeps the input shape (GDAL `-compute_edges` behavior).
- **Nodata never invented**: cells that are nodata, or whose 8-neighborhood
  touches nodata, are emitted as the output sentinel (a 3×3 OR-dilation of the
  invalid mask, padded with `False` so true borders aren't spuriously voided).
- **z_factor is shading-only** — it exaggerates apparent slope for contrast and
  never alters source elevations (consistent with the "display-only exaggeration"
  policy elsewhere in the subsystem).

## Guardrails honored

- **Offline & deterministic**: `src/hillshade.py` imports only `numpy` +
  `src.raster` (`RasterGrid`) + `src.elevation` (`ElevationError`). Pure function;
  identical inputs ⇒ identical output (asserted with `np.array_equal`). Part of
  the parallel elevation/terrain subsystem — **not** in `PIPELINE_STAGES`.
- Reuses `RasterGrid`/`GridTransform` unchanged; no edits to other modules.
- Boundary validation raises `HillshadeError` for `azimuth ∉ [0,360)`,
  `altitude ∉ (0,90]`, `z_factor ≤ 0`.

## Tests (`tests/test_hillshade.py`, 8 tests)

Synthetic DEMs (flat + tilted planes) so every case is hand-reasoned. Coverage:
flat DEM → uniform `255·sin(radians(altitude))` (≈180.31 @ 45°); a plane rising
east (face pointing west) is brighter under a west sun (az 270) than an east sun
(az 90); output preserves shape/CRS/transform and valid values ∈ `[0,255]`;
determinism; larger `z_factor` deepens the darkest interior shadow; an interior
nodata cell + its 8 neighbors propagate to the sentinel while far cells keep real
shade; a no-nodata source yields no sentinel; invalid altitude (0, 91) / azimuth
(360) / z_factor (0) each raise `HillshadeError`.

## Verification

- `tests/test_hillshade.py`: **8 passed**.
- Full suite: **409 passed** (was 401), no regressions.
- `ruff` not installed in this `.venv`, so lint was not run here; code follows the
  repo conventions (`from __future__ import annotations`, docstrings, 88-col).

---

# Implementation report — Animation camera paths (roadmap #22 slice)

## What shipped

`src/camera.py` — pure, deterministic, offline interpolation of
`src.scene.CameraPreset` keyframes into smooth camera motion, the
"animation / camera paths" (experience-mode) slice of the `XL` roadmap #22. Web
delivery and compositing remain deferred.

## Public API (`src/camera.py`)

- `CameraPathError(ValueError)` — invalid `t` / keyframes / up vector.
- `CameraPose` — a frozen, name-less viewpoint (`position`, `target`, unit `up`,
  `fov_deg`); one sampled frame of motion (vs. a named `CameraPreset`).
- `interpolate_camera(a, b, t) -> CameraPose` — lerp position/target/fov,
  normalized-lerp up; `t=0`→a, `t=1`→b.
- `camera_path(keyframes, *, steps_per_segment, loop=False) -> tuple[CameraPose,
  ...]` — open path ends exactly on the last keyframe (`(n-1)·steps + 1` poses);
  looping path is a seamless cycle (`n·steps` poses).

## Design

- **Segment sampling** includes each segment's start and excludes its end, so
  keyframes shared between segments are never duplicated at joins. The open path
  appends one closing pose on the final keyframe; the loop adds a wrap segment
  (`last → first`) and omits the closing pose for a seamless cycle.
- **Up-normalization**: up vectors are normalized before and after the lerp
  (`_nlerp_up`) so every emitted pose has a unit up even from non-unit keyframe
  ups; a zero-length up raises `CameraPathError`.
- **Linear first cut**: position/target/fov use plain lerp — no easing or
  quaternion orientation yet (called out in the spec's not-in-scope).

## Guardrails honored

- **Offline & deterministic**: imports only `math` + `src.scene` (`CameraPreset`);
  pure functions; identical inputs ⇒ identical tuple. No browser/runtime state;
  **not** in `PIPELINE_STAGES`.
- Boundary validation raises `CameraPathError` for `<2` keyframes,
  `steps_per_segment < 1`, `t ∉ [0,1]`, and zero-length up vectors.

## Tests (`tests/test_camera.py`, 7 tests)

Interpolation endpoints/midpoint; open path hits first/last keyframes at the right
length; determinism; seamless loop (no duplicated closing keyframe); unit-length
up from non-unit keyframe ups; the four validation raises.

## Verification

- `tests/test_camera.py`: **7 passed**.
- Full suite: **416 passed** (was 409), no regressions.

---

# Implementation report — Web delivery (roadmap #22 slice)

## What shipped

`src/delivery.py` — a pure, deterministic, offline serializer that packages the
two prior experience-mode products (the hillshade `RasterGrid` and a camera path
of `CameraPose`s) into one stable, browser-loadable **experience document** — plus
`web/experience.html`, a self-contained `file://`-safe viewer. This is the third
and final slice of the `XL` roadmap #22; all three concerns (hillshade, camera
paths, web delivery) have now shipped.

## Public API (`src/delivery.py`)

- `DeliveryError(ValueError)` — empty grid / empty camera path.
- `hillshade_layer(grid) -> dict` — row-major `shade` (nodata → `None`), `width`/
  `height`, `bounds`, `cell_size_m`, valid-only `value_range`.
- `camera_track(poses) -> list[dict]` — `[{position,target,up,fov_deg}]`.
- `experience_document(*, hillshade_grid, camera_poses, crs=None,
  generator=GENERATOR) -> dict` — `{generator, crs, hillshade, camera:{frame_count,
  track}}`; `crs` defaults to the grid's CRS.
- `experience_json(doc) -> str` — deterministic `json.dumps(sort_keys=True)`.

## Design

- **Mirrors `src/preview.py`**: same row-major, nodata→`null`, stable-`sort_keys`
  JSON conventions that already feed `web/3d.html`, so delivery is idiomatic to the
  subsystem. `src/delivery.py` imports only `json` + `src.raster` + `src.camera`
  (numpy only via the grid it reads); no browser state; not in `PIPELINE_STAGES`.
- **Never invents shade**: a hillshade cell equal to `grid.nodata` serializes to
  `None` and is excluded from `value_range`; the viewer paints those transparent.
- **`web/experience.html`**: loads a document via a file picker, paints the
  hillshade grid to a `<canvas>` (grayscale, nodata transparent), and plays/scrubs
  the camera track as a position/target/fov read-out. `src/` never imports `web/`.

## Tests (`tests/test_delivery.py`, 7 tests)

`hillshade_layer` over a real `hillshade()` grid (shape, row-major length,
`[0,255]`, bounds, cell size, valid-only `value_range`, propagated-nodata → `None`
where the 3×3 void dilation reaches); `camera_track` shape/length/vector-lists;
`experience_document` structure + `frame_count`; `experience_json` round-trips
through `json.loads` with nodata as JSON `null`; byte-identical determinism; empty
grid and empty camera path each raise `DeliveryError`.

## Verification

- `tests/test_delivery.py`: **7 passed**. Full suite: **423 passed** (was 416), no
  regressions.
- `web/experience.html`: inline script `node --check` clean; a real
  `experience_json` document (8×6 hillshade with a propagated void + a 24-frame
  looped camera path) parses browser-side (48 cells = w·h, 9 nulls, all shade in
  `[0,255]∪null`).

## Not done / follow-ups (remain open on roadmap #22)

- **Compositing** the hillshade under the river SVG + a `tools/` print renderer
  over a real normalized DEM — the shaded-relief engine ships; blending it into a
  final print is a non-offline follow-on.
- A live `/api/experience` server route that renders + returns a document over a
  real DEM (needs GDAL/NAS); interactive 3D playback in the browser (the viewer is
  a 2D hillshade canvas + camera read-out); PNG/video export of the animation.
- Multidirectional/soft hillshade; and richer camera motion (easing curves,
  Catmull-Rom smoothing, quaternion orientation) beyond the linear first cut.
