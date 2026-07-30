# Implementation Report — W1: Waterbody source layers & classification

_Date: 2026-07-29 · Roadmap Epoch 1.5, Phase 1.5.1 (W1) · Task Group 1 only._

## Scope

Delivered the **ingestion & taxonomy contract** for areal water. This is the
classification layer only — no pipeline stage, no config surface, and no
rendering (those are W2/W3). Default 2D builds are therefore unchanged and
byte-identical; nothing in the live pipeline calls the new code yet.

## Resolved decisions (baked into policy/docs, applied fully in W2/W3)

1. Enablement: **on by default** (render-stage concern, W3).
2. Inland threshold: `min_inland_area_m2` = **0** (keep all valid; W2 selection).
3. Color: **single distinct water color**, independent of watershed palette (W3).
4. Coast: **conservative** — classify bays/inlets/estuaries; exclude SeaOcean
   and clip-boundary fragments until a reviewed coastal mode exists.

## Changes

- `src/loading.py`
  - `WATERBODY_LAYER_ALLOWLIST = ("NHDWaterbody", "NHDArea")` — deliberately
    **separate** from `HYDRO_LAYER_ALLOWLIST` so waterbody polygons never leak
    into the flowline/graph load path.
  - `WATERBODY_ATTRIBUTE_FIELDS` — the source columns retained for
    classification + provenance (FType, FCode, GNIS_Name, Permanent_Identifier,
    ReachCode, AreaSqKm).
  - `discover_waterbody_layers()` — case-insensitive discovery wrapper.
  - `PyogrioLayerLoader.load_waterbody_layers()` — real loader that populates
    `Layer.attributes` (parallel to geometries) from the present attribute
    columns. Marked `# pragma: no cover` (needs GDAL + real data); the offline
    suite exercises the contract via injected fake `Layer`s.
- `src/waterbodies.py` (new)
  - `WaterbodyFeature` immutable value object with full source provenance
    (source_id, layer, dataset, huc4, ftype/fcode, name, crs, attributes,
    class, inclusion_reason, qa_flags).
  - Versioned policy: `WATERBODY_POLICY_VERSION`, `WATERBODY_CLASSES`,
    `FTYPE_CLASS` (FType → normalized class), `FTYPE_LABELS`.
  - `classify_waterbody()` / `classify_layer()`. Classification is FType-driven;
    name is *secondary only* (splits BayInlet into bay vs. inlet). Missing/
    unknown FType → `excluded` + `missing_ftype` QA flag (never guessed).
  - No GIS imports; pure/offline. Repair, reprojection, area measurement, and
    threshold selection are intentionally deferred to W2.

## Classification policy (v2026-07-29.1)

| FType | Label       | Class     | Note                                   |
|-------|-------------|-----------|----------------------------------------|
| 390   | LakePond    | lake      | pond split is area-based (W2)          |
| 436   | Reservoir   | reservoir |                                        |
| 493   | Estuary     | coastal   |                                        |
| 312   | BayInlet    | bay       | name refines bay↔inlet                 |
| 445   | SeaOcean    | excluded  | conservative coast policy              |
| 460   | StreamRiver | excluded  | areal river → drawn as flowline        |
| 466   | SwampMarsh  | excluded  | wetland, not open water                |
| 361   | Playa       | excluded  |                                        |
| 378   | IceMass     | excluded  |                                        |
| 336   | CanalDitch  | excluded  |                                        |

## Tests

- `tests/test_waterbodies.py` (7): FType classification for lake/reservoir/
  estuary; bay↔inlet name refinement; SeaOcean exclusion; missing-FType QA
  flag; `classify_layer` provenance/ordering; stable policy version & vocab.
- `tests/test_loading.py` (+2): waterbody allowlist is separate from flowline
  discovery; `discover_waterbody_layers` case-insensitive filtering.
- New tests: 9. Full suite: **159 passed**, no regressions.

## Follow-ups (W2+)

- W2: polygon repair → EPSG:5070 → region clip → `area_m2` measurement →
  threshold/coastal selection + duplicate-edge QA + `WaterbodySelection` report.
- W3: `waterbodies` config block (enabled/color/threshold/coast) + a pipeline
  stage + dedicated no-fill SVG layers.
- Wire `load_waterbody_layers` into the pipeline (unused until W2/W3).
