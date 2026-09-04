# Raw idea — Epoch 16, Item #65

Hydro-structure source layers and classification. Load and classify the engineered-water
FTypes NHD already ships — dam/weir, gate, lock chamber (NHDLine); gaging station, dam/weir,
water intake/outflow, gate (NHDPoint); canal/ditch, lock chamber, spillway (NHDArea) — into a
versioned `HYDRO_STRUCTURE_POLICY_VERSION` taxonomy, and extend `src/loading.py` allowlists +
attribute fields to load the one genuinely-new source layer (NHDLine).

Mirror the Epoch 15 natural-water-features template (`src/point_features.py`,
`src/areal_features.py`) and the Epoch 1.5 waterbody template beat-for-beat: versioned
FType-driven taxonomy, name-only-refining, missing FType → excluded/never-guessed, full
provenance retained, no geometry math, no top-level GDAL imports (runs fully offline).

This is item #65 only — **source layers and classification**. Rendering (#67), engineered-channel
styling on the flowline network (#66), and QA/presets (#68) are separate later items. Still strictly
water-related and still USGS public domain (sellable with attribution, **no new rights gate**).
