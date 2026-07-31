# Handoff — hydro-art

_Last updated: 2026-07-30, after roadmap item #13 (Epoch 2, DEM normalization)._

## Current state (2026-07-30)

- **Epoch 1 (#1–10):** complete and committed.
- **Epoch 1.5 waterbodies (W1–W4):** complete and committed
  (`46a0766`…`fc60c5c`). Note: the roadmap.md restructure that adds Epochs
  1.5–5 is still uncommitted and does not yet tick W1–W4.
- **Epoch 2 #11 (elevation settings & provenance contract):** implemented,
  **uncommitted** (`src/config.py` elevation block, `src/elevation.py`, CLI
  flags, +19 tests).
- **Epoch 2 #12 (3DEP DEM discovery & cache):** implemented 2026-07-30,
  **uncommitted** — `src/dem.py` + `tests/test_dem.py` (9 tests). Deterministic
  1-degree COG-grid discovery on the `prd-tnm` S3 bucket for `preview`/`state`
  tiers; `local` (1 m) deferred. Delivery decisions resolved: AWS S3 COGs;
  normalize-to-NAVD88 (identity for CONUS 3DEP, enforced later in #13).
- **Epoch 2 #13 (DEM mosaic/clip/pyramid + bilinear sampling):** implemented
  2026-07-30, **uncommitted** (awaiting an explicit "commit item #13"; #11/#12
  are committed as `33a60d9`/`d2296aa`). `src/raster.py` +
  `tests/test_raster.py` (11 tests): numpy
  `RasterGrid`, `mosaic`/`clip_grid`/`build_pyramid`, `sample_bilinear` +
  `GridSampler`, and `normalize_dem` orchestrating read→reproject(EPSG:5070)→
  mosaic→clip→pyramid via injected `RasterReader`/`RasterReprojector` seams.
- **Next:** #14 (terrain sampling service + flowline densification, Group 4) can
  proceed — it consumes `GridSampler`. #16/#17+ (Groups 5–6) blocked on two open
  decisions (mesh/error budget; GLB-vs-OBJ) in the spec's `planning/requirements.md`.
- Full suite: **228 passing**. Spec artifacts:
  `agent-os/specs/2026-07-29-dem-elevation-and-3d-modeling/`.

---


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
