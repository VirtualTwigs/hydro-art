# Requirements: Projection & Region Clipping

## Raw Idea (from roadmap item #4)

Normalize all layers to internal EPSG:5070, support optional EPSG:4326/3857, and clip the hydrography to the configured region boundary, preserving all river classes with no simplification unless requested.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** `Normalize projections` then `Clip to region`, between `Repair geometries` and `Build hydrography graph`.
- **§9 Coordinate Systems:** internal EPSG:5070; optional EPSG:4326, EPSG:3857. SVG coordinates projected into a cartesian system.
- **§11 River Preservation:** preserve every river class; **no simplification unless requested** — reprojection and clipping must not thin or generalize geometry.
- **§5.2 Datasets:** WBD supplies HUC polygons — the source of the region boundary.
- **§28 Error Recovery:** gracefully recover from projection errors and missing attributes.
- **§30/§25 Config:** `projection` is already a validated `Settings` field (default `EPSG:5070`, allowlist `EPSG:5070/4326/3857`).

## Design Notes / Decisions

- **CRS must travel with the data:** `Layer` currently carries geometries only. Add a `crs` field; the real `PyogrioLayerLoader` captures `frame.crs` so reprojection knows the source CRS. Fake loaders set it explicitly in tests.
- **Reproject before clip:** boundary polygons (WBD) and flowlines (NHDFlowline) must share a CRS before intersection, so the `reproject` stage normalizes *all* layers to `settings.projection`, then `clip_to_region` clips in that CRS.
- **Region boundary = union of WBD HUC polygons:** the boundary is derived from the loaded WBD HUC layers (dataset_id `wbd`) — the union of their polygons. Flowline layers are clipped to it; boundary layers pass through.
- **Pure, testable transforms:** reprojection uses `pyproj.Transformer` + `shapely.ops.transform`; clipping uses shapely `intersection`. Both operate on shapely geometries and are unit-tested with hand-built geometries and known CRS pairs (no GDAL, no real data). `pyproj` is already installed transitively via geopandas.
- **No simplification:** intersection/transform preserve vertices; nothing is generalized. A future "simplify if requested" flag is out of scope.
- **Statistics:** clipping returns a `ClipStats` (in/out, fully-dropped-outside, partially-clipped), logged via `rich`, mirroring `RepairStats`.

## Open Questions (resolve during implementation)

- Source CRS of NHDPlus HR / WBD is typically EPSG:4269 (NAD83 geographic); rely on the CRS read from the file rather than hard-coding, and only fall back to a documented default if a layer lacks a CRS.
- Whether to keep clipped boundary layers in the output set or store the boundary separately — decide during pipeline wiring (lean toward storing the boundary in artifacts and passing boundary layers through unchanged).
