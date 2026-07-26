# Handoff — hydro-art

_Last updated: 2026-07-26, after roadmap item #7._

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
Items 1–7 implemented. 1–6 committed; **item #7 committed?** check `git log`.
Full suite: 106 tests passing (as of item #7).

| # | Item | State |
|---|------|-------|
| 1 | Config & CLI foundation | committed |
| 2 | Dataset acquisition & cache | committed (f630be2) |
| 3 | Data loading & geometry repair | committed (546b97a) |
| 4 | Projection & region clipping | committed (094ce41) |
| 5 | Hydrography graph construction | committed (fde1950) |
| 6 | Stream ordering & watershed grouping | committed (70d96c6) |
| 7 | Deterministic basin coloring | implemented; commit pending unless done |
| 8 | Layered SVG rendering | NEXT |
| 9–10 | glow+optimize / export | not started |

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

## Item #8 (layered SVG rendering) starting points
- Consume artifacts item #7 produced: `segment_colors` (segment_id→hex),
  `watershed_colors` (HUC code→hex), plus `watersheds` (HUC code→segment ids)
  for grouping `<g>` layers, and each edge's `geometry`/`length` in `hydro_graph`.
- Goal: render each river as a round-capped/round-joined vector path colored by
  `segment_colors`, grouped per watershed, on `settings.background`, base stroke
  `settings.line_width`; optional width scaling off `stream_orders`/`max_stream_order`.
- Fits the `generate_svg` pipeline stage (currently a stub in `_STAGE_FUNCS`).
- See `agent-os/specs/2026-07-26-deterministic-basin-coloring/implementation/report.md`
  ("Notes for next feature") for the input seams.
