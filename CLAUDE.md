# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hydrographic Vector Art Generator: a Python 3.12+ CLI that turns public USGS hydrography (NHDPlus HR / NHD / WBD) into layered, neon-colored SVG river art for Oregon/Washington. Single-command GIS→SVG pipeline; deterministic (identical inputs → identical output, no randomness). See `docs/PRD.md` for the full spec and `agent-os/product/mission.md` for the product framing.

## Commands

```bash
.venv/bin/python -m pytest -q                     # full test suite
.venv/bin/python -m pytest tests/test_config.py   # one test file
.venv/bin/python -m pytest tests/test_config.py::test_name  # one test
.venv/bin/python build.py                          # run pipeline (defaults)
.venv/bin/python build.py --region Washington --palette neon --glow --output svg pdf
```

There is no separate build step (it's a script). `ruff` is the configured linter (`line-length = 88`).

## Development workflow (Agent OS, spec-driven)

Work proceeds one roadmap item at a time (`agent-os/product/roadmap.md`), following the Builder Methods Agent OS workflow. The user drives with two explicit commands:

1. **"create tasks and implement item #N"** — write spec artifacts under `agent-os/specs/YYYY-MM-DD-<name>/` (`planning/requirements.md`, `spec.md`, `tasks.md`), then TDD-implement in task groups (write 2–8 tests first per group and run ONLY those), tick `tasks.md` checkboxes, write `implementation/report.md`, run the full suite to check regressions, smoke-test, then report and STOP.
2. **"commit item #N"** — committing is a separate, explicit step. Never commit unless asked with this command.

`HANDOFF.md` tracks current progress across roadmap items and is the fastest way to learn what's implemented vs. stubbed. Update it as items land.

## Architecture

The pipeline is a fixed, ordered sequence of stages defined in `src/pipeline.py` (`PIPELINE_STAGES`, order per PRD §8):

```
download → extract → validate → repair_geometries → reproject →
clip_to_region → build_graph → compute_watersheds → assign_colors →
generate_svg → optimize_svg → export
```

Each stage is a `Stage(name, run)` where `run(ctx: RunContext) -> None`. All 12 stages are now implemented (no stubs remain). The stub mechanism is still in place: `PIPELINE_STAGES` builds each stage from `_STAGE_FUNCS.get(name, _stub(name))`, so a new/future stage is wired in by adding its real function to `_STAGE_FUNCS`.

Key structural rules (enforced throughout — preserve them):

- **No global state.** A single immutable `Settings` (`src/config.py`) and a mutable `RunContext` are dependency-injected. Stages communicate only through `ctx.artifacts` (a dict); a stage reads the artifacts prior stages wrote and writes its own. E.g. `assign_colors` reads `hydro_graph` + `watersheds` and writes `segment_colors` / `watershed_colors`.
- **Injectable seams for I/O.** Network, GIS, and external-tool access go through injected collaborators — `Downloader`/`UrllibFetcher` (`src/download.py`), `LayerLoader`/`PyogrioLayerLoader` (`src/loading.py`), `DownloaderLike` (`src/cache.py`), `SvgOptimizer`/`SvgoOptimizer` (`src/optimize.py`, wraps optional `svgo`), `Exporter`/`FileExporter` (`src/export.py`, wraps optional `rsvg-convert`). Tests inject fakes and hand-built shapely/graph inputs so the suite runs **fully offline** — no GDAL, no network, no real datasets. Keep heavy GIS libs lazy-imported behind these seams. External CLI tools (`svgo`, `rsvg-convert`) are optional and degrade gracefully when absent — SVG still ships; installing them unlocks optimized/rasterized output.
- **Validate at the boundary, fail fast.** `build_settings` (`src/config.py`) validates every field against allowlists (`SUPPORTED_REGIONS`, `SUPPORTED_PROJECTIONS`, `SUPPORTED_HUC_LEVELS`, etc.) and raises `ConfigError` with user-facing messages. To add a region/projection/palette/etc., extend the relevant allowlist there (single source of truth).
- **Config precedence:** `defaults < config.yaml < CLI flags` (`src/cli.py`). Argparse flags default to `None` so an unset flag never clobbers a YAML value; only explicitly-passed flags become overrides (`cli_overrides`).
- **Error taxonomy:** config errors subclass `ConfigError`; acquisition/dataset errors subclass `AcquisitionError` (`src/datasets.py`). `build.py` maps them to distinct exit codes (1 = config, 2 = acquisition).

### Module map (`src/`)

`config.py` settings model + validation · `cli.py` arg parsing + precedence · `datasets.py` resolve required USGS files · `download.py` / `cache.py` fetch + persistent file cache + extraction · `loading.py` GeoPandas/pyogrio layer loading · `geometry.py` invalid-geometry repair + `RepairStats` · `projection.py` reproject to EPSG:5070 · `clipping.py` clip to region boundary · `graph.py` directed river network (NetworkX) + stats · `ordering.py` stream order (Strahler/Shreve/Hack/custom) · `watersheds.py` HUC grouping · `coloring.py` deterministic high-contrast palette assignment · `rendering.py` layered SVG generation (stdlib, optional glow) · `optimize.py` optional SVGO pass · `export.py` write SVG + optional PNG/PDF via `rsvg-convert` + SHA-256.

Each `src/<name>.py` has a matching `tests/test_<name>.py`; pipeline-integration tests are `tests/test_*_pipeline.py`.

## Conventions

- Type hints + docstrings on public functions; `from __future__ import annotations` at the top of modules.
- Immutable/frozen dataclasses for value objects (`Settings`, `Stage`); prefer pure functions operating on injected inputs over stateful classes.
- Runtime data dirs `datasets/`, `cache/`, `output/`, `logs/` are large and git-ignored (regenerable). `.venv/` is the project interpreter.
