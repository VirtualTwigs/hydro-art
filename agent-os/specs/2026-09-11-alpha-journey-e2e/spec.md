# Specification: Alpha customer-journey end-to-end tests (Epoch 24)

## Goal
A scripted **Playwright** browser harness that walks the alpha customer site end to end — landing
page → all four catalog pages → a **low-resolution proof** for each endpoint — against a live
`serve.py`. Fast enough to use during design iteration thanks to a new draft `png_size` tier. The
harness is **non-offline and opt-in** (needs the GIS stack + a pre-extracted county); the only change
that enters the offline suite is the draft tier. Nothing enters `PIPELINE_STAGES`; default 2D output
is byte-for-byte identical.

## User Stories
- As the operator of the alpha, I want a one-command browser test that walks a real buyer's path
  (landing → pick a piece → get a proof) so I catch broken links, dead render buttons, and JS errors
  before a customer does.
- As a builder iterating on the site's design, I want proofs to render at low resolution first so the
  e2e loop is seconds, not minutes — then I can bump `png_size` for a final check.

---

## Item #94 — Draft render tier (this session)

The smallest existing raster size is `4096` (`SUPPORTED_PNG_SIZES = (4096, 8192, 16384, 32768,
65536)`), too large for a fast design/e2e loop. #94 adds small draft/preview tiers below it.

### `src/config.py`
- Extend `SUPPORTED_PNG_SIZES` to `(512, 1024, 2048, 4096, 8192, 16384, 32768, 65536)` — keep it
  sorted ascending. `DEFAULTS["png_size"]` **stays 4096** (default output unchanged).
- No change to `_coerce`/validation logic: `build_settings` already rejects any value not in the
  tuple with a `ConfigError` and lists the valid set, so the new tiers are accepted and `1234` still
  fails. Update the docstring on `SUPPORTED_PNG_SIZES` to note the small tiers are draft/preview
  sizes for fast iteration.

### `src/cli.py`
- Update the `--png-size` help text to list the new sizes (`512 1024 2048 4096 8192 16384 32768
  65536`). `--png-size` stays `type=int` with no `choices` (validation stays in `build_settings`).

### Tests (`tests/test_export_config.py`)
- `SUPPORTED_PNG_SIZES` includes `512`, `1024`, `2048` and is sorted ascending.
- `build_settings(png_size=<tier>)` accepts each new draft tier and round-trips it.
- Default is still `4096` (existing `test_png_size_defaults_to_4096` unchanged) and `1234` still
  raises `ConfigError` (existing `test_png_size_rejects_unsupported` unchanged) — no regression.

### Non-goals (#94)
No CLI `choices` restriction, no new default, no `PIPELINE_STAGES` change, no export/rasterizer change
(the converter already sizes to `png_size`). No web or `tools/` change. No Playwright yet.

---

## Items #95–#98 — the Playwright harness (after the commit)

Implemented one at a time on later commands; specified here so the shape is fixed.

### #95 — Harness scaffold (`tests/e2e/`)
- A self-contained Node project: `tests/e2e/package.json` (dev-dep `@playwright/test` only),
  `tests/e2e/playwright.config.ts|js`, and a `README.md` with prerequisites.
- A **server fixture** that starts `serve.py --port <test-port>` with `HYDRO_ART_EXTERNAL_ROOT`/
  `--cache-dir` pointed at the staged datasets and a **temp output dir**, waits for the printed URL to
  answer, yields the base URL, and kills the process on teardown. Base URL configurable
  (default `http://127.0.0.1:8080`) so it can point at an already-running server.
- **Draft resolution is the default** for harness renders (`png_size` from #94, e.g. `1024`), settable
  via env for a high-res confirmation pass.
- Smoke test: `start.html` returns 200, renders the hero `<h1>`, logs **no console errors**, and its
  landing `/output/landing/*.webp` + `web/shared/fonts` assets resolve (no 404s).

### #96 — Landing + navigation e2e
- Assert the landing structure: hero headline, the **four** catalog cards (poster / report / digital
  / animation) with their tag pills and price, and the three how-it-works steps.
- Follow every catalog `a.cover` link + the gallery nav link; assert each destination page loads
  (`load` event, expected title/heading) with **no uncaught JS/console errors**.

### #97 — Four-endpoint low-res proof e2e
Drive each endpoint to a **low-res proof** through its real backend path, asserting a proof artifact:
- **Digital image (`studio.html`)** — set a small region/county, click "Run pipeline"; poll the job
  to success; assert the SVG proof appears (and, if requested, a draft PNG artifact is fetchable via
  `/api/jobs/<id>/artifact?fmt=png`).
- **Poster / print image (`proto-b-guided.html`)** — same 2D `Pipeline` path via `/api/render` (print
  intent). If the page's "Start design" flow is not yet wired to the backend, #97 wires a minimal
  submit (reusing `HydroUX.renderRequest`) rather than duplicating recipe logic.
- **Report (`report.html`)** — the report is a `tools/` subsystem, not the `/api/render` pipeline; the
  proof is a low-res figure produced by driving `tools/build_watershed_report.py` (or a thin proof
  hook) for the target county, asserted as a generated figure file the viewer can display.
- **Animation (`proto-c-canvas.html`)** — likewise a `tools/` subsystem; the proof is a low-res /
  short-frame GIF from `tools/render_monthly.py`, asserted as a produced file.
- Each proof records provenance (public-domain USGS source) consistent with the Rights gate; none is
  marked sellable.

### #98 — Run docs & optional CI wiring
- `tests/e2e/README.md`: prerequisites (staged county in `datasets/`, GIS stack, `serve.py`), and the
  run command `npx playwright test` (plus `PNG_SIZE=…`/`BASE_URL=…` env knobs).
- Optional **gated** CI job (separate workflow or manual dispatch) that stages a small county and runs
  the harness — **never** added to `ci.yml`'s offline job, so the offline suite stays GDAL-free.

## Determinism / discipline note
The proofs themselves are real renders (non-deterministic across environments only via floating GIS
inputs — the pipeline is deterministic per the existing golden discipline). The harness asserts
**presence + basic shape** of proofs, not byte-equality, so it does not become a second, brittle
golden. Byte-level determinism stays the job of `tools/verify_determinism.py` and the golden fixtures.
