# Spec — Terrain-aware 2D hillshade (roadmap #22, print-mode slice)

## Summary

Add `src/hillshade.py`: a pure, deterministic, offline numpy function that turns
an elevation `RasterGrid` into a Lambertian shaded-relief `RasterGrid` (0–255)
using Horn's 3×3 gradient method + a configurable sun. Nodata-aware; never
invents shade. No changes to other modules; not in `PIPELINE_STAGES`.

## Public API (`src/hillshade.py`)

```
HillshadeError(ElevationError)   # invalid azimuth / altitude / z_factor

hillshade(
    grid: RasterGrid,
    *,
    azimuth_deg: float = 315.0,   # compass bearing of the light (NW default)
    altitude_deg: float = 45.0,   # sun angle above the horizon
    z_factor: float = 1.0,        # vertical exaggeration for shading only
    nodata: float = -1.0,         # output sentinel for undefined cells
) -> RasterGrid
```

## Algorithm

For a north-up grid (row 0 = north edge), with cell sizes `cw = pixel_width`,
`ch = pixel_height`, over the 3×3 neighborhood

```
a b c
d e f
g h i
```

- `dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cw)`
- `dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * ch)`
- `slope  = arctan(z_factor * hypot(dz/dx, dz/dy))`
- `aspect = arctan2(dz/dy, -dz/dx)`, wrapped to `[0, 2π)`
- `zenith = radians(90 - altitude_deg)`
- `az     = radians((360 - azimuth_deg + 90) mod 360)`
- `hs = 255 * (cos(zenith)·cos(slope) + sin(zenith)·sin(slope)·cos(az - aspect))`
- clamp `hs` to `[0, 255]`.

Vectorized with numpy. Borders use `np.pad(values, 1, mode="edge")` so every cell
has a neighborhood and the output keeps the input shape.

## Nodata

- `invalid = (values == grid.nodata)` when `grid.nodata is not None`, else all
  false.
- A cell is emitted as `nodata` if it or **any** of its 8 neighbors is invalid
  (gradient would be corrupted). Implemented as a 3×3 OR-dilation of `invalid`
  (padded with `False`, so real border cells are not spuriously invalidated).
- Output `RasterGrid.nodata = nodata`; `provenance` carried through from input.

## Determinism & guardrails

- Pure function; identical inputs ⇒ identical output array (asserted).
- Validation (raises `HillshadeError`): `0 <= azimuth_deg < 360`,
  `0 < altitude_deg <= 90`, `z_factor > 0`.
- `src/hillshade.py` imports only `numpy` + `src.raster` (`RasterGrid`) +
  `src.elevation` (`ElevationError`). Offline; not in `PIPELINE_STAGES`.
- `from __future__ import annotations`; docstrings; 88-col.

## Tests (`tests/test_hillshade.py`)

TG-H1 (core): flat DEM → uniform `255*sin(radians(altitude))` (≈180.31 @ 45°);
a tilted plane is brighter when lit from the up-slope than from the down-slope
direction; output preserves shape/CRS/transform and valid values lie in `[0,255]`;
determinism (`np.array_equal`); larger `z_factor` deepens the darkest shadow on a
slope (more contrast).

TG-H2 (nodata/validation): a single interior nodata cell propagates to itself +
its 8 neighbors as the output sentinel while far cells stay valid; source with no
nodata yields no sentinel; invalid `altitude_deg` (0 and 91), `azimuth_deg` (360),
and `z_factor` (0) each raise `HillshadeError`.

## Not in scope (hillshade slice)

Web delivery, hillshade↔SVG compositing, and a print `tools/` renderer — deferred
on roadmap #22 (see requirements.md). Camera paths are addressed in the follow-on
slice below.

---

# Spec — Animation camera paths (roadmap #22, experience-mode slice)

## Summary

Add `src/camera.py`: pure, deterministic, offline interpolation of
`src.scene.CameraPreset` keyframes into smooth camera motion — a tuple of
`CameraPose` samples for an animation/experience mode. No new dependencies
(`math` + `src.scene` only); not in `PIPELINE_STAGES`; no browser state (a later
web-delivery pass consumes the poses).

## Public API (`src/camera.py`)

```
CameraPathError(ValueError)      # bad t / keyframes / up vector

@dataclass(frozen=True)
class CameraPose:                # a name-less, single interpolated viewpoint
    position: Vec3
    target: Vec3
    up: Vec3                     # always unit-length
    fov_deg: float

interpolate_camera(a: CameraPreset, b: CameraPreset, t: float) -> CameraPose

camera_path(
    keyframes: Sequence[CameraPreset],
    *,
    steps_per_segment: int,
    loop: bool = False,
) -> tuple[CameraPose, ...]
```

## Algorithm

- **Interpolation** (`t ∈ [0, 1]`): `position`, `target`, and `fov_deg` are
  linearly interpolated (`a + (b-a)·t`); the up vector is **normalized-lerped**
  (normalize both endpoints, lerp, renormalize) so it stays unit-length. `t=0`
  reproduces `a` (with a normalized up), `t=1` reproduces `b`.
- **Path sampling**: each consecutive keyframe pair is a *segment* sampled at
  `steps_per_segment` parameters `i / steps_per_segment` for `i` in
  `[0, steps_per_segment)` — segment start included, end excluded, so shared
  keyframes are never duplicated at joins.
- **Open** (`loop=False`): visit `keyframes[0] … keyframes[-1]` and append a
  closing pose on the final keyframe ⇒ length `(n-1)·steps_per_segment + 1`,
  ending exactly on the last keyframe.
- **Loop** (`loop=True`): add a wrap segment `keyframes[-1] → keyframes[0]` and
  omit the closing pose ⇒ seamless cycle of length `n·steps_per_segment`.

## Determinism & guardrails

- Pure function; identical inputs ⇒ identical output tuple (`==`).
- Validation (raises `CameraPathError`): `len(keyframes) >= 2`,
  `steps_per_segment >= 1`, `0 <= t <= 1`, non-zero up vectors.
- Imports only `math` + `src.scene` (`CameraPreset`). Offline; no browser/runtime
  state; not in `PIPELINE_STAGES`.
- `from __future__ import annotations`; docstrings; 88-col.

## Tests (`tests/test_camera.py`)

TG-C1 (interpolate + open path): endpoints reproduce the keyframe poses; midpoint
is the component-wise average; an open path hits the first/last keyframes with
length `(n-1)·steps + 1`; determinism.

TG-C2 (loop/validation/up): a loop is seamless (`n·steps`, no duplicated closing
keyframe, last sample on the way back to start); every pose's up is unit-length
from non-unit keyframe ups; invalid inputs (`<2` keyframes, `steps_per_segment=0`,
`t ∉ [0,1]`, zero-length up) each raise `CameraPathError`.

## Not in scope (camera slice)

Web delivery / serving the animation, easing curves beyond linear (ease-in/out,
Catmull-Rom smoothing), and true quaternion camera orientation — a single linear
interpolation with normalized-lerp up is the first cut.
