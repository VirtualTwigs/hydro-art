# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hydrographic Vector Art Generator (`hydro-art`, v1.0.0): a Python 3.12+ CLI (active interpreter: 3.14) that turns public USGS hydrography (NHDPlus HR / NHD / WBD) into layered, neon-colored SVG river art. Regions: all 50 US states (`SUPPORTED_REGIONS` in `src/config.py` — single source of truth); `--county` targets one county. Single-command GIS→SVG pipeline; deterministic (identical inputs → identical output). See `docs/PRD.md` and `agent-os/product/mission.md`.

## Commands

```bash
.venv/bin/python -m pytest -q                     # full offline test suite
.venv/bin/python -m pytest tests/test_config.py::test_name  # one test
.venv/bin/python build.py --region Washington --palette neon --glow --output svg pdf
.venv/bin/ruff check src tests                     # lint (ruff often absent from .venv; pip install it)
node tests/test_recipe_roundtrip.cjs               # web/ recipe roundtrip (system node, no deps)
python tools/verify_determinism.py --region Oregon # non-offline: double-render + golden-hash check
python tools/coverage_report.py --fail-under 90    # offline coverage gate (scoped to src/, non-suite)
python tools/release_gate.py                        # v1.0 release readiness (goldens + determinism)
python tools/update_status.py                       # stamp HANDOFF.md + roadmap on epoch close
python tools/detect_unfinished.py                   # report-only: open tasks, missing retros, dirty tree

# E2E (Playwright, opt-in — NOT part of the offline suite; needs Node 18+)
cd tests/e2e && npm install && npx playwright install chromium
npx playwright test                                  # boots serve.py, runs full suite (GIS needed for proofs)
npx playwright test tests/01-landing.spec.js         # landing/nav only (no GIS needed)

# Internal demo container (static — no live rendering)
bash deploy/stage-artifacts.sh                       # stage NAS artifacts locally
docker compose -f deploy/docker-compose.yml up --build -d   # http://localhost:8080/
```

No build step (it's a script). `ruff` is the linter (`line-length = 88`). `web/` pages have no build step; the only JS test is the CommonJS `node` roundtrip. **CI** is two GitHub Actions workflows (`.github/workflows/`): `ci.yml` (offline suite + coverage gate + recipe roundtrip) and `reproducibility.yml` (determinism/release gate). Coverage is scoped to `src/` via `[tool.coverage.*]` in `pyproject.toml`; GDAL/network/subprocess seam bodies are covered by injected fakes, not real I/O.

**Dependencies split on purpose.** `pyproject.toml` = always-imported core (`pyyaml`, `rich`); the heavy GIS stack (`shapely`, `geopandas`, `pyogrio`, `numpy`, `networkx`) lives in `requirements.txt` because it's lazy-imported behind seams. Install all: `.venv/bin/pip install -r requirements.txt`. The minimal `pyproject.toml` set keeps the suite importable without GDAL.

**Real runs stage archives on a NAS.** `build.py` caches GDB zips at `NAS_CACHE_DIR = "/Volumes/home/data/incoming"`. But download is **skipped entirely when a dataset is already extracted**: `ensure_cached` (`src/cache.py`) short-circuits any descriptor whose `datasets/<id>/<huc4>` dir exists+non-empty — so a build runs with zero downloads (no NAS, no network) off pre-extracted GDBs. `serve.py` and `build.py` both fall back to local `cache/` when the NAS isn't mounted (`--cache-dir` wins). All three storage roots (cache/datasets/output) can be redirected to an external drive via `src/storage.py` (`--external-root` / `$HYDRO_ART_EXTERNAL_ROOT`); storage is infrastructure resolved before the pipeline builds — not in `Settings`, never changes rendered bytes.

## Development workflow (Agent OS, spec-driven)

One roadmap item at a time (`agent-os/product/roadmap.md`), Builder Methods Agent OS. Two explicit user commands:

1. **"create tasks and implement item #N"** — write specs under `agent-os/specs/YYYY-MM-DD-<name>/` (`planning/requirements.md`, `spec.md`, `tasks.md`), TDD in task groups (2–8 tests first per group, run ONLY those), tick checkboxes, write `implementation/report.md`, run full suite for regressions, smoke-test, report and STOP.
2. **"commit item #N"** — committing is separate and explicit. Never commit otherwise.

`HANDOFF.md` tracks progress (fastest read for what's implemented vs. stubbed); `agent-os/retrospectives/` holds per-epoch closeouts; `tools/update_status.py` automates the bookkeeping. A **SessionStart hook** runs `tools/detect_unfinished.py` (report-only) to surface loose ends a prior session left — open `- [ ]` spec tasks, "commit pending" HANDOFF bullets, closed epochs missing a retrospective, uncommitted tracked changes. Root `AGENTS.md` is a condensed, tool-agnostic mirror of this file — keep them consistent.

## Architecture

Fixed, ordered stages in `src/pipeline.py` (`PIPELINE_STAGES`, PRD §8):

```
download → extract → validate → repair_geometries → reproject →
clip_to_region → build_graph → compute_watersheds → assign_colors →
generate_svg → optimize_svg → export
```

Each stage is `Stage(name, run)` where `run(ctx: RunContext) -> None`. All 12 implemented; the stub mechanism (`_STAGE_FUNCS.get(name, _stub(name))`) remains so a new stage is wired by adding its function.

**This 12-stage pipeline is 2D-only.** The elevation/DEM/terrain/3D, flow, report, and fulfillment subsystems are **parallel** pure/offline modules **not** wired into `PIPELINE_STAGES` and not run by `build.py` — a second data model sharing CRS conventions with its own `tools/` entry points. Exceptions that *do* integrate: waterbodies (Epoch 1.5), natural water features (Epoch 15), and hydro structures (Epoch 16) — `validate` additively loads the `NHDWaterbody` polygon layer when `settings.waterbodies.enabled` **or** `settings.areal_features.enabled` **or** `settings.hydro_structures.enabled`, the `NHDPoint` layer when `settings.point_features.enabled` **or** `settings.hydro_structures.enabled`, and the `NHDLine` layer when `settings.hydro_structures.enabled`; `generate_svg` selects all of these (outline layers, areal fills, point glyphs, engineered structures). All additive loads are gated on both the setting AND loader support, so river-only/disabled builds stay byte-identical.

Key structural rules (preserve):

- **No global state.** Immutable `Settings` + mutable `RunContext`, dependency-injected. Stages communicate only through `ctx.artifacts` (a dict): each reads prior stages' artifacts and writes its own.
- **Injectable seams for I/O.** Network/GIS/external-tool access goes through injected collaborators (`Downloader`/`UrllibFetcher`, `LayerLoader`/`PyogrioLayerLoader`, `SvgOptimizer`, `Exporter`, …). Tests inject fakes + hand-built shapely/graph inputs. External CLI tools (`svgo`, `rsvg-convert`) are optional and degrade gracefully.
- **Validate at the boundary, fail fast.** `build_settings` (`src/config.py`) validates every field against allowlists → `ConfigError`. Add a region/projection/palette by extending the relevant allowlist there.
- **Config precedence:** `defaults < config.yaml < CLI flags` (`src/cli.py`). Unset argparse flags default to `None` so they never clobber YAML.
- **Error taxonomy:** `ConfigError` (exit 1) vs `AcquisitionError` (exit 2), mapped in `build.py`.

### The offline-suite discipline (do not break)

**The entire test suite runs fully offline — no GDAL, no network, no real datasets.** Preserve when adding code:

- `src/` and `tests/` never import GDAL-backed I/O libs (`geopandas`/`pyogrio`/`rasterio`) at module top-level — keep them lazy-imported behind seams (`rasterio` is optional, never imported at `src/` load). `shapely` (GEOS-backed geometry, no GDAL) *is* allowed at top-level and appears there in the geometry/selection/QA modules (`clipping`, `waterbody_selection`, `areal_selection`, `hydro_structure_selection`, `hydro_structure_qa`); the classification modules stay import-free so they run without even shapely.
- `src/` never imports `web/` or `tools/`; the dependency runs one way, `tools/ → src/`. `tools/` and `notebooks/` import GIS eagerly and read real data, so they live outside the suite.
- Every `src/<name>.py` has a matching `tests/test_<name>.py`; pipeline-integration tests are `tests/test_*_pipeline.py`. Run only relevant tests per task group; full suite at the end.

### Subsystem boundaries (`src/`)

Three categories of modules live in `src/` — know which you're touching:

1. **Pipeline-integrated** (wired into `PIPELINE_STAGES`, run by `build.py`): the core 2D modules (config → cli → datasets → download/cache → loading → geometry → crs → projection → clipping → counties → graph → ordering → watersheds → coloring → rendering → optimize → export), plus the three additive feature layers — waterbodies (`waterbodies`/`waterbody_selection`), natural water features (`point_features`/`areal_features`/`areal_selection`), and hydro structures (`hydro_structures`/`hydro_structure_selection`/`hydro_structure_qa`). All additive layers are disabled by default → byte-identical default build.

2. **Parallel subsystems** (pure/deterministic/offline, **not** in `PIPELINE_STAGES`; real renders via `tools/`): elevation/DEM/terrain/3D, flow disaggregation (`monthly_flow`/`historical_flow`/`climate_grid`), watershed report (`flow_metrics`), order fulfillment, production endpoints/gallery/release, determinism/bookkeeping, offline packaging, web backend (`jobs`/`server`), external storage.

3. **Classification modules** (FType/FCode policy tables only — no geometry, no GIS imports, run without even shapely): `waterbodies`, `point_features`, `areal_features`, `hydro_structures`. Each feature taxonomy is **complementary and disjoint** — every NHD polygon/point is classified by exactly one taxonomy.

Key integration rules:
- `crs.py:INTERNAL_CRS` (`"EPSG:5070"`) is the single source — import it, never inline the literal.
- Preset directives (`waterbody_preset`, `width_preset`, etc.) expand to their `*Settings` dataclass at config time (`defaults < preset < explicit`), not stored on frozen settings — no-preset builds stay byte-identical.
- `historical_flow` is **clock-free** — `latest` year is passed in, never `datetime.now`.
- `raster.py` normalizes DEMs **mosaic-before-warp** — don't "simplify" to warp-then-mosaic (see gotchas).

### Ad-hoc tools (`tools/`)

Standalone scripts (`python tools/<name>.py`), outside the pipeline and suite — import GIS eagerly, read real data. May import `src/`, never the reverse.

- **Extend `render_common.py`** (shared "art-quality" recipe: QAMA flow-scaled widths, HUC-N coloring, glow, layered rasterization; shared constants `STATE_HUC4`/`CLARK_BBOX_4326`) rather than duplicating render logic across render scripts.
- `derive_state_huc4.py` is the tool for adding a new state: intersect Census polygon × WBD HU4 → wire into the allowlists.
- Year-over-year renders use `--climate-source {nclimgrid,prism}` (default **nclimgrid**); **never sell a PRISM render** — A/B testing only.

### Web layer (`web/`)

Self-contained HTML/JS (no build step, `file://`-safe). `studio.html` is the canonical expert control surface; `start.html` is the alpha customer landing.

- **Shared foundation:** `web/shared/hydro-ux.js` (`window.HydroUX`) mirrors the Python config side — option data, CLI/YAML mapping, recipe/preset encode/decode. Keep all shared logic here; don't duplicate across pages. **Must stay Node-loadable** (no top-level `document`/`window`) — `tests/test_recipe_roundtrip.cjs` enforces this.
- Archived prototypes live under `archive/web/`, not `web/`.

## Conventions

- Type hints + docstrings on public functions; `from __future__ import annotations` at top of modules.
- Frozen dataclasses for value objects; prefer pure functions over stateful classes.
- Runtime dirs `datasets/`/`cache/`/`output/`/`logs/` are git-ignored (regenerable). `.venv/` is the interpreter.
- `notebooks/` — ad-hoc GIS exploration; imports GIS eagerly, outside the suite. Committed notebooks are tracked; `.ipynb_checkpoints/` + scratch `Untitled.ipynb` are git-ignored.
- **Commit style:** Conventional Commit subjects with optional issue refs — `feat(#46): add yearly renderer`, `fix(#32): preserve source CRS`, `docs: update guide`. Keep commits focused.

## Known debt / gotchas

- **`ruff` may not be in `.venv`** — declared as an optional dev dep (`pip install -e '.[dev]'`) but not in `requirements.txt`; `pip install ruff` if missing.
- **DEM/terrain/3D is not wired into `PIPELINE_STAGES`.** `color_by=elevation` and non-annual `--months` ship as real `build.py` flags but **fail fast** in the 2D pipeline; real renders come from `tools/render_state_mono.py` / `tools/render_monthly.py`.
- **`src/raster.py` mosaic-before-warp** — each 1° 3DEP tile warped independently drifts resolution with latitude; `_require_aligned` uses a *relative* pixel-size tolerance. Don't "simplify" to warp-then-mosaic.
- **Rights gate (commercial data).** USGS NHDPlus/NHD/WBD are federal public domain — free to sell, but record source + attribution per asset. Climate defaults to **nClimGrid-Monthly** (public domain, sellable with attribution); **PRISM is not public domain — never ship a `--climate-source prism` asset commercially** (A/B only). `fulfillment.assert_sellable` enforces this.
