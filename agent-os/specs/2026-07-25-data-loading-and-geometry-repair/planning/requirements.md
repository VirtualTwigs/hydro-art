# Requirements: Data Loading & Geometry Validation/Repair

## Raw Idea (from roadmap item #3)

Load downloaded hydrography layers via GeoPandas/pyogrio and automatically repair invalid polygons, self-intersections, empty/collapsed geometries, duplicate vertices, and multipart inconsistencies, emitting repair statistics.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** the `Validate` and `Repair geometries` stages sit between `Extract` and `Normalize projections`.
- **§10 Geometry Validation:** automatically repair invalid polygons, self intersections, empty geometries, duplicate vertices, collapsed geometries, multipart inconsistencies.
- **§11 River Preservation:** preserve every river class (major → tiny tributaries, intermittent/seasonal/braided/distributary/canal). No simplification unless requested — repair must not drop valid rivers.
- **§27 Logging:** rich terminal output including geometry repair statistics.
- **§28 Error Recovery:** gracefully recover from invalid shapefiles and missing attributes.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests.
- **§29 Tech Stack:** GeoPandas, Pyogrio, GDAL, Shapely, Fiona, NumPy.

## Design Notes / Decisions

- **Loader behind an injectable seam:** reading vector layers from an extracted `.gdb`/shapefile requires GDAL. Define a `LayerLoader` protocol; the real `PyogrioLayerLoader` lazily imports geopandas/pyogrio so tests inject a fake loader that yields in-memory geometries. No test needs a real multi-GB GDB.
- **Repair operates on shapely geometries, not file formats:** the substance of this item (validity repair) is pure shapely and is fully unit-tested with hand-built geometries. shapely is pip-installable with bundled GEOS (no system GDAL required for the repair layer).
- **Preservation over cleanup:** repair fixes validity; it never simplifies or thins vertices beyond removing exact duplicate/collinear-degenerate points. Empty/collapsed geometries (zero-area/zero-length after repair) are the only things dropped, and each drop is counted.
- **Statistics are first-class:** repair returns a `RepairStats` value object counting each category (invalid_fixed, self_intersections_fixed, empties_dropped, collapsed_dropped, duplicate_vertices_removed, multipart_normalized) plus totals in/out, logged via rich.
- **New deps this item:** add `shapely`, `geopandas`, `pyogrio`, `numpy` to `requirements.txt` (previously deferred).

## Open Questions (resolve during implementation)

- Which layer(s) to load from NHDPlus HR: flowlines (`NHDFlowline`) are the render target; WBD supplies HUC polygons. Start with a configurable/known layer-name allowlist and discover matching layers within each extracted dataset dir.
- Repair algorithm for invalid polygons: prefer shapely `make_valid`; fall back to `buffer(0)` where appropriate. Decide per-geometry-type in implementation.
