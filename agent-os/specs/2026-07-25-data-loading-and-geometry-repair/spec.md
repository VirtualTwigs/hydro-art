# Specification: Data Loading & Geometry Validation/Repair

## Goal
Load the extracted hydrography layers into memory and automatically repair invalid or degenerate geometries — invalid polygons, self-intersections, empty/collapsed geometries, duplicate vertices, and multipart inconsistencies — emitting per-category repair statistics, so downstream projection/clipping stages receive clean, valid, render-preserving geometry.

## User Stories
- As a user, I want messy public GIS data to be cleaned automatically so that a run never fails on a single malformed polygon.
- As a user, I want to see how much was repaired so that I trust the output reflects the source rivers.
- As a developer, I want loading behind an injectable interface so that the load→repair flow is fully testable without GDAL or real GDB files.

## Specific Requirements

**Layer loading (DI seam)**
- Define a `LayerLoader` protocol that yields loaded layers (name + geometries/attributes) from an extracted dataset directory.
- Provide a real `PyogrioLayerLoader` that lazily imports geopandas/pyogrio and reads vector layers; tests inject a fake loader.
- Discover the relevant hydrography layer(s) within each extracted dataset dir via a known layer-name allowlist (e.g. `NHDFlowline`, WBD HUC layers); tolerate missing/extra layers.
- No module performs eager GIS imports at module top level; the loader is the only place GDAL is touched.

**Geometry model**
- Represent a loaded layer as a lightweight container (layer name, source dataset/HUC, iterable of shapely geometries + optional attributes).
- Keep repair independent of file format: it consumes/returns shapely geometries.

**Validation & repair**
- Repair invalid polygons (self-intersections, bowties) using shapely `make_valid` / `buffer(0)`, preserving area/topology as far as possible.
- Remove duplicate/consecutive-identical vertices without simplifying real shape.
- Drop empty geometries and geometries that collapse to zero length/area after repair — counting each drop.
- Normalize multipart inconsistencies (e.g. singleton multi-geometries) to a consistent representation; keep genuine multiparts intact.
- Never simplify or thin valid rivers (PRD §11) — repair changes only invalid/degenerate input.

**Repair statistics**
- Return a `RepairStats` value object counting: total in, total out, invalid_fixed, self_intersections_fixed, empties_dropped, collapsed_dropped, duplicate_vertices_removed, multipart_normalized.
- Stats are mergeable across layers and rendered via `rich`.

**Error recovery**
- A single unrepairable geometry is dropped-and-counted, not fatal (PRD §28); the run continues.
- Missing expected layers or attributes produce an actionable warning, not a crash.

**Pipeline integration**
- Replace the `validate` and `repair_geometries` pipeline stubs: `validate` loads layers via the injected loader and flags invalid geometries; `repair_geometries` repairs them and stores repaired layers + merged `RepairStats` in `context.artifacts`, logging the summary via `rich`.
- Downstream stages remain stubs.

**Dependencies**
- Add `shapely`, `geopandas`, `pyogrio`, `numpy` to `requirements.txt`.

## Existing Code to Leverage

**`src/pipeline.py` — `RunContext` / `Stage`**
- `context.artifacts["dataset_dirs"]` (from item #2's extract stage) is the input: the extracted dataset directories to load.
- Replace the `validate` and `repair_geometries` stub `Stage`s; keep DI (a `LayerLoader` injected into `RunContext`, mirroring the `downloader` seam).

**`src/datasets.py` — `AcquisitionError` style**
- Add a sibling `GeometryError` for load/repair failures (specific exception type per the error-handling standard).

**`build.py` / `Pipeline`**
- Add an injectable `loader` param to `Pipeline` (default real `PyogrioLayerLoader`), mirroring the `downloader` param, so tests run offline with a fake loader.

## Out of Scope
- Reprojection / coordinate normalization and region clipping (roadmap item #4).
- Graph construction, stream ordering, watersheds, coloring, rendering, export (items #5–#10).
- Attribute-level semantic validation (stream classes, discharge) beyond what repair needs.
- Performance tuning (multiprocessing/streaming for millions of segments) — correctness first; optimization is a later concern.
- Any geometry simplification/generalization (explicitly forbidden by PRD §11 unless requested, which is a later item).
- Loading real multi-GB datasets in tests — tests build in-memory geometries and inject a fake loader.
