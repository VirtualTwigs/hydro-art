# Requirements — Jupyter Report PDF Generation (2026-10-17)

## Origin

User request: the report builder at `web/report.html` should produce a Jupyter
notebook report and save it as a PDF file.

## Current State

- `web/report.html` generates a **client-side seeded preview only** — no real
  backend report generation from the UI.
- Real reports are built via `tools/build_watershed_report.py` →
  `tools/report_common.py::build_report()`, which produces **matplotlib PNG
  figures** saved to disk plus a JSON metrics summary to stdout.
- `src/flow_metrics.py` (968 lines) contains all pure analytics — fully offline,
  numpy-only, no GIS.
- `src/endpoints.py` defines a `report` endpoint contract with `html` (document)
  and `png` (figures) formats — **no PDF or notebook format exists yet**.
- Existing hand-authored notebooks in `notebooks/` (e.g.
  `clark_county_watershed_report.ipynb`, 24 MB) demonstrate the target aesthetic:
  dark neon theme, multi-panel analysis, inline matplotlib figures.
- **No programmatic notebook generation** (nbformat/papermill) exists.
- **No PDF generation** for reports — only SVG-to-PDF art export via external CLI.
- Dependencies: no `nbformat`, `nbconvert`, `jupyter`, `papermill`, or
  `weasyprint` in `pyproject.toml` or `requirements.txt`.

## Desired Behavior

1. A new `src/` module programmatically builds a Jupyter notebook (.ipynb) from
   the watershed report data — sections mirror those in `web/report.html`
   (headline metrics, watershed map, hydrographs, trend panels, ENSO, regime,
   analogs, records, facilities, FDC, composites).

2. The notebook is converted to PDF (via nbconvert or equivalent).

3. The report endpoint (`src/endpoints.py`) gains `ipynb` and `pdf` as
   deliverable formats.

4. `tools/build_watershed_report.py` gains `--output-format notebook` (or
   `--pdf`) flags to produce the notebook/PDF directly.

5. The `web/report.html` order CTA can request `format=pdf` or `format=notebook`,
   which flows through the order pipeline to produce and deliver the artifact.

## Constraints

- Pure analytics (`src/flow_metrics.py`) must stay offline-testable — no GDAL,
  no network.
- The notebook generation module (`src/`) must be offline-testable: it assembles
  cells from pre-computed metrics/figures, never reads real data directly.
- Heavy I/O (GIS load, climate raster, gauge fetch) stays in `tools/`.
- `nbformat` is an acceptable new dependency (pure Python, no GDAL).
- `nbconvert` + a PDF backend (weasyprint or xelatex) is acceptable as an
  optional dependency — lazy-imported behind a seam, graceful degradation.
- The offline test suite must remain GDAL-free and network-free.
- Default builds stay byte-identical (no PIPELINE_STAGES change).
