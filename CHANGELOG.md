# Changelog

All notable changes to Hydro-Art. This project adheres to semantic versioning; the
release history below is generated from the Agent-OS roadmap epochs.

## v1.0.0 — 2026-09-06

- Generation 1 production release: four stable customer endpoints (digital image, animation, print image, watershed report), a full test pyramid, a flagship all-four-endpoints e2e proof, a rights-clean marketing gallery, and a reproducibility release gate.
- Default 2D pipeline output is byte-for-byte deterministic; only public-domain sources (USGS NHDPlus HR / NHD / WBD, nClimGrid) ship in any sellable asset.

### Epoch 1 — 2D hydrographic art foundation
- **#1** Configuration & CLI foundation
- **#2** Dataset acquisition & cache
- **#3** Data loading & geometry validation/repair
- **#4** Projection & region clipping
- **#5** Hydrography graph construction
- **#6** Stream ordering & watershed grouping
- **#7** Deterministic basin coloring
- **#8** Layered SVG rendering
- **#9** Optional glow & SVG optimization
- **#10** Multi-format export & reproducibility hardening

### Epoch 1.5 — waterbody outlines
- **#W1** Waterbody source layers and classification
- **#W2** Waterbody repair, clipping & selection
- **#W3** Waterbody-outline rendering
- **#W4** Waterbody QA and regional presets

### Epoch 2 — elevation data foundation
- **#11** Elevation settings and provenance model
- **#12** 3DEP DEM discovery, download & cache
- **#13** DEM mosaic, clip & pyramid

### Epoch 3 — accurate terrain and hydrography Z
- **#14** Terrain sampling service
- **#15** River elevation attribution & QA
- **#16** Adaptive terrain mesh

### Epoch 4 — 3D modeling and delivery
- **#17** 3D scene assembly
- **#18** Progressive 3D preview
- **#19** Reproducible 3D export

### Epoch 5 — quality, scale, and productization
- **#20** Accuracy validation suite
- **#21** Regional scale & offline packaging
- **#22** Print/experience modes

### Epoch 6 — interactive art-direction UX
- **#23** Color & line-width art-direction options
- **#24** County scope in the pipeline
- **#25** Monthly-flow rendering option
- **#26** Web control surface
- **#27** Live pipeline integration
- **#28** Presets & shareable render recipes

### Epoch 7 — external storage & data operations
- **#29** External-storage layout & output migration

### Epoch 8 — terrain-aware print output
- **#30** Hillshade print compositing
- **#31** 3DEP COG reader & reprojector
- **#32** Terrain-print real-tile closeout

### Epoch 9 — Codebase health & maintainability
- **#33** De-duplicate the `clip_flowlines` render recipe
- **#34** Canonicalize the internal-CRS constant
- **#35** Derive `STATE_HUC4` from `REGION_HUC4`
- **#36** Extract duplicated `web/` view helpers into `hydro-ux.js`
- **#37** Pipeline orchestrator unit tests
- **#38** Housekeeping & retrospective practice

### Epoch 10 — Verification & real-data confidence
- **#39** Determinism verifier
- **#40** Golden-output fixtures for one small region
- **#41** Real-data smoke harness (opt-in, outside the offline suite)
- **#42** DEM alignment invariant on real tiles
- **#43** HANDOFF/roadmap status automation

### Epoch 11 — Year-over-year historical flow (Option C)
- **#44** Historical-flow disaggregation engine
- **#45** PRISM monthly climate provider
- **#46** Year-over-year render mode
- **#47** Add Utah as a supported region

### Epoch 11.5 — Revenue Validation (gated commercial track)
- **#56** Narrow made-to-order listing
- **#57** Repeatable fulfillment pack
- **#58** Instrument the test
- **#59** Revenue gate

### Epoch 12 — Watershed report analytics
- **#48** Hydrograph-metrics engine
- **#49** Trend, percentile & rolling-normal statistics
- **#50** Model-vs-gauge validation
- **#51** Climate-index teleconnection
- **#52** PRISM back-catalog extension
- **#53** Sub-watershed & longitudinal decomposition
- **#54** Parametrized watershed-report builder

### Epoch 13 — Web watershed-report view
- **#55** Web report mode (proposed UX)

### Epoch 14 — License-free climate source (retire the PRISM rights gate)
- **#60** Public-domain climate provider

### Epoch 15 — Natural water features beyond waterbodies
- **#61** Point-feature source layers and classification
- **#62** Wetland / playa / perennial-ice ingestion, selection & clipping
- **#63** Water-feature rendering
- **#64** Feature QA and presets

### Epoch 16 — Hydro-infrastructure layers
- **#65** Hydro-structure source layers and classification
- **#66** Canal / ditch / aqueduct / pipeline styling
- **#67** Infrastructure rendering
- **#68** Infrastructure QA and presets

### Epoch 17 — Watershed report: creative analytics
- **#69** Snow-vs-rain regime signature
- **#70** Center-of-timing drift as a hero metric
- **#71** Analog-year finder
- **#72** Drought / flood record book
- **#73** Flow-duration-curve panel
- **#74** ENSO / PDO composite hydrographs
- **#75** Longitudinal flow-accumulation animation
- **#76** Report assembly & web view

### Epoch 18 — Scale-aware flow-width presets
- **#77** `width_log` setting + `WIDTH_PRESETS`
- **#78** `--width-preset` flag

### Epoch 19 — Production endpoint contracts & hardening
- **#79** Endpoint output contracts
- **#80** Endpoint dispatch consolidation
- **#81** Provenance & failure-mode hardening

### Epoch 20 — Unit & integration test completion
- **#82** Unit-coverage audit & gap closure
- **#83** Endpoint integration tests (offline)
- **#84** Coverage gate & reporting

### Epoch 21 — Flagship end-to-end proof (all four endpoints)
- **#85** Offline all-endpoints e2e orchestration test
- **#86** Real-data e2e harness (opt-in, outside the suite)
- **#87** E2E golden fixture

### Epoch 22 — High-resolution marketing gallery
- **#88** Curated style matrix
- **#89** High-res render & export
- **#90** Gallery provenance & rights ledger

### Epoch 23 — Release packaging, CI & reproducibility gate
- **#91** CI for the full test pyramid
- **#92** Reproducibility release gate
- **#93** Version, changelog & distribution packaging
