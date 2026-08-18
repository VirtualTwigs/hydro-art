# Implementation report — Hillshade print compositing (roadmap #30)

## What shipped

**`src/compositing.py`** — a pure, offline, numpy-only compositing seam:

- `shade_to_background(grid, *, tint=None, opacity=1.0)` — hillshade `RasterGrid`
  (0-255, nodata sentinel) → `(H, W, 4)` uint8 RGBA. Grayscale by default; a
  single-colour `tint` multiplies the normalised shade; valid cells get
  `round(255*opacity)` alpha; **nodata cells → alpha 0** (relief never invents
  terrain).
- `solid_canvas(h, w, color)` — opaque single-colour RGBA backdrop.
- `alpha_over(base, over)` — Porter-Duff "over" of two equal-shape uint8 RGBA
  arrays (straight alpha in float → rounded to uint8; `out_a==0` → rgb 0).
- `composite_over_background(background, layers)` — folds river-art layers over a
  supplied background via `alpha_over` (generalising the flat-black canvas in
  `tools/rasterize_layered.py` into a *supplied* relief background).
- `CompositingError` boundary type; validates opacity range, tint shape/range,
  and array shape/dtype/channel matches.

**`tools/render_terrain_print.py`** — non-offline executor: clips flowlines via
`tools/render_common.py`, renders the neon art SVG, splits it into per-watershed
layers (`tools/rasterize_layered.split_layers`) and resvg-rasterises each to a
transparent RGBA layer, loads a bare-earth DEM grid, runs `src.hillshade.hillshade`
→ `shade_to_background`, resizes the relief to the render canvas, and composites
`black base ← relief ← river layers` through the seam to a PNG. Supports
state / county / bbox scope, sun params, relief tint/opacity.

## Tests (TDD)

`tests/test_compositing.py` — 13 tests, offline (numpy hand-built inputs):
grayscale mapping, tint multiply, nodata→transparent, opacity scaling, input
validation (TG1); solid canvas, alpha-over opaque/transparent/partial/zero-alpha,
shape-mismatch guard, layer fold order, empty-layers copy (TG2).

**Full suite: 502 passed** (was 489; +13), no regressions. New files stay within
the 88-char line limit.

## Smoke evidence

Ran the full compositing chain end-to-end (offline, no GDAL/resvg): a synthetic
bare-earth DEM (diagonal ridge + a nodata corner) → `hillshade` →
`shade_to_background(tint=(210,180,140), opacity=0.9)` → `composite_over_background`
with two synthetic transparent neon "river" layers → a real
`/tmp/terrain_print_smoke.png` (832 B, 120×120). Verified the nodata corner is
transparent, valid-cell relief alpha is `round(255*0.9)`, and the neon river rows
sit over the tinted relief. Also exercised the tool's `_load_dem_grid` for both
`.npy` and image DEM inputs, and confirmed the tool imports + argparses cleanly.

## Honest scope note (important)

The compositing capability and a runnable print tool shipped and are tested/
smoke-proven. **However, the Epoch 8 gate — a print over *accurate 3DEP bare-earth
relief* — is not yet met**, because the DEM→`RasterGrid` read path does not exist:
`RasterReader`/`RasterReprojector` are Protocol-only (no concrete implementation),
`rasterio` is not a dependency, and no repo code turns cached 3DEP COG tiles into a
grid. So `render_terrain_print.py` takes a *supplied* DEM grid (`--dem` .npy/image)
rather than auto-acquiring from 3DEP. Wiring `dem.acquire_dem_for_settings` →
`raster.normalize_dem` end-to-end needs a concrete COG reader — a separate,
larger, non-offline piece. Recommend tracking that as a follow-on item before
marking #30 fully done / the epoch gate closed.

## Files

- `src/compositing.py` (new), `tests/test_compositing.py` (new)
- `tools/render_terrain_print.py` (new)
- `agent-os/specs/2026-08-17-hillshade-print-compositing/` (spec artifacts)
- `CLAUDE.md` (module map + tools), `agent-os/product/roadmap.md` (#30 progress)
