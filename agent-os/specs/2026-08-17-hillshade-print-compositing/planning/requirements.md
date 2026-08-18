# Requirements — Hillshade print compositing (roadmap #30, Epoch 8)

## Problem

Epoch 5 #22 shipped the pure hillshade primitive (`src/hillshade.hillshade` →
0-255 `RasterGrid`) and a web viewer (`web/experience.html`), but the shaded
relief has never been placed *under* the neon flowlines in a rendered image. The
current print path (`tools/rasterize_layered.py`) alpha-composites the river
layers over a **flat black** canvas (`Image.new("RGBA", size, (0,0,0,255))`). We
want a terrain background: compute hillshade from a region's real DEM, tint it,
and composite the existing river SVG art over it so mountains and valleys read
behind the network.

## Goals

1. A **pure, offline, numpy-only** compositing seam in `src/` that:
   - Turns a hillshade `RasterGrid` into an RGBA background raster: grayscale by
     default, optional single-color **tint** multiply, configurable **opacity**,
     and **nodata → transparent**.
   - Provides the alpha-"over" compositing operator and a fold that layers the
     rasterized river art over a background (generalizing today's flat-black base
     into a *supplied* background).
   - Deterministic; testable with hand-built `RasterGrid`s and small uint8 arrays
     — no GDAL, no resvg, no network.
2. A **thin, non-offline** `tools/render_terrain_print.py` that wires a region's
   real DEM (`dem.acquire_dem_for_settings` → `raster.normalize_dem` →
   `hillshade`) and the shared render recipe (`tools/render_common.py`) through
   the new seam to produce a terrain-backed print image.
3. **Byte-identical defaults**: nothing about the 2D vector pipeline, `Settings`,
   or existing tool output changes. The relief is purely additive in a `tools/`
   renderer.

## Non-goals

- Wiring any of this into `PIPELINE_STAGES` or `Settings` (the DEM subsystem
  stays a parallel, tool-driven model — CLAUDE.md).
- A full hypsometric **elevation** color ramp (single-color relief tint only for
  this slice; elevation-ramp tint is a follow-on).
- Resampling policy: matching the DEM grid resolution to the print canvas is a
  *tool* concern (PIL resize); the `src/` seam composites equal-shape arrays.
- Testing the non-offline tool end-to-end (needs GDAL + a real 3DEP DEM + resvg);
  its compositing math is exercised through the pure seam instead.

## Constraints / conventions

- `src/compositing.py`: `from __future__ import annotations`, numpy imported at
  top (consistent with `src/raster.py`/`src/hillshade.py`), frozen/pure funcs,
  a `CompositingError` boundary type, full docstrings + type hints.
- Every `src/<name>.py` has a matching `tests/test_<name>.py`.
- Determinism: float math folded to `uint8` with explicit rounding; identical
  inputs → identical arrays.

## Acceptance

- `src/compositing.py` + `tests/test_compositing.py` pass offline.
- Full suite stays green (no regressions); default tool output unchanged.
- A smoke render: synthetic DEM → hillshade → relief background → composite
  synthetic river layers → a real PNG on disk, proving the composite path without
  a real DEM.
