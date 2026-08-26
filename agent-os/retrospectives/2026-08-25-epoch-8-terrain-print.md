# Retrospective — Epoch 8: Terrain-aware print output (#30–#32)

_Closed 2026-08-25. Written after the fact (this practice only started in Epoch 9
#38, and Epoch 8's real-tile closeout landed last — commit `96efe49`, after the
Epoch 9 closeout `6c3038a`)._

## What the epoch was

Bring the DEM subsystem's shaded relief into the printed river art: compute a
hillshade from a region's real 3DEP DEM, tint it, and composite the existing neon
flowline art over it — **without touching the canonical 2D pipeline, the vector
art's determinism, or the offline test posture.** The hard constraint held: the
compositing math is pure/numpy-only and stays in the offline suite; the flat-black
default print output is byte-identical when no DEM background is supplied.

## What shipped

- **#30** — Hillshade print compositing seam. `src/compositing.py` (pure, offline,
  numpy-only): `shade_to_background` turns a hillshade `RasterGrid` into a tinted
  RGBA relief (grayscale or single-colour tint multiply, opacity, **nodata→
  transparent**), and `solid_canvas`/`alpha_over` (Porter-Duff "over")/
  `composite_over_background` fold the rasterized river layers over a *supplied*
  background — generalising `tools/rasterize_layered.py`'s flat-black base.
  `CompositingError` boundary validation; `tests/test_compositing.py` (13). Thin
  non-offline `tools/render_terrain_print.py` wired it (commit `877e630`). **Shipped
  with a known gap:** no concrete DEM→`RasterGrid` read path existed, so the tool
  took a *supplied* `--dem` (.npy/image) instead of auto-acquiring.
- **#31** — Concrete 3DEP COG reader & reprojector. `src/raster_io.py` supplies the
  two GDAL/rasterio-backed collaborators `normalize_dem` always expected:
  `grid_from_arrays` (pure rasterio-affine → north-up `RasterGrid`, validates
  2-D/no-rotation/north-up), `RasterioRasterReader(opener=…)` (band 1 + transform +
  crs + nodata, provenance carried through) and `RasterioReprojector(warp=…)` with
  an **identity short-circuit** when already in the dst CRS. `rasterio` added to
  `requirements.txt` as an **optional, lazy-imported** dep (never at `src/` import),
  so the offline suite injects a fake `opener`/`warp` and stays GDAL-free. Ten
  offline tests (`tests/test_raster_io.py`). This closed the #30 gap — `--region`
  alone now produces a terrain-backed print (commit `33be712`).
- **#32** — Real-tile closeout. Ran the auto-acquire path end-to-end in the full
  GIS/DEM environment (rasterio actually installed) for the first time. Added **no
  new `src/` capability** — its deliverable was the artifact + a bug-fix the real
  run surfaced (commit `0954c69`, closeout `96efe49`).

## What went well

- **Seam-first slicing paid off.** The XL capability was cut into three tranches:
  the pure offline compositing seam (#30), the concrete GDAL collaborator *behind*
  that seam (#31), then real-tile validation (#32). Each earlier tranche was fully
  tested offline against injected fakes before the real environment was ever
  touched, so the real run had exactly one moving part left to debug.
- **The gate was not claimed until a real artifact existed.** #30/#31 were
  "code-complete and offline-green," but the epoch rule ("gated by a demonstrable
  artifact, not calendar dates") kept #32 as a distinct item. That discipline is
  precisely what caught the bug below — declaring victory at #31 would have shipped
  it.
- **The fix stayed a pure-module bug-fix.** The real-run bug was corrected inside
  `src/raster.py` (mosaic order + a relative-tolerance alignment check) with 12
  raster tests — no new capability, determinism intact, no change to the flat-black
  default.

## Gotchas found (now in CLAUDE.md "Known debt / gotchas")

- **Injected-fake coverage can't substitute for one real run when a branch only
  fires on real data.** The offline suite exercised only `RasterioReprojector`'s
  **identity short-circuit** (+ an injected warp spy). Real 3DEP 1/3" COGs arrive in
  EPSG:4269 (NAD83 geographic), *not* EPSG:5070 — so the **non-identity warp branch
  fired for the first time** in the #32 run. It exposed a genuine bug the fakes
  structurally could not: `normalize_dem` warped each 1°×1° tile to EPSG:5070
  *independently*, so per-tile output resolution drifted with latitude and the warped
  tiles no longer shared a pixel grid. Notably, the #32 spec **predicted this exact
  risk** ("watch the warped grid's transform/nodata/extent") — the prediction was
  right, which is the argument for keeping a real-tile validation item at all.
- **Fix: mosaic in the shared source CRS *before* the single warp.** Mosaic the
  tiles first, then warp the one mosaic once; `_require_aligned` compares pixel sizes
  with a **relative** tolerance so last-float-digit warp drift mosaics while a genuine
  tier change is still rejected. Do **not** "simplify" this back to warp-then-mosaic
  (now called out in CLAUDE.md).

## Carry-forward

- The real-tile artifact + tile ids/checksums/provenance live outside the offline
  suite by nature (non-offline `tools/` path). Re-confirm the composited PNG stays
  byte-identical on the next real render with the same cached tiles.
- Keep the retrospective practice: one closeout entry per epoch — and, as Epoch 8
  showed, don't let "offline-green" stand in for the real-environment run that
  actually exercises the GDAL/warp branches.
