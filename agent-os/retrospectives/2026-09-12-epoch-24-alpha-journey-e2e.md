# Retrospective — Epoch 24: Alpha customer-journey end-to-end tests (#94–#98)

_Closed 2026-09-12. **No pre-registered watch-list** — the spec folder
(`2026-09-11-alpha-journey-e2e`) carries `planning/requirements.md`, `spec.md`,
`tasks.md`, and `implementation/report.md`, but no `planning/pre-analysis.md`
(consistent with Epochs 16, 18, and Generation 1). This is a narrative closeout
rather than a graded one; the missing pre-analysis is again a process note (see
Lessons)._

## What the epoch was

Prove the **alpha customer site works end to end in a real browser** — not "the
pieces render in pytest" but "a buyer's actual click-path holds up." The landing
page (`web/start.html`) fans out to four catalog pages — poster
(`proto-b-guided.html`), watershed report (`report.html`), digital image
(`studio.html`), year-in-motion animation (`proto-c-canvas.html`) — and a scripted
**Playwright** harness walks that whole journey against a **live `serve.py`** (the
real `Pipeline` + `JobRunner` behind `/api/render`), producing a **low-resolution
proof** per endpoint. The only change entering the offline Python suite is a small
draft `png_size` tier (#94) so proofs render fast enough for a design loop. The
harness itself is **non-offline, opt-in**, and stays out of `ci.yml` — the same
posture as the Epoch 21 real-data e2e harness. All five items closed; the epoch
gate is a green Playwright run.

## What shipped

### #94 — Draft render tier (offline suite; `229d5a4`)

`src/config.py` — `SUPPORTED_PNG_SIZES` extended to `(512, 1024, 2048, 4096, 8192,
16384, 32768, 65536)`, kept sorted ascending, docstring noting the small tiers are
draft/preview sizes. `DEFAULTS["png_size"]` unchanged at **4096** — default output
byte-identical. `src/cli.py` — `--png-size` help lists the new sizes and marks
512/1024/2048 as draft; still `type=int` with no `choices`, validation stays in
`build_settings` (which already `ConfigError`s any value not in the tuple).
`tests/test_export_config.py` — added `test_png_size_draft_tiers_present_and_sorted`
and `test_png_size_accepts_draft_tiers`; existing `test_png_size_defaults_to_4096`
and the reject-`1234` `test_png_size_rejects_unsupported` unchanged. Target file
**8 passed**; full offline suite **892 passed**, no regression, no `PIPELINE_STAGES`
edit. Committed with the roadmap entry and spec, per the "commit before development
of tests" instruction.

### #95–#98 — Playwright harness (`f9c5855`, gated green `f01a0c3`)

Delivered under `tests/e2e/` (non-offline, opt-in; never in the offline Python
suite): `package.json` (`@playwright/test` dev-dep only), `playwright.config.js`,
`global-setup.js`, `helpers.js`, `.gitignore`, `README.md`.

- **`serve.py` — added `--web-root`.** The bundled default still serves `web/`; the
  new flag lets the harness serve a staged root so `start.html`'s repo-root-absolute
  `/web/...` + `/output/...` links and the `/api/*` render routes are same-origin.
- **#95/#96 — `tests/01-landing.spec.js`** — `start.html` 200 + hero `<h1>` +
  **no console errors**, landing-asset/font resolution, the four catalog cards +
  how-it-works, and click-through nav to all four catalog pages + gallery.
- **#97 — `tests/02-endpoints.spec.js`** — a low-res proof per endpoint: digital
  (SVG) + poster (draft PNG, magic-byte check) via `POST /api/render` at the draft
  `png_size` tier; report figures via `tools/build_watershed_report.py`; animation
  GIF via `tools/render_monthly.py`. Endpoint proofs **skip** (not fail) when
  `datasets/` has no pre-extracted county or a tool prerequisite is unmet.
- **#98 — `tests/e2e/README.md`** — prerequisites (extracted county, GIS stack, the
  `/tmp/counties_shp/` Census shapefile), the `npx playwright test` command, and the
  `PORT`/`BASE_URL`/`PNG_SIZE`/`HARNESS_COUNTY`/`RENDER_TIMEOUT_MS` env knobs. CI
  wiring left as a separate gated job, **not** added to `ci.yml`'s offline job.

## Real-data findings

The epoch gate — `npx playwright test` against a live `serve.py --web-root <staged>`
on a staged **Clark County, WA** (`datasets/nhdplus_hr` + `datasets/wbd`, GIS stack,
`PNG_SIZE=1024`) — went **13/13 passed (13.7m)**:

- `01-landing.spec.js` — **8/8** (~4s).
- `02-endpoints.spec.js` — **5/5**: digital SVG (6.0m) + poster PNG (6.0m,
  magic-byte check) via `/api/render`; studio Run button live (0.8s); watershed
  report figures (18.4s); animation GIF (1.2m).

Three findings the live browser run surfaced that offline pytest structurally could
not — this is the epoch's instance of the standing "offline fakes can't verify the
real invocation path" lesson:

- **Serving the repo root directly 404s the landing assets.** `serve.py`'s
  path-traversal guard resolves symlinks and refuses escapes, and the repo's
  `output/` is a NAS symlink — so `/output/landing/*.webp` returned **404**, tripping
  the landing suite's strict no-console-errors check. Fix: `global-setup.js` stages a
  **real (non-symlinked) served root** — copies of `web/` + `deploy/output/` under
  `tests/e2e/.served-root/` — served via `--web-root <staged>`. This mirrors exactly
  what the container deploy does by bind-mounting `deploy/output`. (The authoring
  note's `--web-root .` was replaced by `--web-root <staged>`.)
- **Playwright staging-order gotcha.** The served root must be staged at Playwright
  **config load**, not in the `globalSetup` hook, because Playwright awaits the
  `webServer` readiness probe *before* running `globalSetup` — a hook-staged root
  404-timeouts the boot.
- **The "fast low-res proof" premise partly breaks down for `/api/render`.** A Clark
  County proof measures **~6 min**, because `validate` loads the whole Washington
  region (27 layers, **~2.3M geometries**) and repair+reproject over that dominates;
  the county clip → graph → watersheds → SVG → PNG is only **~13s** once reprojected.
  The draft `png_size` (#94) only speeds rasterization, not the GIS load — so it
  barely helps here. `RENDER_TIMEOUT_MS` default raised 300s → **600s** with an
  explicit per-test budget (`test.slow()`'s 3× of the 120s base was too tight). This
  is a genuine design tension, flagged below as a carry-forward.

Two prerequisites the harness also surfaced: the county value must be the Census
**`NAME`** (`Clark`), not `NAMELSAD` (`Clark County`), because `src/counties.py`
matches `NAME` (helper default corrected); and the two `/api/render` proofs need the
Census cartographic-boundary counties shapefile staged at
`/tmp/counties_shp/cb_2023_us_county_500k.shp` (public-domain, ~12 MB zipped),
documented in the e2e README, **not committed** (regenerable external data). The
report/animation proofs don't need it — they bbox-clip to Clark via
`tools/render_common.CLARK_BBOX_4326`.

## Invariants held

- **Offline suite:** **892 passing** (+2 new in `tests/test_export_config.py`). The
  entire `tests/e2e/` harness is Node/Playwright and lives **outside** the offline
  Python suite; no GDAL/network/`web/`/`tools/` imports leaked into `src/`. The only
  `src/` change is the `SUPPORTED_PNG_SIZES` tuple + the `--png-size` help text.
- **2D default output byte-identical:** yes. `DEFAULTS["png_size"]` stays 4096;
  adding smaller allowlist entries doesn't change any default render, and the export
  converter already sizes to `png_size`. Guarded by the unchanged
  `test_png_size_defaults_to_4096`.
- **`PIPELINE_STAGES` untouched:** yes — no stage added, removed, or reordered. This
  was an explicit non-goal and it held; the `serve.py --web-root` addition is a static
  file-root argument, not a pipeline change.
- **Rights gate:** honored. All four proofs come from public-domain USGS/Census
  sources; **nothing is marked sellable** (the proofs assert presence + basic shape,
  not commercial delivery). No PRISM path involved.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no pre-registered
watch-list to grade against. Had one existed, the three findings above are precisely
the kind of "offline suite is blind to this path" risks it is meant to force —
especially the symlink/served-root 404 and the county-value `NAME`-vs-`NAMELSAD`
mismatch, both invisible until a real browser hit a real `serve.py`. The ~6-min
`/api/render` cost is the one item that a pre-analysis would likely have flagged as a
premise risk ("does the draft tier actually make the loop fast?") and correctly
predicted as only-partly-true.

## Carry-forwards (honestly open, not passed)

- **The county `/api/render` path is ~6 min, dominated by a full-region GIS load.**
  A lighter **county-scoped render path** — clip the source layers to the county
  extent *before* repair+reproject, rather than reprojecting all ~2.3M Washington
  geometries first — would make the design loop genuinely fast. Open design work,
  out of scope here; the draft tier alone does not deliver the "seconds, not minutes"
  premise for the two pipeline endpoints.
- **The green gate is single-host, single-county, and not in CI.** 13/13 was
  demonstrated once, on this machine, against a staged Clark County, WA with the GIS
  stack + the `/tmp/counties_shp/` shapefile. The **gated CI job** (#98) that stages a
  county and runs the harness is documented but deliberately **not wired** — it stays
  a separate, opt-in job so `ci.yml` remains GDAL-free. Wiring it (and picking where
  it runs) is open.
- **Proofs assert presence + basic shape, not byte-equality — by design.** The
  harness checks for an `<svg>`, PNG magic bytes, a figure file, a GIF; it is
  intentionally **not** a second golden. Byte-level determinism remains the job of
  `tools/verify_determinism.py` and the golden fixtures, and no live double-render was
  run in this session — the same standing carry-forward inherited since Epoch 9/14/18.

## Lessons

- **A live browser against a live server finds what fakes cannot.** The three
  findings — symlink-resolving 404, Playwright's `globalSetup`-after-readiness order,
  and the county `NAME` mismatch — were all invisible to the offline suite because it
  never boots `serve.py`, never resolves the NAS symlink, and never runs
  `src/counties.py` against real Census attributes. This is exactly why the epoch
  existed; the harness earned its keep on the first green run.
- **Mirror the deploy topology in the test harness.** The staged-root fix works
  because it copies what the container deploy already does (bind-mount
  `deploy/output`). When the test environment and the production environment disagree
  about how static assets are served, match production — don't special-case the test.
- **"Low-res = fast" only holds where resolution is the cost.** The draft `png_size`
  tier speeds rasterization, but the `/api/render` cost is the GIS load, so it barely
  helped. Name the actual bottleneck before assuming a knob addresses it.
- **Restore the pre-analysis/watch-list step** (now skipped since Epoch 16). A
  browser/real-server epoch is the *most* watch-list-worthy kind: nearly every finding
  here was an "offline can't verify this path" item that a five-minute pre-analysis
  would have listed up front.
