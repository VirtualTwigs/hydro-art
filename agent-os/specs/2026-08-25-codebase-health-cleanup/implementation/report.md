# Implementation report — Codebase health & maintainability (Epoch 9, #33–#38)

Spec: `agent-os/specs/2026-08-25-codebase-health-cleanup/`
Closed: 2026-08-25

## Outcome

All six roadmap items landed. The epoch invariant held throughout: **the offline
suite stays green and the 2D pipeline's default output stays byte-identical** (pure
internal cleanups, no behavior change).

- Full suite: **527 passed** (43 warnings, all pre-existing `svgo`/deprecation noise).
- Web roundtrip: `node tests/test_recipe_roundtrip.cjs` → **11 passed**.
- No duplicated copy of `clip_flowlines` or the named `web/` view helpers remains.
- `src/pipeline.py` now has direct unit coverage (`tests/test_pipeline.py`).

## Task groups

- **TG0 (#37)** — `tests/test_pipeline.py`: stage order, no-stubs-remain, `_stub`
  no-op, `Stage` frozen, `stage_names`, single-`RunContext` threading, `log`
  delegation. Offline, inert sentinel collaborators. Shipped in the planning commit,
  green with no source change.
- **TG1 (#33)** — `render_common.clip_flowlines` gained `extra_vaa_cols`/`include_id`
  (backward-compatible 4-tuple → 5-tuple return); deleted
  `render_state_mono.clip_flowlines_elev` and
  `render_state_mono_peak.clip_flowlines_elev_ids`, both now call the shared recipe.
- **TG2 (#34)** — `src/crs.py:INTERNAL_CRS` is the single source of truth, re-exported
  from `src/raster.py`; `config.py`/`mesh.py`/`waterbody_selection.py` import it.
  `tests/test_crs.py` (5 offline tests) asserts the shared reference. Default
  projection resolves to `EPSG:5070`, value-identical.
- **TG3 (#35)** — `render_common.STATE_HUC4` derived from `src.datasets.REGION_HUC4`
  (+ WA `1707`); standalone table deleted. Derived table verified byte-identical
  (incl. WA's sorted `1707` position).
- **TG4 (#36)** — six DOM view helpers (`drawSwatches`/`fillCounties`/`buildTimeline`/
  `paintTimeline`/`seg`/`bindRange`) moved into `web/shared/hydro-ux.js`; `studio.html`
  /`proto-b-guided.html`/`proto-c-canvas.html` call `HydroUX.*`. Verified in a browser
  (served over `http://`): no console errors, helpers populate the DOM, `seg`/
  `bindRange` mutate state. Two intentional local exceptions documented in-line.
- **TG5 (#38)** — reverted the `web/proto-b-guided.html:7` `/com` corruption; added
  `ruff`/`node` invocations + a "Known debt / gotchas" section to CLAUDE.md and
  repaired the stale hydro-ux.js view-logic claim; started
  `agent-os/retrospectives/` with the epoch-closeout note.

## Verification notes / carry-forward

- **Byte-identical full `build.py` render (svg_sha256):** not run — no local
  `datasets/` and no GDAL environment here, so a real render isn't possible offline.
  The only render-affecting change was #34's constant substitution, verified
  value-identical (`build_settings({'region': ['Oregon']})` still resolves projection
  to `EPSG:5070`). Re-confirm the sha on the next real render.
- **`ruff`:** configured but not installed in `.venv` (now captured under CLAUDE.md
  "Known debt / gotchas").
