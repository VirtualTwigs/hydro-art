# hydro-art

Hydrographic Vector Art Generator: turns public USGS hydrography (NHDPlus HR / NHD /
WBD) into layered, neon-colored SVG river art. See `docs/PRD.md` for the product
spec and `CLAUDE.md` / `AGENTS.md` for architecture and contributor rules.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'          # core deps + ruff
.venv/bin/pip install -r requirements.txt  # GIS stack (shapely, geopandas, pyogrio, …)
```

## Running in development mode

There is no build step and no separate "dev server". You run the same two entry
points from source, and they pick up code changes on every restart.

| Entry point | What it does |
|---|---|
| `serve.py` | Local web server for `web/` (studio, start, order pages) plus the `/api/*` routes. The "Run pipeline" button runs real renders. |
| `build.py` | One-shot CLI render (`--region`, `--county`, `--palette`, …). |

```bash
.venv/bin/python -X dev serve.py                    # http://127.0.0.1:8765/
.venv/bin/python -X dev serve.py --port 9000 --cache-dir cache
.venv/bin/python -X dev build.py --region Washington --palette neon --glow --output svg
```

`-X dev` turns on [Python Development Mode](https://docs.python.org/3/library/devmode.html),
which adds extra runtime checks, `ResourceWarning`s for unclosed files and sockets, and
faulthandler tracebacks on crashes. It never changes rendered output.

Things to know when running locally:

- **Datasets.** Archives are cached on the NAS (`/Volumes/home/data/incoming`) when it
  is mounted, and in local `cache/` when it isn't. If a dataset has already been
  extracted under `datasets/`, nothing is downloaded. Use `--cache-dir` or
  `--external-root` (or `$HYDRO_ART_EXTERNAL_ROOT`) to redirect storage.
- **Email.** Delivery emails are only sent when `HYDRO_ART_GMAIL_APP_PASSWORD` is
  set. Otherwise the server logs "email: not configured" and keeps running.
- **Static pages only.** You can open the `web/` pages straight from disk
  (`file://`). You only need `serve.py` for `/api/*` calls.
- **No auto-reload.** Restart `serve.py` after you change Python code. Changes to
  `web/` files only need a browser refresh.

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

## Tests

```bash
.venv/bin/python -m pytest -q                        # full offline suite (no GDAL/network)
.venv/bin/python -m pytest tests/test_config.py -k X # one test; add --pdb to drop into pdb on failure
node tests/test_recipe_roundtrip.cjs                 # web recipe roundtrip
.venv/bin/ruff check src tests                       # lint
```

`pytest --pdb` (post-mortem on failure) and `pytest --trace` (break at the start of each
test) are the fastest way to debug a failing test. Playwright E2E tests are opt-in; see
`CLAUDE.md` → Commands.
