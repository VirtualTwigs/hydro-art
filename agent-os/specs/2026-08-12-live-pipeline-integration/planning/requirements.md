# Requirements — Live pipeline integration (roadmap #27)

## Problem

The web control surface (`web/studio.html`, #26) emits a deterministic `build.py`
command + `config.yaml` fragment but does **not** run anything. #27 wires it to a
**local job runner** that executes the real pipeline for the selected options and
returns the produced SVG/PNG for preview and download — keeping determinism and the
offline test posture intact.

## Confirmed decisions (asked 2026-08-12)

1. **Request model — structured JSON → `build_settings`.** The browser POSTs the UX
   selection as JSON; the server rebuilds `Settings` through the existing
   `build_settings` boundary validation and runs the injected `Pipeline`. It never
   shell-executes the emitted command string (no command injection), and reuses all
   field validation.
2. **Server tech — stdlib `http.server`.** No new dependency; matches the minimal
   `pyproject` (pyyaml + rich) and the GDAL-free core. A small `ThreadingHTTPServer`
   with a handful of routes. The runner core is a pure, injectable module tested fully
   offline.
3. **Execution model — job-id + poll.** `POST /api/render` validates and returns a job
   id immediately; the browser polls `GET /api/jobs/<id>` until the artifact is ready
   (real runs download + do GIS work for minutes). The runner core
   (request → Settings → run → collect outputs → status) is tested offline with a
   **fake Pipeline**; the real dataset run is a manual smoke, noted honestly because it
   cannot run in the offline suite.

## Functional requirements

- Translate a whitelisted JSON payload of config keys into a validated `Settings`
  (`ConfigError` on bad input → HTTP 400 at submit).
- Run the injected `Pipeline` off the request thread; track job lifecycle
  `pending → running → succeeded | failed`, capturing `export_paths`
  (fmt → path) and `svg_sha256` on success and the error message on failure.
- Serve the produced artifact bytes back to the browser (`GET
  /api/jobs/<id>/artifact?fmt=svg|png`) for inline preview and download.
- Serve the `web/` directory same-origin so `studio.html` + shared assets load without
  CORS, and the Run affordance only lights up when the page is served by the runner
  (not over `file://`).
- The two options that still fail fast in the 2D pipeline (`color_by=elevation`,
  non-annual `--months`) surface as a **failed job** carrying the honest pipeline
  message — not a fake success.

## Non-functional / guardrails

- `src/` stays GDAL-free and import-light: `src/jobs.py` imports only stdlib +
  `src.config`; the concrete `Pipeline` is **injected**, never imported by the runner
  core. Heavy libs remain lazy behind the pipeline's existing seams.
- Fully offline tests: fake Pipeline + inline executor; no sockets, network, or
  datasets in the suite.
- Determinism unchanged: identical requests yield the identical artifact (guaranteed by
  the pipeline); job ids are opaque and may differ.
- `web/` changes stay `file://`-safe and pass `node --check`; the payload builder is a
  pure function of the UX `state`.

## Out of scope

- Real end-to-end dataset run in CI/tests (needs the NAS + GIS stack) — manual smoke.
- Multi-frame `--months` animation export and the DEM/elevation render path (those are
  their own roadmap items; here they legitimately fail the job with the caveat message).
- Auth, multi-user, remote hosting — this is a **localhost** developer tool.
- Presets / shareable recipes (roadmap #28).
