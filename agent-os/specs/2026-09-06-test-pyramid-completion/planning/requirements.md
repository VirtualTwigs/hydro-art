# Requirements — Epoch 20 (Unit & integration test completion, #82–84)

## Goal
Close the base of the test pyramid with a measurable, repeatable coverage gate and offline
integration coverage of the four endpoint orchestrators, without breaking the offline-suite
discipline or the byte-identical default build.

## Functional requirements

### #82 Unit-coverage audit & gap closure
- Measure per-module `src/` coverage with `coverage` (already in `.venv`, 7.16.0).
- Add offline unit tests for genuinely testable branches currently missed (e.g.
  `optimize.py` `CalledProcessError`/success branches via a monkeypatched `subprocess.run`).
- Do NOT attempt to cover GDAL/network/subprocess-tool seam bodies that require real
  external state — instead mark them so coverage math reflects offline-testable code only.

### #83 Endpoint integration tests (offline)
- New file `tests/test_endpoints_integration.py`.
- For EACH of the four endpoints (`digital_image`, `animation`, `print_image`, `report`):
  drive `src.endpoints.dispatch_endpoint` through its full path with an injected fake
  renderer that writes **real bytes** to `tmp_path` for every planned filename, sha256s
  them, and returns the map — exercising `endpoint_plan` → renderer seam → coverage check →
  `endpoint_manifest` → `EndpointResult`.
- Assert per-endpoint: result ok + endpoint, plan filenames/kinds/formats match the
  contract, manifest schema/endpoint/attribution/deliverables, and **byte-identical
  determinism** (same request twice → identical `json.dumps(..., sort_keys=True)`).
- Stay offline: no GDAL/network/real datasets; fakes + `tmp_path` only.

### #84 Coverage gate & reporting
- Add a `[tool.coverage.run]` / `[tool.coverage.report]` config (in `pyproject.toml`) that
  scopes measurement to `src/` and excludes documented offline-untestable seam lines via
  `exclude_lines` patterns (reusing the existing `# pragma: no cover` convention already
  present in `src/`).
- Add `tools/coverage_report.py` (NON-suite): runs `coverage run -m pytest` + `coverage
  report`, accepts `--fail-under N` (report-only when omitted). Lives outside the suite;
  imports nothing from `src/`.

## Non-functional / discipline
- Offline suite stays green and offline (no new GDAL/network import in `src/` or `tests/`).
- Default 2D build byte-for-byte identical (no `PIPELINE_STAGES`/renderer byte change).
- `tools/coverage_report.py` is not imported by `src/` or the suite.
- TDD: 2–8 focused tests first per group; run only those until green; full suite at the end.

## Out of scope
- Enforcing a hard CI threshold (CI wiring is Epoch 23). This epoch ships the gate tool and a
  report-only default; the enforced number is opt-in via `--fail-under`.
- Any new art feature or renderer.

## Acceptance
- `tests/test_endpoints_integration.py` covers all four endpoints with contract + determinism
  assertions and is green.
- Genuine offline gaps closed; residual misses are documented seams excluded by config.
- `tools/coverage_report.py --fail-under <agreed>` passes on the current suite.
- Full offline suite green; default build byte-identical.
