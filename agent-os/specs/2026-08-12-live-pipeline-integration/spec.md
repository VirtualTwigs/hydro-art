# Specification: Live pipeline integration (roadmap #27)

## Goal

Wire the web control surface to a **local job runner** that executes the real pipeline
for the selected options and returns the produced SVG/PNG for preview and download,
keeping determinism and the offline test posture intact. This closes the loop opened by
#26: the surface stops being a mapping-only mockup and drives the real generator.

## Architecture

```text
browser (web/studio.html, served by the runner)
  │  POST /api/render   { region, color_by, width_by, months, ... }   (structured JSON)
  ▼
src/server.py  handle_request()            ← pure routing over stdlib http.server
  │  settings_from_payload → build_settings (boundary validation; ConfigError → 400)
  ▼
src/jobs.py  JobRunner.submit()            ← creates job, schedules off-thread run
  │  executor.submit(_run, job_id, settings)
  ▼
Pipeline.run(settings) → RunContext        ← INJECTED (real Pipeline in serve.py)
        artifacts["export_paths"], artifacts["svg_sha256"]
  ▲
  │  GET /api/jobs/<id>            → { state, error?, outputs?, sha256? }   (poll)
  │  GET /api/jobs/<id>/artifact?fmt=svg → file bytes                       (preview/download)
```

The **runner core** (`src/jobs.py`) is a pure, injectable module: it takes a
duck-typed `pipeline` (anything with `run(settings) -> ctx` where `ctx.artifacts` is a
mapping) and an executor (anything with `submit(fn, *args)`). Tests inject a fake
pipeline + an inline executor and never touch sockets, network, or datasets.

## Modules

### `src/jobs.py` (new — stdlib + `src.config` only, GDAL-free)

- `settings_from_payload(payload) -> Settings` — copy only keys in an accepted
  allowlist (the `DEFAULTS` keys) from the JSON payload, then delegate to
  `build_settings`. Unknown keys are ignored; invalid values raise `ConfigError`.
- Job state constants: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`.
- `@dataclass Job` — `id`, `state`, `error: str | None`, `outputs: dict[str, str]`
  (fmt → path string), `sha256: str | None`.
- `JobRunner`:
  - `__init__(pipeline, *, executor=None)` — default executor is a single-worker
    `ThreadPoolExecutor`; tests inject an inline one. Store guarded by a lock.
  - `submit(payload) -> str` — `settings_from_payload(payload)` (raises `ConfigError`
    to the caller), register a `PENDING` job under a fresh `uuid4().hex`, schedule
    `_run`, return the id.
  - `_run(job_id, settings)` — set `RUNNING`; run the pipeline; on success set
    `SUCCEEDED` with `export_paths`/`svg_sha256`; on any exception set `FAILED` with
    `str(exc)` (this is where `color_by=elevation` / non-annual months land).
  - `status(job_id) -> Job` — raises `KeyError` for an unknown id.
  - `to_dict(job) -> dict` — JSON-serializable status envelope.

### `src/server.py` (new — thin HTTP glue, stdlib `http.server`)

- `Response = namedtuple("Response", "status content_type body")` (`body: bytes`).
- `handle_request(runner, method, path, body, *, web_root) -> Response` — the pure,
  unit-tested dispatcher:
  - `POST /api/render` → `runner.submit(json.loads(body))` → `202 {"job": id}`;
    `ConfigError` → `400 {"error": msg}`; bad JSON → `400`.
  - `GET /api/jobs/<id>` → `200` status envelope; unknown id → `404`.
  - `GET /api/jobs/<id>/artifact?fmt=<fmt>` → `200` file bytes with the right
    content-type; missing/unready → `404`.
  - `GET /` and other paths → serve files under `web_root` (same-origin static),
    `404` outside the root (path-traversal guard).
- `serve(runner, host="127.0.0.1", port=8765, web_root=...)` — thin
  `ThreadingHTTPServer` whose handler delegates to `handle_request` (not unit-tested;
  sockets stay out of the suite).

### `serve.py` (new — top-level entry point, thin, mirrors `build.py`)

Build a real `Pipeline(cache_dir=NAS_CACHE_DIR)`, wrap it in a `JobRunner`, and
`serve(...)` on localhost. Prints the URL. Not unit-tested.

### `web/shared/hydro-ux.js` + `web/studio.html`

- `HydroUX.renderRequest(state) -> object` — a **pure** function turning the UX `state`
  into the structured JSON payload (the same selections `cliMapping`/`yamlMapping`
  encode, but as config keys). Deterministic.
- `studio.html` — a "Run pipeline" affordance enabled only when
  `location.protocol !== 'file:'` (i.e. served by the runner). It POSTs
  `renderRequest(state)`, polls the job, then shows the returned SVG in the preview
  stage and offers a download. Over `file://` the button is disabled with a hint that
  the surface is in mapping-only mode. No duplicated option data or mapping logic.

## Acceptance criteria

1. A valid payload submitted to `JobRunner` runs the injected pipeline and exposes
   `SUCCEEDED` with `export_paths` + `svg_sha256`; an invalid payload raises
   `ConfigError` at submit.
2. A pipeline that raises (e.g. `color_by=elevation`, non-annual months) yields a
   `FAILED` job carrying the pipeline's message — never a fake success.
3. `handle_request` routes render/status/artifact/static correctly, maps `ConfigError`
   to 400 and unknown ids to 404, and refuses path traversal outside `web_root`.
4. `settings_from_payload` accepts only known config keys and produces a `Settings`
   byte-consistent with the equivalent `build.py`/`config.yaml` selection.
5. `src/jobs.py` imports only stdlib + `src.config` (no Pipeline import, no GDAL); the
   suite runs fully offline with a fake pipeline + inline executor.
6. `web/` changes pass `node --check`, `renderRequest(state)` is deterministic, and the
   surface still opens over `file://` (Run disabled) with no new dependency.

## Verification approach

- Python offline suite: `tests/test_jobs.py`, `tests/test_server.py` (fake pipeline,
  inline executor, temp `web_root`; no sockets/network/datasets).
- Web: `node --check` on `hydro-ux.js` + the `studio.html` inline script; a headless
  determinism check that `renderRequest(state)` is stable and its keys agree with
  `cliMapping`/`yamlMapping`.
- Real end-to-end run (browser → localhost server → real `Pipeline` → NAS/GIS) is a
  **manual smoke**, noted honestly since it can't run in the offline suite.
