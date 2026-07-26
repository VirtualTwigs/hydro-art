# Implementation Report: Projection & Region Clipping

**Date:** 2026-07-25
**Status:** Complete — all 3 task groups done, 62/62 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/projection.py` | `reproject_geometry`/`reproject_layer` via cached `pyproj.Transformer` + `shapely.ops.transform`; identity when source CRS already equals target; `ProjectionError`. |
| `src/clipping.py` | `region_boundary` (union of WBD polygon layers), `clip_geometry`/`clip_layers` (shapely intersection), immutable mergeable `ClipStats`, `is_boundary_layer`. |
| `src/loading.py` | `Layer` gains a `crs` field; `PyogrioLayerLoader` captures `frame.crs`. |
| `src/pipeline.py` | Real `reproject` stage (normalizes repaired layers to `settings.projection`) and `clip_to_region` stage (clips projected flowlines to the WBD boundary), storing `projected_layers`, `clipped_layers`, `region_boundary`, `clip_stats`. |
| `tests/test_projection.py`, `test_clipping.py`, `test_projection_clip_pipeline.py` | 4 + 6 + 2 = 12 new tests (62 total suite). |

## Key decisions

- **CRS travels with the layer:** added `Layer.crs`; `repair_layer`'s `dataclasses.replace` already preserves it, so CRS flows load → repair → reproject untouched. A layer with no CRS is a clear `ProjectionError`, not a silent mis-projection.
- **Reproject before clip:** the `reproject` stage normalizes *all* layers (flowlines and WBD boundary) to `settings.projection` first, so clipping intersects geometries in one consistent CRS.
- **Boundary = union of WBD HUC polygons:** layers with `dataset_id == "wbd"` supply the boundary; flowline layers are trimmed to it and boundary layers pass through. Missing boundary → warn and pass hydrography through unclipped (graceful degradation per PRD §28).
- **No simplification (PRD §11):** reprojection preserves vertex count (test-verified) and clipping only intersects — nothing is generalized.
- **Deterministic, pure transforms:** `pyproj` + shapely functions on shapely geometries; the `Transformer` is `lru_cache`d by CRS pair. No injected dependency needed — transforms are deterministic. Tests use in-memory geometries with explicit CRS (no GDAL, no real data).
- **Stats are first-class:** `ClipStats` (in/out, dropped_outside, clipped_partial) is stored in artifacts and logged via `rich`, mirroring `RepairStats`.

## Acceptance criteria met

- All layers normalize to EPSG:5070/4326/3857; identity path is a no-op; missing CRS raises; vertex count preserved.
- Flowlines are trimmed to the region boundary; fully-outside geometry dropped-and-counted; inside geometry preserved; boundary exposed in artifacts.
- Pipeline `reproject`/`clip_to_region` run with a fake loader in tests and real transforms in production; projected + clipped layers, boundary, and stats land in `context.artifacts`.
- Full suite passes with no regressions (62 passed); 12 new tests (TG1 4, TG2 6, TG3 2).

## Notes for next feature (roadmap #5: hydrography graph construction)

- `context.artifacts["clipped_layers"]` (flowlines in the internal CRS, trimmed to region) is the input seam; `region_boundary` is available for extent/background.
- Graph construction needs segment endpoints as junction nodes — the clipped flowline geometries are already single-CRS and valid, so endpoint snapping/tolerance is the main new concern.
- `Layer.attributes` is still unused; NHDPlus flow-direction / reach-code attributes will likely be needed for directed-graph edges — extend the loader to carry them when item #5 lands.
