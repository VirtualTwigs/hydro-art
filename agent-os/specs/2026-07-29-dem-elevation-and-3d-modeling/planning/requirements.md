# Requirements: DEM Elevation & 3D Modeling

## Source

- Product direction: evolve the GIS-to-SVG generator into an accurate terrain-and-rivers
  modeler, beginning with Oregon and Clark County, Washington.
- Product roadmap: Epochs 2–4 in `agent-os/product/roadmap.md`.
- Authoritative source decision: USGS 3DEP **bare-earth DEMs**. Lidar point clouds are an
  optional future higher-fidelity input, not the default processing format.

## Problem

The current `web/3d.html` is an intentionally experimental visual prototype: its Z values come
from a synthetic `elevationAt()` field and therefore cannot represent real terrain or be
exported as an accurate model. Hydrography is presently 2D; it has no per-vertex ground
elevation, vertical datum provenance, or terrain surface to sit on.

## Product requirements

1. A build can request elevation data for the configured region at a named resolution tier:
   `preview`, `state`, or `local`.
2. The system discovers and caches the minimal set of USGS 3DEP bare-earth DEM assets that
   cover the target boundary. Network access is injectable and offline tests use fixtures or
   fakes.
3. Every elevation artifact records its source URL/product, retrieval/checksum, horizontal
   CRS, vertical CRS/datum when supplied, units, nominal cell size, and processing lineage.
4. Raster data is mosaicked, clipped, and reprojected to the project’s internal horizontal
   CRS (EPSG:5070) without silently changing vertical units or datum.
5. A sampler returns a ground elevation in meters plus coverage/nodata diagnostics for any
   projected point. It supports deterministic bilinear interpolation.
6. Flowline geometry is densified no farther apart than the active DEM cell size before
   sampling. The resulting 3D vertices retain the original segment identity and 2D geometry.
7. The system flags, but does not silently alter, sampled river profiles containing nodata or
   downstream elevation inversions. Any monotonic repair is explicit, render-only, and records
   its parameters.
8. Terrain mesh generation derives entirely from the normalized DEM. It supports an adaptive
   level of detail and clips exactly to the selected region boundary.
9. The only allowed display adjustment to accurate Z is explicit vertical exaggeration. It
   never modifies stored source-derived Z values. River microlift is an independent small
   display offset to avoid z-fighting.
10. The interactive browser preview uses derived low-resolution data while a user manipulates
    controls, then commits the selected full-resolution level after release.
11. The first portable 3D export is GLB, accompanied by a JSON provenance manifest. Camera,
    lighting, palette, vertical-exaggeration, source DEM metadata, and geometry hashes are
    recorded.
12. Given identical hydrography, DEM assets, settings, and software version, produced sampled
    elevations, terrain geometry, and manifest are deterministic.

## Non-functional constraints

- Keep heavy raster/GIS dependencies lazy-loaded behind injected interfaces, consistent with
  the current downloader/loader/exporter architecture.
- Do not download statewide 1 m data by default. Use a budgeted resolution policy and explicit
  escalation from preview to local detail.
- “Accurate” is prohibited in UI/export labels unless source/datum/units are present and no
  synthetic elevation field is in use.
- Alaska and non-U.S. elevation products are out of the first implementation scope because
  their horizontal/vertical source characteristics differ; the interfaces must leave room for
  them.

## Decisions

Resolved (2026-07-30):

1. **DEM delivery/format — RESOLVED: 3DEP Cloud-Optimized GeoTIFFs on the USGS `prd-tnm`
   AWS S3 bucket** (same staged-products host as the hydrography archives). For the seamless
   1 arc-second (`preview`) and 1/3 arc-second (`state`) products USGS stages one COG per
   1°×1° cell named by its NW corner (`n45w124`), so discovery is deterministic and
   offline-constructible from a lon/lat bbox — no discovery API call. Implemented in
   `src/dem.py` (item 12). The 1 m `local` tier is project/UTM-tiled, needs project-based
   discovery, and is deferred (raises a clear `ElevationError` for now).
2. **Target vertical reference — RESOLVED: normalize to NAVD88** for the first CONUS release.
   3DEP 1"/13" products are natively NAD83 horizontal (EPSG:4269) and NAVD88 vertical in
   meters, so for these tiers the normalization is an identity and is recorded verbatim in
   each tile's `ElevationProvenance`. Enforcement of an actual datum/units transform for any
   non-NAVD88 source is a raster-normalization concern (item 13), not acquisition.

Still open (needed by later task groups, not by items 11–12):

3. What mesh/error budget is acceptable for state, county, and GLB export tiers? (blocks Group 5)
4. Is GLB-only sufficient for the first 3D export, or must OBJ and/or terrain GeoTIFF ship in
   the same epoch? (blocks Group 6)
