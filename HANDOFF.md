# Handoff — hydro-art

_Last updated: 2026-07-26, after roadmap item #9._

## Project
Hydrographic Vector Art Generator: a Python 3.12+ (running 3.14.6) GIS→SVG
pipeline turning USGS hydrography into neon river art for Oregon/Washington.
Built incrementally following the Builder Methods Agent OS spec-driven workflow
(specs in `agent-os/specs/YYYY-MM-DD-<name>/`).

## Per-item workflow (repeat for each roadmap item)
User drives with two commands:
1. **"create tasks and implement item #N"** — write spec artifacts
   (`planning/requirements.md`, `spec.md`, `tasks.md`), then TDD-implement in
   task groups (2–8 tests first per group, run ONLY those), mark `tasks.md`
   checkboxes, write `implementation/report.md`, run full suite for
   regressions, smoke-test, then report and STOP.
2. **"commit item #N"** — commit that item as a separate explicit step. Never
   commit without this.

## Status
Items 1–9 implemented. 1–8 committed; **item #9 commit pending** (awaiting
"commit item #9"). Full suite: 134 tests passing (as of item #9).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | committed (70d96c6) |
| 7 | Deterministic basin coloring | committed (31f93ca) |
| 8 | Layered SVG rendering | committed |
| 9 | Optional glow & SVG optimization | implemented; commit pending |
| 10 | Multi-format export & reproducibility | NEXT |

## Key conventions
- Run tests: `.venv/bin/python -m pytest -q`
- Config precedence: defaults < YAML < CLI; argparse flags default to `None` so
  unset flags never clobber YAML. Allowlist validation at the boundary in
  `build_settings` (`src/config.py`), raising `ConfigError`.
- Pipeline stages (`src/pipeline.py`) are DI'd via `RunContext`, share results
  through `context.artifacts`, no global state. Heavy GIS libs are lazy-imported
  behind injectable seams (Downloader, LayerLoader) so tests run offline with
  hand-built shapely/graph inputs — no GDAL, no real data.
- Module errors subclass `AcquisitionError` (`src/datasets.py`).

## Item #10 (multi-format export & reproducibility) starting points
- Input seam: `artifacts["optimized_svg"]` (the optimized SVG string from item
  #9's `optimize_svg` stage). Everything is still in memory — `export` owns all
  filesystem writes.
- `export` is the last remaining stub in `_STAGE_FUNCS` (`src/pipeline.py`).
  Write the SVG to disk and convert to the requested `settings.outputs`
  (svg/pdf/png). No output dir wiring exists on `RunContext` yet.
- Reproducibility: pipeline is deterministic (identical inputs → identical
  bytes); export should preserve that and likely record a manifest/provenance.
- See
  `agent-os/specs/2026-07-26-glow-and-svg-optimization/implementation/report.md`
  ("Notes for next feature") for details.
