# Handoff — hydro-art

_Last updated: 2026-07-26, after roadmap item #8._

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
Items 1–8 implemented. 1–7 committed; **item #8 committed?** check `git log`.
Full suite: 120 tests passing (as of item #8).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | committed (70d96c6) |
| 7 | Deterministic basin coloring | committed (31f93ca) |
| 8 | Layered SVG rendering | implemented; commit pending unless done |
| 9 | Optional glow & SVG optimization | NEXT |
| 10 | Multi-format export & reproducibility | not started |

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

## Item #9 (optional glow & SVG optimization) starting points
- Input seam: `artifacts["svg"]` (the SVG document string from item #8's
  `generate_svg` stage). `render_svg` (`src/rendering.py`) emits a bare `<defs/>`
  for glow filters to populate.
- Glow: `settings.glow` bool already exists (Mode A pure-vector / Mode B SVG
  Gaussian blur, PRD §20); add a configurable radius (no config field yet).
- SVGO optimization (PRD §21) is a Node subprocess — keep it behind an
  injectable seam (mirror the Downloader/LayerLoader pattern) so tests stay
  offline. Fits the `optimize_svg` stage (still a stub in `_STAGE_FUNCS`).
- SVG chosen over `svgwrite`: hand-rolled stdlib serializer for determinism +
  offline tests (see item #8 report). `export` (item #10) writes files to disk.
- See `agent-os/specs/2026-07-26-layered-svg-rendering/implementation/report.md`
  ("Notes for next feature") for details.
