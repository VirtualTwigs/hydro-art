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
- [ ] Extend `tools/render_common.clip_flowlines` with `extra_vaa_cols`/`include_id`
      (backward-compatible return shape).
- [ ] Delete `render_state_mono.clip_flowlines_elev` +
      `render_state_mono_peak.clip_flowlines_elev_ids`; point both at the shared
      recipe.
- [ ] Smoke-render one state through each mono renderer (non-offline).

## TG2 — Canonical internal-CRS constant (#34)
- [ ] Add `src/crs.py` (`INTERNAL_CRS`), re-export from `src/raster.py`.
- [ ] Replace raw `"EPSG:5070"` in `config.py`/`mesh.py`/`hydro_z.py`/
      `waterbody_selection.py` with the import.
- [ ] Add a tiny offline test asserting the shared reference; confirm default
      output byte-identical.

## TG3 — Derive `STATE_HUC4` from `REGION_HUC4` (#35)
- [ ] `render_common` imports `REGION_HUC4`, extends it with WA `1707`; delete the
      standalone table.

## TG4 — Extract `web/` view helpers (#36)
- [ ] Move `drawSwatches`/`buildTimeline`/`paintTimeline`/`fillCounties`/
      `bindRange`/`seg` into `web/shared/hydro-ux.js` (superset signatures).
- [ ] Update `studio.html`/`proto-b-guided.html`/`proto-c-canvas.html` to call
      `HydroUX.*`; verify pages + `node tests/test_recipe_roundtrip.cjs`.

## TG5 — Housekeeping & retrospective (#38)
- [ ] Revert `web/proto-b-guided.html:7` `/com` corruption.
- [ ] CLAUDE.md: add `ruff`/`node` commands + "known debt / gotchas"; repair the
      `hydro-ux.js` view-logic claim.
- [ ] Add `agent-os/retrospectives/` closeout note when Epoch 9 lands.

## Closeout
- [ ] Full suite green (no regressions). Default `build.py` render byte-identical
      (compare `svg_sha256`). Write `implementation/report.md`. Tick Epoch 9 items
      `[x]` in the roadmap.
