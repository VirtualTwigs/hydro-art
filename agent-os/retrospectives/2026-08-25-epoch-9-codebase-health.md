# Retrospective — Epoch 9: Codebase health & maintainability (#33–#38)

_Closed 2026-08-25. First entry in this practice (the 2026-08-25 audit found zero retro/lessons docs)._

## What the epoch was

No new product capability — every item was a refactor, test, or housekeeping fix
surfaced by the 2026-08-25 codebase audit. The hard invariant: **the offline suite
stays green and the 2D pipeline's default output stays byte-identical.** Held.

## What shipped

- **#33** — De-duplicated the `clip_flowlines` render recipe. Extended the canonical
  `tools/render_common.clip_flowlines` with `extra_vaa_cols`/`include_id` (backward-
  compatible return shape: 4-tuple unless extras/id requested, then 5-tuple) and
  deleted the two mirror copies (`render_state_mono.clip_flowlines_elev`,
  `render_state_mono_peak.clip_flowlines_elev_ids`).
- **#34** — Canonicalized the internal-CRS constant into `src/crs.py:INTERNAL_CRS`,
  re-exported from `src/raster.py`; `config.py`/`mesh.py`/`waterbody_selection.py`
  import it instead of raw `"EPSG:5070"`. Default projection still resolves to
  `EPSG:5070` (value-identical).
- **#35** — Derived `render_common.STATE_HUC4` from `src.datasets.REGION_HUC4`
  (extended with WA `1707`), killing the hand-maintained-mirror drift hazard. Derived
  table verified byte-identical to the old standalone one.
- **#36** — Extracted the six duplicated `web/` view helpers (`drawSwatches`,
  `fillCounties`, `buildTimeline`, `paintTimeline`, `seg`, `bindRange`) into
  `web/shared/hydro-ux.js`; all three pages call `HydroUX.*`. Two intentional local
  exceptions kept + documented: studio's `renderCountyOptions`, proto-c's divergent
  timeline pair.
- **#37** — `tests/test_pipeline.py` (stage order, no-stubs-remain, `_stub` no-op,
  `Stage` frozen, `stage_names`, single-`RunContext` threading). Shipped in the
  planning commit, green against existing behavior, no source change.
- **#38** — Housekeeping: reverted the `web/proto-b-guided.html:7` `/com` corruption,
  added `ruff`/`node` invocations + a "Known debt / gotchas" section to CLAUDE.md,
  repaired the stale "view logic lives only in `hydro-ux.js`" claim, and started this
  retrospective practice.

## What went well

- **Backward-compatible-shape discipline.** #33's optional-tuple return and #35's
  derived table were both verified byte-identical, so no downstream tool changed
  behavior. The "prove it's identical" step caught nothing broken but made the
  refactors safe to commit without a full GDAL render.
- **Tight commit scoping.** Several source files carried pre-existing uncommitted
  work (`src/raster.py`, `tests/test_raster.py`, a CLAUDE.md reformat). Each item's
  commit staged only its own hunks — `git apply --cached` with a crafted patch split
  the mixed `src/raster.py` (#34) and `proto-b-guided.html` (#36 vs the `/com` revert
  deferred to #38) files cleanly.

## Gotchas found (now in CLAUDE.md "Known debt / gotchas")

- **`ruff` isn't installed in `.venv`** and isn't pinned in `pyproject.toml`/
  `requirements.txt`, though it's the configured linter. `.venv/bin/ruff` was absent
  during #34; fell back to an AST-based unused-import check. `pip install ruff` first.
- The `web/` pages can only be loaded by the browser-automation MCP tool over
  **`http://`** (a local `python -m http.server`), not `file://` — the navigate tool
  hard-prepends `https://`. Verified all three pages that way (no console errors).

## Carry-forward

- Byte-identical **full** `build.py` render compare (svg_sha256) needs a GDAL + real-
  datasets environment; this epoch verified the only render-affecting change (#34's
  constant substitution) as value-identical instead. Re-confirm the sha on the next
  real render.
- Keep the retrospective practice: one closeout entry per epoch.
