# Tasks — Alpha customer-journey end-to-end tests (Epoch 24)

One roadmap item at a time. **This session implements Task Group 1 (#94) only**, then commits the
foundation (roadmap + spec + config + unit tests) before any Playwright harness is developed. Groups
2–5 (#95–#98) are the browser harness, implemented after the commit / on later commands.

## Task Group 1 — #94 Draft render tier (offline suite; committed this session)

- [x] 1.1 Tests first (run only these) — `tests/test_export_config.py`: `SUPPORTED_PNG_SIZES` contains
  `512`/`1024`/`2048` and is sorted ascending; `build_settings(png_size=<tier>)` accepts each new
  draft tier; default stays `4096` and `1234` still raises `ConfigError` (no regression).
- [x] 1.2 `src/config.py` — extend `SUPPORTED_PNG_SIZES` to `(512, 1024, 2048, 4096, 8192, 16384,
  32768, 65536)`; keep `DEFAULTS["png_size"] = 4096`; note draft/preview tiers in the docstring.
- [x] 1.3 `src/cli.py` — update the `--png-size` help to list the new sizes.
- [x] 1.4 Run only `tests/test_export_config.py`; green (8).
- [x] 1.5 Full offline suite for regressions; **892 green**; no `PIPELINE_STAGES` touched (2D byte-identical).
- [x] 1.6 Tick roadmap #94; write `implementation/report.md`.

> **Status (2026-09-12):** Groups 2–5 **DONE — epoch gate green.** `npx playwright test`:
> **13/13 passed (13.7m)** against a live `serve.py` on a staged Clark County, WA:
> landing/nav 8/8 (~4s), digital SVG + poster PNG via `/api/render` at the draft tier (~6m each),
> report figures (18.4s), animation GIF (1.2m), studio Run button live. Key findings baked into the
> harness: a **staged real served-root** (copies of `web/` + `deploy/output/`) is required because
> `serve.py`'s path-traversal guard rejects the repo's NAS `output/` symlink, and staging runs at
> config load (webServer readiness is probed before the `globalSetup` hook); the `/api/render` county
> proof is **~6 min** (full-Washington GIS load dominates, county value is the Census `NAME` `Clark`);
> the county clip needs the Census counties shapefile at `/tmp/counties_shp/` (documented, not committed).

## Task Group 2 — #95 Playwright harness scaffold (after commit)

- [x] 2.1 `tests/e2e/package.json` (dev-dep `@playwright/test`), `playwright.config`, `README.md`.
- [x] 2.2 Server fixture: boot `serve.py --port <test-port>` with a temp output dir + staged
  `--cache-dir`/`datasets`, wait for readiness, yield base URL, kill on teardown; `BASE_URL`/
  `PNG_SIZE` env overrides (draft tier default).
- [x] 2.3 Smoke test: `start.html` 200 + hero `<h1>` + no console errors + landing assets/fonts resolve.
- [x] 2.4 `npx playwright test` green against a live `serve.py` on a staged county.

## Task Group 3 — #96 Landing + navigation e2e (after commit)

- [x] 3.1 Landing structure asserts: hero, four catalog cards (poster/report/digital/animation), how
  -it-works steps.
- [x] 3.2 Follow every catalog `a.cover` link + gallery link; each destination loads with no JS/console
  errors.

## Task Group 4 — #97 Four-endpoint low-res proof e2e (after commit)

- [x] 4.1 Digital (`studio.html`): set small county, click "Run pipeline", poll job to success, assert
  SVG proof (+ draft PNG via `/api/jobs/<id>/artifact?fmt=png`) at the draft `png_size`.
- [x] 4.2 Poster/print (`proto-b-guided.html`): 2D `Pipeline` via `/api/render` (print intent); wire a
  minimal submit reusing `HydroUX.renderRequest` if the page isn't backend-wired (no duplicated recipe).
- [x] 4.3 Report (`report.html`): low-res figure via `tools/build_watershed_report.py` for the county;
  assert a produced figure the viewer can display.
- [x] 4.4 Animation (`proto-c-canvas.html`): low-res/short-frame GIF via `tools/render_monthly.py`;
  assert a produced file.
- [x] 4.5 Each proof records public-domain provenance; none marked sellable.

## Task Group 5 — #98 Run docs & optional CI wiring (after commit)

- [x] 5.1 `tests/e2e/README.md`: prerequisites + `npx playwright test` + env knobs.
- [x] 5.2 Opt-in/gated CI job (separate workflow/manual dispatch); **never** in `ci.yml`'s offline job.
- [x] 5.3 Close out: tick roadmap #95–#98 as delivered; append `implementation/report.md`.
