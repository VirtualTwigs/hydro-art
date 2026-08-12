# Task Breakdown — Live pipeline integration (roadmap #27)

TDD: write 2–8 tests first per group, run only those, then implement until green.
Runner core stays GDAL-free and offline (fake pipeline + inline executor; no sockets).

## Task Group 1: `src/jobs.py` runner core

- [x] Tests (`tests/test_jobs.py`, new): `settings_from_payload` maps a whitelisted
  payload → `Settings` (region/color_by/width_by/months) and ignores unknown keys;
  bad value raises `ConfigError`. `JobRunner.submit` + inline executor → `SUCCEEDED`
  with `outputs`/`sha256` from a fake pipeline; a raising fake pipeline →
  `FAILED` with the message; unknown id → `KeyError`; invalid payload → `ConfigError`
  at submit.
- [x] Implement `settings_from_payload`, job-state constants, `Job`, `JobRunner`
  (`submit`/`status`/`to_dict`, injected executor defaulting to a 1-worker
  `ThreadPoolExecutor`, lock-guarded store). Imports: stdlib + `src.config` only.

## Task Group 2: `src/server.py` routing

- [x] Tests (`tests/test_server.py`, new): `handle_request` with a fake runner —
  `POST /api/render` valid → 202 + job id; `ConfigError` → 400; bad JSON → 400;
  `GET /api/jobs/<id>` known → 200 envelope, unknown → 404;
  `GET /api/jobs/<id>/artifact?fmt=svg` → 200 bytes + content-type, unready → 404;
  static `GET /` from a temp `web_root` → 200; path traversal (`/../secret`) → 404.
- [x] Implement `Response`, `handle_request` (routing + JSON + static + traversal
  guard) and a thin `serve()` over `ThreadingHTTPServer` delegating to it.

## Task Group 3: `serve.py` entry point + web wiring

- [x] `serve.py` (top-level, thin): build real `Pipeline(cache_dir=NAS_CACHE_DIR)` +
  `JobRunner`, `serve()` on localhost, print the URL. Not unit-tested.
- [x] `web/shared/hydro-ux.js`: add pure `renderRequest(state)` payload builder
  (config-key JSON mirroring `cliMapping`); export on `window.HydroUX`.
- [x] `web/studio.html`: "Run pipeline" affordance enabled only when served
  (`location.protocol !== 'file:'`); POST → poll → show returned SVG + download;
  disabled hint over `file://`. No duplicated option data/mapping.
- [x] `node --check` both scripts; headless determinism check of `renderRequest`.

## Task Group 4: Verification & docs

- [x] Write `implementation/report.md`.
- [x] Tick these checkboxes; mark roadmap #27 `[x]`; update `HANDOFF.md` and the
  `web/` + module-map notes in `CLAUDE.md`.
- [x] Run the full suite for regressions; smoke-test the runner offline.
- [x] Report and STOP (commit is a separate explicit step).

## Verification gates

1. `src/jobs.py` imports only stdlib + `src.config`; suite runs offline with a fake
   pipeline + inline executor (no sockets/network/datasets).
2. Valid payload → `SUCCEEDED` with outputs/sha; raising pipeline → `FAILED` message;
   invalid payload → `ConfigError` at submit (→ 400 in the server).
3. `handle_request` maps routes/errors correctly and refuses path traversal.
4. `web/` passes `node --check`; `renderRequest(state)` deterministic and file://-safe.
5. Full suite green; `src/` stays GDAL-free and offline.
