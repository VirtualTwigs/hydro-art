# Handoff — hydro-art

_Last updated: 2026-07-26, after roadmap item #6._

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
Items 1–6 implemented. 1–5 committed; **item #6 committed?** check `git log`.
Full suite: 91 tests passing (as of item #6).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | implemented; commit pending unless done |
| 7 | Deterministic basin coloring | NEXT |
| 8–10 | SVG rendering / glow+optimize / export | not started |

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

## Item #7 (basin coloring) starting points
- Consume artifacts item #6 produced: `stream_orders` (segment_id→order),
  `watersheds` (HUC code→segment ids), `max_stream_order`.
- Goal: deterministic graph-coloring of adjacent watersheds for max contrast,
  then neon-palette assignment; identical inputs → identical colors (no random).
- Fits the `assign_colors` pipeline stage (currently a stub in `_STAGE_FUNCS`).
- See `agent-os/specs/2026-07-26-stream-ordering-and-watershed-grouping/implementation/report.md`
  ("Notes for next feature") for the input seams.
