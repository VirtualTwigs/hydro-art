# Specification: Jupyter Notebook Report + PDF Export

## Goal

Add programmatic Jupyter notebook assembly and PDF conversion to the watershed report pipeline, so reports can be delivered as downloadable `.ipynb` or `.pdf` files alongside the existing PNG figures.

## User Stories

- As a customer ordering a watershed report, I want to receive a polished PDF so that I can print or share the analysis without needing Jupyter.
- As a data-literate customer, I want to receive a `.ipynb` notebook so that I can inspect the methodology and re-run cells with my own parameters.
- As the CLI operator, I want `--notebook` and `--pdf` flags on the report builder so that I can produce all delivery formats from one command.

## Architecture Placement

- **Offline `src/` module(s):** `src/notebook_report.py` -- assembles `.ipynb` from pre-computed metrics + figure PNGs; converts to PDF via injectable seam.
- **Non-offline `tools/` entry point(s):** extends `tools/build_watershed_report.py` with `--notebook` / `--pdf` flags (calls into `src/notebook_report.py`).
- **Touches `PIPELINE_STAGES`?** No -- report is a parallel subsystem.
- **Injected seam reused/extended:** New `NotebookConverter` protocol in `src/notebook_report.py`; follows the same injectable-collaborator pattern as `Downloader`, `SvgOptimizer`, etc.
- **Determinism impact:** No effect on 2D default output. Notebook and PDF are new artifacts produced only when explicitly requested.

## Specific Requirements

**Notebook assembly (`src/notebook_report.py`)**
- `build_notebook(ws_name, years, metrics, figures_dir, *, sections=None) -> nbformat.v4.NotebookNode` -- takes pre-computed data only, never loads GIS or real files.
- `ws_name`, `years` (start/end tuple), and `metrics` (the summary dict from `build_report`) are the structured inputs; `figures_dir` is a `Path` to the directory of PNGs produced by `tools/report_common.py::build_report`.
- Notebook cells: title markdown (watershed name, date range, attribution), headline metrics markdown (peak, low-flow, center-of-timing, flashiness from `metrics` dict), one section per panel (markdown heading + base64-embedded PNG in an image/png display_data output cell), and a closing attribution/rights cell.
- Section names mirror `web/report.html` toggles: `map`, `hydrographs`, `long_record`, `typical_year`, `low_flow`, `validation`, `enso`, `timing_drift`, `analog_years`, `record_book`, `decade_fdc`, `composites`.
- `sections` param: `None` means all sections; a `set[str]` produces only those sections in canonical order. Unknown section names raise `ValueError`.
- Figure PNGs are read from `figures_dir` by convention: `{tag}_{section}.png` (same naming `build_report` already uses). Missing PNGs for an enabled section are skipped with a markdown note, not an error.
- The module must import `nbformat` at module top level (pure Python, no GDAL). `nbformat` is added to `pyproject.toml` dependencies.

**Notebook save**
- `save_notebook(nb, output_path) -> Path` -- writes `.ipynb` via `nbformat.write`, returns the resolved path.
- Validates the notebook structure before writing (`nbformat.validate`); raises on malformed cells.

**PDF conversion seam**
- `NotebookConverter` protocol: single method `to_pdf(nb: NotebookNode, output_path: Path) -> Path`.
- Production implementation `NbconvertPdfConverter`: lazy-imports `nbconvert` + `weasyprint` (never at module top level), uses `nbconvert.HTMLExporter` to render HTML then `weasyprint.HTML` to produce PDF. Dark theme CSS injected inline to match the neon report aesthetic.
- If `nbconvert` or `weasyprint` is not installed, `NbconvertPdfConverter.__init__` raises `ImportError` with a clear message naming the missing package.
- Convenience function `notebook_to_pdf(nb, output_path, *, converter=None) -> Path` -- uses `NbconvertPdfConverter` by default; accepts an injected `converter` for testing.
- `SOURCE_DATE_EPOCH=0` must be respected: the PDF converter should not embed wall-clock timestamps.

**Endpoint contract update (`src/endpoints.py`)**
- Add `("ipynb", "notebook")` and `("pdf", "document")` to the report `EndpointContract.formats` tuple, after the existing `("html", "document")` and `("png", "figures")`.
- `endpoint_plan` will automatically generate filenames `{stem}.ipynb` and `{stem}.pdf` when those formats are requested.
- The rights gate (`assert_sellable`) continues to block PRISM-sourced reports regardless of format.

**CLI changes (`tools/build_watershed_report.py`)**
- Add `--notebook` flag (store_true): after `build_report` completes, call `build_notebook` + `save_notebook` to write `{tag}_report.ipynb` to `--out-dir`.
- Add `--pdf` flag (store_true): after notebook assembly, call `notebook_to_pdf` to write `{tag}_report.pdf` to `--out-dir`. Implies `--notebook` internally (PDF is built from the notebook).
- Both flags are optional and off by default; existing behavior is unchanged.

**Web report page (`web/report.html`)**
- Add "PDF" and "Notebook" buttons to the `#formatGrid` delivery-format chooser, alongside existing "Digital", "Print", "Web".
- PDF button: `data-format="pdf"`. Notebook button: `data-format="notebook"`.
- Order CTA URL includes `format=pdf` or `format=notebook` as appropriate when navigating to `order.html`.
- No build step; vanilla JS only.

**Dependency changes**
- `nbformat` added to `pyproject.toml` `[project.dependencies]` (pure Python, always importable, needed by `src/notebook_report.py`).
- `nbconvert` and `weasyprint` added to `requirements.txt` (optional GIS-tier deps, lazy-imported behind the converter seam).

**Test strategy (`tests/test_notebook_report.py`)**
- All tests fully offline -- no GDAL, no network, no real data.
- Test notebook cell structure: correct cell count, cell types (markdown vs code/output), section ordering matches canonical order.
- Test section filtering: passing `sections={"map", "long_record"}` produces only title + those two sections + attribution.
- Test figure embedding: given a temp dir with a fake PNG, the corresponding cell contains base64-encoded image data.
- Test missing figure graceful skip: enabled section with no PNG file produces a markdown "figure not available" note instead of raising.
- Test unknown section name raises `ValueError`.
- Test `save_notebook` round-trips: write then read back and validate structure.
- Test PDF converter seam: `FakeNotebookConverter` injected into `notebook_to_pdf` is called with correct args and its return value is forwarded.
- Test headline metrics formatting: given a metrics dict, the headline cell contains the expected formatted values.

## Existing Code to Leverage

**`tools/report_common.py` -- figure recipe + WatershedSeries**
- `build_report(ws, ...)` already produces the full set of PNG figures to a directory with deterministic naming (`{tag}_{section}.png`).
- `WatershedSeries` dataclass holds all the data the notebook title/metrics cells need (name, huc4, years, reach count, peak_month).
- The summary dict returned by `build_report` contains the exact metrics keys the notebook headline cell should render.
- The figure function names (`fig_watershed_map` -> `map`, `fig_hydrographs` -> `hydrographs`, etc.) establish the section-to-filename mapping.

**`src/endpoints.py` -- endpoint contracts**
- `ENDPOINT_CONTRACTS["report"]` already defines the report's format tuple; extending it with two new `(fmt, kind)` pairs is a one-line change.
- `endpoint_plan` automatically generates `Deliverable` items for requested formats using the contract's `format_names` and `kind_for` lookup.
- `EndpointRequest.formats` is a frozenset of format strings; the validator and plan generator need no structural changes.

**`tools/build_watershed_report.py` -- CLI driver**
- Already wires `load_watershed_series` -> `build_report` -> JSON stdout. The notebook/PDF flags add post-processing steps after `build_report` returns.
- `--out-dir` already controls output location; notebook and PDF files land in the same directory.

**Injectable seam pattern (project-wide)**
- `Downloader`/`UrllibFetcher`, `SvgOptimizer`/`SvgoOptimizer`, `Exporter` -- all follow the same protocol + production-impl + fake-for-tests pattern that `NotebookConverter` should match.
- Seam bodies are lazy-imported; the protocol itself is a plain class with abstract-style methods (no ABC required, just duck typing or `Protocol`).

## Rights & Determinism Notes

- No new data sources. Notebooks and PDFs are assembled from existing USGS-derived analytics (public domain). Attribution cell includes the standard `attribution_line` from `src/fulfillment`.
- Climate source rights gate still applies: `--climate-source prism` reports are not sellable in any format. The endpoint's `assert_sellable` check is format-independent.
- 2D default render is not touched. Notebook/PDF are new, opt-in artifacts outside `PIPELINE_STAGES`.
- PDF determinism: `SOURCE_DATE_EPOCH=0` suppresses weasyprint timestamps. Notebook `.ipynb` is deterministic by construction (no random IDs, sorted keys).

## Out of Scope

- Executing the notebook (cells are display-only, not executable).
- Interactive widgets, ipywidgets, or kernel attachment.
- Real data loading or GIS imports in `src/notebook_report.py`.
- Changes to `src/flow_metrics.py` (already complete).
- LaTeX-based PDF via xelatex (weasyprint is the chosen backend).
- Notebook serving, viewing, or previewing in the browser.
- Changes to `PIPELINE_STAGES`.
- New climate data sources or rights-gate changes.
- Generating report figures from within the notebook (figures come pre-rendered from `tools/report_common.py`).
- Animated or interactive visualizations in the notebook.
