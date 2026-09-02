# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hydrographic Vector Art Generator: a Python 3.12+ CLI that turns public USGS hydrography (NHDPlus HR / NHD / WBD) into layered, neon-colored SVG river art. Regions: Oregon, Washington, California, Idaho (`SUPPORTED_REGIONS` in `src/config.py` — single source of truth); `--county` targets one county. Single-command GIS→SVG pipeline; deterministic (identical inputs → identical output). See `docs/PRD.md` and `agent-os/product/mission.md`.

## Commands

```bash
.venv/bin/python -m pytest -q                     # full offline test suite
.venv/bin/python -m pytest tests/test_config.py::test_name  # one test
.venv/bin/python build.py --region Washington --palette neon --glow --output svg pdf
.venv/bin/ruff check src tests                     # lint (ruff often absent from .venv; pip install it)
node tests/test_recipe_roundtrip.cjs               # web/ recipe roundtrip (system node, no deps)
python tools/verify_determinism.py --region Oregon # non-offline: double-render + golden-hash check
```

No build step (it's a script). `ruff` is the linter (`line-length = 88`). `web/` pages have no build step; the only JS test is the CommonJS `node` roundtrip.

**Dependencies split on purpose.** `pyproject.toml` = always-imported core (`pyyaml`, `rich`); the heavy GIS stack (`shapely`, `geopandas`, `pyogrio`, `numpy`, `networkx`) lives in `requirements.txt` because it's lazy-imported behind seams. Install all: `.venv/bin/pip install -r requirements.txt`. The minimal `pyproject.toml` set keeps the suite importable without GDAL.

**Real runs stage archives on a NAS.** `build.py` caches GDB zips at `NAS_CACHE_DIR = "/Volumes/home/data/incoming"`. But download is **skipped entirely when a dataset is already extracted**: `ensure_cached` (`src/cache.py`) short-circuits any descriptor whose `datasets/<id>/<huc4>` dir exists+non-empty — so a build runs with zero downloads (no NAS, no network) off pre-extracted GDBs. `serve.py` and `build.py` both fall back to local `cache/` when the NAS isn't mounted (`--cache-dir` wins). All three storage roots (cache/datasets/output) can be redirected to an external drive via `src/storage.py` (`--external-root` / `$HYDRO_ART_EXTERNAL_ROOT`); storage is infrastructure resolved before the pipeline builds — not in `Settings`, never changes rendered bytes.

## Development workflow (Agent OS, spec-driven)

One roadmap item at a time (`agent-os/product/roadmap.md`), Builder Methods Agent OS. Two explicit user commands:

1. **"create tasks and implement item #N"** — write specs under `agent-os/specs/YYYY-MM-DD-<name>/` (`planning/requirements.md`, `spec.md`, `tasks.md`), TDD in task groups (2–8 tests first per group, run ONLY those), tick checkboxes, write `implementation/report.md`, run full suite for regressions, smoke-test, report and STOP.
2. **"commit item #N"** — committing is separate and explicit. Never commit otherwise.

`HANDOFF.md` tracks progress (fastest read for what's implemented vs. stubbed); `agent-os/retrospectives/` holds per-epoch closeouts; `tools/update_status.py` automates the bookkeeping. Root `AGENTS.md` is a condensed, tool-agnostic mirror of this file — keep them consistent.

## Architecture

Fixed, ordered stages in `src/pipeline.py` (`PIPELINE_STAGES`, PRD §8):

```
download → extract → validate → repair_geometries → reproject →
clip_to_region → build_graph → compute_watersheds → assign_colors →
generate_svg → optimize_svg → export
```

Each stage is `Stage(name, run)` where `run(ctx: RunContext) -> None`. All 12 implemented; the stub mechanism (`_STAGE_FUNCS.get(name, _stub(name))`) remains so a new stage is wired by adding its function.

**This 12-stage pipeline is 2D-only.** The elevation/DEM/terrain/3D, flow, report, and fulfillment subsystems are **parallel** pure/offline modules **not** wired into `PIPELINE_STAGES` and not run by `build.py` — a second data model sharing CRS conventions with its own `tools/` entry points. Exception: waterbodies (Epoch 1.5) *do* integrate — `validate` additively loads waterbody layers when `settings.waterbodies.enabled`, and `generate_svg` selects them into outline layers.

Key structural rules (preserve):

- **No global state.** Immutable `Settings` + mutable `RunContext`, dependency-injected. Stages communicate only through `ctx.artifacts` (a dict): each reads prior stages' artifacts and writes its own.
- **Injectable seams for I/O.** Network/GIS/external-tool access goes through injected collaborators (`Downloader`/`UrllibFetcher`, `LayerLoader`/`PyogrioLayerLoader`, `SvgOptimizer`, `Exporter`, …). Tests inject fakes + hand-built shapely/graph inputs. External CLI tools (`svgo`, `rsvg-convert`) are optional and degrade gracefully.
- **Validate at the boundary, fail fast.** `build_settings` (`src/config.py`) validates every field against allowlists → `ConfigError`. Add a region/projection/palette by extending the relevant allowlist there.
- **Config precedence:** `defaults < config.yaml < CLI flags` (`src/cli.py`). Unset argparse flags default to `None` so they never clobber YAML.
- **Error taxonomy:** `ConfigError` (exit 1) vs `AcquisitionError` (exit 2), mapped in `build.py`.

### The offline-suite discipline (do not break)

**The entire test suite runs fully offline — no GDAL, no network, no real datasets.** Preserve when adding code:

- `src/` and `tests/` never import GDAL-backed libs (`geopandas`/`pyogrio`/`rasterio`/`shapely`) at module top-level — keep them lazy-imported behind seams (`rasterio` is optional, never imported at `src/` load).
- `src/` never imports `web/` or `tools/`; the dependency runs one way, `tools/ → src/`. `tools/` and `notebooks/` import GIS eagerly and read real data, so they live outside the suite.
- Every `src/<name>.py` has a matching `tests/test_<name>.py`; pipeline-integration tests are `tests/test_*_pipeline.py`. Run only relevant tests per task group; full suite at the end.

### Module map (`src/`)

**2D pipeline (Epoch 1):** `config` (settings + validation) · `cli` (args + precedence) · `datasets` (resolve USGS files, `REGION_HUC4`) · `download`/`cache` (fetch + file cache + extraction) · `loading` (pyogrio layer load) · `geometry` (invalid-geometry repair) · `crs` (`INTERNAL_CRS = "EPSG:5070"`, single source — import it, never inline the literal) · `projection` (→ EPSG:5070) · `clipping` · `counties` (`--county` scope via injectable Census provider) · `graph` (directed NetworkX network) · `ordering` (Strahler/Shreve/Hack — invoked *inside* `compute_watersheds`, no stage of its own) · `watersheds` (HUC grouping) · `coloring` (deterministic palette) · `rendering` (layered SVG, optional glow, `flow_widths`) · `optimize` (optional SVGO) · `export` (SVG + optional PNG/PDF + SHA-256).

**Waterbodies (Epoch 1.5, *integrated* into pipeline):** `waterbodies` (NHD polygon classification) · `waterbody_selection` (repair/reproject/clip + area/detail selection → outlines). Art-direction presets in `config.WATERBODY_PRESETS` (`screen`/`print-state`/`print-county`); a `preset` directive expands to `WaterbodySettings` at config time (`defaults < preset < explicit`), not stored on frozen settings, so no-preset builds stay byte-identical.

The rest are **parallel subsystems** — all pure/deterministic/offline, **not in `PIPELINE_STAGES`**; heavy reads live in matching `tools/`:

- **Elevation/DEM/terrain/3D (Epochs 2–5):** vertical exaggeration is display-only, never overwrites source Z. `elevation` (provenance + `TileDiscoverer`/`RasterReader`/`ElevationSampler` seams) · `dem` (3DEP COG discovery/cache on S3; `count_tiles`/`acquire_dem_for_settings`/`region_bounds`) · `raster` (`RasterGrid` mosaic/clip/pyramid + `normalize_dem` — **mosaic-before-warp**, see gotchas) · `terrain` · `hydro_z` (attach ground Z, keeps 2D path, inversion QA) · `mesh` (TIN) · `scene` (`SceneModel`) · `camera` (keyframe interpolation) · `delivery` (JSON experience doc for `web/experience.html`) · `export3d` (GLB/OBJ/MTL) · `preview` (heightfield tiles for `web/3d.html`) · `accuracy` (DEM-vs-truth metrics) · `hillshade` (Lambertian relief) · `compositing` (art over relief; nodata→transparent) · `raster_io` (rasterio-backed reader/reprojector `normalize_dem` needs; optional lazy dep).
- **Flow disaggregation (Epochs 10–11, 14):** numpy-only. `monthly_flow` (`disaggregate_monthly` — snow-aware water → monthly volume → downstream HydroSeq accumulation, conserving annual mean) · `historical_flow` (per-calendar-year; `YearlyClimate` + injectable `ClimateProvider` seam; **clock-free** — `latest` is passed in, never `datetime.now`) · `climate_grid` (source-agnostic sampling helpers: `band_for_month`/`cells_from_lonlat`/`fill_nodata`).
- **Watershed report (Epoch 12):** `flow_metrics` — numpy-only stats over the `{year:[n,12]}` series (hydrograph shape, Mann-Kendall trend, `outlet_index`, model-vs-observed validation, ENSO/PDO teleconnection). `nan` skipped never zero-filled; never touches network. Feeds `web/report.html`.
- **Order fulfillment (Epoch 11.5, Revenue Validation):** `fulfillment` — stdlib-only order → deterministic deliverable plan + provenance manifest; `assert_sellable` is the **Rights gate** (see gotchas); manifest is byte-identical for equal inputs so a re-order regenerates identically.
- **Determinism & bookkeeping (Epoch 9):** `determinism` (golden-hash registry `tests/fixtures/golden/registry.json` + verdict; double-render is `tools/verify_determinism.py`) · `status` (idempotent `HANDOFF.md`/roadmap string transforms; CLI is `tools/update_status.py`).
- **Offline packaging (Epoch 5):** `manifest` (portable cache manifest, sha256+size) · `packaging` (`plan_package` "is this cache ready to ship?" verdict).
- **Web control-surface backend (Epoch 6):** `jobs` (`settings_from_payload` + `JobRunner`, validate-at-submit → run injected pipeline off-thread) · `server` (stdlib `http.server` dispatcher + static `web/` with path-traversal guard). Both stdlib-only/GDAL-free; the real `Pipeline` is injected. `serve.py` wires them on localhost.
- **External storage (Epoch 7, infra, not in `Settings`):** `storage` — `resolve_storage` maps one external root into `<root>/{cache,datasets,output}`, mount-aware (never `mkdir`s an unmounted `/Volumes`, falls back to local); `plan_migration`/`apply_migration` move a local tree onto the drive leaving a symlink. Never affects rendered bytes.

### Ad-hoc tools (`tools/`)

Standalone scripts (`python tools/<name>.py`), outside the pipeline and suite — import GIS eagerly, read real data. May import `src/`, never the reverse. **Extend `render_common.py`** (the shared "art-quality" recipe: QAMA flow-scaled widths, HUC-N coloring, glow, layered rasterization; shared constants `STATE_HUC4`/`CLARK_BBOX_4326`) rather than duplicating render logic.

- *2D clip/rasterize:* `render_region_clip` (political-boundary clip + `--min-order`), `render_county_clip`, `render_state_svg`, `render_state_mono` (hypsometric elevation tint), `rasterize_layered` (split SVG per watershed layer past the ~1M-node resvg cap, composite over black), `render_terrain_print` (art over DEM relief; auto-acquires 3DEP when no `--dem`), `overlay_facilities`.
- *Monthly flow / "year in motion":* `monthly_flow` (data-prep), `render_monthly` (12-frame GIF; log flow→width mapping fixed once so seasonality shows), `render_infographic`/`render_infographic_year`, `render_state_mono_peak` (elevation color + peak-month width).
- *True year-over-year (Epoch 11/14):* real per-year climate, not synthetic normals. `render_state_yoy` drives the offline `yearly_flow_series` with a provider chosen by `--climate-source {nclimgrid,prism}` (default **nclimgrid**). `nclimgrid_fetch`/`nclimgrid_flow` (public-domain default; stacked NetCDF by band), `prism_fetch`/`historical_flow` (`PrismClimateProvider`, A/B only — **never sell a PRISM render**).
- *Watershed report (Epoch 12):* `render_watershed_yoy` (single HUC12-group), `report_common` (shared report recipe + caches), `build_watershed_report` (CLI → figures in `notebooks/figures/`), `nwis_gauge` (observed USGS discharge, NAS-snapshotted), `climate_index` (ENSO/PDO, NAS-snapshotted).
- *Determinism/status (Epoch 9):* `verify_determinism` (double-render + golden), `update_status` (epoch-close bookkeeping).
- *Stylized 3D:* `render_county_3d`/`render_state_3d` (height from Strahler order — stylized, NOT surveyed DEM), `waterbody_qa`.
- *Packaging/infra:* `package_cache`, `cache_manifest`, `acquire_dem` (real 3DEP fetch), `migrate_storage`, `derive_state_huc4` (add a state: intersect Census polygon × WBD HU4 → wire into the allowlists).
- *Order fulfillment (Epoch 11.5):* `fulfill_order` (order → dispatch on style renderer → stamp title block → export sizes + manifest under `output/orders/<id>/`).

### Web prototypes (`web/`)

Self-contained HTML/JS (no build step, `file://`-safe). `studio.html` is the **canonical control surface** (roadmap #26) — when *served* by `serve.py` its "Run pipeline" button POSTs `HydroUX.renderRequest(state)` (structured JSON of real `src/config` keys) to the localhost runner; over `file://` it stays mapping-only. `proto-b-guided.html`/`proto-c-canvas.html` are alternate UX explorations; `index.html` (early concept); `3d.html` (WebGL terrain lab over `src/preview.py` tiles); `experience.html` (hillshade + camera-track viewer over `src/delivery.py`); `report.html` (watershed-report viewer over `src/flow_metrics`).

**Shared foundation** — `web/shared/ux.css` + `web/shared/hydro-ux.js` (`window.HydroUX`, classic `<script src>`). `hydro-ux.js` mirrors the Python side: option data, procedural preview generator, seasonal flow simulation, `cliMapping`/`yamlMapping` (→ `build.py` command + `config.yaml`), `renderRequest`, DOM view helpers, and the **recipe/preset** layer (`toRecipe`/`encodeRecipe`/`decodeRecipe`/`PRESETS`, round-trip tested in `tests/test_recipe_roundtrip.cjs`). Keep option data, preview, mapping, and recipe logic here — don't duplicate across pages. Mapping emits `color_by`/`width_by`/`--county`/`--months` as real flags; `color_by=elevation` and non-annual `--months` fail fast in the 2D pipeline (honest caveat in the output contract — keep it).

## Conventions

- Type hints + docstrings on public functions; `from __future__ import annotations` at top of modules.
- Frozen dataclasses for value objects; prefer pure functions over stateful classes.
- Runtime dirs `datasets/`/`cache/`/`output/`/`logs/` are git-ignored (regenerable). `.venv/` is the interpreter.
- `notebooks/` — ad-hoc GIS exploration; imports GIS eagerly, outside the suite. Committed notebooks are tracked; `.ipynb_checkpoints/` + scratch `Untitled.ipynb` are git-ignored.

## Known debt / gotchas

- **`ruff` may not be in `.venv`** — configured linter but undeclared/unpinned; `pip install ruff` first.
- **`EPSG:5070` single source: `src/crs.py:INTERNAL_CRS`** — import it, never re-inline the literal in `src/`.
- **DEM/terrain/3D is not wired into `PIPELINE_STAGES`.** `color_by=elevation` and non-annual `--months` ship as real `build.py` flags but **fail fast** in the 2D pipeline; real renders come from `tools/render_state_mono.py` / `tools/render_monthly.py`.
- **`src/raster.py` normalizes DEMs mosaic-before-warp** — each 1° 3DEP tile warped independently drifts resolution with latitude; `_require_aligned` uses a *relative* pixel-size tolerance. Don't "simplify" to warp-then-mosaic.
- **Rights gate (commercial data).** USGS NHDPlus/NHD/WBD are federal public domain — free to sell, but record source + attribution per asset. Climate defaults to **nClimGrid-Monthly** (public domain, sellable with attribution); **PRISM is not public domain — never ship a `--climate-source prism` asset commercially** (A/B only). `fulfillment.assert_sellable` enforces this.
- **`web/shared/hydro-ux.js` must stay Node-loadable** — no top-level `document`/`window` (only inside function bodies), or `tests/test_recipe_roundtrip.cjs` breaks.
