# Spec Requirements: Natural Water Features (Epoch 15)

## Initial Description

Extend the hydro-art SVG river-art pipeline past lake/pond/reservoir/bay/inlet waterbody outlines (already shipped in Epoch 1.5) to the OTHER natural water features USGS NHD already ships in the same GDBs: springs/seeps, waterfalls, rapids, wetlands (marsh/swamp), playas, and perennial ice (glacier/snowfield). These are native FType-coded features in NHD NHDPoint / NHDArea (and NHDFlowline for falls/rapids on the network). Water-only theme — no roads or political basemap. No new data source and no new rights gate (USGS NHD is federal public domain, sellable with attribution). Must follow the Epoch 1.5 waterbody template exactly: versioned taxonomy → repair/reproject/clip/select → dedicated fill-free/point SVG layers → QA + screen/print presets. Integrates ADDITIVELY into PIPELINE_STAGES (loaded in the validate stage, selected in generate_svg) so a build stays byte-identical when the features are disabled (the default). Roadmap items 61–64.

## Requirements Discussion

### First Round Questions

The user answered **"all defaults"** — every proposed default is accepted exactly as framed, for all 10 numbered questions plus the two extras.

**Q1 (First-cut scope):** Should the first cut cover all six families end-to-end, with wells/sinkholes classified-but-excluded?
**Answer:** Accept default. First-cut scope = all six families (springs/seeps, waterfalls, rapids, wetlands marsh/swamp, playas, perennial ice) end-to-end. Wells and sinkholes are classified-but-excluded (present in the taxonomy, off by default).

**Q2 (Falls/rapids source):** Should falls/rapids come from NHDPoint only for the first cut, deferring flowline-coded falls/rapids?
**Answer:** Accept default. Falls/rapids from NHDPoint only (point glyphs). Flowline-coded falls/rapids on the network are deferred to a future note.

**Q3 (Loader seam):** Should we add a separate NHDPoint allowlist plus a `load_point_features` loader seam, mirroring `load_waterbody_layers`?
**Answer:** Accept default. Separate NHDPoint allowlist + `load_point_features` loader seam, mirroring the Epoch 1.5 `load_waterbody_layers` pattern.

**Q4 (Point glyphs):** Should point glyphs be springs = dots, waterfalls = chevrons, rapids = tick/zigzag, with configurable size/color per family?
**Answer:** Accept default. Point glyphs: springs = dots, waterfalls = chevrons, rapids = tick/zigzag marks; size and color configurable per family.

**Q5 (Areal treatment):** Should areals get differentiated treatment (wetlands = hatch/stipple, perennial ice = low-opacity fill, playas = dashed outline), each in its own `<g>` with configurable z-order?
**Answer:** Accept default. Differentiated areal treatment: wetlands = hatch/stipple, perennial ice = low-opacity fill, playas = dashed outline. Each family renders into its own `<g>` group with configurable z-order.

**Q6 (Z-order):** Should areals sit beneath flowlines/waterbodies and point glyphs sit on top of everything?
**Answer:** Accept default. Z-order: areals beneath flowlines/waterbodies; point glyphs on top of everything.

**Q7 (Preset controls):** Should presets control areal min-area thresholds AND a point-feature density cap / spacing knob?
**Answer:** Accept default. Presets control areal min-area thresholds AND a point-feature density cap / spacing knob.

**Q8 (Wetlands source):** Should wetlands be NHD-only, with NWI explicitly out of scope?
**Answer:** Accept default. NHD-only for wetlands; NWI (National Wetlands Inventory) explicitly out of scope / future note.

**Q9 (Default enablement):** Should every new natural-feature family default to `enabled: False` so the default build stays byte-identical (opt-in)?
**Answer:** Accept default. Every new natural-feature family defaults `enabled: False`; the default build stays byte-identical. Features are opt-in.

**Q10 (Exclusions):** Confirm the exclusions list?
**Answer:** Accept default. Out of scope: no elevation/3D or monthly-flow interaction; no `web/studio.html` control-surface wiring; no rights-gate / fulfillment changes; no flowline-network styling.

### Extra Questions

**Extra A (Existing code to mirror):** Any existing point-marker precedent to reference?
**Answer:** `tools/overlay_facilities.py` is the existing point-marker precedent — note it for the spec-writer.

**Extra B (Visual assets):** Any mockups/wireframes provided?
**Answer:** None provided (visuals folder empty).

### Existing Code to Reference

**Similar Features Identified:**
- **Epoch 1.5 waterbody template (primary model to mirror exactly):**
  - `src/waterbodies.py` — NHD polygon classification (versioned taxonomy pattern).
  - `src/waterbody_selection.py` — repair / reproject / clip + area/detail selection → outlines; `load_waterbody_layers` loader seam to mirror with the new `load_point_features` seam.
  - `config.WATERBODY_PRESETS` — `screen` / `print-state` / `print-county` art-direction presets; the `preset` directive expands to settings at config time (`defaults < preset < explicit`), stored off the frozen settings so no-preset builds stay byte-identical.
  - `validate` stage — additively loads waterbody layers when `settings.waterbodies.enabled`; the new point/areal loaders integrate the same way.
  - `generate_svg` stage — selects waterbody layers into outline layers; new families select into their own `<g>` layers here.
- **Point-marker rendering precedent:** `tools/overlay_facilities.py` — existing point-marker drawing logic; reference for glyph placement (dots/chevrons/ticks).
- **Shared render recipe:** `tools/render_common.py` — shared art-quality recipe (layered rasterization, HUC-N coloring, glow); extend rather than duplicate for any tool-side rendering.

### Follow-up Questions

None required — the user accepted all defaults, so there is no ambiguity to resolve.

## Visual Assets

### Files Provided:

No visual assets provided. Bash check of `planning/visuals/` returned no image/PDF files (folder is empty).

### Visual Insights:

None — no visual assets to analyze.

## Requirements Summary

### Functional Requirements

- Classify and render six additional natural water-feature families already present in the USGS NHD GDBs consumed by the pipeline:
  - **Springs / seeps** (NHDPoint) → dot glyphs.
  - **Waterfalls** (NHDPoint only, first cut) → chevron glyphs.
  - **Rapids** (NHDPoint only, first cut) → tick/zigzag glyphs.
  - **Wetlands — marsh / swamp** (NHDArea) → hatch/stipple areal treatment.
  - **Playas** (NHDArea) → dashed-outline areal treatment.
  - **Perennial ice — glacier / snowfield** (NHDArea) → low-opacity fill areal treatment.
- **Versioned taxonomy** including wells and sinkholes as classified-but-excluded entries (present in taxonomy, off by default).
- **Separate NHDPoint allowlist** and a **`load_point_features` loader seam** mirroring `load_waterbody_layers`.
- Point glyphs have **configurable size and color per family**; areal families each render into **their own `<g>` group with configurable z-order**.
- **Z-order:** areal features beneath flowlines/waterbodies; point glyphs on top of everything.
- **Presets** control areal **min-area thresholds** AND a **point-feature density cap / spacing knob**.
- **Additive pipeline integration:** load in the `validate` stage (when the family is enabled), select/render in `generate_svg` — mirroring the Epoch 1.5 waterbody integration.
- QA + screen/print presets follow the waterbody preset pattern (`defaults < preset < explicit`, expanded at config time, not stored on frozen settings).

### Reusability Opportunities

- Mirror `src/waterbodies.py` + `src/waterbody_selection.py` structure for the new point/areal classification and selection modules.
- Reuse the `load_waterbody_layers` loader-seam pattern for `load_point_features`.
- Reuse the `WATERBODY_PRESETS` / `preset` directive pattern for the new families' presets.
- Reference `tools/overlay_facilities.py` for point-marker glyph placement.
- Extend `tools/render_common.py` for any tool-side rendering rather than duplicating render logic.

### Scope Boundaries

**In Scope:**
- All six families end-to-end (springs/seeps, waterfalls, rapids, wetlands marsh/swamp, playas, perennial ice).
- Wells/sinkholes in the taxonomy but excluded by default.
- Falls/rapids from NHDPoint only.
- Differentiated point-glyph and areal SVG treatments with per-family configurable styling and z-order.
- Screen/print presets controlling areal min-area thresholds and point density/spacing.
- Additive load-in-validate / render-in-generate_svg integration.

**Out of Scope / Future Notes:**
- Flowline-coded (network) falls/rapids styling — deferred.
- NWI (National Wetlands Inventory) as a wetlands source — NHD-only for now.
- Elevation / 3D or monthly-flow interaction.
- `web/studio.html` control-surface wiring.
- Rights-gate / fulfillment changes.
- Flowline-network styling.
- No new data source; no roads or political basemap (water-only theme).

### Technical Considerations

- **Offline-suite discipline preserved:** no top-level GDAL-backed imports (`geopandas`/`pyogrio`/`rasterio`/`shapely`) in `src/` — keep them lazy-imported behind seams; every new `src/<name>.py` gets a matching `tests/test_<name>.py`; the full suite must remain runnable offline with no network and no real datasets.
- **Byte-identical default output:** every new family defaults `enabled: False`, so a default build produces byte-identical output to current. Preset/enablement state is resolved off the frozen `Settings` (mirroring the waterbody `preset` directive) so no-feature builds don't change rendered bytes.
- **Deterministic:** identical inputs → identical SVG output; preserve the no-global-state / immutable-`Settings` + mutable-`RunContext` discipline; stages communicate only through `ctx.artifacts`.
- **No new data source:** all features already exist in the USGS NHD GDBs the pipeline already consumes.
- **No new rights gate:** USGS NHD is federal public domain, sellable with attribution; no `fulfillment.assert_sellable` changes.
- **Additive integration only:** new work loads in `validate` and renders in `generate_svg` without adding or reordering `PIPELINE_STAGES`.
- **Boundary validation:** extend the relevant allowlists in `src/config.py` (NHDPoint allowlist) with fail-fast `ConfigError` validation, per existing conventions.
- **CRS:** import `INTERNAL_CRS` from `src/crs.py` (EPSG:5070); never re-inline the literal.
- Roadmap items 61–64.
