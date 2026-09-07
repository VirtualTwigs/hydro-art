# Spec: Flagship end-to-end proof — all four endpoints (Epoch 21, #85–87)

Third epoch of Generation 1 and the headline deliverable: **one region, one path, all four
endpoints.** Builds directly on the Epoch 19 contract layer and Epoch 20 integration tests.

## Design

### 1. Combined e2e provenance — `src/endpoints.py` additions (offline)
Two pure functions, byte-identical under `sort_keys`, reused by the offline test, the golden
fixture, and the real harness:

- `combined_manifest(results, *, sources=DEFAULT_SOURCES) -> dict` — aggregates a sequence of
  `EndpointResult` (one per endpoint) into schema `hydro-art/e2e-manifest@1`. Validates the
  results share one region/county/style and that endpoints are unique (`EndpointError`
  otherwise). Emits: `schema`, `region`/`county`/`style`, `attribution`,
  `sources`, and `endpoints` (a dict keyed by endpoint → that endpoint's per-file manifest).
- `e2e_contract_digest(requests, *, sources=DEFAULT_SOURCES) -> dict` — the **render-
  independent** skeleton (schema `hydro-art/e2e-contract@1`): builds each request's plan and
  records per-endpoint `filename`/`kind`/`fmt`/`width_px`/`height_px` plus `attribution` +
  `sources`. No checksums, so it depends only on the validated requests — deterministic and
  safe to commit as a golden.

Both raise `EndpointError` on inconsistent/duplicate endpoints, mirroring the existing
coverage-check discipline. `__all__` extended accordingly.

### 2. Offline all-endpoints e2e orchestration test — `tests/test_endpoints_e2e.py` (#85)
ONE flow (the flagship proof, offline):
1. Shared base = Washington / Wahkiakum / neon-basin; per-endpoint extras (animation→year,
   print→size, report→huc).
2. For each endpoint: `build_endpoint_request` → `dispatch_endpoint` with a fake renderer
   that writes real bytes to `tmp_path` and sha256s them.
3. `combined_manifest([...four results...])`.
Assertions: all four endpoints present; each plan equals its `ENDPOINT_CONTRACTS` entry;
combined manifest carries every deliverable + attribution; re-running the whole flow yields
byte-identical combined-manifest JSON (determinism). A companion test asserts
`e2e_contract_digest` is byte-identical and lists all four endpoints.

### 3. Real-data e2e harness — `tools/render_all_endpoints.py` (#86, non-suite)
Thin CLI over the offline core: build the four requests, inject the four REAL renderer
factories already defined in `tools/render_endpoint.py` (`_render_digital`, `_render_animation`,
`_render_print`, `_render_report`), dispatch each, aggregate with `combined_manifest`, and write
`<region>-<county>_e2e_manifest.json`. `--check-determinism` renders the full set twice and
compares per-file sha256s; with `--record`/registry it can update the golden via
`src.determinism`. Imports only `src/` + `tools.render_endpoint`; outside the suite. Real
execution is deferred to the GDAL+NAS machine (documented). Exit: `EndpointError`→1, render→2,
determinism drift→3.

### 4. E2E golden fixture — `tests/fixtures/golden/e2e/washington-wahkiakum.json` (#87)
The committed `e2e_contract_digest` for Washington/Wahkiakum (render-independent). An in-suite
test recomputes the digest and asserts equality with the committed JSON — regression-guarding
the contracts/plans/provenance of the flagship path. The real artifact sha256s stay with the
`--check-determinism` harness on the GDAL machine (recorded into the existing `registry.json`),
deferred like the Epoch 19 real run.

## Discipline / invariants
- `src/endpoints.py` stays offline (stdlib + `src.config` + `src.fulfillment`); no behavior/
  byte change to existing functions → default 2D build byte-identical.
- No GDAL/network in `src/` or `tests/`.
- `tools/render_all_endpoints.py` outside the suite.

## Files
- EDIT `src/endpoints.py` (`combined_manifest`, `e2e_contract_digest`, schemas, `__all__`)
- NEW `tests/test_endpoints_e2e.py`
- NEW `tools/render_all_endpoints.py`
- NEW `tests/fixtures/golden/e2e/washington-wahkiakum.json`
- NEW `agent-os/specs/2026-09-06-flagship-endpoints-e2e/implementation/report.md`
