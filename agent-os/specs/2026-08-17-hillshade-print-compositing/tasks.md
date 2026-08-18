# Tasks — Hillshade print compositing (roadmap #30)

## TG1 — Relief background from hillshade (`shade_to_background`)
- [x] Write tests: grayscale mapping (r=g=b=shade); tint multiply; nodata cell →
      alpha 0; opacity scales valid-cell alpha; validation errors (bad opacity /
      malformed tint) raise `CompositingError`; output is HxWx4 uint8.
- [x] Implement `CompositingError` + `shade_to_background` in `src/compositing.py`.
- [x] Run ONLY the TG1 tests green.

## TG2 — Alpha compositing (`solid_canvas`, `alpha_over`, `composite_over_background`)
- [x] Write tests: `solid_canvas` opaque single colour; `alpha_over` opaque-over,
      transparent-over (identity), partial-alpha blend, out_a==0 → rgb 0;
      shape/dtype mismatch raises; `composite_over_background` folds in order and
      empty layers returns background copy.
- [x] Implement the three functions in `src/compositing.py`.
- [x] Run ONLY the TG2 tests green.

## TG3 — Non-offline print tool + docs
- [x] Add `tools/render_terrain_print.py` wiring DEM → hillshade → seam →
      `render_common` river art → composited PNG.
- [x] Smoke: synthetic DEM grid → hillshade → `shade_to_background` →
      `composite_over_background` with synthetic river layers → write a real PNG.
- [x] Update CLAUDE.md (module map + tools) and `implementation/report.md`.
- [x] Full suite green (no regressions). #30 left as a **progress** note (not
      `[x]`): the compositing seam + runnable tool shipped and are tested, but the
      epoch gate (print over accurate 3DEP relief) awaits a concrete DEM
      `RasterReader` — a documented follow-on. See report.md "Honest scope note".
