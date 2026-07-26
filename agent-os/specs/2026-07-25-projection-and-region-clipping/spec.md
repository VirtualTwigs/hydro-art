# Specification: Projection & Region Clipping

## Goal
Normalize every loaded, repaired hydrography layer to the configured internal projection (default EPSG:5070; optionally EPSG:4326/3857) and clip the hydrography to the configured region's boundary (derived from WBD HUC polygons), preserving all river classes without simplification, so downstream graph/render stages work in a single cartesian CRS over exactly the region of interest.

## User Stories
- As a user, I want all data normalized to one projection so that distances/areas and the final art are geographically correct.
- As a user, I want rivers outside my region trimmed away so that the output shows only my region.
- As a developer, I want reprojection and clipping as pure geometry functions so that they are fully testable without GDAL or real datasets.

## Specific Requirements

**CRS on layers**
- Add a `crs` field to `Layer`; the real `PyogrioLayerLoader` populates it from the source (`frame.crs`).
- A layer without a known CRS cannot be reprojected — raise an actionable `ProjectionError`.

**Reprojection**
- Provide `reproject_geometry(geom, transformer)` and `reproject_layer(layer, target_crs)`.
- Transform to `settings.projection` (allowlist already validated in config: EPSG:5070 default, EPSG:4326, EPSG:3857).
- Use `pyproj.Transformer` (always_xy) + `shapely.ops.transform`; when source CRS already equals target, return the layer unchanged (identity, new `crs` set).
- Reprojection preserves every vertex — no simplification/generalization.

**Region boundary**
- Derive the region boundary as the union of the loaded WBD HUC polygon layers (dataset_id `wbd`).
- If no boundary layer is available, warn and pass hydrography through unclipped (graceful degradation).

**Clipping**
- Provide `clip_geometry(geom, boundary)` (shapely intersection; `None` when the result is empty) and `clip_layers(layers, boundary)`.
- Clip flowline (non-boundary) layers to the boundary; drop geometries entirely outside; keep partially-inside geometries trimmed to the boundary.
- Boundary layers pass through unchanged; the computed boundary is exposed for later stages/background.
- No simplification — clipping only intersects.

**Statistics**
- `ClipStats` value object: total_in, total_out, dropped_outside, clipped_partial; mergeable across layers; logged via `rich`.

**Error recovery**
- Projection errors (missing/unknown CRS) produce actionable messages; a single un-clippable geometry is dropped-and-counted, not fatal (PRD §28).

**Pipeline integration**
- Replace the `reproject` stub: reproject every layer in `artifacts["repaired_layers"]` to `settings.projection`; store `artifacts["projected_layers"]`.
- Replace the `clip_to_region` stub: compute the boundary from the projected WBD layers, clip the projected flowline layers, store `artifacts["clipped_layers"]` and `artifacts["region_boundary"]`, and log the `ClipStats` via `rich`.
- Downstream stages remain stubs.

## Existing Code to Leverage

**`src/loading.py` — `Layer`**
- Extend `Layer` with `crs`; `repair_layer`'s `dataclasses.replace` already preserves extra fields, so CRS flows from load → repair → reproject unchanged.

**`src/config.py` — `Settings.projection` / `SUPPORTED_PROJECTIONS`**
- `settings.projection` is the validated target CRS; reuse `SUPPORTED_PROJECTIONS` — no new config or CLI work.

**`src/datasets.py` — dataset ids**
- WBD layers carry `dataset_id == "wbd"`; use it to distinguish boundary layers from flowlines. Reuse the `AcquisitionError` hierarchy for `ProjectionError`.

**`src/pipeline.py` — `RunContext` / stages**
- Input seam is `artifacts["repaired_layers"]` (from item #3); replace the `reproject` and `clip_to_region` stub `Stage`s. No new injected dependency needed (pyproj is pure-Python-callable and deterministic).

## Out of Scope
- Graph construction, stream ordering, watersheds, coloring, rendering, export (items #5–#10).
- Any geometry simplification/generalization or a `--simplify` flag (PRD §11 "unless requested" is a later concern).
- Reprojecting to CRSs beyond the validated allowlist (EPSG:5070/4326/3857).
- Advanced boundary sources (custom shapefiles, buffers, dissolve tuning) beyond the union of WBD HUC polygons.
- Performance tuning (vectorized/pygeos-batch reprojection) — correctness first.
- Loading real datasets in tests — tests use in-memory geometries with explicit CRS and a fake loader.
