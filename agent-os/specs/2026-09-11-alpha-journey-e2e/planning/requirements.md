# Requirements — Alpha customer-journey end-to-end tests (Epoch 24)

## Source
Roadmap Epoch 24 (`agent-os/product/roadmap.md`), items **#94–#98**. Prove the alpha customer site
works end to end in a real browser: the landing page fans out to the four catalog pages, and each
produces a **low-resolution proof** fast enough to use during design iteration.

## The alpha site (analysis)
The alpha URL (`http://localhost:8080/` today, a plain `python -m http.server` over the repo root)
serves `web/start.html` — the customer landing page ("Hydro·Art — rivers, made to order"). Its
catalog fans out to four endpoint pages, one per product endpoint:

| Catalog card        | Page                     | Product endpoint (`src/endpoints.py`) | Backend path today |
|---------------------|--------------------------|---------------------------------------|--------------------|
| Archival poster     | `proto-b-guided.html`    | `print_image`                         | mapping-only over `file://`; 2D `Pipeline` via `/api/render` when served by `serve.py` |
| Watershed report    | `report.html`            | `report`                              | viewer over `src/flow_metrics`; figures built by `tools/build_watershed_report.py` |
| Digital image       | `studio.html`            | `digital_image`                       | **wired**: "Run pipeline" POSTs `HydroUX.renderRequest(state)` to `/api/render` |
| Year in motion      | `proto-c-canvas.html`    | `animation`                           | preview-only; real GIF from `tools/render_monthly.py` |

The landing also links `web/gallery.html` and displays pre-rendered `/output/landing/*.webp` assets.

### Server reality (load-bearing)
- The alpha as served on `:8080` is **static** (`SimpleHTTP`) — no `/api/render`, so no real render.
  Real, low-res proofs require **`serve.py`**, which serves the same `web/` tree **plus** the
  `/api/render` + `/api/jobs/<id>` + `/api/jobs/<id>/artifact` routes backed by the real `Pipeline`
  and `JobRunner`. The e2e harness therefore boots `serve.py` on the test port (it can be `8080`).
- The render API today runs **only the 2D `Pipeline`** (digital / print image → SVG + optional
  PNG/PDF). **Animation and report are parallel subsystems** (`tools/render_monthly.py`,
  `tools/build_watershed_report.py`) **not wired to the web backend.** So "a proof for all four
  endpoints" is produced through the appropriate path per endpoint (pipeline via `/api/render` for
  digital + poster; the matching `tools/` command for animation + report), all at draft resolution.
- Real renders need the GIS stack **and** a pre-extracted county in `datasets/` (downloads are
  skipped when a dataset dir exists — see `src/cache.ensure_cached`). The landing showcases **Clark
  County, WA**, so the harness targets a small pre-extracted county (Clark County the default).

## Discipline (carried from the offline-suite rules + Epoch 21 posture)
- **The browser e2e harness is non-offline and opt-in.** It needs a live server + real GDAL renders +
  a staged county, so — like `tools/` and the Epoch 21 real-data e2e harness — it lives **outside**
  the Python offline suite (`.venv/bin/python -m pytest`). It never runs in `ci.yml`'s offline job.
- **Only one change enters the offline suite:** the draft `png_size` tier (#94), a pure config
  allowlist addition with unit tests. Nothing touches `PIPELINE_STAGES`; **default 2D output stays
  byte-for-byte identical** (default `png_size` remains 4096).
- **No duplicated recipe logic.** Proof renders reuse the existing backend/tools; the harness only
  drives the browser + asserts artifacts.
- **Rights posture unchanged.** Proofs come from public-domain USGS sources (Clark County NHDPlus HR);
  climate defaults stay `nclimgrid` — no PRISM asset is treated as sellable.

## Scope by item
- **#94** Draft render tier — add a small `png_size` tier (512/1024/2048) to `SUPPORTED_PNG_SIZES`,
  update `--png-size` help, unit-test in `tests/test_export_config.py`. Offline-suite; default 4096
  unchanged; 2D output byte-identical. (This is the only pre-commit code change.)
- **#95** Playwright harness scaffold — `tests/e2e/` Node project (`package.json`,
  `playwright.config`), a fixture that boots `serve.py` on a test port with a temp output dir and
  tears it down, and a `start.html` smoke test (loads, no console errors, assets resolve).
- **#96** Landing + navigation e2e — landing renders (hero, four catalog cards, how-it-works); every
  catalog link + gallery link navigates to a page that loads without JS errors.
- **#97** Four-endpoint low-res proof e2e — drive each endpoint (poster, report, digital, animation)
  to a **low-res proof** via its backend path at the draft tier; assert a proof artifact/preview.
- **#98** Run docs & optional CI wiring — document `npx playwright test` (prereqs: extracted county,
  `serve.py`); wire an opt-in/gated CI job, never in the offline Python suite.

## This session
Per the "commit before development of tests" instruction, this session ships **#94 only** (the draft
`png_size` tier + unit tests) plus this spec, its tasks, and the Epoch 24 roadmap entry — then
commits that foundation. Items **#95–#98** (the Playwright harness itself) are specified here and
implemented after the commit / on subsequent commands.
