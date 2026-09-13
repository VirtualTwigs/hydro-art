# Repository Guidelines

## Project Structure & Module Organization

`src/` contains the Python implementation: the ordered 2D GIS-to-SVG pipeline,
configuration, rendering, and parallel terrain/flow subsystems. Keep production
code independent of heavy GIS imports at module load time. `tests/` mirrors
`src/` (`src/foo.py` → `tests/test_foo.py`); pipeline coverage uses names such
as `test_rendering_pipeline.py`. `tools/` and `notebooks/` are ad-hoc,
real-data entry points and may use the full GIS stack. Self-contained browser
prototypes live in `web/`; shared browser code is in `web/shared/`. Product
documentation is under `docs/`. Runtime data (`cache/`, `datasets/`, `output/`,
and `logs/`) is generated and ignored by Git.

## Build, Test, and Development Commands

Use the project interpreter when available:

```bash
.venv/bin/pip install -r requirements.txt  # install full GIS/dev environment
.venv/bin/python -m pytest -q               # run the offline Python suite
.venv/bin/python -m pytest tests/test_config.py::test_name
.venv/bin/python build.py --region Washington --palette neon
.venv/bin/ruff check src tests               # lint; install ruff if absent
node tests/test_recipe_roundtrip.cjs          # test browser recipe logic

# E2E (Playwright, opt-in — NOT part of the offline suite; needs Node 18+)
cd tests/e2e && npx playwright test           # boots serve.py; GIS needed for proof tests
npx playwright test tests/01-landing.spec.js  # landing/nav only (no GIS)

# Internal demo container (static, no live rendering)
bash deploy/stage-artifacts.sh && docker compose -f deploy/docker-compose.yml up --build -d
```

`build.py` has no compilation step. Real data runs may require the configured
cache/NAS mount; tests must not require it, a network connection, GDAL, or data
downloads.

## Coding Style & Naming Conventions

Target Python 3.12+, use four-space indentation, type hints, and docstrings on
public functions. Ruff enforces an 88-character line limit. Prefer small pure
functions, frozen dataclasses for value objects, and injected collaborators for
I/O. Keep `from __future__ import annotations` at the top of new modules.
Use `snake_case` for modules, functions, variables, and test names; `PascalCase`
for classes. Import `INTERNAL_CRS` from `src/crs.py` rather than repeating
`"EPSG:5070"`.

## Testing Guidelines

Add or update the matching test file with each source change. Tests use pytest
and should inject fakes for downloads, GIS readers, and external executables;
do not add top-level imports of GDAL-backed packages to `src/` or tests. Run the
focused test first, then the full suite before handoff. Keep browser shared code
Node-loadable so the CommonJS recipe test continues to run.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit-style subjects, often with issue
references: `feat(#46): add yearly renderer`, `fix(#32): preserve source CRS`,
or `docs: update guide`. Keep commits focused. Pull requests should summarize
behavioral changes, link relevant issues/specs, list validation commands, and
include output screenshots or SVG/visual examples for rendering or web changes.
