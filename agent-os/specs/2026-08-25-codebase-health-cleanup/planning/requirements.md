# Requirements — Codebase health & maintainability (roadmap #33–#38)

## Problem

A 2026-08-25 codebase audit (test coverage, code reuse, workflow/retrospective
state) surfaced concrete maintainability debt that no product feature depends on
but that erodes the project's stated invariants:

1. **Triplicated render recipe.** The "single art-quality recipe"
   (`tools/render_common.clip_flowlines`) is copy-pasted into
   `tools/render_state_mono.clip_flowlines_elev` and
   `tools/render_state_mono_peak.clip_flowlines_elev_ids` — ~120 lines of the same
   GDB iteration + VAA/EROM join + Strahler filter + shapely clip, differing only
   in which extra columns are carried. Both copies' docstrings admit they "Mirror"
   the original. `render_state_mono_peak.py` is currently **untracked**, so this is
   the moment to fix it before a third permanent copy lands.
2. **Scattered internal-CRS literal.** `src/raster.py` has the named constant
   `INTERNAL_CRS = "EPSG:5070"`, but `src/config.py`, `src/mesh.py`,
   `src/hydro_z.py`, and `src/waterbody_selection.py` hardcode the raw string.
3. **Hand-maintained HUC4 mirror.** `tools/render_common.STATE_HUC4` duplicates
   `src/datasets.REGION_HUC4` (Washington intentionally adds `1707`); the two can
   silently diverge.
4. **Duplicated `web/` view helpers.** `drawSwatches`, `buildTimeline`,
   `paintTimeline`, `fillCounties`, `bindRange`, `seg` are duplicated across
   `studio.html`, `proto-b-guided.html`, `proto-c-canvas.html` and are absent from
   the shared `web/shared/hydro-ux.js`, contradicting CLAUDE.md's stated rule.
5. **No `tests/test_pipeline.py`.** The 12-stage orchestrator (`src/pipeline.py`,
   ~550 LOC) has zero direct unit tests — only indirect coverage via the
   `test_*_pipeline.py` integration files.
6. **Uncommitted noise + no feedback loop.** `web/proto-b-guided.html:7` carries an
   accidental `/com` corruption; CLAUDE.md's Commands omit `ruff`/`node` test
   invocations; and the repo has zero retrospective/lessons docs despite a mature
   spec-per-item workflow.

## Scope (this item)

A single code-health batch (roadmap Epoch 9, items #33–#38). Each fix is a pure
refactor, a new test, or housekeeping — **no new `src/` capability**.

## Constraints (carried from the project)

- **Byte-identical default output.** The canonical 2D pipeline's default render
  must be byte-for-byte unchanged. #34/#35 touch only constants/imports; #33/#36
  touch `tools/`+`web/` (outside the pipeline); #37 adds tests only.
- **Offline suite stays green & GDAL-free.** No new top-level GIS imports under
  `src/`. `test_pipeline.py` must run offline (fake stages / injected collaborators,
  no real downloader/loader/network).
- **`src/` never imports `tools/` or `web/`.** #35 keeps the dependency direction
  `tools/ → src/` (render_common imports datasets, never the reverse).
- **`tools/` scripts stay outside the suite.** #33's closeout is a smoke-render of
  the two mono renderers, not a unit test (they import the GIS stack eagerly).

## Non-goals

- Any change to `PIPELINE_STAGES`, `Settings`, or rendered output semantics.
- Backfilling tests for every under-covered `tools/` script (only the
  orchestrator gap, #37, is in scope here).
- A full retrospective culture — just the lightweight directory + one closeout
  note (#38).

## Acceptance

- No duplicated copy of `clip_flowlines` remains; `render_state_mono` and
  `render_state_mono_peak` call the shared `render_common.clip_flowlines` with
  extra columns; both smoke-render.
- One canonical internal-CRS constant is imported by `config`/`mesh`/`hydro_z`/
  `waterbody_selection`; a test asserts the shared reference.
- `render_common.STATE_HUC4` is derived from `src.datasets.REGION_HUC4` (no manual
  duplicate table).
- The six named `web/` view helpers live only in `hydro-ux.js`; the three pages
  call them; no character-for-character duplicate remains.
- `tests/test_pipeline.py` covers stage order, "no stubs remain", `_stub` no-op,
  `Stage` immutability, `stage_names`, and single-`RunContext` threading — green
  against existing behavior.
- `web/proto-b-guided.html` corruption reverted; CLAUDE.md Commands gain
  `ruff check .` + `node tests/test_recipe_roundtrip.cjs`; `agent-os/retrospectives/`
  exists with one closeout note.
- Full suite green (no regressions); default output byte-identical.
