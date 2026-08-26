# Spec — Codebase health & maintainability (roadmap #33–#38)

A batch of pure refactors + one test + housekeeping. Grouped below by roadmap
item. The planning commit ships only #37's test (green now); the rest are
implemented in the follow-up per the two-command workflow.

## #33 — De-duplicate `clip_flowlines`

Extend the canonical recipe instead of mirroring it.

- `tools/render_common.clip_flowlines(...)` gains keyword-only params:
  - `extra_vaa_cols: list[str] = []` — extra `NHDPlusFlowlineVAA` columns to read
    and attach to each returned record (e.g. `MinElevSmo`, `MaxElevSmo`).
  - `include_id: bool = False` — carry `NHDPlusID` through when a caller needs the
    stable reach id (the peak renderer's join key).
  - The return shape stays backward-compatible: existing callers that don't pass
    the new params get today's records unchanged.
- Delete `tools/render_state_mono.clip_flowlines_elev` and
  `tools/render_state_mono_peak.clip_flowlines_elev_ids`; both callers use
  `render_common.clip_flowlines(..., extra_vaa_cols=["MinElevSmo","MaxElevSmo"],
  include_id=…)`.
- Closeout: smoke-render one state through each mono renderer (non-offline, so no
  unit test); confirm the image is produced. Fix lands **before**
  `render_state_mono_peak.py` is committed so no third copy is ever tracked.

## #34 — Canonicalize the internal-CRS constant

- Introduce one canonical constant. Preferred: a tiny `src/crs.py` exporting
  `INTERNAL_CRS = "EPSG:5070"` (GDAL-free, stdlib-only), and have `src/raster.py`
  re-export/import it for its existing name so nothing downstream breaks.
- Replace the raw `"EPSG:5070"` literals in `src/config.py` (the
  `"projection": "EPSG:5070"` default), `src/mesh.py` (the `crs` field default),
  `src/hydro_z.py`, and `src/waterbody_selection.py` with the imported constant.
  Leave `SUPPORTED_PROJECTIONS` (a user-facing allowlist that legitimately lists
  several EPSG strings) as-is, but its `EPSG:5070` entry may reference the constant.
- Determinism: this is a rename; the resolved default projection string is
  identical, so default output is byte-identical.

## #35 — Derive `STATE_HUC4` from `REGION_HUC4`

- `tools/render_common` imports `REGION_HUC4` from `src.datasets` and builds
  `STATE_HUC4` by copying it and adding Washington's extra `"1707"` (documented
  inline as the one intentional delta). No standalone duplicate table.
- Dependency direction preserved (`tools/ → src/`).

## #36 — Extract duplicated `web/` view helpers

- Move into `web/shared/hydro-ux.js` (on the `window.HydroUX` object, mirroring the
  existing helper style) as pure functions over already-exported option data:
  `drawSwatches(state)`, `buildTimeline()`, `paintTimeline(state)`,
  `fillCounties(state)`, `bindRange(...)`, `seg(...)`. Where a page had a slight
  variation (e.g. `studio.html`'s `bindRange` `after` callback), the shared version
  takes the superset signature so all three pages can adopt it.
- `studio.html`, `proto-b-guided.html`, `proto-c-canvas.html` drop their local
  copies and call `HydroUX.*`.
- Keep the CommonJS `module.exports` shim in `hydro-ux.js` intact so
  `tests/test_recipe_roundtrip.cjs` (and any new headless check) still loads it.

## #37 — Pipeline orchestrator unit tests (ships in the planning commit)

`tests/test_pipeline.py`, offline, no real collaborators. Covers the structural
contracts of `src/pipeline.py`:

1. `PIPELINE_STAGES` names equal the canonical 12-stage order (PRD §8).
2. **No stubs remain** — every `PIPELINE_STAGES` entry's `.run` is the exact
   `_STAGE_FUNCS[name]` object (not a `_stub`).
3. `_stub(name)` returns a no-op that logs `(stub)` and never touches
   `ctx.artifacts`.
4. `Stage` is a frozen dataclass (`FrozenInstanceError` on mutation).
5. `Pipeline(stages=…).stage_names` reflects the injected stage order.
6. `Pipeline.run` threads a **single** `RunContext` through the stages in order:
   two fake stages (one writes an artifact, the next reads it) prove ordering +
   shared `artifacts`, and the returned context carries both writes. Injected
   downloader/loader/optimizer/exporter are inert sentinels (the fake stages never
   use them), so no GDAL/network is touched.
7. `RunContext.log` delegates to `console.log`.

## #38 — Housekeeping & retrospective practice

- Revert `web/proto-b-guided.html:7` — the stylesheet `<link>` must end `... />`
  with no trailing `/com`.
- CLAUDE.md Commands: add `.venv/bin/ruff check .` and
  `node tests/test_recipe_roundtrip.cjs`; add a short "known debt / gotchas" note
  (pipeline test gap now filled by #37; the de-dup items #33–#35; the byte-identical
  invariant). Also soften/repair the "view logic lives only in `hydro-ux.js`" claim
  once #36 makes it true.
- `agent-os/retrospectives/` gains a lightweight closeout note (template + the first
  entry when Epoch 9 closes).

## Test & verification plan

- #37 test is written and run green now (only-those-tests, then full suite).
- #34 gains a tiny offline unit assertion that `config`/`mesh` reference the shared
  constant (written during implementation).
- #33/#35/#36 are `tools/`+`web/` changes: verified by smoke-render / opening the
  pages / the existing `node` harness, not the offline pytest suite.
- Epoch-close check: full suite green + a default `build.py` render is
  byte-identical to a pre-change baseline (compare `svg_sha256`).
