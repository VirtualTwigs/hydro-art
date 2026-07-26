# Implementation Report: Data Loading & Geometry Validation/Repair

**Date:** 2026-07-25
**Status:** Complete — all 3 task groups done, 50/50 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/loading.py` | `LayerLoader` protocol + real `PyogrioLayerLoader` (lazy geopandas/pyogrio import), `Layer` container, `discover_layers` allowlist filter (`HYDRO_LAYER_ALLOWLIST`), `.gdb`/`.shp` source discovery, `GeometryError`. |
| `src/geometry.py` | shapely-based `repair_geometry`/`repair_layer`, immutable `RepairStats` (per-category counters + `merge`), `RepairOutcome`. |
| `src/pipeline.py` | Real `validate` stage (loads layers via injected loader) and `repair_geometries` stage (repairs + merges stats, logs summary); `loader` seam added to `RunContext`/`Pipeline`. |
| `requirements.txt` | Added `shapely`, `geopandas`, `pyogrio`, `numpy` (previously deferred). |
| `tests/test_loading.py`, `test_geometry.py`, `test_repair_pipeline.py` | 4 + 7 + 2 = 13 new tests (50 total suite). Item #2 offline tests updated to inject a `NullLayerLoader`. |

## Key decisions

- **Loading behind a lazy-import seam:** `PyogrioLayerLoader` imports geopandas/pyogrio only inside `load_layers`, so importing the pipeline never requires GDAL. Tests inject fake loaders — no real GDB is read.
- **Repair is pure shapely, file-format-free:** the validity logic lives in `src/geometry.py` and is unit-tested with hand-built geometries (shapely ships bundled GEOS, pip-installable without system GDAL).
- **Preservation over cleanup (PRD §11):** repair only fixes validity and removes exact-duplicate vertices via `remove_repeated_points`; it never simplifies valid rivers. Only empty and collapsed (zero length/area) geometries are dropped.
- **Collapse judged against the *original* geometry family:** a line that `make_valid` reduces to a point counts as collapsed, while a genuine point is preserved.
- **Statistics are first-class:** `RepairStats` counts each category and merges across layers; the pipeline logs a one-line summary via `rich`.
- **Item #2 offline tests inject `NullLayerLoader`:** now that `validate`/`repair` run for real in every pipeline, the acquisition tests supply an offline loader — the same injection pattern already used for the fake downloader.

## Acceptance criteria met

- Real loading is behind an injectable seam with no eager GDAL imports; discovery finds target layers (NHDFlowline/WBD) and tolerates missing ones with a warning.
- Repair fixes invalid polygons/self-intersections, removes duplicate vertices, drops empty/collapsed geometries, and normalizes singleton multiparts — all counted — without simplifying valid geometry.
- Pipeline `validate`/`repair_geometries` run load+repair with a fake loader in tests and the real loader in production; merged `RepairStats` and repaired layers land in `context.artifacts`.
- Full suite passes with no regressions (50 passed); 13 new tests (≤10-per-group budget respected: TG1 4, TG2 7, TG3 2).

## Notes for next feature (roadmap #4: projection & region clipping)

- `context.artifacts["repaired_layers"]` (list of `Layer` with clean shapely geometries) is the input seam for reprojection/clipping.
- `Layer` currently carries geometries only; CRS metadata will be needed for EPSG:5070 normalization — extend `Layer` (or the loader) to capture source CRS when item #4 lands.
- `pyproj` is already installed (transitively via geopandas) and can back the EPSG:5070/4326/3857 transforms.
