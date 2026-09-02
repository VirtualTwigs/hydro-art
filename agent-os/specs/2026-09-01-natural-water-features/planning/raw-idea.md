# Raw Idea: Natural Water Features (Epoch 15)

## Feature Description

Extend the hydro-art SVG river-art pipeline past lake/pond/reservoir/bay/inlet waterbody outlines (already shipped in Epoch 1.5) to the OTHER natural water features USGS NHD already ships in the same GDBs: springs/seeps, waterfalls, rapids, wetlands (marsh/swamp), playas, and perennial ice (glacier/snowfield). These are native FType-coded features in NHD NHDPoint / NHDArea (and NHDFlowline for falls/rapids on the network). Water-only theme — no roads or political basemap. No new data source and no new rights gate (USGS NHD is federal public domain, sellable with attribution). Must follow the Epoch 1.5 waterbody template exactly: versioned taxonomy → repair/reproject/clip/select → dedicated fill-free/point SVG layers → QA + screen/print presets. Integrates ADDITIVELY into PIPELINE_STAGES (loaded in the validate stage, selected in generate_svg) so a build stays byte-identical when the features are disabled (the default). Roadmap items 61–64.

## Roadmap Items

- Item 61
- Item 62
- Item 63
- Item 64

## Key Constraints

- No new data source — all features already exist in the USGS NHD GDBs already consumed by the pipeline.
- No new rights gate — USGS NHD is federal public domain, sellable with attribution.
- Must follow the Epoch 1.5 waterbody template exactly.
- Additive integration only — a build with features disabled must remain byte-identical to current output.
- Water-only theme — no roads or political basemap.

## NHD Feature Types to Support

- Springs / seeps (NHDPoint)
- Waterfalls (NHDPoint / NHDFlowline)
- Rapids (NHDPoint / NHDFlowline)
- Wetlands — marsh / swamp (NHDArea)
- Playas (NHDArea)
- Perennial ice — glacier / snowfield (NHDArea)

## Implementation Template

Follow the Epoch 1.5 waterbody pattern:
1. Versioned taxonomy
2. Repair / reproject / clip / select
3. Dedicated fill-free / point SVG layers
4. QA + screen/print presets
5. Additive load in the validate stage; render in generate_svg
