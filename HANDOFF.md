# Handoff — hydro-art

_Last updated: 2026-07-26, after roadmap item #10 (final item)._

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
All 10 roadmap items implemented — the PRD §8 pipeline runs end-to-end with no
stubs. Items 1–9 committed; **item #10 commit pending** (awaiting "commit item
#10"). Full suite: 147 tests passing (as of item #10).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | committed (70d96c6) |
| 7 | Deterministic basin coloring | committed (31f93ca) |
| 8 | Layered SVG rendering | committed (3c3df62) |
| 9 | Optional glow & SVG optimization | committed (06869ba) |
| 10 | Multi-format export & reproducibility | implemented; commit pending |

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

## Roadmap complete — where things stand
- The full PRD §8 pipeline is implemented (`download → extract → validate →
  repair_geometries → reproject → clip_to_region → build_graph →
  compute_watersheds → assign_colors → generate_svg → optimize_svg → export`);
  no stage is a stub.
- `export` (`src/pipeline.py` `_export_stage`) writes `output_dir/<regions>.<fmt>`
  for each `settings.outputs`, records `artifacts["export_paths"]` and
  `artifacts["svg_sha256"]`. SVG is written with pure stdlib.
- External tools are optional and injected, both degrading gracefully when
  absent: `svgo` (`SvgoOptimizer`, optimize_svg) and `rsvg-convert`
  (`FileExporter`, export). Installing them unlocks optimized / rasterized
  outputs; without them SVG still ships.
- Possible follow-ups (not roadmap items): package/document the optional CLI
  tools (or add a `cairosvg` fallback), real raster tiling for 65536px, and the
  PRD §33 future-work outputs (web/animated/GeoJSON/vector tiles).
