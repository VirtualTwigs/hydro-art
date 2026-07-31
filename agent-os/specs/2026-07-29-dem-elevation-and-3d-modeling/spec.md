# Specification: DEM-backed Elevation & 3D Modeling

## Goal

Replace the experimental synthetic Z field with a reproducible, source-traceable 3D data path:
USGS 3DEP bare-earth DEM → normalized raster pyramid → sampled Z-enabled hydrography + terrain
mesh → progressive browser preview and portable 3D export.

## Scope and delivery strategy

This is a multi-epoch capability, not one implementation item. Work must land in the sequence
below; each phase has a usable, independently testable result.

| Phase | Deliverable | Depends on |
|---|---|---|
| A. Elevation contract | `ElevationSettings`, provenance records, resolution policy, injected raster interfaces | Existing config/cache |
| B. DEM acquisition | 3DEP discovery/cache with fixture-backed tests | A |
| C. Raster normalization | clipped EPSG:5070 DEM pyramid and queryable coverage metadata | B |
| D. Z attribution | bilinear sampler, densified flowlines, river profile QA | C + existing clipped flowlines |
| E. Terrain mesh | adaptive mesh plus deterministic LODs | C |
| F. 3D scene/export | scene assembler, GLB, provenance manifest | D + E |
| G. Browser integration | DEM-backed 3D lab with progressive preview | F |

## Data model

### Source metadata

`ElevationSource` is an immutable value object containing:

- provider/product and source URL;
- asset identifier, checksum, retrieval timestamp, and license/attribution;
- horizontal CRS, vertical CRS/datum if known, units, cell size, nodata value;
- source bounds and a content hash.

### Normalized raster

`ElevationRaster` represents a cached, clipped EPSG:5070 raster plus its source metadata. It
must distinguish horizontal projection from vertical reference. Reprojection is horizontal-only
unless an explicit tested vertical transformation is configured.

### Three-dimensional feature data

`ElevatedLine` contains a segment ID and ordered `(x_m, y_m, z_m)` vertices. It also contains
the original 2D geometry, interpolation method, DEM identifier, nodata count, and profile QA
flags. Geographic/source Z is immutable; render Z is calculated later as:

`render_z = source_z * vertical_exaggeration + river_lift`.

### Mesh and scene

`TerrainMesh` contains positions in meters, triangle indices, UV/optional color data, boundary
identity, LOD, source-raster hash, and deterministic geometry hash. `SceneModel` joins terrain,
rivers, material settings, cardinal/axis annotation data, and camera presets without embedding
browser state.

## Pipeline integration

The current fixed pipeline remains valid for canonical 2D SVG output. Elevation is a parallel
branch after `clip_to_region`:

```text
clip_to_region ──> build_graph ──> ... ──> SVG/export
       │
       ├──> acquire_elevation ──> normalize_elevation ──> sample_elevation
       │                                      │                    │
       │                                      └──> build_terrain_mesh
       │                                                           │
       └──────────────────────────────────────────────────────────┴──> assemble_3d_scene → GLB/manifest
```

The 2D-only run must not acquire elevation or require raster dependencies. A requested 3D output
activates the elevation branch. All I/O collaborators are injected through `RunContext`; every
stage writes named artifacts only.

## Resolution policy

- `preview`: roughly 10–30 m cell size, bounded for responsive state-wide interaction.
- `state`: roughly 10 m where available; use for default statewide terrain/export.
- `local`: 1 m 3DEP DEM where coverage is available; requires explicit region/budget request and
  is the default tier for Clark County-level work.

Actual selected source/cell size is always recorded. A requested tier is a policy, not a claim
that identical resolution exists everywhere.

## Accuracy and QA policy

- Bare-earth ground altitude, not canopy/building elevation, is the authoritative surface.
- Sampling uses bilinear interpolation after the query and raster share EPSG:5070.
- Nodata is surfaced as an error or diagnostic according to the selected output policy; it is
  never silently substituted by synthetic height.
- River-profile QA reports elevation inversions in the directed graph. Any correction is off by
  default and affects only the rendered water surface.
- Vertical exaggeration is opt-in display metadata, never a data transformation.

## Browser experience

`web/3d.html` is retained as a prototype until Phase G. Its synthetic terrain controls must be
visibly labeled experimental. After Phase G it consumes prebuilt DEM-derived preview assets,
renders a low-detail sub-window during drag/slider input, and commits a full LOD when the input
ends. It does not fetch multi-gigabyte DEMs directly from the browser.

## Out of scope

- Flood simulation, hydraulic water surfaces, bathymetry, and real-time terrain editing.
- Nationwide 1 m prefetching, raw point-cloud processing, and Alaska/IfSAR normalization.
- Treating arbitrary SVG paths as an accurate 3D model without associated source/DEM provenance.

## Acceptance criteria for the first shippable 3D build

1. Clark County, WA can produce a cached DEM-backed terrain/rivers scene with recorded source
   metadata and no synthetic Z values.
2. Every river vertex in the scene has a queryable source-derived elevation or an explicit
   nodata diagnostic.
3. The preview uses a lower LOD during interaction and full LOD only on commit.
4. A GLB and adjacent JSON manifest export deterministically from the same cached inputs.
5. The existing 2D SVG path remains operational and does not download DEMs unless 3D is asked
   for.
