# Requirements: Waterbody Outlines

## Source

- User request: outline lakes, inlets, bays, and large ponds in the generated art.
- Existing assets: NHDPlus HR/NHD hydrography archives, which currently load only flowlines and
  WBD boundaries through `src/loading.py`.
- Existing output rule: SVG is editable, deterministic, primarily fill-free vector art.

## Problem

The current art represents linear hydrography only. Lakes, ponds, bays, inlets, reservoirs, and
other areal water features are absent even when the source hydrography contains their polygons.
Naively drawing every polygon would create dense visual noise, introduce invalid/multipart rings,
and can accidentally portray clipped ocean/coastal polygons as closed inland lakes.

## Functional requirements

1. Discover and load the relevant NHD waterbody/area polygon layers in addition to the present
   flowline and WBD layers. Preserve per-feature source attributes required for classification.
2. Create an explicit taxonomy based on source feature type/code and geometry—not display name
   matching—for: lake, pond, reservoir, bay, inlet, estuary/coastal water, and excluded feature.
3. Retain the source feature ID, layer name, dataset/HUC source, and classification decision for
   every rendered waterbody.
4. Repair invalid geometry, normalize to EPSG:5070, and clip against the same selected region
   boundary as flowlines. Preserve polygon holes and multipart membership.
5. Support separate configurable inclusion thresholds for inland water and coastal water. “Large
   ponds” means a documented projected-area threshold, never an arbitrary rendering side effect.
6. Render selected features as closed SVG outlines with `fill="none"`, round joins, and stable
   IDs. Each feature is independently editable in Illustrator, Affinity Designer, Figma, and
   Inkscape.
7. Keep waterbody outlines in dedicated layers, separate from watershed flowline groups, so their
   z-order, stroke width, color policy, and visibility can be changed without rebuilding data.
8. Prevent duplicate shared edges/multiple identical polygon outlines from creating visibly
   over-thick strokes.
9. Define an explicit coast policy. Region clipping must not turn an open bay/inlet or a
   truncated sea polygon into a misleading closed waterbody outline.
10. The default selection must be deterministic. Identical input layers and settings produce
    byte-identical waterbody SVG fragments and a stable selection report.

## Non-functional requirements

- Reuse the project’s injectable `LayerLoader`, repair/reproject/clip seams, and offline test
  patterns; no network/GDAL requirement for the normal unit suite.
- No polygon simplification by default. Any optional simplification must be topology-preserving,
  named in configuration, and recorded in output metadata.
- Rendering must scale to state output without one SVG path per ring causing unacceptable file
  size or rasterization time; size/detail tiers are a policy surface, not silent dropping.

## Out of scope

- Filled water, bathymetry, shoreline elevation, or 3D water surfaces.
- Inferring missing water areas from imagery or tracing third-party artwork.
- Changing the existing flowline graph, stream order, watershed color assignment, or default 2D
  build unless waterbody outlines are explicitly enabled.

## Decisions resolved (2026-07-29)

1. **Enablement** — Waterbody outlines are **on by default** for new builds. (Applies to the W3
   render stage; W1/W2 add no default-build behavior change since they don't render yet.)
2. **Inland threshold** — `min_inland_area_m2` defaults to **0** (keep every valid inland
   polygon). Clutter is controlled later via presets/tiers, not a baked-in default.
3. **Color policy** — Outlines use a **single distinct water color**, independent of the
   watershed palette (`color_mode: water`). Changing waterbody config must not touch watershed
   coloring.
4. **Coast policy** — **Conservative**: classify bays/inlets/estuaries but exclude open-ocean
   extent (SeaOcean) and ambiguous clip-boundary fragments until a reviewed coastal-outline mode
   exists. Favor omission over misleading closed geometry.
