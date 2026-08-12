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

**Dependencies are split across two files on purpose.** `pyproject.toml` lists only the always-imported core deps (`pyyaml`, `rich`); the heavy GIS stack (`shapely`, `geopandas`, `pyogrio`, `numpy`, `networkx`) lives in `requirements.txt` because it's lazy-imported behind injectable seams (see Architecture). Install everything with `.venv/bin/pip install -r requirements.txt`; the minimal `pyproject.toml` set is what keeps the test suite importable without GDAL.

**The download stage stages archives on a NAS, not locally.** `build.py` sets `NAS_CACHE_DIR = "/Volumes/home/data/incoming"` (a Synology `home` share) so the large hydrography GDB zips are cached off-machine and reused. Expect this mount to be involved in real (non-test) runs.

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

**This 12-stage pipeline is 2D-only.** The elevation/DEM/terrain/3D subsystem (roadmap Epochs 2–4, the `dem`/`raster`/`terrain`/`hydro_z`/`mesh`/`scene`/`preview`/`export3d` modules) is a *parallel* set of pure, deterministic, offline modules that is **not** wired into `PIPELINE_STAGES` and is not run by `build.py`. It's exercised by the test suite and driven ad-hoc by the `tools/` 3D scripts and preview-asset generation. Treat it as a second data model that shares the projection/CRS conventions but has its own entry points. Waterbodies (Epoch 1.5) are the exception: they *do* integrate into the existing pipeline — `validate` additively loads waterbody layers when `settings.waterbodies.enabled` and the loader supports it, and `generate_svg` classifies/selects them (`_select_waterbody_outlines`) into dedicated outline layers.

Key structural rules (enforced throughout — preserve them):

- **No global state.** A single immutable `Settings` (`src/config.py`) and a mutable `RunContext` are dependency-injected. Stages communicate only through `ctx.artifacts` (a dict); a stage reads the artifacts prior stages wrote and writes its own. E.g. `assign_colors` reads `hydro_graph` + `watersheds` and writes `segment_colors` / `watershed_colors`.
- **Injectable seams for I/O.** Network, GIS, and external-tool access go through injected collaborators — `Downloader`/`UrllibFetcher` (`src/download.py`), `LayerLoader`/`PyogrioLayerLoader` (`src/loading.py`), `DownloaderLike` (`src/cache.py`), `SvgOptimizer`/`SvgoOptimizer` (`src/optimize.py`, wraps optional `svgo`), `Exporter`/`FileExporter` (`src/export.py`, wraps optional `rsvg-convert`). Tests inject fakes and hand-built shapely/graph inputs so the suite runs **fully offline** — no GDAL, no network, no real datasets. Keep heavy GIS libs lazy-imported behind these seams. External CLI tools (`svgo`, `rsvg-convert`) are optional and degrade gracefully when absent — SVG still ships; installing them unlocks optimized/rasterized output.
- **Validate at the boundary, fail fast.** `build_settings` (`src/config.py`) validates every field against allowlists (`SUPPORTED_REGIONS`, `SUPPORTED_PROJECTIONS`, `SUPPORTED_HUC_LEVELS`, etc.) and raises `ConfigError` with user-facing messages. To add a region/projection/palette/etc., extend the relevant allowlist there (single source of truth).
- **Config precedence:** `defaults < config.yaml < CLI flags` (`src/cli.py`). Argparse flags default to `None` so an unset flag never clobbers a YAML value; only explicitly-passed flags become overrides (`cli_overrides`).
- **Error taxonomy:** config errors subclass `ConfigError`; acquisition/dataset errors subclass `AcquisitionError` (`src/datasets.py`). `build.py` maps them to distinct exit codes (1 = config, 2 = acquisition).

### Module map (`src/`)

**2D pipeline (Epoch 1):** `config.py` settings model + validation · `cli.py` arg parsing + precedence · `datasets.py` resolve required USGS files · `download.py` / `cache.py` fetch + persistent file cache + extraction · `loading.py` GeoPandas/pyogrio layer loading · `geometry.py` invalid-geometry repair + `RepairStats` · `projection.py` reproject to EPSG:5070 · `clipping.py` clip to region boundary · `graph.py` directed river network (NetworkX) + stats · `ordering.py` stream order (Strahler/Shreve/Hack/custom) · `watersheds.py` HUC grouping · `coloring.py` deterministic high-contrast palette assignment · `rendering.py` layered SVG generation (stdlib, optional glow) · `optimize.py` optional SVGO pass · `export.py` write SVG + optional PNG/PDF via `rsvg-convert` + SHA-256.

**Waterbodies (Epoch 1.5):** `waterbodies.py` NHD waterbody/area polygon classification (lake/reservoir/pond/bay/inlet/coastal taxonomy) · `waterbody_selection.py` repair/reproject/region-clip + area/detail selection policy → render-ready outlines. Both hook into the 2D pipeline as described above.

**Elevation/DEM/terrain/3D (Epochs 2–5, parallel subsystem, not in `PIPELINE_STAGES`):** `elevation.py` immutable `ElevationProvenance` contract + `TileDiscoverer`/`RasterReader`/`ElevationSampler` seams · `dem.py` deterministic 3DEP COG-tile discovery/cache on S3 · `raster.py` numpy `RasterGrid` mosaic/clip/pyramid + bilinear `GridSampler` + `normalize_dem` (read→reproject→mosaic→clip→pyramid) · `terrain.py` densify river lines to DEM spacing + `TerrainSampler` · `hydro_z.py` attach ground Z to river vertices (`ElevatedLine`, keeps original 2D path), inversion QA, opt-in render-only monotonic repair · `mesh.py` error-bounded TIN terrain mesh from a DEM pyramid · `scene.py` `assemble_scene` → immutable `SceneModel` (terrain + Z-rivers + materials + cardinal/axis annotations + camera presets + display-only exaggeration) · `export3d.py` deterministic stdlib GLB + OBJ/MTL writers + JSON provenance manifest · `preview.py` browser heightfield tiles (coarse interaction + fine commit) for `web/3d.html` · `accuracy.py` (Epoch 5 #20) pure, numpy-free accuracy-validation suite — compares DEM-sampled vertices against known truths (`error_metrics`: max/mean abs error + RMSE, nodata/uncovered skipped never zero-filled), plus `coverage_report`, `crs_report` (verbatim from provenance), `qa_rollup` (river-profile inversions, structural over `ProfileQA`) → `AccuracyReport`/`validate_against_sampler` over the injected `ElevationSampler` seam. All are pure/deterministic/offline; vertical exaggeration is display-only and never overwrites source Z.

**Web control-surface backend (Epoch 6 #27, localhost job runner — not in `PIPELINE_STAGES`):** `jobs.py` `settings_from_payload` (whitelists the `DEFAULTS` keys, validates via `build_settings`) + `JobRunner` (validate-at-`submit` → 400, then run an **injected**, duck-typed pipeline off-thread; tracks `pending→running→succeeded|failed` + `export_paths`/`svg_sha256`) · `server.py` pure `handle_request` dispatcher over stdlib `http.server` (`POST /api/render`, `GET /api/jobs/<id>`, `GET …/artifact?fmt=`, static `web/` with a path-traversal guard) + a thin `serve()`. Both are stdlib-only and GDAL-free (`jobs.py` imports only stdlib + `src.config`; the real `Pipeline` is injected, never imported by the runner core), so `tests/test_jobs.py`/`tests/test_server.py` run fully offline with a fake pipeline + inline executor. The top-level `serve.py` entry point wires the real `Pipeline(cache_dir=NAS_CACHE_DIR)` into a `JobRunner` and serves the control surface on localhost.

Not every module maps 1:1 to a pipeline stage: `ordering.py` (`assign_stream_order`) has no stage of its own — it's invoked inside the `compute_watersheds` stage (`src/pipeline.py`), which produces both `stream_orders` and `watersheds` artifacts.

Each `src/<name>.py` has a matching `tests/test_<name>.py`; pipeline-integration tests are `tests/test_*_pipeline.py`.

### Ad-hoc tools (`tools/`)

Standalone scripts run directly (`python tools/<name>.py`), outside the pipeline and outside the test suite — they import heavy GIS libs eagerly and read real datasets, so they only work in a full (non-offline) environment. They *may* import from `src/` (e.g. `src.rendering`, `src.coloring`); the dependency never runs the other way — `src/` and the test suite stay GDAL-free and must not import `tools/`.

**Shared recipe:** `render_common.py` is the single "art-quality" rendering recipe every 2D clip renderer calls so outputs never drift apart — QAMA flow-scaled stroke widths (channels taper/widen at each confluence via `src.rendering.flow_widths`), HUC-N sub-watershed coloring by point-in-polygon join against WBD boundaries, neon glow, and high-res layered rasterization. It also holds shared constants (e.g. `STATE_HUC4`, `CLARK_BBOX_4326`, the Census state/county shapefile paths under `/tmp`). Prefer extending this over duplicating render logic in a new tool.

*2D clip/rasterize:* `render_region_clip.py` clips flowlines to a *political* boundary (e.g. the actual Oregon state polygon) rather than the pipeline's WBD watershed basins, with a Strahler `--min-order` filter to thin clutter; `render_county_clip.py` is its county-granularity sibling (clips to a single Census county polygon, colors by HUC4 basin, overlays the county outline in red); `render_state_svg.py` renders a whole-state SVG; `render_state_mono.py` paints every flowline by its NHDPlus smoothed *elevation* (`MinElevSmo`/`MaxElevSmo`, white summit → deep-blue sea) as a hypsometric tint instead of basin colors — needs the color-`None` `rivers_unassigned` group so it bypasses `build_inputs`; `rasterize_layered.py` rasterizes SVGs that exceed the ~1M-node cap of librsvg/resvg by splitting the document into one standalone SVG per `<g id="watershed_...">` layer, rasterizing each with `resvg`, then alpha-compositing over black (also rescales meter-unit stroke/glow widths to pixels); `overlay_facilities.py` overlays point facilities.

*Monthly flow / "year in motion":* `monthly_flow.py` is a data-prep prototype (not a renderer) that disaggregates NHDPlus HR mean-annual EROM discharge (`QAMA`) into a 12-month flow series using the GDB's real per-catchment monthly precip/temperature climatology (snow-aware available water → incremental monthly volume → downstream `HydroSeq` accumulation), conserving each reach's annual mean. `render_monthly.py` consumes it to render a 12-frame GIF where channel width tracks monthly flow — the key trick is computing the log flow→width mapping **once** across all twelve months and holding it fixed, so seasonal swell/retreat is actually visible (per-frame renormalization would hide it). `render_infographic.py` composes a still infographic (river map at its driest month + a left panel with axial-tilt/season diagram, precip bar chart, and moon-phase diagram); `render_infographic_year.py` is its animated sibling, walking the calendar in `--frames` steps (52 = weekly) with month-interpolated flow, supporting both a Clark County bbox and a whole-state (`--state Oregon`) clip.

*Stylized 3D:* `render_county_3d.py` / `render_state_3d.py` render a tilted, glowing pseudo-3D image where height is *derived from the hydrography itself* (each flowline's Strahler order sets its Z, so headwaters ride high and mainstems sink) — note this is a stylized hydrology field, **not** the surveyed-DEM terrain of the `src/` 3D subsystem. `waterbody_qa.py` is a waterbody QA/validation helper.

### Web prototypes (`web/`)

Self-contained HTML/JS pages (no build step — open directly over `file://`) exploring the interactive UX for the generator. They are still `file://`-safe mockups by default, but the canonical control surface (`web/studio.html`) can now also be **served** by the top-level `serve.py` to run the real pipeline (Epoch 6 #27 — see the control-surface backend in the module map); the dependency direction is one-way — `src/` + the offline test suite must stay free of any dependency on `web/`. `index.html` is an early standalone control-panel concept; `3d.html` is a WebGL "3D Terrain Lab" that orbits the terrain-and-rivers model — it consumes the DEM-backed heightfield tiles emitted by `src/preview.py` (replacing its earlier synthetic `elevationAt()` field).

**Shared foundation.** `web/shared/ux.css` (design tokens + components) and `web/shared/hydro-ux.js` (`window.HydroUX`, loaded as a classic `<script src>` not an ES module) are the single source of the studio look and client-side model. `hydro-ux.js` mirrors the Python side — option data (`STATES`, `COUNTIES`, `PALETTES`, `HYPSO`, `HUC_LEVELS`, `MONTH_ABBR`) drawn from `src/config`/`src/coloring`/`render_common`, a deterministic procedural network generator + SVG builder for a datasetless preview, a seasonal monthly-flow *simulation* (a client-side stand-in for `tools/monthly_flow.py`, scaled on a fixed year-max so seasonal swell/retreat shows), `applyStyles()`, and the mapping helpers (`cliMapping`/`yamlMapping`) that translate UX selections back into a `build.py` command + `config.yaml` fragment. Keep option data, preview engine, and mapping logic here — do not duplicate across pages.

**Prototypes → product.** `web/studio.html` is the **canonical control surface** (roadmap #26, `agent-os/specs/2026-08-10-web-control-surface/`): Prototype A's dense left-rail studio layout using Prototype B's click-to-set month timeline. `proto-b-guided.html` (step-by-step wizard) and `proto-c-canvas.html` (canvas-first toolbar/popovers) remain as the two alternate UX explorations over the shared foundation. The control surface drives a live client-side preview and emits a deterministic CLI/YAML output contract from one mutable `state` object. Since #23–#25 have shipped, the mapping helpers now emit `color_by`/`width_by` (min/max/gamma), `--county`, and `--months` as **real `build.py` flags** (no more `(proposed)` markers). Two options are shipped-as-flags but still fail fast in the *2D* pipeline and carry an honest caveat in the output contract: `color_by=elevation` (needs the DEM subsystem → `tools/render_state_mono.py`) and non-annual `--months` (live month frames → `tools/render_monthly.py`). Base `line_width`/`background` have no CLI flag and appear only in the YAML fragment.

**Live pipeline runs (#27).** When `studio.html` is *served* by `serve.py` (not opened over `file://`), a "Run pipeline" button POSTs `HydroUX.renderRequest(state)` — a pure builder emitting the **structured JSON payload** of real `src/config` keys, never the shell command string — to the localhost job runner, polls the job, and shows the produced SVG with a download. Over `file://` the button is disabled and the surface stays mapping-only. `color_by=elevation` and non-annual `--months` come back as a **failed job** carrying the pipeline's fail-fast message. Keep `renderRequest` alongside the other mapping helpers in `hydro-ux.js`; do not duplicate option data or mapping logic in the page.

**Recipes & presets (#28).** `hydro-ux.js` also owns a **recipe** layer — the canonical, serializable subset of `state` capturing exactly the reproducible art-direction selections (preview-only fields excluded): `toRecipe`/`sanitizeRecipe`/`encodeRecipe`/`decodeRecipe`/`applyRecipe` plus a named `PRESETS` catalog (`presetById`/`applyPreset`). `decodeRecipe` sanitizes every field against the same option catalogs the UX uses, so a shared/hand-edited link can never inject invalid state; the round-trip is exact and headlessly tested in `tests/test_recipe_roundtrip.cjs` (run with the system `node` — the module is CommonJS-loadable via `module.exports` in addition to `window.HydroUX`; base64url uses `btoa`/`atob` with a Node `Buffer` fallback). `studio.html` adds a **Presets & sharing** fieldset, a "Copy share link" that writes the recipe into `location.hash`, a `syncControls()` that reflects `state` back onto every DOM control after a preset/recipe apply, and a boot `restoreFromHash()`. This closed Epoch 6. Keep all recipe/preset logic in `hydro-ux.js` — the page only wires UI to it.

## Conventions

- Type hints + docstrings on public functions; `from __future__ import annotations` at the top of modules.
- Immutable/frozen dataclasses for value objects (`Settings`, `Stage`); prefer pure functions operating on injected inputs over stateful classes.
- Runtime data dirs `datasets/`, `cache/`, `output/`, `logs/` are large and git-ignored (regenerable). `.venv/` is the project interpreter.
