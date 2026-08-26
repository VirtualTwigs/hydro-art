# Tasks — Codebase health & maintainability (roadmap #33–#38)

## TG0 — Planning & the orchestrator test (this commit)
- [x] Add Epoch 9 (#33–#38) to `agent-os/product/roadmap.md`.
- [x] Write spec artifacts (`planning/requirements.md`, `spec.md`, `tasks.md`).
- [x] Write `tests/test_pipeline.py` (#37): stage order, no-stubs-remain, `_stub`
      no-op, `Stage` frozen, `stage_names`, single-`RunContext` threading, `log`
      delegation. Offline, inert sentinel collaborators.
- [x] Run ONLY `tests/test_pipeline.py` green.
- [x] Commit planning + the orchestrator test (leave #33–#36, #38 for implement).

## TG1 — De-duplicate `clip_flowlines` (#33)
- [x] Extend `tools/render_common.clip_flowlines` with `extra_vaa_cols`/`include_id`
      (backward-compatible return shape).
- [x] Delete `render_state_mono.clip_flowlines_elev` +
      `render_state_mono_peak.clip_flowlines_elev_ids`; point both at the shared
      recipe.
- [ ] Smoke-render one state through each mono renderer (non-offline; needs GDAL+NAS).

## TG2 — Canonical internal-CRS constant (#34)
- [x] Add `src/crs.py` (`INTERNAL_CRS`), re-export from `src/raster.py`.
- [x] Replace raw `"EPSG:5070"` in `config.py`/`mesh.py`/
      `waterbody_selection.py` with the import (`hydro_z.py` had only docstring
      mentions — no code literal to replace).
- [x] Add a tiny offline test asserting the shared reference; confirm default
      output byte-identical (resolved default projection unchanged: `EPSG:5070`).

## TG3 — Derive `STATE_HUC4` from `REGION_HUC4` (#35)
- [x] `render_common` imports `REGION_HUC4`, extends it with WA `1707`; delete the
      standalone table. (Derived table verified byte-identical to the old one,
      incl. WA's sorted `1707` position.)

## TG4 — Extract `web/` view helpers (#36)
- [x] Move `drawSwatches`/`buildTimeline`/`paintTimeline`/`fillCounties`/
      `bindRange`/`seg` into `web/shared/hydro-ux.js` (superset signatures).
- [x] Update `studio.html`/`proto-b-guided.html`/`proto-c-canvas.html` to call
      `HydroUX.*`; verify pages + `node tests/test_recipe_roundtrip.cjs`.

## TG5 — Housekeeping & retrospective (#38)
- [x] Revert `web/proto-b-guided.html:7` `/com` corruption.
- [x] CLAUDE.md: add `ruff`/`node` commands + "known debt / gotchas"; repair the
      `hydro-ux.js` view-logic claim.
- [x] Add `agent-os/retrospectives/` closeout note when Epoch 9 lands.

## Closeout
- [x] Full suite green (no regressions; 527 passed). Default `build.py` render
      byte-identical: not run offline (no local `datasets/`/GDAL); the only
      render-affecting change (#34 constant) verified value-identical instead —
      re-confirm `svg_sha256` on the next real render. Wrote `implementation/report.md`.
      Ticked Epoch 9 items `[x]` in the roadmap.
