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

> **Status (2026-09-11):** Groups 2–5 are **authored** under `tests/e2e/` and the `serve.py
> --web-root` support they need is in place; the server contract is validated (see
> `implementation/report.md`). Boxes stay unticked until a full `npx playwright test` green run
> (the epoch gate) is demonstrated on an environment with Playwright installed + a pre-extracted
> county in `datasets/`.

## Task Group 2 — #95 Playwright harness scaffold (after commit)

- [ ] 2.1 `tests/e2e/package.json` (dev-dep `@playwright/test`), `playwright.config`, `README.md`.
- [ ] 2.2 Server fixture: boot `serve.py --port <test-port>` with a temp output dir + staged
  `--cache-dir`/`datasets`, wait for readiness, yield base URL, kill on teardown; `BASE_URL`/
  `PNG_SIZE` env overrides (draft tier default).
- [ ] 2.3 Smoke test: `start.html` 200 + hero `<h1>` + no console errors + landing assets/fonts resolve.
- [ ] 2.4 `npx playwright test` green against a live `serve.py` on a staged county.

## Task Group 3 — #96 Landing + navigation e2e (after commit)

- [ ] 3.1 Landing structure asserts: hero, four catalog cards (poster/report/digital/animation), how
  -it-works steps.
- [ ] 3.2 Follow every catalog `a.cover` link + gallery link; each destination loads with no JS/console
  errors.

## Task Group 4 — #97 Four-endpoint low-res proof e2e (after commit)

- [ ] 4.1 Digital (`studio.html`): set small county, click "Run pipeline", poll job to success, assert
  SVG proof (+ draft PNG via `/api/jobs/<id>/artifact?fmt=png`) at the draft `png_size`.
- [ ] 4.2 Poster/print (`proto-b-guided.html`): 2D `Pipeline` via `/api/render` (print intent); wire a
  minimal submit reusing `HydroUX.renderRequest` if the page isn't backend-wired (no duplicated recipe).
- [ ] 4.3 Report (`report.html`): low-res figure via `tools/build_watershed_report.py` for the county;
  assert a produced figure the viewer can display.
- [ ] 4.4 Animation (`proto-c-canvas.html`): low-res/short-frame GIF via `tools/render_monthly.py`;
  assert a produced file.
- [ ] 4.5 Each proof records public-domain provenance; none marked sellable.

## Task Group 5 — #98 Run docs & optional CI wiring (after commit)

- [ ] 5.1 `tests/e2e/README.md`: prerequisites + `npx playwright test` + env knobs.
- [ ] 5.2 Opt-in/gated CI job (separate workflow/manual dispatch); **never** in `ci.yml`'s offline job.
- [ ] 5.3 Close out: tick roadmap #95–#98 as delivered; append `implementation/report.md`.
