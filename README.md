# hydro-art

Hydrographic Vector Art Generator -- a Python 3.12+ CLI that turns public USGS hydrography data (NHDPlus HR / NHD / WBD) into layered, neon-colored SVG river art.

All 50 US states are supported. The pipeline is deterministic: identical inputs produce byte-identical output.

## Prerequisites

- **Python 3.12+** (active interpreter: 3.14)
- **Node 18+** (only for the web recipe roundtrip test and Playwright e2e)
- **GDAL** (only for real pipeline renders; the test suite runs fully offline without it)
- Optional external tools: `svgo` (SVG optimizer), `rsvg-convert` (PNG/PDF rasterization)

## Installation

```bash
# Clone
git clone https://github.com/VirtualTwigs/hydro-art.git
cd hydro-art

# Create virtualenv and install
python3 -m venv .venv

# Core deps (enough for the offline test suite)
.venv/bin/pip install -e .

# Full GIS stack (needed for real renders)
.venv/bin/pip install -r requirements.txt

# Dev tools (pytest, ruff)
.venv/bin/pip install -e '.[dev]'
```

**Dependency split:** `pyproject.toml` declares the always-imported core (`pyyaml`, `rich`). The heavy GIS stack (`shapely`, `geopandas`, `pyogrio`, `numpy`, `networkx`, `rasterio`) lives in `requirements.txt` and is lazy-imported behind seams, keeping the test suite importable without GDAL.

## Starting services

### Dev server (live pipeline renders)

Serves the web control surface and exposes `/api/render` + `/api/jobs/<id>` routes. Requires the full GIS stack and pre-extracted datasets.

```bash
python serve.py                      # http://127.0.0.1:8765
python serve.py --port 9000          # custom port
python serve.py --web-root .         # serve repo root (for e2e harness)
python serve.py --cache-dir /path    # override archive cache location
python serve.py --external-root /Volumes/home/data/hydro-art  # redirect all storage
```

Open `http://127.0.0.1:8765` and use `web/studio.html`'s "Run pipeline" button.

The server falls back to a local `cache/` directory when the NAS share (`/Volumes/home/data/incoming`) is not mounted.

### Static demo container (no live rendering)

Serves the web pages with pre-rendered SVGs. No GDAL needed.

```bash
# Stage artifacts from NAS to the local deploy/output/ dir
bash deploy/stage-artifacts.sh

# Build and run
docker compose -f deploy/docker-compose.yml up --build -d

# Visit http://localhost:8080/
```

Stop with:
```bash
docker compose -f deploy/docker-compose.yml down
```

## Running the pipeline (CLI)

```bash
# Basic render
python build.py --region Washington --palette neon --glow --output svg pdf

# County-scoped render
python build.py --region Washington --county "Clark County" --output svg

# With config file (config.yaml)
python build.py

# External storage root
HYDRO_ART_EXTERNAL_ROOT=/Volumes/home/data/hydro-art python build.py --region Oregon
```

Configuration precedence: `built-in defaults < config.yaml < CLI flags`.

## Test suites

### Offline test suite (primary -- no GDAL, no network)

The entire offline suite runs without GDAL, network access, or real datasets. This is the primary quality gate and runs in CI on every push/PR.

```bash
# Full suite
.venv/bin/python -m pytest -q

# Single test file
.venv/bin/python -m pytest tests/test_config.py -q

# Single test
.venv/bin/python -m pytest tests/test_config.py::test_name

# With verbose output
.venv/bin/python -m pytest -v
```

### Coverage report

Scoped to `src/` via `pyproject.toml`. GDAL/network/subprocess seam bodies are excluded (covered by injected fakes).

```bash
python tools/coverage_report.py --fail-under 90   # gate (default threshold)
python tools/coverage_report.py --quiet            # report-only, no fail
```

### Linting

```bash
.venv/bin/ruff check src tests                     # lint check
.venv/bin/ruff check src tests --fix               # auto-fix
```

If `ruff` is not in `.venv`, install it: `.venv/bin/pip install ruff`.

### Web recipe roundtrip (Node)

Validates that `web/shared/hydro-ux.js` stays Node-loadable and recipe encode/decode round-trips correctly. No npm dependencies needed.

```bash
node tests/test_recipe_roundtrip.cjs
```

### Determinism / release gate (requires GDAL + real data)

Double-renders a region through the real pipeline and proves byte-identical output + golden-hash match. Requires the full GIS stack and pre-extracted datasets.

```bash
python tools/verify_determinism.py --region Oregon   # double-render + hash compare
python tools/release_gate.py                          # full release gate (goldens + determinism)
python tools/release_gate.py --offline-only           # fixture-match only (no GDAL)
```

### End-to-end (Playwright -- opt-in)

Browser-based e2e tests. Not part of the offline suite.

```bash
cd tests/e2e
npm install
npx playwright install chromium

# Full suite (boots serve.py, needs GIS for proof tests)
npx playwright test

# Landing/nav only (no GIS needed)
npx playwright test tests/01-landing.spec.js
```

### CI workflows

Two GitHub Actions workflows run automatically:

| Workflow | File | Trigger | What it checks |
|----------|------|---------|----------------|
| Offline test pyramid | `.github/workflows/ci.yml` | push/PR to `main` | pytest suite, recipe roundtrip, coverage, release gate (offline), changelog |
| Reproducibility gate | `.github/workflows/reproducibility.yml` | manual / weekly (Mon 06:00 UTC) | Real-data double-render determinism on a self-hosted GDAL runner |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `HYDRO_ART_EXTERNAL_ROOT` | Redirect cache/datasets/output to an external drive |
| `DATABASE_URL` | PostgreSQL connection string for the operations ledger (optional; falls back to JSON) |
| `HYDRO_ART_GMAIL_APP_PASSWORD` | Gmail app password for email delivery (optional) |
| `SOURCE_DATE_EPOCH` | Set to `0` for deterministic timestamps in rasterized output |
| `HYDRO_ART_REAL_DATA` | Set to `1` to enable `@pytest.mark.real_data` tests |

## Project structure

```
build.py              # CLI entry point (GIS-to-SVG pipeline)
serve.py              # Dev server (web control surface + API)
config.yaml           # Default pipeline configuration
src/                  # Core library (offline-safe, no top-level GDAL imports)
tests/                # Offline test suite (pytest)
  e2e/                # Playwright browser tests (opt-in)
tools/                # Ad-hoc operator scripts (import GIS eagerly)
web/                  # Self-contained HTML/JS control surface (no build step)
deploy/               # Docker demo container
migrations/           # PostgreSQL schema migrations
notebooks/            # Ad-hoc GIS exploration (Jupyter)
agent-os/             # Specs, retrospectives, roadmap
```

## License

See repository for license details. Data sources (USGS NHDPlus HR, NHD, WBD, 3DEP, nClimGrid) are US federal public domain.
