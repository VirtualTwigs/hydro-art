# Implementation report — Flagship end-to-end proof, all four endpoints (Epoch 21, #85–87)

**Status:** implemented (offline), not committed. Third epoch of Generation 1 — the headline
deliverable: **one region, one path, all four endpoints.**

## What shipped

- **`src/endpoints.py` (EDIT, additive/offline) — e2e provenance core.** Two pure functions
  (byte-identical under `sort_keys`), reused by the offline test, the golden fixture, and the
  real harness:
  - `combined_manifest(results, *, sources=DEFAULT_SOURCES)` — aggregates the four
    `EndpointResult`s into schema `hydro-art/e2e-manifest@1`; enforces one shared
    region/county/style and unique endpoints (`EndpointError` otherwise); `endpoints` maps
    each endpoint → its per-file manifest, so the doc is order-independent.
  - `e2e_contract_digest(requests, *, sources=DEFAULT_SOURCES)` — the **render-independent**
    skeleton (schema `hydro-art/e2e-contract@1`): per-endpoint filenames/kinds/formats/dims +
    attribution + sources, derived purely from validated requests (no checksums).
  - New constants `E2E_MANIFEST_SCHEMA` / `E2E_CONTRACT_SCHEMA`; `__all__` extended. No
    existing function changed → default 2D build byte-identical.
- **`tests/test_endpoints_e2e.py` (NEW, offline) — #85.** 6 tests: combined-manifest
  aggregation + byte-identity + identity/duplicate rejection; contract-digest render-
  independence + byte-identity; the **flagship single-flow test** walking
  Washington/Wahkiakum/neon-basin through all four endpoints (fake renderers writing real
  bytes to `tmp_path`, hashed) asserting every contract, full deliverable coverage in the
  combined manifest, and whole-flow determinism; and the golden-match test.
- **`tools/render_all_endpoints.py` (NEW, non-suite) — #86.** Real-data harness: builds the
  four requests for one county, injects the four REAL renderer factories from
  `tools/render_endpoint.py`, dispatches each, stamps one combined manifest, and (with
  `--check-determinism`) renders the set twice and compares real artifact sha256s. Defaults
  target Wahkiakum County, WA. Exit taxonomy: `EndpointError`→1, render→2, determinism
  drift→3. Imports only `src/` + `tools.render_endpoint`; outside the suite.
- **`tools/render_endpoint.py` (EDIT) — bug fix.** Added the standard
  `sys.path.insert(0, REPO)` (with `# noqa: E402`) so the Epoch 19 CLI actually runs via
  `python tools/render_endpoint.py` (it previously failed to import `src` under direct
  invocation, the documented usage). Same fix applied to the new harness.
- **`tests/fixtures/golden/e2e/washington-wahkiakum.json` (NEW) — #87.** The committed
  `e2e_contract_digest` for the flagship county (render-independent), asserted by the
  golden-match test.

## Deferred (per roadmap: author offline, run real later)

- The **real four-artifact run** of `tools/render_all_endpoints.py --check-determinism`
  against Wahkiakum County is exercised on the GDAL+NAS machine (inherits the Epoch 19
  deferral). Its real per-artifact sha256s are recorded into
  `tests/fixtures/golden/registry.json` via `src.determinism` at that time; the child-tool CLI
  flags in the renderer bodies should be verified during that run.

## Verification

- `pytest tests/test_endpoints_e2e.py` → **6 passed**.
- Full offline suite `pytest -q` → **833 passed** (was 827; +6; no regressions).
- Direct-run restored: `python tools/render_endpoint.py --help` and
  `python tools/render_all_endpoints.py --help` both work.
- Offline discipline: `src/endpoints.py` still imports only stdlib + `src.config` +
  `src.fulfillment` (grep-verified: no GDAL/numpy/network); e2e tests import only stdlib +
  `src.*`.
- Byte-identical default: `src/endpoints.py` change is purely additive; nothing enters
  `PIPELINE_STAGES`; default build unaffected.

## Item gate

One in-suite flow proves all four endpoints on a single path with contract + determinism
assertions; the render-independent e2e path is golden-guarded; and an opt-in real-data harness
(combined manifest + double-render determinism check) is ready for the GDAL+NAS run — ready for
Epoch 22 (high-res marketing gallery) and Epoch 23 (release gate).
