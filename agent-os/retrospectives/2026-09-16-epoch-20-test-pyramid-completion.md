# Retrospective — Epoch 20: Unit & integration test completion (#82-84)

_Closed 2026-09-06 (single commit `f7f1c6d`); retro written 2026-09-16. **No
pre-registered watch-list** — the spec folder
(`2026-09-06-test-pyramid-completion`) carries `planning/raw-idea.md`,
`planning/requirements.md`, `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout rather than a graded one. Second epoch of Generation 1
(Epochs 19-23, #79-93)._

## What the epoch was

Turn the existing 94% offline coverage baseline into a **documented, gated**
base of the test pyramid: add offline integration tests that drive the four
endpoint orchestrators shipped in Epoch 19 end-of-path, close the last
genuinely-offline-testable coverage gaps (the `SvgoOptimizer` subprocess
branches in `src/optimize.py`), scope the coverage metric to `src/` via
`pyproject.toml`, and deliver a repeatable `tools/coverage_report.py` gate.
Adds no art feature and no `PIPELINE_STAGES` change — the default 2D build
stays byte-for-byte identical.

All three planned items (#82-84) shipped and the epoch closed on #84.

## What shipped (`f7f1c6d`)

### `tests/test_endpoints_integration.py` (NEW, 128 lines) — #83

10 test functions driving `dispatch_endpoint` end-of-path for every endpoint.
A realistic fake renderer (`_disk_renderer`) writes REAL bytes to `tmp_path`
per planned filename, sha256s them, and returns `{filename: sha256}` — so the
full `endpoint_plan -> renderer seam -> coverage check -> endpoint_manifest ->
EndpointResult` chain runs under test:

- `test_endpoint_orchestrator_matches_contract` (parametrized x4): result
  `ok=True` and `endpoint` correct; plan `formats`/`kinds` match
  `ENDPOINT_CONTRACTS` in canonical order; manifest carries
  `schema="hydro-art/endpoint-manifest@1"`, endpoint, attribution, and
  per-file sha256s verified against the real on-disk bytes.
- `test_endpoint_orchestrator_is_byte_identical` (parametrized x4): same
  request dispatched twice -> `json.dumps(manifest, sort_keys=True)` identical,
  plan filenames identical.
- `test_print_endpoint_carries_pixel_dims`: print 18x24 @ 300dpi -> png
  deliverable carries `(5400, 7200)`.
- `test_rights_gate_precedes_renderer_at_integration`: PRISM-flagged style ->
  `EndpointError` raised, renderer never wrote a file (`tmp_path` empty).

### `tests/test_optimize.py` (EDIT, +3 tests) — #82 gap closure

Three monkeypatched `subprocess.run` tests closing the previously-missed
`SvgoOptimizer` branches in `src/optimize.py`:

- `test_svgo_present_but_failing_returns_input_with_warning`:
  `CalledProcessError` -> returns unoptimized SVG + `UserWarning`.
- `test_svgo_success_returns_optimized_stdout`: successful run returns
  `result.stdout`.
- `test_svgo_success_empty_stdout_falls_back_to_input`: empty stdout edge case
  falls back to unoptimized input.

`src/optimize.py` now measures **100%** coverage under the scoped config.

### `pyproject.toml` (EDIT) — #82/#84

Added `[tool.coverage.run]` (`source = ["src"]`, `branch = false`) and
`[tool.coverage.report]` with `exclude_lines` for `pragma: no cover`,
`if TYPE_CHECKING:`, `raise NotImplementedError`, and `...` (ellipsis stubs).
This scopes the metric to offline-testable `src/` code and honors the existing
pragma convention on env-dependent import guards.

### `tools/coverage_report.py` (NEW, 66 lines) — #84

Thin stdlib-only CLI: `coverage run -m pytest` -> `coverage report --sort=cover`,
with `--fail-under N` (report-only when omitted) and `--quiet`. Exit taxonomy:
suite fail -> 1, coverage below threshold -> 2, else 0. Verified both ways:
`--fail-under 90` -> exit 0 (94% total); `--fail-under 99` -> exit 2.

### Coverage audit conclusion (#82)

Baseline after the gap-closure tests: **94% total** (scoped to `src/`).
Residual misses are injectable I/O seam bodies that are offline-untestable
by design — these four modules are covered by injected fakes at their call
sites, not by real I/O in the suite:

- `counties.py` `CensusCountyProvider.load` (geopandas `read_file`).
- `download.py` (urllib network fetch).
- `loading.py` `PyogrioLayerLoader.load_layers` (GDAL `gpd.read_file`).
- `server.py` (live `http.server` request handlers).

### Commit totals

11 files changed, 576 insertions, 1 deletion. Full offline suite: **827
passed** (was 814 after Epoch 19; +13 new endpoint integration + optimize
gap-closure tests; no regressions).

## Real-data findings

No real-data run in this epoch by design. The spec scoped this as "author
offline, run later" — the real four-artifact endpoint run was deferred to
Epoch 21 (`26e8aee`) on the GDAL+NAS machine. No bug-the-real-run-surfaced to
report. The expected pattern (resolution drift, silent truncation, wall-clock
PDF dates, SMB chflags) would apply to the renderers exercised at Epoch 21,
not to the pure test/tooling layer added here.

## Invariants held

- **Offline suite:** 827 passed (+13 new), no regressions.
- **2D default output byte-identical:** yes. No `src/` behavior change — the
  commit adds only `pyproject.toml` coverage config + new tests + a non-suite
  tool. No pipeline module touched.
- **`PIPELINE_STAGES` untouched:** yes.
- **Rights gate:** enforced. `test_rights_gate_precedes_renderer_at_integration`
  confirms `dispatch_endpoint` raises `EndpointError` for a PRISM-flagged
  style before the renderer is invoked (renderer wrote no file to `tmp_path`).

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no
pre-registered watch-list to grade against. The spec's design section
identified three deliverables; all shipped as specified:

1. **Endpoint integration tests (#83).** Delivered: 10 tests, all four
   endpoints, contract + determinism + Rights gate at the integration level.
   No `src/` implementation change needed — the tests drove existing
   `src/endpoints.py` code.
2. **Coverage config + gap-closure tests (#82).** Delivered: `pyproject.toml`
   scoping, 3 optimize gap tests, audit conclusion documenting residual I/O
   seam misses.
3. **Coverage gate tool (#84).** Delivered: `tools/coverage_report.py` with
   `--fail-under` + `--quiet`, stdlib-only, verified both pass and fail exit
   codes.

The spec predicted a baseline of 94% and a recommended `--fail-under` of 90%.
Both confirmed exactly.

## Carry-forwards

- **No live byte-identical `verify_determinism.py` double-render was run for
  this epoch.** Byte-identity rests on the "no `src/` behavior change"
  invariant, not a fresh double-render — matching the standing carry-forward
  from Epochs 9/10/14/16/18/19.
- **Coverage gate not yet wired into CI.** `tools/coverage_report.py` runs
  locally; Epoch 23 (`f233773`) wired it into `.github/workflows/ci.yml`.
  This was an intentional deferral, not a gap.
- **Residual I/O seam coverage.** The four offline-untestable modules
  (`counties.load`, `download`, `loading`, `server`) remain covered only by
  injected fakes, not by real-data tests. The Epoch 21 flagship e2e
  (`26e8aee`) exercises some of these paths against real data; the Epoch 10
  real-data smoke harness (#41/#42) remains open for the rest.

## Lessons

- **Coverage audits pay for themselves as documentation.** The audit's real
  value was not the three gap-closure tests (trivial to write) but the
  documented conclusion that the residual misses are I/O seam bodies,
  offline-untestable by design. Future contributors can read the
  `implementation/report.md` and know the gap is intentional, not neglected.
- **Integration tests should drive real orchestrators, not re-implement them.**
  `test_endpoints_integration.py` calls `dispatch_endpoint` with a realistic
  fake renderer — it does not re-build the plan/manifest/rights chain. This
  means a regression in the orchestrator's wiring is caught, not masked by a
  test-side re-implementation.
- **Consider adding a pre-analysis even for "test infrastructure" epochs.**
  As with Epochs 16, 18, and 19, none was written. The scope was small and
  all deliverables landed exactly as specified, but a pre-analysis would have
  cost little and made this retrospective a graded one rather than a narrative
  one.
