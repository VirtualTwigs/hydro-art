# hydro-art invariants (the real standards)

This is the authoritative, project-specific standards file for the Hydrographic
Vector Art Generator. It supersedes the generic `backend/`, `frontend/`, and
placeholder `global/` standards for this codebase. When an agent needs the full
picture, read `CLAUDE.md` and `AGENTS.md` at the repo root — this file is the
condensed rule set agents must not violate.

## What this project is

A Python 3.12+ **CLI** that turns public USGS hydrography (NHDPlus HR / NHD /
WBD) into deterministic, layered, neon SVG river art. There is **no web
framework, no database, no ORM, no migrations, no responsive UI, no
authentication**. Ignore any standard that assumes those. `web/` is
self-contained `file://`-safe vanilla JS/HTML with no build step.

## The offline-suite discipline (highest-value invariant — never break)

- The **entire pytest suite runs fully offline**: no GDAL, no network, no real
  datasets.
- `src/` and `tests/` **never import GDAL-backed libs at module top level**
  (`geopandas`, `pyogrio`, `rasterio`, `shapely`). Keep them **lazy-imported
  behind injected seams** (`Downloader`, `LayerLoader`, `RasterReader`, …).
- Every `src/<name>.py` has a matching `tests/test_<name>.py`; pipeline
  integration tests are `tests/test_*_pipeline.py`.
- Tests inject fakes + hand-built shapely/graph/numpy inputs. They must not
  require the NAS, a network connection, or downloads.

## Dependency direction (one way only)

- `src/` never imports `web/` or `tools/`.
- `tools/` and `notebooks/` may import `src/` and eagerly import the GIS stack;
  they read real data and live **outside** the offline suite.
- `web/shared/hydro-ux.js` must stay **Node-loadable** (no top-level
  `document`/`window`), or `tests/test_recipe_roundtrip.cjs` breaks.

## Determinism (contractual, checked every epoch)

- Identical inputs → **byte-identical output**. The golden-hash registry
  (`tests/fixtures/golden/registry.json`) + `tools/verify_determinism.py`
  enforce it.
- The **2D pipeline default output must stay byte-identical** unless a change
  deliberately targets rendered bytes. Adding a new parallel `src/` module,
  a new `tools/` entry point, or a disabled-by-default feature must not perturb
  it.
- Wall-clock leaks are the enemy (PDF `CreationDate`, timestamps). Pin
  `SOURCE_DATE_EPOCH=0` for external rasterizers.

## Architecture rules to preserve

- **No global state.** Immutable `Settings` (frozen) + mutable `RunContext`,
  dependency-injected. Stages communicate only through `ctx.artifacts`.
- **`PIPELINE_STAGES` is fixed and 2D-only.** The DEM/terrain/3D, flow, report,
  and fulfillment subsystems are **parallel** modules **not** wired into it.
  Do not add stages or wire parallel subsystems into the pipeline unless the
  spec explicitly targets that. (Exception already integrated: waterbodies.)
- **Validate at the boundary, fail fast.** `build_settings` (`src/config.py`)
  validates every field against allowlists → `ConfigError`. Add a region /
  projection / palette / source by extending the relevant allowlist there.
- **Config precedence:** `defaults < config.yaml < CLI flags`. Unset argparse
  flags default to `None` so they never clobber YAML.
- **Error taxonomy:** `ConfigError` (exit 1) vs `AcquisitionError` (exit 2).
- **`EPSG:5070` has one source: `src/crs.py:INTERNAL_CRS`.** Import it; never
  re-inline the literal in `src/`.
- **`tools/` shares one art recipe:** extend `tools/render_common.py` (QAMA
  flow-scaled widths, HUC-N coloring, glow, layered rasterization; shared
  `STATE_HUC4`/`CLARK_BBOX_4326`) rather than duplicating render logic.

## Rights gate (commercial data)

- USGS NHDPlus/NHD/WBD are U.S. federal **public domain** — sellable, but record
  source + attribution per asset.
- Climate defaults to **nClimGrid-Monthly** (public domain, sellable with
  attribution). **PRISM is NOT public domain — never mark a
  `--climate-source prism` asset sellable** (A/B comparison only).
  `fulfillment.assert_sellable` enforces this.

## Testing approach (focused TDD)

- Per task group: write **2–8 focused tests first**, then implement, then run
  **ONLY those tests**. A dedicated gap-analysis group may add **≤10** more.
- Do not run the full suite mid-group; run it once at the end for regressions.
- Test behavior, not implementation. Inject fakes for downloads/GIS/external
  executables.

## Coding style

- Python 3.12+, 4-space indent, type hints + docstrings on public functions,
  `from __future__ import annotations` at the top of new modules. Ruff line
  length 88. Prefer small pure functions and frozen dataclasses for value
  objects. `snake_case` modules/functions/vars/tests; `PascalCase` classes.

## Workflow & bookkeeping

- Spec-driven, one roadmap item at a time (`agent-os/product/roadmap.md`). Two
  explicit user commands: **"create tasks and implement item #N"** and, only
  when asked, **"commit item #N"**. Never commit otherwise.
- `HANDOFF.md` tracks implemented-vs-stubbed. Close each epoch with a note in
  `agent-os/retrospectives/`. `tools/update_status.py` automates bookkeeping.
- Keep `CLAUDE.md` and `AGENTS.md` consistent — `AGENTS.md` is the condensed,
  tool-agnostic mirror.
