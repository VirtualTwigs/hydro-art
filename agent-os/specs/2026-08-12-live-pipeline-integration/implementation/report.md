# Implementation Report — Live pipeline integration (roadmap #27)

## Confirmed direction (2026-08-12)

Asked and confirmed all three recommended options:

1. **Request model** — structured JSON → `build_settings` → injected `Pipeline`
   (never shell-exec the emitted CLI string).
2. **Server tech** — stdlib `http.server` (no new dependency).
3. **Execution model** — job-id + poll; the runner core is tested offline with a fake
   pipeline + inline executor; the real dataset run is a manual smoke.

## Changes

### New `src/jobs.py` (runner core — stdlib + `src.config` only, GDAL-free)

- `settings_from_payload(payload)` — copies only keys in `ACCEPTED_KEYS`
  (`= frozenset(DEFAULTS)`) from the browser payload and delegates to `build_settings`,
  so unknown/`__proto__`-style keys are dropped and every value is boundary-validated.
- `Job` dataclass (`id`, `state`, `error`, `outputs`, `sha256`) + lifecycle constants
  `PENDING`/`RUNNING`/`SUCCEEDED`/`FAILED`.
- `JobRunner(pipeline, *, executor=None)` — `submit` validates first (so `ConfigError`
  fails fast → HTTP 400) then schedules `_run` off-thread (default a 1-worker
  `ThreadPoolExecutor`; tests inject an inline one). `_run` runs the injected pipeline,
  reading `ctx.artifacts["export_paths"]`/`["svg_sha256"]`; any exception →
  `FAILED` with the message (this is where `color_by=elevation` and non-annual
  `--months` land honestly). `status` / `to_dict` complete the surface. The pipeline is
  duck-typed (`PipelineLike`), so the module never imports `src.pipeline`.

### New `src/server.py` (thin HTTP glue — stdlib `http.server`)

- `Response = namedtuple("Response","status content_type body")`.
- `handle_request(runner, method, path, body, *, web_root)` — the pure, unit-tested
  dispatcher: `POST /api/render` (JSON → `submit`; `ConfigError`/bad-JSON → 400;
  success → 202 `{"job": id}`), `GET /api/jobs/<id>` (status envelope; unknown → 404),
  `GET /api/jobs/<id>/artifact?fmt=…` (file bytes + MIME; unready → 404), and static
  file serving under `web_root` with a path-traversal guard (`/` → `studio.html`).
- `make_handler` / `serve` wrap it in a `ThreadingHTTPServer` (thin, not unit-tested —
  sockets stay out of the suite).

### New `serve.py` (top-level entry point, thin)

Builds a real `Pipeline(cache_dir=NAS_CACHE_DIR)` (lazily imported so the offline suite
never pulls the GIS stack through `serve.py`), wraps it in a `JobRunner`, and serves
`web/` + the API on localhost. Mirrors `build.py`'s NAS staging.

### Web wiring (`web/shared/hydro-ux.js`, `web/studio.html`)

- `HydroUX.renderRequest(state)` — a **pure** function turning the UX `state` into the
  structured JSON payload of real `src/config` keys (mirrors `cliMapping`'s selections).
- `studio.html` gains a "▶ Run pipeline" button, enabled only when served
  (`location.protocol !== 'file:'`). It POSTs `renderRequest(state)`, polls the job,
  and on success swaps the returned SVG into the preview stage and offers a download.
  Over `file://` the button is disabled with a hint — the surface stays mapping-only.
  No option data or mapping logic is duplicated.

## Verification

- **Offline Python suite: 361 passing** (was 345; +8 `tests/test_jobs.py`,
  +8 `tests/test_server.py`), fully offline with a fake pipeline + inline executor and a
  temp `web_root` — no sockets, network, GDAL, or datasets.
- `src/jobs.py`/`src/server.py` import **no** heavy GIS libs (asserted in a smoke: none
  of geopandas/pyogrio/shapely/numpy/networkx enters `sys.modules`).
- Integrated offline smoke: real `JobRunner` + fake pipeline driven through
  `handle_request` → `POST /api/render` = 202, `GET /api/jobs/<id>` = 200 succeeded.
- **Contract round-trip**: the JS `renderRequest(state)` payload (county + flow + single
  colour, and the default watershed case) validates cleanly through the Python
  `settings_from_payload` → correct `regions`/`county`/`months`/`color_by`/`width_by`.
- Web: `node --check` on `hydro-ux.js` + the `studio.html` inline script pass;
  `renderRequest(state)` is deterministic; the surface still opens over `file://` (Run
  disabled).

## Not done (honest caveats)

- **Manual browser + real-dataset smoke** (browser → `python serve.py` → real
  `Pipeline` → NAS/GIS → live SVG) is not exercisable in the offline suite; it needs the
  full GIS environment and the NAS mount. The routing, runner, and contract are covered
  by the offline tests above.
- `color_by=elevation` and non-annual `--months` intentionally produce a **failed job**
  carrying the pipeline's fail-fast message (their real render paths are the DEM
  subsystem / a future multi-frame export, not this item).
