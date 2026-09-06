# Task Breakdown: Production endpoint contracts & hardening (Epoch 19, #79–81)

## Overview
Total: 4 task groups. Build a pure/offline four-endpoint contract layer that mirrors
`src/fulfillment.py`: contracts + request validation → plan + provenance manifest → injectable
dispatch seam + non-offline CLI wrapper → determinism/regression gate. Adds no art feature and
no `PIPELINE_STAGES` change; the default 2D build must stay BYTE-FOR-BYTE identical.

## Cross-cutting constraints (apply to every relevant group)
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green; no exhaustive coverage.
- **Matching test file:** `src/endpoints.py` → `tests/test_endpoints.py`.
- **Offline discipline:** `src/endpoints.py` and its tests import ONLY stdlib + `src.config` +
  `src.fulfillment`; NO GDAL/numpy/network/`web`/`tools`. `tools/render_endpoint.py` lives
  outside the suite.
- **Reuse, don't fork:** import `DataSource`, `DEFAULT_SOURCES`, `Size`/`SIZES`, `Deliverable`,
  `DeliverablePlan`, `attribution_line`, and the Rights gate from `src.fulfillment`.
- **CRS/constants:** never inline `"EPSG:5070"`; import `INTERNAL_CRS` from `src.crs` if needed.
- **Byte-identical default:** no pipeline/renderer bytes change; verify before closing.

---

## Task List

### Task Group 1: Endpoint contracts + request validation
**Dependencies:** none (`src/fulfillment.py` exists)

- [x] 1.0 `src/endpoints.py` contracts + `build_endpoint_request` + tests
  - [x] 1.1 Write 2–8 focused tests FIRST in `tests/test_endpoints.py`:
    - `ENDPOINT_CONTRACTS` has all four endpoints with expected kinds/formats/naming.
    - `build_endpoint_request` accepts a valid payload per endpoint → frozen `EndpointRequest`.
    - unsupported region / unknown endpoint / unknown style / bad format → `EndpointError`.
    - endpoint-specific param rules (print requires `size`; report requires `huc`; animation
      requires `year` or `months`) → `EndpointError` when missing.
    - payload is not mutated.
    - Run ONLY these tests.
  - [x] 1.2 Implement `EndpointError`, `ENDPOINTS`, `EndpointContract`, `ENDPOINT_CONTRACTS`,
    `EndpointRequest`, and `build_endpoint_request` (allowlist validation, no mutation).
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** 1.1 tests pass; contracts cover all four endpoints; validation fails fast with
`EndpointError`; no GDAL/numpy import; no payload mutation.

---

### Task Group 2: Deliverable plan + provenance manifest
**Dependencies:** Task Group 1

- [x] 2.0 `endpoint_plan` + `endpoint_manifest` + Rights gate + tests
  - [x] 2.1 Write tests FIRST in `tests/test_endpoints.py`:
    - `endpoint_plan` returns the deterministic, add-on-order-independent deliverables per
      endpoint (e.g. digital_image → svg+png; print_image → png/pdf/tiff per request).
    - `endpoint_manifest` schema `hydro-art/endpoint-manifest@1`, includes endpoint +
      attribution + per-file sha256; `json.dumps(sort_keys=True)` byte-identical for equal inputs.
    - checksum coverage mismatch (missing/extra) → `EndpointError`.
    - `assert_sellable` refuses a PRISM-flagged style; passes a public-domain style.
    - Run ONLY these tests.
  - [x] 2.2 Implement `endpoint_plan` (reuse `Deliverable`/`DeliverablePlan`, a documented
    `_stem`), `endpoint_manifest` (reuse `attribution_line` + checksum-coverage check), and
    `assert_sellable` (delegate to `src.fulfillment` semantics).
  - [x] 2.3 Run ONLY the 2.1 tests until green.

**Acceptance:** 2.1 tests pass; plan deterministic; manifest versioned + byte-identical +
coverage-enforced; Rights gate enforced.

---

### Task Group 3: Dispatch seam + CLI wrapper
**Dependencies:** Task Group 2

- [x] 3.0 `dispatch_endpoint` (pure, injectable) + `tools/render_endpoint.py` (non-offline)
  - [x] 3.1 Write tests FIRST in `tests/test_endpoints.py`:
    - `dispatch_endpoint(request, renderers={...fakes...})` routes to the correct fake renderer
      per endpoint and returns `EndpointResult(ok=True, plan, manifest)`.
    - the Rights gate runs BEFORE the renderer (PRISM style → `EndpointError`, renderer never
      called — assert via a fake that records calls).
    - a renderer returning checksums not matching the plan → `EndpointError` (coverage check).
    - Run ONLY these tests.
  - [x] 3.2 Implement `EndpointResult` + `dispatch_endpoint(request, *, renderers)`: Rights gate
    → look up renderer seam → obtain checksums → build manifest → return result; no real I/O.
  - [x] 3.3 Author `tools/render_endpoint.py`: argparse → `build_endpoint_request` → inject the
    four real renderer callables (wrapping `build.py`, `render_monthly`/`render_state_yoy`,
    `render_terrain_print`, `build_watershed_report`; extend `render_common.py`) → write manifest
    sidecar; `EndpointError`→exit 1, acquisition→exit 2. NOT imported by `src/` or the suite.
  - [x] 3.4 Run ONLY the 3.1 tests until green.

**Acceptance:** 3.1 tests pass; dispatch routes via injected seam; Rights gate precedes the
renderer; coverage enforced; `tools/render_endpoint.py` imports only `src/` + `render_common.py`.

---

### Task Group 4: Determinism, offline-discipline & full-suite regression gate
**Dependencies:** Task Group 3

- [x] 4.0 Validate the item and guard against regressions
  - [x] 4.1 Review TG1–TG3 tests; add ≤5 strategic gap-filling tests for THIS item only
    (e.g. every `ENDPOINT_CONTRACTS` entry round-trips build→plan→manifest; naming stems are
    filesystem-safe + deterministic).
  - [x] 4.2 Verify offline discipline: grep that `src/endpoints.py` has no GDAL/numpy/network/
    `tools`/`web` import; confirm default 2D build byte-identical
    (`tools/verify_determinism.py --region Oregon` or golden-hash byte-identity).
  - [x] 4.3 Run the FULL offline suite: `.venv/bin/python -m pytest -q`. Lint:
    `.venv/bin/ruff check src tests` (pip install ruff if absent).
  - [x] 4.4 Write `implementation/report.md`.

**Acceptance:** all item-specific tests pass; ≤5 gap-filling tests added; `src/endpoints.py`
offline; DEFAULT build byte-for-byte identical; full offline suite green; lint clean. Item gate:
each endpoint has a documented contract, a validated request yields a deterministic plan +
provenance manifest, and dispatch routes through an injectable seam with the Rights gate enforced
— ready for Epoch 20 (unit/integration completion) and Epoch 21 (flagship e2e).

---

## Execution Order
1. Endpoint contracts + request validation (TG1).
2. Deliverable plan + provenance manifest (TG2).
3. Dispatch seam + CLI wrapper (TG3).
4. Determinism, discipline & regression gate (TG4).
