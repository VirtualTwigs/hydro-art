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

## Not in scope

Camera paths, web delivery, hillshade↔SVG compositing, and a print `tools/`
renderer — deferred on roadmap #22 (see requirements.md).
