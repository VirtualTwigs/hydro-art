# Retrospective — Epoch 6: Interactive art-direction UX (#23--#28)

_Closed 2026-08-12 (final commit `b80296d`, #28). Retro written 2026-09-16. **No
pre-registered watch-list** -- none of the six spec folders carry a
`planning/pre-analysis.md`. This is a narrative closeout; the missing pre-analysis
is noted under Lessons._

## What the epoch was

The first epoch that gave a non-developer a way to **see and control** the
pipeline's art-direction knobs. Before Epoch 6 the renderer had a fixed default
style (watershed coloring, uniform stroke widths, no county scope, no monthly
disaggregation) and the only way to change it was editing Python dicts. This epoch
promoted every proposed art-direction option into validated `Settings` fields with
CLI flags, added a canonical web control surface (`web/studio.html`) with a live
preview and a real pipeline integration path, and closed with shareable render
recipes encoded into a URL hash -- so one user can hand a link to another and
reproduce the exact same art-direction state.

Six items, shipped in strict dependency order: #23 (config/render) -> #24
(county) -> #25 (monthly) -> #26 (web surface) -> #27 (live pipeline) -> #28
(recipes).

## What shipped

### #23 -- Color & line-width art-direction options (`5910141`)

`src/config.py` -- `SUPPORTED_COLOR_MODES` (`watershed`|`single`|`elevation`),
`SUPPORTED_WIDTH_MODES` (`uniform`|`flow`); six new `Settings` fields
(`color_by`, `single_color`, `width_by`, `width_min`, `width_max`, `width_gamma`)
with boundary validation. `src/rendering.py` -- `hypsometric_colors` and
`scaled_widths` promoted from the tools layer. `src/pipeline.py` --
`_assign_colors_stage` branches on `color_by` (including fail-fast `ConfigError`
for `elevation`); `_generate_svg_stage` branches on `width_by` via
`_resolve_stroke_widths`. Six CLI flags in `src/cli.py`. Tests: +18 across
`test_config.py` (+8), `test_cli.py` (+2), `test_rendering_svg.py` (+4),
`test_rendering_pipeline.py` (+4). Suite: **294 passing** (was 276).

### #24 -- County scope in the pipeline (`489b511`)

New `src/counties.py`: `STATE_FIPS`, `state_fips_for_region`,
`county_boundary` + injectable `CountyBoundaryProvider`/`CensusCountyProvider`
(lazy geopandas, GDAL-free at import). `src/pipeline.py` -- `_clip_stage`
branches on `settings.county` (county polygon vs. WBD region); `_export_stage`
names the file after the county (e.g. `oregon-hood-river.svg`). CLI: `--county`.
Tests: +16 across `test_config.py` (+4), `test_cli.py` (+3), `test_counties.py`
(6 new), `test_county_pipeline.py` (3 new). Suite: **310 passing**.

### #25 -- Monthly-flow rendering option (`6c18a0d`)

New `src/monthly_flow.py` (numpy-only, offline):
`snow_available_water`/`normalize_shape`/`accumulate_downstream`/`disaggregate_monthly`.
`src/rendering.py` -- `fixed_flow_span`/`widths_on_span`/`monthly_width_frames`.
`src/config.py` -- `parse_months` (single/name/range/wrapping) + `Settings.months:
tuple[int, ...]` (empty = annual). Pipeline fail-fast on non-annual months (same
pattern as `color_by=elevation`). `tools/monthly_flow.py` and
`tools/render_monthly.py` refactored to consume `src/`. Tests: +18 across
`test_monthly_flow.py` (6 new), `test_rendering.py` (+5), `test_config.py` (+3),
`test_cli.py` (+2), `test_monthly_pipeline.py` (2 new). Suite: **345 passing**.

### #26 -- Web control surface (`0f2c7eb`)

`web/proto-a-studio.html` promoted (via `git mv`) to `web/studio.html`.
`web/shared/hydro-ux.js` `cliMapping`/`yamlMapping` rewritten to emit real flags
(`--color-by`, `--width-by`, `--county`, `--months`) instead of `(proposed)`
markers. Added `mappingSelfCheck(state)`, "Preview source" fieldset (procedural /
real SVG file picker), and `build.py` | `config.yaml` toggle with copy. Two
honest caveats: `color_by=elevation` and non-annual `--months` carry commented-out
notes below the command because they fail fast in the 2D pipeline. Suite:
**345 passing** (no `src/` change -- web layer is outside the offline suite).

### #27 -- Live pipeline integration (`3613ed8`, reconcile `5dc8ebf`)

New `src/jobs.py`: `settings_from_payload` (whitelists `DEFAULTS` keys +
boundary-validates via `build_settings`), `JobRunner` with injectable
duck-typed pipeline + executor. New `src/server.py`: `handle_request` dispatcher
(`POST /api/render`, `GET /api/jobs/<id>`, static serving with path-traversal
guard). New `serve.py` entry point. `web/studio.html` "Run pipeline" button (POST
-> poll -> SVG swap; disabled over `file://`). Tests: +16 (`test_jobs.py` 8 new,
`test_server.py` 8 new). Suite: **361 passing**.

**Run-pipeline reconcile** (`5dc8ebf`, `c5a6b2d`): clicking "Run pipeline" on a
real `serve.py` failed with `[Errno 13] Permission denied: '/Volumes/home'`. Two
fixes: (1) `src/cache.py` gains `is_extracted` + `ensure_cached` skips
already-extracted descriptors (zero downloads off pre-extracted `datasets/`);
(2) `serve.py` `_resolve_cache_dir()` prefers the NAS only when mounted, else
falls back to local `cache/`. Verified end-to-end: `POST /api/render` Oregon
Deschutes County -> job succeeded -> `oregon-deschutes.svg` (8.4 MB, sha256
`0f1f0976...a4055733`), no downloads triggered. Tests: +8 (`test_cache.py` +4,
`test_acquisition_integration.py` +1, `test_serve.py` +3). Suite: **452 passing**
at reconcile.

### #28 -- Presets & shareable render recipes (`b80296d`)

`web/shared/hydro-ux.js`: `RECIPE_KEYS` (17 keys), `toRecipe`/`sanitizeRecipe`/
`encodeRecipe`/`decodeRecipe`/`applyRecipe`, `PRESETS` catalog (`or-screen`,
`clark-print`, `print-mono`, `screen-glow`), base64url encode/decode with Node
`Buffer` fallback. Round-trip exact: `decodeRecipe(encodeRecipe(s))` deep-equals
`toRecipe(s)`. `decodeRecipe` never throws (garbage -> `null`). Module made
Node-loadable (`module.exports`). `web/studio.html` -- preset buttons,
"Copy share link" -> `location.hash`, `syncControls()`, boot `restoreFromHash()`.
Tests: `tests/test_recipe_roundtrip.cjs` (11 headless Node tests, stdlib `node`
only). Suite: **361 passing** (Python unchanged; recipe tests are Node-only).

## Real-data findings

The real-data finding for this epoch came from the #27 reconcile, not from the
initial commit. The initial `serve.py` integration was "offline tests all pass,
manual browser smoke deferred." When the manual smoke finally ran:

- **The bug the real run surfaced:** `_download_stage` unconditionally fetched
  archives from the NAS even when the extracted GDBs already existed on disk.
  Combined with `serve.py` hardcoding the NAS cache dir, clicking "Run pipeline"
  on a machine without the NAS mount produced `[Errno 13] Permission denied:
  '/Volumes/home'`. This is invisible to offline tests because the download stage
  always operates on injected fakes.
- **Fix:** `src/cache.py` `is_extracted` short-circuits before any
  cache/downloader touch; `serve.py` `_resolve_cache_dir()` mount-aware fallback.
- **Verified:** Deschutes County, OR SVG (8.4 MB), sha256
  `0f1f0976e6c4b93e2cc46f136ce84c8e5cf3cdad1e259bad03309a89a4055733`, with zero
  downloads.

## Invariants held

- **Offline suite:** 361 passing at epoch close (was 276 at start; +85 tests).
  After the post-epoch #27 reconcile: 452 passing.
- **2D default output byte-identical:** yes. Every new field defaults to the
  prior behavior (`color_by=watershed`, `width_by=uniform`, `county=None`,
  `months=()` = annual). No existing render path is altered.
- **`PIPELINE_STAGES` untouched:** yes. No stage added, removed, or reordered.
  The pipeline changes are within existing stage bodies (`_assign_colors_stage`,
  `_generate_svg_stage`, `_clip_stage`, `_export_stage`), branching on new settings
  with the default branch identical to the prior code.
- **Rights gate:** N/A -- no new data source; `fulfillment.assert_sellable` not
  touched. All renders use USGS public-domain data.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for any of the six spec folders, so there is
no pre-registered watch-list to grade against. The epoch's one genuine surprise --
the NAS-mount download crash on the real `serve.py` path -- is exactly the kind of
item a pre-analysis would have flagged ("does the download stage fire when it
shouldn't?") and is now a standing lesson: the download stage should always
short-circuit when extracted data is present.

## Carry-forwards (honestly open, not passed)

- **`color_by=elevation` and non-annual `--months` fail fast in the 2D pipeline.**
  Both options are validated, stored on `Settings`, and accepted by the CLI, but
  the core pipeline does not carry per-segment elevation or per-reach monthly
  discharge. Their real render paths remain `tools/render_state_mono.py` and
  `tools/render_monthly.py` respectively. Wiring them into `PIPELINE_STAGES` is a
  deliberate non-goal documented in CLAUDE.md, not a gap.
- **`width_by=flow` uses stream-order as a proxy, not true QAMA discharge.** The
  offline pipeline graph has no per-reach discharge; `_resolve_stroke_widths` feeds
  stream order to `scaled_widths`. The `tools/` renderers operate on real QAMA.
  This was addressed more precisely by Epoch 18's `WIDTH_PRESETS`, but the proxy
  vs. reality gap persists in the pipeline path.
- **No live `verify_determinism.py` double-render was run for this epoch.** The
  byte-identity claim rests on the default-disabled invariant (all new fields
  default to prior behavior) plus the test guards, not a fresh real `build.py`
  double-render. This is the standing carry-forward inherited from Epoch 1.
- **Live browser DOM smoke for `web/studio.html` was not run during this epoch.**
  The Chrome extension was not connected in the sessions that implemented #26 and
  #28. Headless `node --check` and `mappingSelfCheck` passed; the `syncControls`
  / preset-button / hash-restore wiring was verified only structurally, not in a
  live browser. This was subsequently exercised in later epochs (Epoch 24's
  Playwright harness boots `studio.html` and interacts with it via
  `01-landing.spec.js`).
- **County download scoping deferred.** `--county` clips after download, so a
  county build still downloads/loads the full state's NHDPlus HR archives. A
  county-scoped download would skip unused HUC4s but was out of scope.

## Lessons

- **The real `serve.py` run found what offline fakes could not.** The download
  stage's unconditional NAS fetch and the hardcoded cache dir were both invisible
  to the test suite because the download stage always operates through injected
  `Downloader`/`Fetcher` fakes. This is the project's recurring pattern: the first
  live invocation of a path that offline tests cover with fakes surfaces a
  real-environment assumption. The fix (`is_extracted` short-circuit) was also
  independently valuable -- it made builds genuinely offline-capable from
  pre-extracted data.
- **Strict item sequencing paid off.** Shipping #23-#25 (config/render) before #26
  (web surface) meant the web mapping could emit real flags instead of `(proposed)`
  markers. Shipping #26 before #27 (live pipeline) meant the control surface
  existed before the runner. Shipping #27 before #28 (recipes) meant the recipes
  could be tested against a working pipeline. Each item was independently
  committable because its predecessors were already landed.
- **The `web/` layer's isolation from `src/` is load-bearing.** None of the 85 new
  Python tests touch `web/`; the 11 recipe tests are pure Node. The `src/` never
  imports `web/`; the web layer never imports `src/`. This boundary kept the six
  items from creating cross-cutting regressions. The `hydro-ux.js` Node-loadable
  pattern (`module.exports` fallback) deserves reuse -- it made the recipe
  round-trip testable without Playwright.
- **Restore the pre-analysis step.** Six items with no pre-analysis is too many.
  The NAS-mount download crash would have been on a watch-list; the
  `color_by=elevation` fail-fast would have been explicitly predicted rather than
  discovered item-by-item. Even a brief pre-analysis per epoch (not per item)
  would have caught the #27 reconcile issue before the first commit.
