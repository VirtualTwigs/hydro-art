# Specification: Source-traceable Waterbody Outlines

## Goal

Extend the canonical 2D hydrography render with accurate, editable outlines for selected areal
water features: lakes, reservoirs, large ponds, bays, and inlets. The result remains original,
deterministic, and derived only from public hydrography data.

## Data flow

```text
NHD waterbody/area layers
  → attribute-preserving load
  → classify by source type/code + geometry
  → repair → EPSG:5070 → region/coast-aware clip
  → area/detail selection + duplicate-edge QA
  → layered SVG waterbody outlines
  → optimize/export + selection report
```

This joins the present pipeline after data loading and follows the same repair/reprojection/clip
semantics as flowlines. It does **not** enter the directed river graph.

## Proposed model

`WaterbodyFeature` is an immutable value object:

- `source_id`, `source_layer`, `dataset_id`, `huc4`;
- geometry and original/normalized CRS;
- source attribute subset, type/code, optional name;
- normalized class (`lake`, `pond`, `reservoir`, `bay`, `inlet`, `coastal`, `excluded`);
- `area_m2`, inclusion reason, and QA flags.

`WaterbodySelection` contains the deterministic selected set plus counts and excluded-feature
reasons. This report is retained in `RunContext.artifacts` and optionally written next to output.

## Classification and selection

Classification is a versioned policy table keyed by source layer/type/code, with geometry and
region context as secondary evidence. Names may improve a human-readable report but cannot be
the sole classification method.

The initial policy has two independent thresholds:

- `min_inland_area_m2`: applies to ponds/lakes/reservoirs, with `0` preserving all valid source
  features;
- `min_coastal_area_m2`: applies to bays/inlets/coastal polygons only after coast policy.

The policy must explicitly exclude open-ocean extent and ambiguous clip-boundary fragments until
a reviewed coastal-outline mode is implemented. This favors omission over misleading geometry.

## Geometry processing

1. Use polygon-aware repair and remove empty/collapsed output.
2. Reproject to EPSG:5070 before area measurement.
3. Clip to the requested political/region boundary while preserving interior rings.
4. Preserve multipolygons as one source feature/group; retain holes in SVG path commands.
5. Detect duplicate or coincident edges between selected polygons. Render a canonical edge once
   where practical, or report an intentional overlap rather than double-stroking silently.

No simplification is applied by default. If enabled, it is a deterministic topology-preserving
operation applied after clipping and before rendering.

## SVG architecture

```xml
<g id="waterbodies" fill="none" stroke-linecap="round" stroke-linejoin="round">
  <g id="waterbody_<source-id>" data-class="lake">
    <path id="waterbody_<source-id>_outline" d="…"/>
  </g>
</g>
```

The `waterbodies` group is placed above the background and below or above flowlines according to
a configurable render order. A waterbody style includes stroke color, opacity, width, and
visibility. It defaults to a separate style rather than mutating watershed coloring.

## Configuration proposal

```yaml
waterbodies:
  enabled: false
  classes: [lake, reservoir, pond, bay, inlet]
  min_inland_area_m2: 0
  min_coastal_area_m2: 0
  coastal_mode: conservative
  style: outline
  stroke_width: 0.45
  color_mode: water
  simplification_tolerance_m: 0
```

CLI overrides, validation, and precedence must follow the current defaults < YAML < explicit CLI
pattern. Exact default values are an art-direction decision and must be approved before coding.

## Acceptance criteria

1. Fixture tests prove class selection, threshold behavior, hole/multipart preservation,
   EPSG:5070 area measurement, deterministic IDs, and no-fill SVG output.
2. A real Clark County, WA build visually validates at least one lake/pond and avoids accidental
   coast closure; Oregon/Washington builds validate larger inland/coastal examples.
3. Changing waterbody configuration affects only the waterbody branch/layers, not flowline graph,
   stream order, or watershed colors.
4. Default 2D builds remain unchanged until `waterbodies.enabled` is selected.
