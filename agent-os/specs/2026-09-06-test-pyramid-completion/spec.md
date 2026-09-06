# Spec: Unit & integration test completion (Epoch 20, #82–84)

Second epoch of Generation 1. Turns the existing 94% offline baseline into a *documented,
gated* base of the test pyramid, and adds offline integration coverage of the four-endpoint
layer shipped in Epoch 19.

## Design

Three coordinated deliverables, all offline:

### 1. Endpoint integration tests — `tests/test_endpoints_integration.py` (#83)
A higher-level companion to `tests/test_endpoints.py`. Where the unit tests exercise each
function in isolation with trivial fakes, the integration tests drive the **whole
orchestrator** (`dispatch_endpoint`) end-of-path for every endpoint, with a fake renderer
that behaves like a real one: it writes real bytes to `tmp_path` for each planned filename,
hashes them with `hashlib.sha256`, and returns `{filename: sha256}`. This exercises the real
`endpoint_plan → renderer seam → coverage check → endpoint_manifest → EndpointResult` chain.

Per endpoint the test asserts:
- `result.ok` and `result.endpoint == <endpoint>`;
- plan filenames/kinds/formats equal the `ENDPOINT_CONTRACTS[endpoint]` contract (canonical
  order), print carrying pixel dims;
- manifest `schema`/`endpoint`/`attribution`/`deliverables` (with the real per-file sha256s);
- **determinism**: dispatching the same request twice yields byte-identical manifest JSON
  under `sort_keys=True`, and identical plan filenames.

A separate case confirms the Rights gate still short-circuits before the renderer at the
integration level (PRISM-flagged style → `EndpointError`, renderer never writes a file).

### 2. Coverage config + gap-closure tests (#82)
- `pyproject.toml` gains `[tool.coverage.run]` (`source = ["src"]`, `branch = false`) and
  `[tool.coverage.report]` with `exclude_lines` = the default `pragma: no cover` plus the
  patterns already used defensively in `src/` (e.g. `if TYPE_CHECKING:`, `raise
  NotImplementedError`). This scopes the number to offline-testable `src/` code and honors
  the existing `# pragma: no cover` markers on env-dependent import-guards.
- Add a handful (≤5) of strategic offline unit tests for branches that ARE offline-testable
  but currently missed — primarily `src/optimize.py` lines 55–62 (svgo present-but-failing
  `CalledProcessError` branch and the success `return result.stdout` branch) via a
  monkeypatched `subprocess.run`. `tests/test_optimize.py` already exists; extend it.
- The audit conclusion is documented in the report: residual misses
  (`counties.load`, `download` fetch, `loading` GDAL read, `server` handlers) are injectable
  I/O seam bodies requiring GDAL/network — offline-untestable by design and covered instead
  by injected fakes at the call sites.

### 3. Coverage gate tool — `tools/coverage_report.py` (#84)
A thin NON-suite CLI: `argparse` → `coverage run -m pytest -q` → `coverage report` →
optional `coverage report --fail-under N` returning a non-zero exit when below threshold.
Report-only when `--fail-under` is omitted. Imports only stdlib + subprocess; never imported
by `src/` or the suite. Mirrors the taxonomy of the other `tools/` scripts.

## Discipline / invariants
- `src/` unchanged except (possibly) adding `# pragma: no cover` on already-untestable import
  guards — no behavior/byte change; default build stays byte-identical.
- No GDAL/network import enters `src/` or `tests/`.
- `tools/coverage_report.py` outside the suite.

## Agreed threshold
Report-only default; the recommended `--fail-under` for the gate is **90%** (current scoped
baseline is 94%), leaving headroom for seam lines not yet pragma-marked. Epoch 23 raises/
enforces this in CI.

## Files
- NEW `tests/test_endpoints_integration.py`
- EDIT `tests/test_optimize.py` (≤5 added tests)
- EDIT `pyproject.toml` (`[tool.coverage.*]`)
- NEW `tools/coverage_report.py`
- NEW `agent-os/specs/2026-09-06-test-pyramid-completion/implementation/report.md`
