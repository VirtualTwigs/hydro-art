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

## Running in development mode

There is no build step and no separate "dev server". You run the same two entry
points from source, and they pick up code changes on every restart.

| Entry point | What it does |
|---|---|
| `serve.py` | Local web server for `web/` (studio, start, order pages) plus the `/api/*` routes. The "Run pipeline" button runs real renders. |
| `build.py` | One-shot CLI render (`--region`, `--county`, `--palette`, ...). |

### Dev server (live pipeline renders)

Serves the web control surface and exposes `/api/render` + `/api/jobs/<id>` routes. Requires the full GIS stack and pre-extracted datasets.

```bash
.venv/bin/python -X dev serve.py                    # http://127.0.0.1:8765/
.venv/bin/python -X dev serve.py --port 9000        # custom port
.venv/bin/python -X dev serve.py --cache-dir cache  # override archive cache location
.venv/bin/python -X dev serve.py --web-root .       # serve repo root (for e2e harness)
.venv/bin/python -X dev serve.py --external-root /Volumes/home/data/hydro-art  # redirect all storage
```

`-X dev` turns on [Python Development Mode](https://docs.python.org/3/library/devmode.html),
which adds extra runtime checks, `ResourceWarning`s for unclosed files and sockets, and
faulthandler tracebacks on crashes. It never changes rendered output.

### CLI pipeline

```bash
# Basic render
.venv/bin/python build.py --region Washington --palette neon --glow --output svg pdf

# County-scoped render
.venv/bin/python build.py --region Washington --county "Clark County" --output svg

# With config file (config.yaml)
.venv/bin/python build.py

# External storage root
HYDRO_ART_EXTERNAL_ROOT=/Volumes/home/data/hydro-art .venv/bin/python build.py --region Oregon
```

Configuration precedence: `built-in defaults < config.yaml < CLI flags`.

### Static demo container (no live rendering)

Serves the web pages with pre-rendered SVGs. No GDAL needed.

```bash
bash deploy/stage-artifacts.sh                              # stage NAS artifacts locally
docker compose -f deploy/docker-compose.yml up --build -d   # http://localhost:8080/
docker compose -f deploy/docker-compose.yml down            # stop
```

### Things to know when running locally

- **Datasets.** Archives are cached on the NAS (`/Volumes/home/data/incoming`) when it
  is mounted, and in local `cache/` when it isn't. If a dataset has already been
  extracted under `datasets/`, nothing is downloaded. Use `--cache-dir` or
  `--external-root` (or `$HYDRO_ART_EXTERNAL_ROOT`) to redirect storage.
- **Email.** Order confirmation, proof, and delivery emails are only sent when
  `HYDRO_ART_GMAIL_APP_PASSWORD` is set. Otherwise the server logs
  "email: not configured" and keeps running. See [Email setup](#email-setup).
- **Static pages only.** You can open the `web/` pages straight from disk
  (`file://`). You only need `serve.py` for `/api/*` calls.
- **No auto-reload.** Restart `serve.py` after you change Python code. Changes to
  `web/` files only need a browser refresh.

### Email setup

`serve.py` sends order emails through Gmail SMTP (`smtp.gmail.com:465`). They are
sent from the fixed address `FROM_ADDRESS` in `src/email_delivery.py`, which is
currently `neiljrunde@gmail.com`. To make sending work:

1. Sign in to the `FROM_ADDRESS` Gmail account. 2-Step Verification must be on.
2. Generate an app password at <https://myaccount.google.com/apppasswords>. It
   **must** come from the `FROM_ADDRESS` account, because Gmail rejects the login
   otherwise. A normal account password won't work either.
3. Export it in the same shell that starts the server:

   ```bash
   export HYDRO_ART_GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
   .venv/bin/python serve.py
   ```

4. Check that the startup output says `email: configured`. To trigger a proof
   email, move an order with a buyer email to `proof_ready`. The PATCH response
   includes `"email_sent": true` when the send succeeded.

To send from a different account, change `FROM_ADDRESS` in `src/email_delivery.py`
and use an app password from that account.

Known limitations:

- Proof and delivery links in emails are hard-coded to `http://localhost:8765/...`
  (`src/server.py`, `_update_order`). They only work on the machine running
  `serve.py`, so they can't reach customers yet.
- The proof-link signing secret is hard-coded (`b"proof-secret"`) in both
  `serve.py` and `src/server.py`.
- If a send fails, the error is logged but the order update still goes through.
  Check the server console for `Failed to send proof email`.

## Debugging

### Quick: `pdb` / `breakpoint()`

```bash
.venv/bin/python -m pdb build.py --region Oregon --output svg   # stops at line 1; `c` to continue
```

You can also drop `breakpoint()` anywhere in `src/` and run `build.py` or `serve.py`
normally. `build.py` runs the pipeline on the main thread, so this is the easiest path.

### Recommended: IDE debugger (VS Code / PyCharm)

`serve.py` handles each HTTP request on its own thread, and it runs pipeline jobs on a
background `ThreadPoolExecutor` worker (`src/jobs.py`). An IDE debugger handles those
threads cleanly.

**VS Code:** install the Python extension, select `.venv/bin/python` as the
interpreter, and add `.vscode/launch.json`:

```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "serve.py (dev)",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/serve.py",
      "args": ["--cache-dir", "cache"],
      "cwd": "${workspaceFolder}",
      "justMyCode": false,
      "env": { "PYTHONDEVMODE": "1" }
    },
    {
      "name": "build.py Washington",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/build.py",
      "args": ["--region", "Washington", "--palette", "neon", "--glow", "--output", "svg"],
      "cwd": "${workspaceFolder}",
      "env": { "PYTHONDEVMODE": "1" }
    },
    {
      "name": "pytest (current file)",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["-q", "${file}"],
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

**PyCharm:** the repo already has an `.idea/` project. Create a Python run
configuration with script `serve.py` (or `build.py` plus its args), working directory
set to the repo root, and the `.venv` interpreter. Then click **Debug**.

### Attach to a running server (debugpy, any editor)

```bash
.venv/bin/pip install debugpy
.venv/bin/python -X dev -m debugpy --listen 127.0.0.1:5678 --wait-for-client serve.py
```

Then attach from your editor to `127.0.0.1:5678` (in VS Code, use `"request": "attach"`
with `"connect": {"host": "127.0.0.1", "port": 5678}`).

### Where errors hide

- **Pipeline failures in `serve.py` are caught.** `JobRunner._run` (`src/jobs.py`)
  catches every exception and saves only `str(exc)` on the job, so `/api/jobs/<id>`
  shows the message without a traceback. To see the full stack, set a breakpoint in
  that `except` block, or turn on "Raised exceptions" in your debugger. Or reproduce
  the same settings with `build.py`, which lets the exception propagate.
- **HTTP access logging is silenced.** `log_message` in `src/server.py` is a no-op.
  Temporarily have it call `super().log_message(*args)` if you need a request log.
- **Front end.** Use the browser DevTools (Console and Network tabs) on
  `http://127.0.0.1:8765/`. The shared logic lives in `web/shared/hydro-ux.js`.

## Test suites

### Offline test suite (primary -- no GDAL, no network)

The entire offline suite runs without GDAL, network access, or real datasets. This is the primary quality gate and runs in CI on every push/PR.

```bash
.venv/bin/python -m pytest -q                                # full suite
.venv/bin/python -m pytest tests/test_config.py -q           # single file
.venv/bin/python -m pytest tests/test_config.py::test_name   # single test
.venv/bin/python -m pytest -v                                # verbose output
```

`pytest --pdb` (post-mortem on failure) and `pytest --trace` (break at the start of each
test) are the fastest way to debug a failing test.

### Coverage report

Scoped to `src/` via `pyproject.toml`. GDAL/network/subprocess seam bodies are excluded (covered by injected fakes).

```bash
.venv/bin/python tools/coverage_report.py --fail-under 90   # gate (default threshold)
.venv/bin/python tools/coverage_report.py --quiet            # report-only, no fail
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
.venv/bin/python tools/verify_determinism.py --region Oregon   # double-render + hash compare
.venv/bin/python tools/release_gate.py                          # full release gate (goldens + determinism)
.venv/bin/python tools/release_gate.py --offline-only           # fixture-match only (no GDAL)
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
| `HYDRO_ART_GMAIL_APP_PASSWORD` | Gmail app password for `FROM_ADDRESS` (`src/email_delivery.py`). Required for confirmation, proof, and delivery emails. See [Email setup](#email-setup) |
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
deploy/               # Docker + Cloudflare deployment
migrations/           # PostgreSQL schema migrations
notebooks/            # Ad-hoc GIS exploration (Jupyter)
agent-os/             # Specs, retrospectives, roadmap
```

## License

See repository for license details. Data sources (USGS NHDPlus HR, NHD, WBD, 3DEP, nClimGrid) are US federal public domain.
