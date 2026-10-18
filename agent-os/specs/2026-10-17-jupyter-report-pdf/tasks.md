# Tasks — Jupyter Notebook Report + PDF Export

Legend: `[x]` done · `[ ]` todo. Offline groups ship **tests-first** (write 2-8
tests per group, run ONLY those, then implement). `tools/` groups are
non-offline (closeout = smoke-run + record real numbers). Grade against
`planning/requirements.md` at close.

## Group 1 — Notebook assembly (`src/notebook_report.py`) · offline
**Dependencies:** None

- [x] 1.1 Add `nbformat` to `pyproject.toml` `[project.dependencies]`.
- [x] 1.2 Write `tests/test_notebook_report.py` first — 8 focused tests:
  1. `build_notebook` produces valid notebook structure (correct cell count,
     cell types: markdown title + markdown metrics + N section cells +
     attribution markdown).
  2. Section filtering: `sections={"map", "long_record"}` yields only title +
     those two sections + attribution, in canonical order.
  3. Unknown section name in `sections` raises `ValueError`.
  4. Figure embedding: given a temp dir with a fake PNG, the corresponding
     cell contains base64-encoded `image/png` display_data output.
  5. Missing figure graceful skip: enabled section with no PNG produces a
     markdown "figure not available" note, not an error.
  6. Headline metrics formatting: given a metrics dict, the headline cell
     contains expected formatted values (peak, low-flow, center-of-timing,
     flashiness).
  7. `save_notebook` round-trip: write then `nbformat.read` back; validate
     structure passes.
  8. PDF converter seam: `FakeNotebookConverter` injected into
     `notebook_to_pdf` is called with correct args and its return value
     forwarded.
  Run ONLY `tests/test_notebook_report.py`.
- [x] 1.3 Implement `src/notebook_report.py`:
  - `from __future__ import annotations`, `import nbformat` at top level
    (pure Python, no GDAL).
  - `__all__` exports.
  - `CANONICAL_SECTIONS`: ordered tuple matching `web/report.html` toggles
    (`map`, `hydrographs`, `long_record`, `typical_year`, `low_flow`,
    `validation`, `enso`, `timing_drift`, `analog_years`, `record_book`,
    `decade_fdc`, `composites`).
  - `build_notebook(ws_name, years, metrics, figures_dir, *, sections=None)
    -> nbformat.v4.NotebookNode` — assembles cells from pre-computed data
    only. `sections=None` means all; `set[str]` filters to those in
    canonical order. Unknown names raise `ValueError`. Missing PNGs produce
    a markdown note. Attribution cell always present.
  - `save_notebook(nb, output_path) -> Path` — validates via
    `nbformat.validate`, writes via `nbformat.write`.
  - `NotebookConverter` protocol: `to_pdf(nb, output_path) -> Path`.
  - `NbconvertPdfConverter` class: lazy-imports `nbconvert` + `weasyprint`
    in `__init__` (raises `ImportError` with clear message if missing).
    `to_pdf` uses `HTMLExporter` then `weasyprint.HTML` with dark-theme CSS.
    Respects `SOURCE_DATE_EPOCH`.
  - `notebook_to_pdf(nb, output_path, *, converter=None) -> Path` —
    convenience wrapper, defaults to `NbconvertPdfConverter`.
  - NO top-level import of `nbconvert` or `weasyprint`. NO `tools/` or
    `web/` imports.
- [x] 1.4 Run ONLY `tests/test_notebook_report.py` — record pass count.

**Acceptance:** 8 tests pass; module imports with no GDAL in `sys.modules`;
`src/` imports neither `web/` nor `tools/`; `nbformat` importable from
`pyproject.toml` deps.

## Group 2 — Endpoint contract + CLI flags · offline (`src/`) + non-offline (`tools/`)
**Dependencies:** Group 1

- [x] 2.1 Write 3 tests in `tests/test_notebook_report.py` (or
  `tests/test_endpoints.py` if endpoint tests already live there):
  1. `ENDPOINT_CONTRACTS["report"].formats` includes `("ipynb", "notebook")`
     and `("pdf", "document")`.
  2. `endpoint_plan` generates `{stem}.ipynb` and `{stem}.pdf` deliverables
     when those formats are requested.
  3. Requesting `format=pdf` or `format=notebook` does not break
     `assert_sellable` for public-domain sources.
  Run ONLY those tests.
- [x] 2.2 Update `src/endpoints.py`: add `("ipynb", "notebook")` and
  `("pdf", "document")` to the report `EndpointContract.formats` tuple.
- [x] 2.3 Run the 3 new tests — record pass count: 3 passed.
- [x] 2.4 Update `tools/build_watershed_report.py`:
  - Add `--notebook` flag (store_true): after `build_report` completes, call
    `build_notebook` + `save_notebook` to write `{tag}_report.ipynb`.
  - Add `--pdf` flag (store_true): implies `--notebook` internally; after
    notebook assembly, call `notebook_to_pdf` to write `{tag}_report.pdf`.
  - Both flags optional, off by default; existing behavior unchanged.
- [x] 2.5 Fake-reader offline smoke: import `tools/build_watershed_report`
  module and verify the argparse additions parse correctly (no real data
  needed).

**Acceptance:** Endpoint contract includes new formats; `endpoint_plan`
generates correct filenames; CLI parses `--notebook` and `--pdf` without error;
existing report behavior unchanged.

## Group 3 — Web report page update (`web/report.html`) · web-only
**Dependencies:** None (independent of Groups 1-2)

- [ ] 3.1 Add "PDF" and "Notebook" buttons to `#formatGrid` in
  `web/report.html`:
  - PDF button: `data-format="pdf"`.
  - Notebook button: `data-format="notebook"`.
- [ ] 3.2 Wire format choice into order CTA URL: `format=pdf` or
  `format=notebook` query param when navigating to `order.html`.
- [ ] 3.3 Run `node tests/test_recipe_roundtrip.cjs` — confirm no breakage.
- [ ] 3.4 Visual spot-check: load `report.html` in dev server, confirm new
  buttons render and CTA URL includes the selected format param.

**Acceptance:** New format buttons visible; CTA URL carries correct `format=`
param; recipe roundtrip green; no build step or external deps added.

## Group 4 — Real-data smoke + validation · non-offline (record real numbers)
**Dependencies:** Groups 1-2

- [ ] 4.1 *Deferred* — Run `tools/build_watershed_report.py` with `--notebook --pdf` against
  real data (Clark County or equivalent). Needs GIS stack + weasyprint installed.
- [ ] 4.2 *Deferred* — Verify `SOURCE_DATE_EPOCH=0` produces byte-identical PDF on
  back-to-back runs. Needs weasyprint installed.

**Acceptance:** Real numbers recorded; notebook opens in Jupyter without errors;
PDF renders all sections legibly; values physically plausible.

## Group 5 — Close out + regression · offline + docs
**Dependencies:** Groups 1-4

- [x] 5.1 Full offline suite green — **1738 passed** (was 1727, +11 new tests).
  **No `PIPELINE_STAGES` edit → 2D default render byte-identical.**
- [x] 5.2 Recipe roundtrip green: `node tests/test_recipe_roundtrip.cjs` — **12/12**.
- [x] 5.3 Rights gate confirmation: no new data sources; notebook/PDF assembled
  from existing USGS-derived analytics (public domain). `assert_sellable`
  continues to block PRISM-sourced reports regardless of format.
- [x] 5.4 Docs sweep: `CLAUDE.md` module map updated (notebook_report in parallel
  subsystems), roadmap Epoch 34 added, `implementation/report.md` written.
- [ ] 5.5 *Deferred* — Epoch retrospective (epoch not yet closed; Group 4 deferred).

**Acceptance:** Full offline suite green (count = N+k); recipe roundtrip green;
no PIPELINE_STAGES change; CLAUDE.md and AGENTS.md updated; report.md written.

## Execution Order
1. Group 1 (offline `src/` module — notebook assembly + converter seam)
2. Groups 2 and 3 in parallel (endpoint/CLI and web UI — independent)
3. Group 4 (real-data smoke after Groups 1-2 complete)
4. Group 5 (close out + regression after all groups)
