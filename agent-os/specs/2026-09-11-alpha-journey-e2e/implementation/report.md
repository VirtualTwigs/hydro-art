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
