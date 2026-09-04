# Raw idea — Epoch 16 Item #67: Infrastructure rendering

From roadmap (`agent-os/product/roadmap.md`, Phase 16.3):

> 67. Infrastructure rendering — Symbol set for structures: dam/weir line symbols,
> gaging-station and intake point markers, spillway/lock areal treatment; dedicated
> `<g>` layers with z-order above water so a dam reads on the channel it crosses.
> Reuses the Epoch 15 point-glyph seam. `M`

Builds directly on #65 (`src/hydro_structures.py` — versioned FType taxonomy +
`src/loading.py` NHDLine seam), which is taxonomy + loader only. #67 is the render
item that makes those classified structures visible: it adds the selection/clip step,
the symbology, config settings, and pipeline wiring — mirroring how Epoch 15
(`src/point_features.py` / `src/areal_features.py` → `src/areal_selection.py` →
`src/rendering.py` → `src/pipeline.py`) shipped natural water features.

Kicked off 2026-09-03 by user ("kick off #67").
