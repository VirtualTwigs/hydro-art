# Implementation report — Alpha customer-journey e2e (Epoch 24)

## #94 — Draft render tier (2026-09-11)

**What shipped (the only pre-commit code change; offline suite).**
- `src/config.py` — `SUPPORTED_PNG_SIZES` extended to `(512, 1024, 2048, 4096, 8192, 16384, 32768,
  65536)`, kept sorted ascending; docstring notes the small tiers are draft/preview sizes for fast
  design + e2e iteration. `DEFAULTS["png_size"]` unchanged at `4096`, so default output is unchanged.
  Validation is unchanged — `build_settings` already rejects any value not in the tuple.
- `src/cli.py` — `--png-size` help lists the new sizes and marks 512/1024/2048 as draft (default 4096).
  Still `type=int` with no `choices`; validation stays in `build_settings`.
- `tests/test_export_config.py` — added `test_png_size_draft_tiers_present_and_sorted` and
  `test_png_size_accepts_draft_tiers`. Existing `test_png_size_defaults_to_4096` and
  `test_png_size_rejects_unsupported` (1234) unchanged and still pass — no regression.

**Verification.**
- `tests/test_export_config.py` — 8 passed.
- Full offline suite — **892 passed**. No `PIPELINE_STAGES` edit; default 2D output byte-identical.

**Committed with:** the Epoch 24 roadmap entry (#94–#98), this spec (`spec.md`,
`planning/requirements.md`, `tasks.md`), per the "commit before development of tests" instruction.

## #95–#98 — Playwright browser harness (authored after the commit)

Delivered under `tests/e2e/` (non-offline, opt-in; never in the offline Python suite):
- `package.json` (`@playwright/test` dev-dep), `playwright.config.js`, `helpers.js`, `.gitignore`,
  `README.md` (prerequisites + run + env knobs).
- `tests/01-landing.spec.js` — #95 smoke (start.html 200, title, hero, no console errors) + #96
  landing structure (four cards, how-it-works) and click-through nav to all four catalog pages +
  gallery. The landing-asset check **skips** with a pointer when `/output/landing/*` isn't staged.
- `tests/02-endpoints.spec.js` — #97 low-res proofs: digital (SVG) + poster (draft PNG, magic-byte
  check) via `POST /api/render` at `png_size=1024`; report + animation via spawning
  `tools/build_watershed_report.py` / `tools/render_monthly.py` at low-res. Endpoint proofs
  `skip` (not fail) when `datasets/` has no pre-extracted county.

**`serve.py` — added `--web-root`.** The bundled default serves `web/`, which does **not** resolve
`start.html`'s repo-root-absolute `/web/...` + `/output/...` links. New `--web-root` (default
unchanged) lets the harness serve the repo root so the landing journey and the `/api/*` render routes
are same-origin. `playwright.config.js` boots `serve.py --web-root . --port <PORT>`.

**Validated here (no Playwright/GDAL needed):**
- All harness JS passes `node --check`; `package.json` parses.
- Booted `serve.py --web-root . --port 8099`: `web/start.html`, `web/studio.html`,
  `web/gallery.html`, `web/shared/ux.css` → **200**; `/api/jobs/<id>` → **404 JSON** (routes wired);
  `/output/landing/*.webp` → **404** (expected — assets live in `deploy/output/landing/`; the
  asset test skips until `deploy/stage-artifacts.sh` runs or the NAS is mounted).

**Execution status.** The harness is authored and its server contract is proven, but a full
`npx playwright test` green run (the epoch gate for #95–#98) needs an environment with
`npm install` + `npx playwright install chromium`, and — for #97 — a pre-extracted county in
`datasets/` and the GIS stack. Roadmap #95–#98 are therefore left **unchecked** until that run is
demonstrated. The harness + the `serve.py --web-root` change are **left uncommitted** for review
(the pre-commit foundation was committed separately, per the "commit before development" instruction).

## #95–#98 — Epoch gate GREEN (2026-09-12)

`npx playwright test` — **13/13 passed (13.7m)** against a live `serve.py --web-root <staged>` on a
staged Clark County, WA (`datasets/nhdplus_hr` + `datasets/wbd`, GIS stack, PNG_SIZE=1024):

- `01-landing.spec.js` — **8/8** (~4s): smoke, hero, no-console-errors, landing-asset/font resolution,
  per-card + gallery navigation.
- `02-endpoints.spec.js` — **5/5**: digital SVG (6.0m) + poster PNG (6.0m, magic-byte check) via
  `/api/render` at the draft tier; studio Run button live (0.8s); watershed report figures (18.4s);
  animation GIF (1.2m).

**Findings that changed the harness (vs. the pre-commit authoring):**
- **Staged real served-root.** Serving the repo root directly makes `/output/landing/*.webp` 404 —
  `serve.py`'s path-traversal guard resolves the repo's NAS `output/` symlink and refuses the escape,
  tripping the landing suite's strict no-console-errors check. New `global-setup.js` stages a real
  (non-symlinked) root: copies of `web/` + `deploy/output/`, served via `--web-root <staged>`. Staging
  runs at **config load**, not the `globalSetup` hook, because Playwright probes webServer readiness
  first (a `globalSetup`-hook stage would 404-timeout). The `serve.py --web-root .` from the authoring
  note is replaced by `--web-root <staged>`.
- **`/api/render` county proof is ~6 min.** `validate` loads the whole Washington region (27 layers,
  ~2.3M geometries); repair + reproject over that dominates. The county clip → graph → watersheds →
  SVG → PNG export is only ~13s once reprojected — so the draft `png_size` (#94) barely helps here (it
  only speeds rasterization, not the GIS load). `RENDER_TIMEOUT_MS` default raised 300s → **600s**, with
  an explicit per-test budget (`test.slow()`'s 3× of the 120s base was too tight).
- **County value is the Census `NAME`.** `src/counties.py` matches `NAME` (`Clark`), not `NAMELSAD`
  (`Clark County`); helper default corrected to `Clark`.
- **Census counties shapefile prerequisite.** The county clip reads
  `/tmp/counties_shp/cb_2023_us_county_500k.shp` (public-domain Census cartographic boundaries, ~12 MB
  zipped). README documents staging it; **not committed** (regenerable external data). The
  report/animation proofs don't need it — they bbox-clip via `tools/render_common.CLARK_BBOX_4326`.
- The landing-asset skip-guard now reads `deploy/output/landing/` (the staging source of truth).

All four endpoints produce a real low-res proof; provenance is public-domain USGS/Census; nothing marked
sellable. Suite stays out of `ci.yml` (offline-suite discipline); any CI wiring is a separate gated job.
