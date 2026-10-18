# Implementation Report — Jupyter Notebook Report + PDF Export (Epoch 34)

## Summary

New `src/notebook_report.py` module programmatically assembles Jupyter notebooks
from pre-computed watershed report metrics and figure PNGs, with optional PDF
conversion via an injectable `NotebookConverter` seam. Report endpoint gains
`ipynb` and `pdf` formats; CLI gains `--notebook` and `--pdf` flags; web report
page gains PDF and Notebook delivery format buttons. No pipeline changes.

## Changes

### New: `src/notebook_report.py`

- `CANONICAL_SECTIONS` ordered tuple (12 sections matching web/report.html toggles)
- `build_notebook(ws_name, years, metrics, figures_dir, *, sections=None, fig_prefix="")` → `NotebookNode`
  - Assembles: title markdown, headline metrics markdown, section cells (markdown heading + base64-embedded PNG display_data), attribution cell
  - Section filtering via `sections` set; unknown names raise `ValueError`
  - Missing PNGs gracefully skipped with markdown note
- `save_notebook(nb, output_path)` → validated write via `nbformat.validate` + `nbformat.write`
- `NotebookConverter` protocol: `to_pdf(nb, output_path) -> Path`
- `NbconvertPdfConverter`: lazy-imports `nbconvert` + `weasyprint`, dark-theme CSS, `SOURCE_DATE_EPOCH` aware
- `notebook_to_pdf(nb, output_path, *, converter=None)` → convenience wrapper

### Modified: `src/endpoints.py`

Added `("ipynb", "notebook")` and `("pdf", "document")` to the report
`EndpointContract.formats` tuple. `endpoint_plan` automatically generates
correct filenames and kinds.

### Modified: `tools/build_watershed_report.py`

Added `--notebook` (store_true) and `--pdf` (store_true) argparse flags.
Post-processing after `build_report()` returns: assembles notebook, optionally
converts to PDF. `--pdf` implies notebook assembly. Off by default; existing
behavior unchanged.

### Modified: `web/report.html`

Added "PDF" (`data-format="pdf"`) and "Notebook" (`data-format="notebook"`)
buttons to the `#formatGrid` delivery format chooser. Format flows into order
CTA URL automatically via existing `selectedFormat` → `goToOrder()` wiring.

### Modified: `pyproject.toml`

Added `nbformat>=5.9` to `[project.dependencies]`.

### Modified: `CLAUDE.md`

Added `notebook_report` to the parallel subsystems module map.

### Golden fixtures updated

- `tests/fixtures/golden/e2e/washington-wahkiakum.json` — includes new ipynb + pdf deliverables
- `tests/fixtures/golden/gallery/ledger.json` — reflects updated report contract

## Test results

| Suite | Result |
|-------|--------|
| Offline pytest | **1738 passed** (+11 new) in 4.15s |
| Recipe roundtrip | 12/12 green |
| Notebook tests | 8/8 |
| Endpoint tests | 37/37 |

## Files added/modified

- `src/notebook_report.py` (new)
- `tests/test_notebook_report.py` (new, 8 tests)
- `src/endpoints.py` (2 format tuples added)
- `tools/build_watershed_report.py` (2 CLI flags)
- `web/report.html` (2 format buttons)
- `pyproject.toml` (nbformat dep)
- `CLAUDE.md` (module map)
- `agent-os/product/roadmap.md` (Epoch 34 added)
- Golden fixtures (2 files updated)

## Deferred

- **Group 4 real-data smoke:** needs full GIS pipeline run + weasyprint installed
- **PDF determinism check:** needs weasyprint for `SOURCE_DATE_EPOCH=0` verification
