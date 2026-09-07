# Task Breakdown: Flagship end-to-end proof — all four endpoints (Epoch 21, #85–87)

## Overview
Total: 4 task groups. Prove **one region, one path, all four endpoints** at two layers: an
offline in-suite orchestration e2e (fakes) and an opt-in real-artifact harness (GDAL+NAS),
regression-guarded by a render-independent golden fixture. Adds no art feature and no
`PIPELINE_STAGES` change; the default 2D build stays BYTE-FOR-BYTE identical.

## Cross-cutting constraints (apply to every relevant group)
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green.
- **Offline discipline:** `src/endpoints.py` + tests import ONLY stdlib + `src.config` +
  `src.fulfillment`; NO GDAL/numpy/network/`web`. `tools/render_all_endpoints.py` lives
  OUTSIDE the suite.
- **Reuse, don't fork:** aggregate the existing `EndpointResult`/`dispatch_endpoint`; reuse the
  real renderer factories in `tools/render_endpoint.py`; reuse `src.determinism` for the golden.
- **Byte-identical default:** no pipeline/renderer bytes change; verify before closing.

---

## Task List

### Task Group 1: Combined e2e provenance core — `src/endpoints.py`
**Dependencies:** Epoch 19 (`src/endpoints.py`)

- [x] 1.0 `combined_manifest` + `e2e_contract_digest` + schemas + tests
  - [x] 1.1 Write tests FIRST in `tests/test_endpoints_e2e.py`:
    - `combined_manifest` of four results → schema `hydro-art/e2e-manifest@1`, endpoints dict
      has all four, attribution present; byte-identical under `sort_keys` for equal inputs.
    - inconsistent region/county/style across results → `EndpointError`; duplicate endpoint →
      `EndpointError`.
    - `e2e_contract_digest` of four requests → schema `hydro-art/e2e-contract@1`, per-endpoint
      filenames/kinds/formats present, NO checksums; byte-identical.
    - Run ONLY these tests.
  - [x] 1.2 Implement `E2E_MANIFEST_SCHEMA`, `E2E_CONTRACT_SCHEMA`, `combined_manifest`,
    `e2e_contract_digest`; extend `__all__`.
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** both functions byte-identical + coverage/consistency-checked; offline; green.

---

### Task Group 2: Offline all-endpoints e2e orchestration test (#85)
**Dependencies:** Task Group 1

- [x] 2.0 `tests/test_endpoints_e2e.py` — one flow, all four endpoints
  - [x] 2.1 Write the flagship test FIRST:
    - shared base Washington/Wahkiakum/neon-basin + per-endpoint extras; for each endpoint
      `build_endpoint_request` → `dispatch_endpoint` with a fake renderer writing real bytes
      to `tmp_path` and hashing them; `combined_manifest([...])`.
    - assert all four endpoints present, each plan matches `ENDPOINT_CONTRACTS`, combined
      manifest carries every deliverable + attribution, whole-flow re-run byte-identical.
    - Run ONLY these tests.
  - [x] 2.2 No `src/` change expected (drives existing code); adjust only on a real gap.
  - [x] 2.3 Run ONLY the 2.1 tests until green.

**Acceptance:** single offline flow proves all four endpoints with contract + determinism.

---

### Task Group 3: Real-data e2e harness (opt-in, non-suite) (#86)
**Dependencies:** Task Group 1

- [x] 3.0 `tools/render_all_endpoints.py`
  - [x] 3.1 Author the CLI: argparse → build four requests → inject the four REAL renderer
    factories from `tools/render_endpoint.py` → dispatch each → `combined_manifest` → write
    manifest sidecar; `--check-determinism` renders twice + compares per-file sha256s (optional
    `src.determinism` record/verify). Exit: `EndpointError`→1, render→2, drift→3. Imports only
    `src/` + `tools.render_endpoint`.
  - [x] 3.2 Compile-check (`python -c "import ast; ast.parse(...)"`); real run deferred to
    GDAL+NAS (documented in the report).

**Acceptance:** harness authored, imports clean, compiles; outside the suite; real run deferred.

---

### Task Group 4: E2E golden fixture + regression gate (#87)
**Dependencies:** TG1–TG3

- [x] 4.0 Golden fixture + gate + report
  - [x] 4.1 Generate `tests/fixtures/golden/e2e/washington-wahkiakum.json` from
    `e2e_contract_digest` (render-independent) and commit it; add an in-suite test asserting
    the recomputed digest equals the committed golden.
  - [x] 4.2 Run the FULL offline suite: `.venv/bin/python -m pytest -q`. Confirm no new
    GDAL/network import in `src/`/`tests/`; default 2D build byte-identical.
  - [x] 4.3 Write `implementation/report.md`.

**Acceptance:** golden committed + golden-match test green; full offline suite green; default
build byte-for-byte identical. Item gate: one in-suite flow proves all four endpoints with
contract + determinism, the render-independent e2e path is golden-guarded, and an opt-in real
harness is ready for the GDAL+NAS run — ready for Epoch 22 (marketing gallery) and Epoch 23
(release gate).

---

## Execution Order
1. Combined e2e provenance core (TG1).
2. Offline all-endpoints orchestration test (TG2).
3. Real-data harness (TG3).
4. Golden fixture + regression gate (TG4).
