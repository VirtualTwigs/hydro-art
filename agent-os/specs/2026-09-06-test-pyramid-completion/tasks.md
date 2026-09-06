# Task Breakdown: Unit & integration test completion (Epoch 20, #82–84)

## Overview
Total: 3 task groups. Turn the 94% offline baseline into a documented, gated base of the
pyramid: offline integration tests for all four endpoint orchestrators, gap-closure unit
tests for genuinely offline-testable branches, and a repeatable coverage gate tool. Adds no
art feature and no `PIPELINE_STAGES` change; the default 2D build stays BYTE-FOR-BYTE
identical.

## Cross-cutting constraints (apply to every relevant group)
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green; no exhaustive coverage.
- **Offline discipline:** new tests import ONLY stdlib + `src.*`; NO GDAL/numpy/network/`web`.
  `tools/coverage_report.py` lives OUTSIDE the suite and imports nothing from `src/`.
- **Reuse, don't fork:** drive the real `src.endpoints.dispatch_endpoint`; reuse
  `ENDPOINT_CONTRACTS`, `build_endpoint_request`, `endpoint_plan`.
- **Byte-identical default:** no pipeline/renderer bytes change; verify before closing.

---

## Task List

### Task Group 1: Endpoint integration tests (offline) — #83
**Dependencies:** Epoch 19 (`src/endpoints.py` exists)

- [x] 1.0 `tests/test_endpoints_integration.py` — all four orchestrators end-of-path
  - [x] 1.1 Write 2–8 focused tests FIRST:
    - A fake renderer that writes REAL bytes to `tmp_path` per planned filename, sha256s
      them, returns `{filename: sha256}`.
    - Parametrized over the four endpoints: `dispatch_endpoint` → `EndpointResult(ok, endpoint)`,
      plan filenames/kinds/formats match `ENDPOINT_CONTRACTS`, manifest schema/endpoint/
      attribution/deliverables carry the real sha256s.
    - Determinism: same request twice → byte-identical `json.dumps(manifest, sort_keys=True)`.
    - Rights gate at integration level: PRISM-flagged style → `EndpointError`, renderer wrote
      no file.
    - Run ONLY these tests.
  - [x] 1.2 Implement nothing in `src/` (tests drive existing code); adjust only if a genuine
    gap is found.
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** all four endpoints covered end-of-path with contract + determinism + rights
assertions; fully offline; green.

---

### Task Group 2: Coverage config + gap-closure unit tests — #82
**Dependencies:** none

- [x] 2.0 `[tool.coverage.*]` config + ≤5 gap tests
  - [x] 2.1 Write tests FIRST (extend `tests/test_optimize.py`):
    - svgo present but failing → `CalledProcessError` branch returns the unoptimized SVG
      (monkeypatch `subprocess.run` to raise).
    - svgo present and succeeding → returns `result.stdout` (monkeypatch to return a fake
      completed process).
    - Run ONLY these tests.
  - [x] 2.2 Add `[tool.coverage.run]` (`source=["src"]`) + `[tool.coverage.report]`
    (`exclude_lines` incl. `pragma: no cover`, `if TYPE_CHECKING:`) to `pyproject.toml`.
    Add `# pragma: no cover` only where a line is already an env-dependent import guard.
  - [x] 2.3 Run ONLY the 2.1 tests until green; re-measure scoped coverage.

**Acceptance:** optimize branches covered; coverage config scopes to `src/` and honors
pragmas; residual misses documented as I/O seams in the report.

---

### Task Group 3: Coverage gate & reporting tool — #84
**Dependencies:** Task Group 2 (config)

- [x] 3.0 `tools/coverage_report.py` (non-offline-suite)
  - [x] 3.1 Author `tools/coverage_report.py`: argparse (`--fail-under`, `--quiet`) →
    `coverage run -m pytest -q` → `coverage report` (+ `--fail-under` passthrough). Exit
    non-zero when below threshold; report-only otherwise. Imports only stdlib.
  - [x] 3.2 Manually run `python tools/coverage_report.py --fail-under 90` → passes on the
    current suite. (Tool is outside the suite; not a pytest test.)

**Acceptance:** `tools/coverage_report.py --fail-under 90` passes; tool imports only stdlib;
not imported by `src/` or the suite.

---

### Task Group 4: Regression gate & report
**Dependencies:** TG1–TG3

- [x] 4.0 Validate the item and guard against regressions
  - [x] 4.1 Run the FULL offline suite: `.venv/bin/python -m pytest -q`.
  - [x] 4.2 Confirm default 2D build byte-identical (no `src/` behavior change; grep no new
    GDAL/network import in `src/`/`tests/`).
  - [x] 4.3 Write `implementation/report.md`.

**Acceptance:** full offline suite green; default build byte-for-byte identical; integration
tests cover all four endpoints; coverage gate tool runs. Item gate: base of the pyramid is
documented + gated, all four endpoint orchestrators have offline integration coverage —
ready for Epoch 21 (flagship e2e).

---

## Execution Order
1. Endpoint integration tests (TG1).
2. Coverage config + gap tests (TG2).
3. Coverage gate tool (TG3).
4. Regression gate & report (TG4).
